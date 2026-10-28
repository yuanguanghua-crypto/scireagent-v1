# -*- coding: utf-8 -*-
"""给上架产品的 SKU 灌 / 清「占位库存」。

## 为什么需要它

远端的测试人员只能访问生产站，看不到本地库。要让 PO 全流程（下单 → 锁库 → 发货 →
释放）真的能跑，生产上必须有库存数据 —— 而真实盘点要等产品上架、SKU + COA/SDS 齐备
之后才有（2026-10-28 实测生产 `inventory` = 0 行）。

## 这是**假数据**，所以有三条硬约束，缺一条就不要跑

1. **可识别**：每条都写 `InventoryMovement(reason='PLACEHOLDER:<qty>')`。
   将来要抓「哪些是占位」只需 `reason__startswith='PLACEHOLDER'`。
2. **可清且只清干净的那部分**：`--purge` 只删「还活着」的占位行，即
   `available` 恰好等于当初灌的量、`allocated == 0`、且没有任何 `Allocation` 记录。
   被卖过 / 被占用过的行一律跳过并打印原因 —— 硬删会连真实业务数据一起带走。
3. **不覆盖真实库存**：某 SKU 只要已有任何库存行，就整条跳过。真实数据永远优先。

## 用法

    python manage.py seed_inventory_placeholder --dry-run        # 先看要做什么
    python manage.py seed_inventory_placeholder --qty 100        # 灌
    python manage.py seed_inventory_placeholder --purge --dry-run
    python manage.py seed_inventory_placeholder --purge          # 清（上线前必做）
    python manage.py seed_inventory_placeholder --qty 100 --sku SC8001-1

⚠️ `--purge` 之后会自动把「不再有任何库存行」的 SKU 的 `is_stock_tracked` 关掉 ——
   否则会留下「纳管但 0 库存」的状态，那个 SKU 的所有下单都会被拦。
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.commerce.models import SKU
from apps.inventory.models import Allocation, Inventory, InventoryMovement
from apps.inventory.services import InventoryService

#: 占位标记前缀。改它等于让历史占位行失联，不要改。
PLACEHOLDER_PREFIX = 'PLACEHOLDER:'


class Command(BaseCommand):
    help = '给上架产品的 SKU 灌/清占位库存（测试联调用；生产仅限远端联调期）'

    def add_arguments(self, parser):
        parser.add_argument('--qty', type=int, default=100,
                            help='每个 SKU 灌多少件（默认 100）')
        parser.add_argument('--location', default=Inventory.Location.MAIN,
                            choices=[c[0] for c in Inventory.Location.choices],
                            help='库位（默认 MAIN）')
        parser.add_argument('--sku', action='append', default=None,
                            help='只处理指定 sku_code，可重复传')
        parser.add_argument('--purge', action='store_true',
                            help='清除占位库存（只清未被使用过的行）')
        parser.add_argument('--dry-run', action='store_true',
                            help='只打印计划，不写库')

    def handle(self, *args, **opts):
        if opts['purge']:
            return self._purge(opts)
        return self._seed(opts)

    # ── 灌 ─────────────────────────────────────────────────────────────
    def _seed(self, opts):
        qty = int(opts['qty'])
        if qty <= 0:
            raise SystemExit('--qty must be positive')

        qs = (SKU.objects
              .filter(product__status='active', product__archived=False)
              .select_related('product')
              .order_by('sku_code'))
        if opts['sku']:
            qs = qs.filter(sku_code__in=opts['sku'])

        seeded, skipped, skipped_unpublished = 0, [], []
        for sku in qs:
            if Inventory.objects.filter(sku_id=sku.id).exists():
                skipped.append(sku.sku_code)
                continue
            if opts['dry_run']:
                self.stdout.write(f'  [dry] would seed {sku.sku_code:20s} '
                                  f'+{qty} @ {opts["location"]}')
                seeded += 1
                continue
            # ⚠️ 必须包事务：`InventoryService.receipt` 内部用 `select_for_update`，
            #    在 autocommit 下会抛 TransactionManagementError（management command
            #    没有 ATOMIC_REQUESTS 兜底）。逐条包而不是整批包，是为了不让 36 次
            #    行锁同时持有。
            with transaction.atomic():
                InventoryService.receipt(
                    sku.id, opts['location'], qty,
                    reason=f'{PLACEHOLDER_PREFIX}{qty}')
            seeded += 1

        # 未上架产品的 SKU 不灌，但要报告数量（免得"以为全灌了"）
        all_skus = SKU.objects.count()
        tracked = SKU.objects.filter(is_stock_tracked=True).count()
        unpublished = all_skus - qs.count()

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'{"[dry-run] " if opts["dry_run"] else ""}seeded {seeded} SKU(s) '
            f'with {qty} @ {opts["location"]}'))
        if skipped:
            self.stdout.write(f'  跳过（已有库存行，不覆盖真实数据）: {len(skipped)}')
            self.stdout.write(f'    {", ".join(skipped[:15])}'
                              f'{" …" if len(skipped) > 15 else ""}')
        if unpublished:
            self.stdout.write(f'  未上架产品的 SKU（不灌）: {unpublished}')
        self.stdout.write(f'  当前 is_stock_tracked=True: {tracked} / {all_skus}')
        if opts['dry_run']:
            self.stdout.write('  (dry-run，未写库)')
        else:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                '⚠️ 这是占位数据。上线前必须执行：'
                'python manage.py seed_inventory_placeholder --purge'))

    # ── 清 ─────────────────────────────────────────────────────────────
    def _purge(self, opts):
        dry = opts['dry_run']
        marks = InventoryMovement.objects.filter(
            kind=InventoryMovement.Kind.RECEIPT,
            reason__startswith=PLACEHOLDER_PREFIX)
        inv_ids = sorted(set(marks.values_list('inventory_id', flat=True)))
        if not inv_ids:
            self.stdout.write('没有找到任何占位库存（reason 以 PLACEHOLDER: 开头），无事可做。')
            return

        removed, skipped = 0, []
        touched_skus = set()
        for inv in (Inventory.objects
                    .filter(id__in=inv_ids)
                    .select_related('sku', 'sku__product')
                    .order_by('sku__sku_code')):
            seeded = sum(m.quantity for m in marks.filter(inventory_id=inv.id))
            blockers = []
            if Allocation.objects.filter(inventory_id=inv.id).exists():
                blockers.append('有 Allocation 记录')
            if inv.allocated != 0:
                blockers.append(f'allocated={inv.allocated}')
            if inv.available != seeded:
                blockers.append(f'available={inv.available} ≠ 当初灌的 {seeded}')
            if blockers:
                skipped.append((inv.sku.sku_code, '；'.join(blockers)))
                continue

            touched_skus.add(inv.sku_id)
            if dry:
                self.stdout.write(f'  [dry] would purge {inv.sku.sku_code:20s} '
                                  f'({seeded} @ {inv.location})')
            else:
                inv.delete()   # 级联删该行的 InventoryMovement（占位数据，不需要保留审计）
            removed += 1

        # 脱管：purge 后不再有任何库存行的 SKU 必须关掉开关，
        # 否则它会变成「纳管但 0 库存」⇒ 该 SKU 的所有下单被拦。
        untracked = 0
        if not dry:
            with transaction.atomic():
                for sku_id in touched_skus:
                    if not Inventory.objects.filter(sku_id=sku_id).exists():
                        untracked += SKU.objects.filter(
                            pk=sku_id, is_stock_tracked=True
                        ).update(is_stock_tracked=False)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'{"[dry-run] " if dry else ""}purged {removed} placeholder row(s)'))
        if untracked:
            self.stdout.write(f'  同时脱管 {untracked} 个 SKU（已无库存行）')
        if skipped:
            self.stdout.write(f'  跳过 {len(skipped)} 行（已被使用，不能删）:')
            for code, why in skipped[:15]:
                self.stdout.write(f'    {code:20s} {why}')
            if len(skipped) > 15:
                self.stdout.write(f'    … 还有 {len(skipped) - 15} 行')
            self.stdout.write('  ⇒ 这些行要么已被卖出/占用，要么数量已变，'
                              '请人工核对后再决定（先用 Adjust 调到 0 再重跑）。')
