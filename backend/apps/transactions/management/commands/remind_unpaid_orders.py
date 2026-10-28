# -*- coding: utf-8 -*-
"""给「下单满 N 天仍未付款」的客户发一封催款提醒。

## 为什么要有这一条

2026-10-28 起下单/审核会**真实占用库存**。客户下单后如果一直不付款，那批货被锁着、
别人买不到 —— 而且**不报任何错**。所以在「释放占用」（默认 7 天）之前，
必须有一个更早的提醒点（默认 3 天），否则客户会觉得"货怎么突然没了"。

两个阈值是**独立配置**的，别写死成同一个：
  · `--hours`（提醒，默认 72 = 3 天）
  · `release_expired_reservations --hours`（释放，默认 168 = 7 天）
正文里会写出释放阈值，让客户知道后果。

## 有意不做什么

- **不取消订单**、不改任何状态。只发一封信 + 记一个时间戳。
- **每个订单只提醒一次**（`Order.unpaid_reminder_sent_at`）。重复发信会让客户
  直接把我们的邮件丢进垃圾箱，以后真要紧的信也看不到了。
- **不发没有邮箱的订单**（下单时 `shipping_email` 可空），但会打印出来让人看见 ——
  静默跳过等于"以为提醒了其实没有"。

## 用法

    python manage.py remind_unpaid_orders --dry-run
    python manage.py remind_unpaid_orders --hours 72 --release-hours 168
    python manage.py remind_unpaid_orders --hours 72 --limit 50

建议 crontab（与释放错开半小时，避免同时抢锁）：

    0 4 * * * docker exec scireagent-backend-1 python manage.py remind_unpaid_orders --hours 72
    30 4 * * * docker exec scireagent-backend-1 python manage.py release_expired_reservations --hours 168
"""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.notifications.services import EmailService
from apps.transactions.models import Order

logger = logging.getLogger(__name__)

#: 还没付款、且订单仍有效（不是报价草稿、不是已取消/已完成）的状态。
#: 刻意包含 shipped/delivered/invoiced —— 货发了但钱没到，正是最该催的时候。
UNPAID_STATUSES = (
    Order.Status.PO_RECEIVED,
    Order.Status.CONFIRMED,
    Order.Status.IN_PRODUCTION,
    Order.Status.SHIPPED,
    Order.Status.DELIVERED,
    Order.Status.INVOICED,
)


class Command(BaseCommand):
    help = '给下单满 N 天仍未付款的客户发催款提醒（每单只发一次）'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=72,
                            help='下单后多少小时仍未付款就提醒（默认 72 = 3 天）')
        parser.add_argument('--release-hours', type=int, default=168,
                            help='多久后释放占用（只用于邮件正文告知客户，默认 168 = 7 天）')
        parser.add_argument('--limit', type=int, default=200,
                            help='单次最多处理多少张订单（默认 200）')
        parser.add_argument('--dry-run', action='store_true', help='只打印，不发信不改库')

    def handle(self, *args, **opts):
        hours = int(opts['hours'])
        release_hours = int(opts['release_hours'])
        cutoff = timezone.now() - timedelta(hours=hours)
        dry = opts['dry_run']

        qs = (Order.objects
              .filter(created_at__lt=cutoff,
                      unpaid_reminder_sent_at__isnull=True,
                      status__in=UNPAID_STATUSES)
              .order_by('created_at'))

        sent, no_email, failed = 0, [], []
        for order in qs[:opts['limit']]:
            days_since = max(1, int((timezone.now() - order.created_at).total_seconds() // 86400))
            if not (order.shipping_email or '').strip():
                no_email.append(order.order_no)
                continue

            if dry:
                self.stdout.write(
                    f'  [dry] {order.order_no:16s} {order.status:14s} '
                    f'{days_since}d  {order.shipping_email}')
                sent += 1
                continue

            try:
                EmailService.enqueue(
                    'order_unpaid_reminder',
                    to=[order.shipping_email.strip()],
                    ctx={
                        'contact_name': order.shipping_name or 'there',
                        'order_no': order.order_no,
                        'days_since': days_since,
                        'currency': order.currency or 'USD',
                        'amount_due': f'{order.grand_total or 0:.2f}',
                        'status_label': order.get_status_display(),
                        'release_days': max(1, release_hours // 24),
                    },
                )
            except Exception:   # noqa: BLE001 —— 单封失败不能中断整批
                logger.exception('unpaid reminder enqueue failed: order=%s', order.order_no)
                failed.append(order.order_no)
                continue

            # 只在这封信成功入队后才打标记：先标后发会导致"以为提醒过、其实没发"，
            # 而那个订单再也不会被提醒。
            order.unpaid_reminder_sent_at = timezone.now()
            order.save(update_fields=['unpaid_reminder_sent_at'])
            sent += 1
            self.stdout.write(f'  {order.order_no:16s} reminded ({days_since}d)')

        self.stdout.write('')
        if sent == 0 and not no_email and not failed:
            self.stdout.write('没有需要提醒的订单。')
            return
        self.stdout.write(self.style.SUCCESS(
            f'{"[dry-run] " if dry else ""}reminded {sent} order(s) '
            f'(cutoff: created_at < {cutoff:%Y-%m-%d %H:%M})'))
        if no_email:
            self.stdout.write(self.style.WARNING(
                f'  跳过 {len(no_email)} 张（没有收货邮箱，无法发信）: '
                f'{", ".join(no_email[:10])}{" …" if len(no_email) > 10 else ""}'))
        if failed:
            self.stdout.write(self.style.ERROR(
                f'  {len(failed)} 张入队失败（下次运行会重试）: '
                f'{", ".join(failed[:10])}'))
