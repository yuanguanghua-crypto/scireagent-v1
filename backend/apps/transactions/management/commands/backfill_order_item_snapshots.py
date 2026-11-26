"""回填 OrderItem 的商品标识快照（A-080 止损）。

## 为什么需要这个命令
2026-11-26 生产实测：89 行订单明细里 **32 行（36%）的 `sku_id` 与 `product_id`
同时为 NULL** —— 涉及 16 个订单、合计 7,730,065.00（占全库订单总额的 99%）。
那 32 行的商品标识已随 Product/SKU 删除永久丢失，**本命令无法恢复**（无源可取）。

本命令只做能做的：把**主数据还在**的行的快照补齐，
让它们从今以后即使 SKU/Product 被删也能读出"卖的是什么"。

## ⚠️ 为什么用 `update()` 而不是 `save()`
`OrderItem.save()` 里有 `self.subtotal = self.unit_price * self.quantity` ——
那是给**新建**行算小计的。对**存量行**调 `save()` 会把历史 subtotal 按当前
`unit_price × quantity` 重算，一旦某行存在折扣/手工调价（历史 subtotal ≠ 乘积），
就会被静默改写。铁律 15：覆盖既有数据的操作必须先保住原值。
⇒ 回填只写三个快照列，`queryset.update()` 不触发 save()，subtotal 一根毫毛都不动。

## 用法
    python manage.py backfill_order_item_snapshots --dry-run     # 只统计（默认）
    python manage.py backfill_order_item_snapshots --apply       # 实际写入
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.transactions.models import OrderItem


class Command(BaseCommand):
    help = '回填 OrderItem 的 SKU/产品标识快照（A-080 止损；不触碰 subtotal）'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='实际写入（默认只统计，不落库）')
        parser.add_argument('--dry-run', action='store_true', default=True,
                            help='只统计（默认行为，显式给出更清楚）')

    def handle(self, *args, **opts):
        apply = bool(opts.get('apply'))
        mode = 'APPLY' if apply else 'DRY-RUN'
        self.stdout.write(f'=== 回填 OrderItem 快照（{mode}）===')

        qs = list(OrderItem.objects.select_related('sku', 'product').all())
        total = len(qs)

        fillable, lost, already = [], [], []
        for it in qs:
            has_src = bool(it.sku_id or it.product_id)
            has_snap = bool(it.sku_code_snapshot and it.product_name_snapshot)

            if has_snap:
                already.append(it)
            elif has_src:
                fillable.append(it)
            else:
                lost.append(it)

        self.stdout.write(f'  明细总行数: {total}')
        self.stdout.write(f'  已有快照（跳过）: {len(already)}')
        self.stdout.write(f'  可回填（主数据还在）: {len(fillable)}')
        self.stdout.write(f'  ★ 无法回填（sku 与 product 均已被删）: {len(lost)}')

        if lost:
            order_nos = sorted({it.order.order_no for it in lost})
            self.stdout.write('    受影响订单: ' + ', '.join(order_nos))

        if not fillable:
            self.stdout.write(self.style.WARNING('  没有可回填的行，结束。'))
            return

        if not apply:
            self.stdout.write(self.style.WARNING(
                f'  [DRY-RUN] 未写入任何数据。确认无误后加 --apply 执行。'))
            # 抽样展示将要写入的内容
            for it in fillable[:5]:
                spec = ''
                if it.sku_id:
                    spec = ' · '.join(x for x in (it.sku.pack_size, it.sku.concentration) if x)
                self.stdout.write(
                    f'    item#{it.id} → sku_code={it.sku.sku_code if it.sku_id else ""!r} '
                    f'product={(it.product.name if it.product_id else "")!r} spec={spec!r}')
            return

        written = 0
        with transaction.atomic():
            for it in fillable:
                fields = {}
                if it.sku_id and not it.sku_code_snapshot:
                    fields['sku_code_snapshot'] = it.sku.sku_code
                    spec = ' · '.join(x for x in (it.sku.pack_size, it.sku.concentration) if x)
                    if spec and not it.sku_spec_snapshot:
                        fields['sku_spec_snapshot'] = spec
                if it.product_id and not it.product_name_snapshot:
                    fields['product_name_snapshot'] = it.product.name
                if fields:
                    # ★ update() 不触发 OrderItem.save() ⇒ subtotal 不会被重算
                    OrderItem.objects.filter(pk=it.pk).update(**fields)
                    written += 1

        self.stdout.write(self.style.SUCCESS(f'  ✓ 已回填 {written} 行（subtotal 未改动）'))
        self.stdout.write(f'  仍无法回填: {len(lost)} 行（源对象已不存在）')
