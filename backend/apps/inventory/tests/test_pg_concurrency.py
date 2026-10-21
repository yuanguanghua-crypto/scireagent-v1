# -*- coding: utf-8 -*-
"""L4 并发 —— 在**真实 PostgreSQL** 上验证库存的锁语义

## 为什么这两个用例在 sqlite 上必须 skip
sqlite 的 `select_for_update()` 是 **no-op**（实发 SQL 不含 `FOR UPDATE`），
而且它是整库文件锁 —— 于是：
  · "并发不超卖"在 sqlite 上会**假通过**（锁根本没起作用，只是串行化了）
  · "并发不丢更新"在 sqlite 上会**假失败**（写冲突被文件锁放大成 `database is locked`）
两种结果都不可信。这两条不变量**只能在 Postgres 上验证**。

## 断言的是"业务不变量"，不是"代码有没有写 select_for_update"
`InventoryService` 的注释说「所有扣减/释放均经 select_for_update」，
但那只是**意图**。真正要证明的是：
  ① 库存 3 件、8 个并发请求各要 1 件 ⇒ **正好 3 个成功、5 个被拒**，且最终
     `available=0` / `allocated=3`（既不超卖，也不少卖）
  ② 8 个并发入库各 +1 ⇒ `available=8`（读-改-写没有丢失更新）

## 怎么跑
```bash
cd backend
DB_ENGINE=django.db.backends.postgresql DB_NAME=scireagent_l4 \
DB_USER=scireagent DB_HOST=127.0.0.1 DB_PORT=5433 \
venv/Scripts/python.exe -m pytest apps/inventory/tests/test_pg_concurrency.py -q
```
（本机 PG 17.11 手动集群，端口 5433；sqlite 下本文件整体 skip，不污染常规回归。）
"""
import threading
from decimal import Decimal

import pytest
from django.db import connection, connections

from apps.accounts.models import Organization, User
from apps.commerce.models import Product, SKU
from apps.inventory.models import InsufficientInventoryError, Inventory
from apps.inventory.services import InventoryService
from apps.transactions.models import Order, OrderItem

LOCATION = 'MAIN'


@pytest.mark.django_db(transaction=True)
class TestInventoryConcurrencyOnPostgres:
    """`transaction=True` 是必须的：TestCase 会把测试包在事务里，
    子线程的连接看不到未提交的数据 ⇒ 并发根本发生不了。"""

    def setup_method(self):
        self.org = Organization.objects.create(name='Conc Lab', org_type='academic')
        self.user = User.objects.create_user(
            username='conc_proc', password='x', organization=self.org, role='procurement')
        self.product = Product.objects.create(name='Conc Reagent', slug='conc-reagent')
        self.sku = SKU.objects.create(
            product=self.product, sku_code='SKU-CONC', price=Decimal('10.00'))

    # ── helpers ────────────────────────────────────────────────────────
    def _make_item(self, i: int) -> OrderItem:
        order = Order.objects.create(
            user=self.user, order_no=f'ORD-CONC-{i}', status=Order.Status.CONFIRMED)
        return OrderItem.objects.create(
            order=order, product=self.product, sku=self.sku,
            quantity=1, unit_price=Decimal('10.00'))

    @staticmethod
    def _run_threads(n, target):
        """N 个线程在 barrier 上对齐后同时开跑，返回 (成功, 被拒, 异常)。"""
        ok, rejected, other = [], [], []
        lock = threading.Lock()
        barrier = threading.Barrier(n)

        def worker(i):
            try:
                barrier.wait(timeout=30)
                target(i)
                with lock:
                    ok.append(i)
            except InsufficientInventoryError:
                with lock:
                    rejected.append(i)
            except Exception as exc:                       # noqa: BLE001
                with lock:
                    other.append(repr(exc))
            finally:
                # 线程用完必须关连接，否则 PG 里残留 session，teardown 删库会失败
                # （实测 `database ... is being accessed by other users`）
                connections.close_all()

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        return ok, rejected, other

    # ── ① 不超卖 ───────────────────────────────────────────────────────
    def test_allocate_does_not_oversell(self):
        """库存 3、8 个并发各要 1 ⇒ 正好 3 成功。"""
        if connection.vendor != 'postgresql':
            pytest.skip(
                '需 Postgres：sqlite 下 select_for_update 为 no-op + 整库文件锁，'
                '并发不变量无法验证（sqlite 结果为假通过/假失败）'
            )

        available, n = 3, 8
        inv = Inventory.objects.create(sku=self.sku, location=LOCATION, available=available)
        items = [self._make_item(i) for i in range(n)]

        ok, rejected, other = self._run_threads(
            n, lambda i: InventoryService.allocate(items[i], inv.id, 1))

        assert not other, f'出现非预期异常（不是"库存不足"，说明是别的缺陷）：{other}'
        assert len(ok) == available, (
            f'并发分配数量不对：成功 {len(ok)} 个，应为 {available} 个'
            f'（多了 = 超卖；少了 = 锁粒度过大导致误拒）。被拒 {len(rejected)}')
        assert len(rejected) == n - available

        inv.refresh_from_db()
        assert inv.available == 0, f'available 应扣到 0，实际 {inv.available}'
        assert inv.allocated == available, f'allocated 应为 {available}，实际 {inv.allocated}'

    # ── ② 不丢更新 ─────────────────────────────────────────────────────
    def test_receipt_does_not_lose_updates(self):
        """8 个并发入库各 +1 ⇒ available 必须等于 8（读-改-写不能丢）。"""
        if connection.vendor != 'postgresql':
            pytest.skip(
                '需 Postgres：sqlite 下 select_for_update 为 no-op，'
                '读-改-写丢更新无法在本地验证'
            )

        n = 8
        inv = Inventory.objects.create(sku=self.sku, location=LOCATION, available=0)

        ok, _, other = self._run_threads(
            n, lambda i: InventoryService.receipt(self.sku.id, LOCATION, 1))

        assert not other, f'并发入库出现异常：{other}'
        assert len(ok) == n, f'入库成功数应为 {n}，实际 {len(ok)}'

        inv.refresh_from_db()
        assert inv.available == n, (
            f'丢更新：8 次 +1 后 available 应为 {n}，实际 {inv.available}'
            f'（少了说明读-改-写没有互斥）')

    # ── ③ 并发入库 vs 分配：不能把"已分配"占掉 ──────────────────────────
    def test_allocate_and_receipt_interleave_safely(self):
        """一边入库 +5、一边分配 5，最终账要平：available + allocated 守恒。

        这条抓的是"锁的是同一个对象"：若 allocate 与 receipt 锁了不同的行/快照，
        总量会漂移（多出或凭空少掉库存）。
        """
        if connection.vendor != 'postgresql':
            pytest.skip('需 Postgres：sqlite 下无法验证跨操作的锁一致性')

        inv = Inventory.objects.create(sku=self.sku, location=LOCATION, available=0)
        items = [self._make_item(i) for i in range(5)]

        def target(i):
            if i < 5:
                InventoryService.receipt(self.sku.id, LOCATION, 1)
            else:
                InventoryService.allocate(items[i - 5], inv.id, 1)

        # 5 个入库 + 5 个分配，但库存从 0 起 —— 分配可能因库存不足被拒，
        # 这是**正确**行为；关键是账要守恒，不能凭空造出库存。
        ok, rejected, other = self._run_threads(10, target)
        assert not other, f'出现非预期异常：{other}'

        inv.refresh_from_db()
        total = inv.available + inv.allocated
        assert total == 5, (
            f'总量不守恒：available={inv.available} + allocated={inv.allocated} '
            f'= {total}，应为 5（入库 5 件，不管分配成不成功，总量都不该变）')
