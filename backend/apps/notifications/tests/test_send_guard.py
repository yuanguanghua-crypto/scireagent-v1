"""投递任务的降级守卫 —— 防止把没发出去的信标成 SENT。

2026-10-23 真实事故：加 cron 后 5 分钟（守卫上线前），`send_outbox_emails`
在 console backend 下把 49 条 PENDING 全标成 SENT，实际只在容器日志打了一行。
后果：状态造假 + 接上真实通道后这些信再也不会重发。
"""
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.notifications.models import EmailOutbox


class SendOutboxGuardTest(TestCase):
    def _mk(self, **kw):
        return EmailOutbox.objects.create(
            to_emails='someone@lab.example.org',
            subject=kw.get('subject', 'Hello'),
            body_text=kw.get('body_text', 'Body'),
        )

    def test_console_backend_keeps_pending_and_does_not_stamp_sent(self):
        m = self._mk()
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'):
            call_command('send_outbox_emails', verbosity=0)
        m.refresh_from_db()
        self.assertEqual(m.status, EmailOutbox.Status.PENDING, '不可达后端下不得标记 SENT')
        self.assertIsNone(m.sent_at, 'sent_at 不应被写入')
        self.assertEqual(m.retry_count, 0, '跳过不是失败，不该累加重试次数')

    def test_dummy_and_filebased_also_guarded(self):
        for backend in (
            'django.core.mail.backends.dummy.EmailBackend',
            'django.core.mail.backends.filebased.EmailBackend',
        ):
            m = EmailOutbox.objects.create(
                to_emails='x@y.z', subject='s', body_text='b'
            )
            with override_settings(EMAIL_BACKEND=backend):
                call_command('send_outbox_emails', verbosity=0)
            m.refresh_from_db()
            self.assertEqual(m.status, EmailOutbox.Status.PENDING, f'{backend} 应保持 PENDING')

    def test_locmem_backend_still_delivers(self):
        """locmem 被视为可达（测试专用），守卫不能误伤正常投递路径。"""
        m = self._mk()
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            call_command('send_outbox_emails', verbosity=0)
        m.refresh_from_db()
        self.assertEqual(m.status, EmailOutbox.Status.SENT)
        self.assertIsNotNone(m.sent_at)
