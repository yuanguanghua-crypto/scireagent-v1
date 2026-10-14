"""`send_outbox_emails` 管理命令测试 —— 投递 Outbox 中 PENDING 邮件。

背景：`EmailService.enqueue` 只入队不发送；本命令是真正投递那一步（P1-3 的发送半边）。
"""
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.notifications.models import EmailOutbox


class SendOutboxEmailsTest(TestCase):
    def _enqueue(self, **kwargs):
        defaults = dict(
            to_emails='a@example.com', subject='Hi', body_text='Hello',
            status=EmailOutbox.Status.PENDING, next_retry_at=timezone.now(),
        )
        defaults.update(kwargs)
        return EmailOutbox.objects.create(**defaults)

    def test_pending_email_is_sent(self):
        outbox = self._enqueue()
        call_command('send_outbox_emails')
        outbox.refresh_from_db()
        self.assertEqual(outbox.status, EmailOutbox.Status.SENT)
        self.assertIsNotNone(outbox.sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Hi')

    def test_future_retry_is_skipped(self):
        outbox = self._enqueue(next_retry_at=timezone.now() + timezone.timedelta(hours=1))
        call_command('send_outbox_emails')
        outbox.refresh_from_db()
        self.assertEqual(outbox.status, EmailOutbox.Status.PENDING, '未到重试时间应跳过')
        self.assertEqual(len(mail.outbox), 0)

    def test_html_body_attached_as_alternative(self):
        self._enqueue(body_html='<b>bold</b>')
        call_command('send_outbox_emails')
        msg = mail.outbox[0]
        self.assertTrue(any(alt[1] == 'text/html' for alt in msg.alternatives))
        self.assertIn('<b>bold</b>', msg.alternatives[0][0])

    def test_send_failure_increments_retry(self):
        outbox = self._enqueue()
        with mock.patch(
            'apps.notifications.management.commands.send_outbox_emails.EmailMultiAlternatives.send',
            side_effect=Exception('boom'),
        ):
            call_command('send_outbox_emails')
        outbox.refresh_from_db()
        self.assertEqual(outbox.retry_count, 1)
        self.assertEqual(outbox.status, EmailOutbox.Status.PENDING, '未达上限应保持 PENDING 待重试')
        self.assertIsNotNone(outbox.next_retry_at)
        self.assertIn('boom', outbox.last_error)

    def test_max_retries_marks_failed(self):
        outbox = self._enqueue(retry_count=4)  # 第 5 次失败 → FAILED
        with mock.patch(
            'apps.notifications.management.commands.send_outbox_emails.EmailMultiAlternatives.send',
            side_effect=Exception('boom'),
        ):
            call_command('send_outbox_emails')
        outbox.refresh_from_db()
        self.assertEqual(outbox.retry_count, 5)
        self.assertEqual(outbox.status, EmailOutbox.Status.FAILED)
