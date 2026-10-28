from datetime import timedelta

from django.db import transaction
from apps.inventory.models import (
    Inventory, Allocation, InsufficientInventoryError, InventoryMovement,
    StockShortageAlert,
)

# ★ P2：`available`/`allocated` 是裸 IntegerField，Postgres 侧为 int4（上限 2147483647）。
# 本模块的 quantity/delta 都是**增量**语义（available += x）⇒ 单字段合法 ≠ 累加后合法：
#   available=2,000,000,000 + quantity=300,000,000 ⇒ 2,300,000,000 溢出 int4（实测 500）。
# 故除serializer 的单字段上界外，累加前必须再查一次上界。
INT4_MAX = 2_147_483_647


def _guard_accumulation(current: int, delta: int, field: str = 'available') -> int:
    """累加上界守卫：返回累加结果，越界则抛 ValueError。

    ⚠️ 必须抛 `ValueError`：api/v1/views.py:82/101 的
    `except (ValueError, InsufficientInventoryError)` 已捕获它 ⇒ 零新增捕获逻辑即变400。
    ⚠️ 不能只靠 DB 兜底：SQLite 是 int8，会静默接受越界值（本地测试也测不出 500），
    而生产 Postgres 会直接抛 DataError/OverflowError ⇒ 500。
    """
    result = current + delta
    if result > INT4_MAX:
        raise ValueError(
            f'累加后超出上限：当前 {field}={current}，本次变更 {delta:+d}，'
            f'累加后 {result}，超出 int4 上限 {INT4_MAX}。请调小本次数量。'
        )
    return result


class InventoryService:
    """库存原子操作 — 所有扣减/释放均经 select_for_update，禁止直接改 available。"""

    @staticmethod
    def _lock(inventory_id: int) -> Inventory:
        return Inventory.objects.select_for_update().get(pk=inventory_id)

    @staticmethod
    @transaction.atomic
    def allocate(order_item, inventory_id: int, quantity: int) -> Allocation:
        """锁定指定库存并记录占用（RESERVED）。"""
        inv = InventoryService._lock(inventory_id)
        # ★ P2：`allocated` 同为裸 IntegerField，且是**累加**语义 ——
        #   models.Inventory.allocate 的 `available >= qty` 兜底只管 available，
        #   allocated 可被反复占用同一行推过 int4 ⇒ 同样要在写库前查上界。
        #   ValueError 已被 transactions/api/v1/po_views.py:210 的 except 捕获 ⇒ 自动 400。
        # ★★ 必须先查后加（与 receipt/adjust 一致）：`inv.allocate(qty)` 内部已执行
        #   `allocated += qty`，若在其之后再守卫，传入的 current 已是加完后的新值，
        #   再 +quantity 就多算一次 ⇒ 合法占用被误拒（实测：INT4_MAX-100 占 60 被拒）。
        _guard_accumulation(inv.allocated, quantity, field='allocated')
        inv.allocate(quantity)  # raises InsufficientInventoryError if over-commit
        inv.save(update_fields=['available', 'allocated', 'updated_at'])
        allocation = Allocation.objects.create(
            order_item=order_item,
            inventory=inv,
            quantity=quantity,
            status=Allocation.Status.RESERVED,
        )
        # ★ v4.1 DEV-1：变动流水（同事务审计）
        InventoryMovement.objects.create(
            inventory=inv, kind=InventoryMovement.Kind.ALLOCATE,
            delta_available=-quantity, delta_allocated=quantity, quantity=quantity,
            reason=f'order:{order_item.order_id}', order_id=order_item.order_id,
        )
        return allocation

    @staticmethod
    @transaction.atomic
    def allocate_for_order(order, lines: list) -> list:
        """节点 B 批量锁定：lines=[{order_item_id, inventory_id, quantity}]。"""
        from apps.transactions.models import OrderItem
        allocations = []
        for line in lines:
            oi = OrderItem.objects.get(pk=line['order_item_id'], order=order)
            allocations.append(
                InventoryService.allocate(oi, line['inventory_id'], int(line['quantity']))
            )
        return allocations

    @staticmethod
    @transaction.atomic
    def release(allocation: Allocation, quantity: int | None = None) -> int:
        """发货：实物已出，释放占用量（allocated-=q，available 不变）。

        ★ 2026-10-16 修 P0（部分发货占用被整额释放）：原实现无条件释放
          `allocation.quantity` 整额，而调用方（ShippingService.mark_shipped）
          的 `remaining` 只决定何时停止遍历、不决定释放多少 ⇒ 占用 10、发货 5
          会把 allocated 直接归零，账实不符。
          现支持 `quantity` 参数做部分释放：只减实发量，流水按实发量写，
          `allocation.released_quantity` 累计，仅当释放完毕才转 SHIPPED。
          `quantity=None`（默认）时为全量释放，行为与修复前完全一致。

        返回实际释放量。
        """
        # ★ 重取并加行锁：调用方传进来的 allocation 可能是发货前读出的快照，
        #   同一 order_item 的多批发货并发 mark_shipped 时 released_quantity 会是陈值
        #   ⇒ 累计量算错、status 误判。与本类「所有扣减/释放均经 select_for_update」一致。
        allocation = Allocation.objects.select_for_update().get(pk=allocation.pk)
        inv = InventoryService._lock(allocation.inventory_id)
        if quantity is None:
            quantity = allocation.remaining_quantity
        quantity = min(int(quantity), allocation.remaining_quantity)
        if quantity <= 0:
            return 0
        inv.release(quantity)
        inv.save(update_fields=['allocated', 'updated_at'])
        allocation.released_quantity += quantity
        update_fields = ['released_quantity', 'updated_at']
        # ★ 仅在占用被全部释放时才置 SHIPPED；部分释放保持 RESERVED
        if allocation.released_quantity >= allocation.quantity:
            allocation.status = Allocation.Status.SHIPPED
            update_fields.append('status')
        allocation.save(update_fields=update_fields)
        # ★ v4.1 DEV-1：发货出库流水（同事务审计）—— 按**实际释放量**写，
        #   不能按 allocation.quantity 整额写，否则流水与账面不符。
        InventoryMovement.objects.create(
            inventory=inv, kind=InventoryMovement.Kind.SHIP,
            delta_allocated=-quantity, quantity=quantity,
            reason=f'order:{allocation.order_item.order_id}', order_id=allocation.order_item.order_id,
        )
        return quantity

    @staticmethod
    @transaction.atomic
    def release_quantity(inventory_id: int, quantity: int):
        inv = InventoryService._lock(inventory_id)
        inv.release(quantity)
        inv.save(update_fields=['allocated', 'updated_at'])
        # ★ v4.1 DEV-1：占用释放流水（同事务审计）
        InventoryMovement.objects.create(
            inventory=inv, kind=InventoryMovement.Kind.RELEASE,
            delta_allocated=-quantity, quantity=quantity,
        )

    @staticmethod
    @transaction.atomic
    def receipt(sku_id: int, location: str, quantity: int, *,
                batch_id=None, user=None, reason: str = '') -> Inventory:
        """入库：指定 (sku, batch, location) 累加可分配量（无则建行），写 RECEIPT 流水。

        并发说明：行不存在时首建存在唯一约束兜底（unique_together），
        极端并发下第二个事务会 IntegrityError —— 内部低频操作可接受。
        """
        if quantity <= 0:
            raise ValueError('quantity must be positive')
        lookup = {'sku_id': sku_id, 'location': location, 'batch_id': batch_id}
        inv = Inventory.objects.filter(**lookup).select_for_update().first()
        if inv is None:
            inv = Inventory.objects.create(**lookup, available=0, allocated=0)
            inv = InventoryService._lock(inv.pk)
        inv.available = _guard_accumulation(inv.available, quantity)
        inv.save(update_fields=['available', 'updated_at'])
        InventoryMovement.objects.create(
            inventory=inv, kind=InventoryMovement.Kind.RECEIPT,
            delta_available=quantity, quantity=quantity, reason=reason, created_by=user,
        )
        return inv

    @staticmethod
    @transaction.atomic
    def adjust(inventory_id: int, delta: int, *, user=None, reason: str = '') -> Inventory:
        """盘点调整：available += delta（结果不可为负），写 ADJUST 流水。"""
        if delta == 0:
            raise ValueError('delta must be non-zero')
        inv = InventoryService._lock(inventory_id)
        if inv.available + delta < 0:
            raise InsufficientInventoryError(
                f'Adjust would over-draw: available {inv.available}, delta {delta}'
            )
        inv.available = _guard_accumulation(inv.available, delta)
        inv.save(update_fields=['available', 'updated_at'])
        InventoryMovement.objects.create(
            inventory=inv, kind=InventoryMovement.Kind.ADJUST,
            delta_available=delta, quantity=abs(delta), reason=reason, created_by=user,
        )
        return inv

    @staticmethod
    def available_for_sku(sku_id: int):
        rows = Inventory.objects.filter(sku_id=sku_id)
        return {
            'available': sum(r.available for r in rows),
            'allocated': sum(r.allocated for r in rows),
            'on_hand': sum(r.on_hand for r in rows),
        }


class StockShortageService:
    """下单前的库存校验 + 缺货留痕（2026-10-28 新增）。

    ── 判定口径（用户 2026-10-28 拍板，写死在这里避免各入口各判一套）──
      ① `SKU.inventory_status == 'out_of_stock'` ⇒ 拦（运营显式标记缺货）
      ② 该 SKU **已建库存记录**（`inventory` 有行）且 `sum(available) < 下单量` ⇒ 拦
      ③ 没有任何库存记录的 SKU = 尚未纳入库存管理 ⇒ **不判定**

    ★ 为什么 ③ 必须放过（否则就是事故）：
      生产 `inventory` 表实测 **0 行**、36 个 SKU 全部 `in_stock`、`sum(available)=0`。
      若把"没建账"当成"没货"，上线当天 **全部下单（PO 提交 + 购物车结账）都会被拒**，
      整站无法成交。运营之后在库存台入库（`/inventory/receipt/`）自然会进入口径 ②。

    ★ 本服务是**UX 闸门，不是最后一道防线**：并发下两个用户可能同时通过校验（读的是
      快照）。真正的超卖保护是 `InventoryService.allocate` 的 `select_for_update` 与
      `InsufficientInventoryError`，这一层只负责"提前、清楚地把话说给用户和运营听"。
    """

    #: 同 (用户, SKU, 来源) 的重复拦截在这个窗口内合并为一条（occurrences += 1）
    DEDUPE_WINDOW = timedelta(hours=24)

    @classmethod
    def is_short(cls, sku, quantity):
        """返回 (是否缺货, 当时可用量, 原因)。sku 为 None 时视为不缺货（交给上层报错）。"""
        from apps.commerce.models import SKU

        if sku is None:
            return (False, None, '')
        qty = int(quantity or 0)
        snap = cls._available(sku.id)
        if sku.inventory_status == SKU.InventoryStatus.OUT_OF_STOCK:
            return (True, snap, StockShortageAlert.Reason.OUT_OF_STOCK)
        if not cls._is_tracked(sku.id):
            return (False, None, '')
        if snap < qty:
            return (True, snap, StockShortageAlert.Reason.INSUFFICIENT)
        return (False, snap, '')

    @staticmethod
    def _available(sku_id):
        return sum(r.available for r in Inventory.objects.filter(sku_id=sku_id))

    @staticmethod
    def _is_tracked(sku_id):
        """该 SKU 是否已纳入库存管理（只要有一行库存记录就算）。"""
        return Inventory.objects.filter(sku_id=sku_id).exists()

    @classmethod
    def check_items(cls, user, items, source, record=True):
        """批量校验下单明细。返回缺货清单（空列表 = 全部可下单）。

        `items` 形如 `[{'sku_id': 12, 'quantity': 3}, ...]`。
        **不抛异常** —— 由调用方决定返回 400 还是继续。
        """
        from apps.commerce.models import SKU

        sku_ids = []
        for it in items or []:
            sid = it.get('sku_id')
            if sid:
                try:
                    sku_ids.append(int(sid))
                except (TypeError, ValueError):
                    continue
        skus = {s.id: s for s in SKU.objects.select_related('product').filter(id__in=sku_ids)}

        shortages = []
        for it in items or []:
            try:
                sid = int(it.get('sku_id'))
            except (TypeError, ValueError):
                continue
            sku = skus.get(sid)
            if sku is None:
                continue          # 不存在的 SKU 由序列化器/服务各自报错，这里不重复报
            qty = int(it.get('quantity') or 0)
            short, available, reason = cls.is_short(sku, qty)
            if not short:
                continue
            shortages.append({
                'sku': sku,
                'sku_id': sku.id,
                'sku_code': sku.sku_code,
                'product_name': getattr(sku.product, 'name', '') or '',
                'requested_quantity': qty,
                'available_quantity': int(available or 0),
                'reason': reason,
            })

        if shortages and record:
            cls.record_alerts(user, shortages, source)
        return shortages

    @classmethod
    def record_alerts(cls, user, shortages, source):
        """把缺货留痕写库。**任何失败都不能影响主流程** ⇒ 全捕获 + 记日志。"""
        import logging
        logger = logging.getLogger(__name__)
        from django.utils import timezone

        since = timezone.now() - cls.DEDUPE_WINDOW
        for sh in shortages:
            try:
                existing = (StockShortageAlert.objects
                            .filter(user=user, sku_id=sh['sku_id'], source=source,
                                    status=StockShortageAlert.Status.NEW,
                                    created_at__gte=since)
                            .order_by('-created_at')
                            .first())
                if existing:
                    existing.occurrences += 1
                    existing.requested_quantity = sh['requested_quantity']
                    existing.available_quantity = sh['available_quantity']
                    existing.save(update_fields=[
                        'occurrences', 'requested_quantity', 'available_quantity', 'updated_at',
                    ])
                    continue
                StockShortageAlert.objects.create(
                    user=user,
                    user_email=getattr(user, 'email', '') or '',
                    user_name=getattr(user, 'username', '') or '',
                    sku_id=sh['sku_id'],
                    sku_code=sh['sku_code'],
                    product_name=sh['product_name'],
                    requested_quantity=sh['requested_quantity'],
                    available_quantity=sh['available_quantity'],
                    reason=sh['reason'],
                    source=source,
                )
            except Exception:                     # noqa: BLE001 — 留痕失败不得阻断下单拦截
                logger.exception('记录缺货告警失败：sku=%s user=%s',
                                 sh.get('sku_code'), getattr(user, 'id', None))

    @classmethod
    def shortage_message(cls, shortages):
        """给客户看的一句话（英文，与站点语言一致）。

        ★ 2026-10-28 实测修正：`out_of_stock` 是**运营手动标记**的商品状态，可以与账面
          可用量矛盾（实测某 SKU 被标记缺货但 `available=1014`）。此时若照抄可用量会
          输出 "requested 3, available 1014" —— 客户一看就是系统在自相矛盾。
          故只有 `insufficient`（真的数量不够）才报可用量，`out_of_stock` 只说 unavailable。
        """
        parts = []
        for s in shortages:
            if s['reason'] == StockShortageAlert.Reason.OUT_OF_STOCK:
                parts.append(f"{s['sku_code']} (requested {s['requested_quantity']}, "
                             f"currently unavailable)")
            else:
                parts.append(f"{s['sku_code']} (requested {s['requested_quantity']}, "
                             f"available {s['available_quantity']})")
        return ('The following item(s) are out of stock and cannot be ordered: '
                + '; '.join(parts)
                + '. Our team has been notified and will contact you about restocking or alternatives.')
