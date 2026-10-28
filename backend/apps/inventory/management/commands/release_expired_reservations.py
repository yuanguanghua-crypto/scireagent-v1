# -*- coding: utf-8 -*-
"""释放「长期没动过」的订单占用（下单/审核已锁库后，客户一直不付款的那种）。

## 为什么必须有这一条

2026-10-28 起，购物车下单与运营审核通过都会**真实扣减可分配量**（`available -= n`）。
如果客户下了单就消失，这批货会一直被锁着 —— 而且**不会报任何错**，只是库存慢慢变少。
这是「锁库」这个能力的必要配套，不是可选项。

## 有意不做什么

- **不取消订单**。只释放占用，订单状态、明细、金额一律不动。运营仍可重新确认/发货。
  自动取消客户订单是业务决策，不该由一个 cron 命令替人做。
- **不碰 `in_production` / 已发货的订单**。正在备货的占用是"正在用"的：
  释放了会导致后续 `mark_shipped` 找不到 RESERVED 占用而静默不扣减（账实不符）。
  只处理 `po_received`（待审核）与 `confirmed`（已确认但未排产）。
- **不碰已经有发货记录的订单**（多一层保险，防状态回退之类的情况）。

## 用法

    python manage.py release_expired_reservations --dry-run
    python manage.py release_expired_reservations --hours 72
    python manage.py release_expired_reservations --hours 72 --dry-run --limit 20

建议挂 crontab（与 `send_outbox_emails` 同一个模式）：

    0 3 * * * docker exec scireagent-backend-1 python manage.py release_expired_reservations --hours 72
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.transactions.models import Order, ShippingRecord, StatusLog
from apps.inventory.models import Allocation
from apps.inventory.services import InventoryService

#: 只释放这两个状态的占用。理由见模块 docstring。
RELEASABLE_STATUSES = (Order.Status.PO_RECEIVED, Order.Status.CONFIRMED)


class Command(BaseCommand):
    help = '释放长期未推进订单的库存占用（不取消订单，只还库存）'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=72,
                            help='超过多少小时未更新视为「没动过」（默认 72）')
        parser.add_argument('--dry-run', action='store_true', help='只打印，不改库')
        parser.add_argument('--limit', type=int, default=200,
                            help='单次最多处理多少张订单（默认 200，防一次锁太多行）')

    def handle(self, *args, **opts):
        hours = int(opts['hours'])
        cutoff = timezone.now() - timedelta(hours=hours)
        dry = opts['dry_run']

        # 只挑「确实有 RESERVED 占用」的订单，避免全表扫
        with_locks = Allocation.objects.filter(
            status=Allocation.Status.RESERVED).values('order_item__order_id')
        orders = (Order.objects
                  .filter(id__in=with_locks,
                          status__in=RELEASABLE_STATUSES,
                          updated_at__lt=cutoff)
                  .exclude(id__in=ShippingRecord.objects.values('order_id'))
                  .order_by('updated_at')
                  .distinct()[:opts['limit']])

        done, total_qty = 0, 0
        for order in orders:
            if dry:
                qty = sum(a.remaining_quantity for a in Allocation.objects.filter(
                    order_item__order=order, status=Allocation.Status.RESERVED))
                self.stdout.write(
                    f'  [dry] {order.order_no:16s} status={order.status:12s} '
                    f'updated={order.updated_at:%Y-%m-%d %H:%M} would release {qty}')
                total_qty += qty
                done += 1
                continue

            released = InventoryService.release_for_order(
                order, reason=f'timeout:{hours}h:{order.order_no}')
            if released:
                # 在订单时间线留一条痕，运营看得到「为什么库存回来了」
                StatusLog.objects.create(
                    order=order,
                    actor=None,
                    action_type=StatusLog.ActionType.NOTED,
                    from_status=order.status,
                    to_status=order.status,
                    note=f'Reserved stock auto-released after {hours}h inactivity '
                         f'({released} unit(s))',
                )
                total_qty += released
                done += 1
                self.stdout.write(
                    f'  {order.order_no:16s} released {released}')

        self.stdout.write('')
        if done == 0:
            self.stdout.write('没有需要释放的占用。')
            return
        self.stdout.write(self.style.SUCCESS(
            f'{"[dry-run] " if dry else ""}{done} order(s), '
            f'{total_qty} unit(s) released '
            f'(cutoff: updated_at < {cutoff:%Y-%m-%d %H:%M})'))
        if dry:
            self.stdout.write('  (dry-run，未改库)')
