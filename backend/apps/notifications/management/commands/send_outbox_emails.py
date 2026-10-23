"""投递 Outbox 中待发送的邮件 —— P1-3 自动通知邮件的「发送」半边。

`EmailService.enqueue` 只入队（写 EmailOutbox PENDING），本命令负责真正投递；
配合 cron 定时调用（见 PRD/ARCH：`send_outbox_emails` 建议每 1~5 分钟）。
"""
import os
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.notifications.models import EmailOutbox
from apps.notifications.services import email_delivery_is_unavailable

MAX_RETRIES = 5
# 退避（秒）：1m, 5m, 15m, 1h, 2h
RETRY_BACKOFF_SECONDS = [60, 300, 900, 3600, 7200]


class Command(BaseCommand):
    help = '投递 EmailOutbox 中待发送的邮件（PENDING 且 next_retry_at <= now）。'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100, help='单次最多投递封数')
        parser.add_argument('--force', action='store_true', help='忽略 next_retry_at，投递所有 PENDING')

    def handle(self, *args, **options):
        # ★ 守卫：发信通道不可达时**绝不能投递**。
        #   否则会把 PENDING 标成 SENT —— 造成"已发送"的假象，而且接上真实通道后
        #   这些信再也不会重发（状态已经是 SENT 了）。
        #   保持 PENDING 才是正确语义：等配置好 SPF/DKIM + API key，cron 自动把它们发出去。
        if email_delivery_is_unavailable():
            pending = EmailOutbox.objects.filter(status=EmailOutbox.Status.PENDING).count()
            if pending:
                self.stdout.write(self.style.WARNING(
                    f'[跳过投递] EMAIL_BACKEND={getattr(settings, "EMAIL_BACKEND", "")} '
                    f'无法把信送到用户，{pending} 封保持 PENDING。'
                    f'配置真实发信通道（Resend/Mailgun/SMTP）后会自动发出。'
                ))
            return

        now = timezone.now()
        qs = EmailOutbox.objects.filter(status=EmailOutbox.Status.PENDING)
        if not options['force']:
            qs = qs.filter(Q(next_retry_at__isnull=True) | Q(next_retry_at__lte=now))
        qs = qs.order_by('created_at')[:options['limit']]

        sent = failed = 0
        for outbox in qs:
            try:
                self._send(outbox)
                outbox.status = EmailOutbox.Status.SENT
                outbox.sent_at = now
                outbox.last_error = ''
                outbox.save(update_fields=['status', 'sent_at', 'last_error', 'updated_at'])
                sent += 1
            except Exception as exc:
                # 单封失败不中断整批；达重试上限才标记 FAILED
                outbox.retry_count += 1
                if outbox.retry_count >= MAX_RETRIES:
                    outbox.status = EmailOutbox.Status.FAILED
                else:
                    idx = min(outbox.retry_count, len(RETRY_BACKOFF_SECONDS)) - 1
                    outbox.next_retry_at = now + timedelta(seconds=RETRY_BACKOFF_SECONDS[idx])
                outbox.last_error = str(exc)[:500]
                outbox.save(update_fields=[
                    'retry_count', 'next_retry_at', 'last_error', 'status', 'updated_at',
                ])
                failed += 1

        self.stdout.write(self.style.SUCCESS(f'Sent {sent}, failed {failed}'))

    def _send(self, outbox: EmailOutbox) -> None:
        to = [e.strip() for e in outbox.to_emails.split(',') if e.strip()]
        cc = [e.strip() for e in outbox.cc_emails.split(',') if e.strip()]
        msg = EmailMultiAlternatives(
            subject=outbox.subject,
            body=outbox.body_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=to,
            cc=cc or None,
        )
        if outbox.body_html:
            msg.attach_alternative(outbox.body_html, 'text/html')
        for path in (outbox.attachment_paths or []):
            if os.path.exists(path):
                msg.attach_file(path)
        msg.send(fail_silently=False)
