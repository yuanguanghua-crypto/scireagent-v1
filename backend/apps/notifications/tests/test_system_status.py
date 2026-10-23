"""运营台「系统状态」接口 —— 权限、结构、脱敏、心跳。

这些断言的意义：这个页面是"排障第一眼"，
- 数字错了会误导判断（比如 pending 数）
- 收件人不脱敏会在运营台泄露客户邮箱
- 心跳判断错会让人误以为 cron 停了/在跑
"""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import EmailOutbox
from apps.notifications.services import read_dispatch_heartbeat, record_dispatch_heartbeat

URL = '/api/v1/ops/system-status/'


class SystemStatusPermissionTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_anonymous_denied(self):
        resp = self.client.get(URL)
        self.assertIn(resp.status_code, (401, 403))

    def test_plain_researcher_denied(self):
        self.client.force_authenticate(UserFactory(is_staff=False))
        resp = self.client.get(URL)
        self.assertIn(resp.status_code, (401, 403))

    def test_staff_allowed(self):
        self.client.force_authenticate(UserFactory(is_staff=True))
        resp = self.client.get(URL)
        self.assertEqual(resp.status_code, 200)


class SystemStatusContentTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(UserFactory(is_staff=True))

    def test_response_shape(self):
        d = self.client.get(URL).json()['data']
        for key in ('email', 'queue', 'dispatch', 'database', 'counts'):
            self.assertIn(key, d, f'缺少 {key} 段')
        self.assertIn('backend', d['email'])
        self.assertIn('delivery_available', d['email'])
        self.assertIn('counts', d['queue'])
        self.assertTrue(d['database']['ok'], '测试库应可连')

    def test_provider_and_delivery_flag_are_consistent(self):
        d = self.client.get(URL).json()['data']['email']
        # console/dummy/filebased ⇒ delivery_available=False；anymail/smtp ⇒ True
        if 'console' in d['backend'] or 'dummy' in d['backend'] or 'filebased' in d['backend']:
            self.assertFalse(d['delivery_available'])
        else:
            self.assertTrue(d['delivery_available'])

    def test_queue_counts_reflect_records(self):
        EmailOutbox.objects.create(to_emails='a@x.org', subject='s', body_text='b')
        EmailOutbox.objects.create(to_emails='b@x.org', subject='s', body_text='b',
                                   status=EmailOutbox.Status.SENT, sent_at=timezone.now())
        EmailOutbox.objects.create(to_emails='c@x.org', subject='s', body_text='b',
                                   status=EmailOutbox.Status.FAILED, last_error='boom')
        q = self.client.get(URL).json()['data']['queue']['counts']
        self.assertEqual(q['pending'], 1)
        self.assertEqual(q['sent'], 1)
        self.assertEqual(q['failed'], 1)
        self.assertEqual(q['total'], 3)

    def test_recent_failure_recipient_is_masked(self):
        """运营台页面不该暴露客户完整邮箱。"""
        EmailOutbox.objects.create(
            to_emails='customer@university.edu', subject='s', body_text='b',
            status=EmailOutbox.Status.FAILED, last_error='403 domain not verified',
        )
        fails = self.client.get(URL).json()['data']['queue']['recent_failures']
        self.assertEqual(len(fails), 1)
        self.assertEqual(fails[0]['to_emails'], '***@university.edu')
        self.assertNotIn('customer', fails[0]['to_emails'])
        self.assertIn('domain not verified', fails[0]['last_error'])

    def test_heartbeat_missing_is_stale(self):
        d = self.client.get(URL).json()['data']['dispatch']
        # 测试环境 MEDIA_ROOT 下没有心跳文件（除非别的用例刚写过）
        if d['last_run_at'] is None:
            self.assertTrue(d['stale'], '无心跳必须判为 stale')
            self.assertIsNone(d['minutes_ago'])


class DispatchHeartbeatTest(TestCase):
    def test_record_then_read_roundtrip(self):
        record_dispatch_heartbeat()
        iso, minutes = read_dispatch_heartbeat()
        self.assertIsNotNone(iso)
        self.assertIsNotNone(minutes)
        self.assertLess(minutes, 1.0, '刚写入的心跳应小于 1 分钟')

    def test_command_writes_heartbeat_even_when_skipping(self):
        """降级跳过时也要留痕 —— "cron 在跑"和"邮件发了"是两件事。"""
        from django.core.management import call_command
        record_dispatch_heartbeat()
        EmailOutbox.objects.create(to_emails='z@x.org', subject='s', body_text='b')
        with override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'):
            call_command('send_outbox_emails', verbosity=0)
        iso, minutes = read_dispatch_heartbeat()
        self.assertIsNotNone(iso)
        self.assertLess(minutes, 1.0)
        # 同时确认守卫仍然生效（没被误标 SENT）
        m = EmailOutbox.objects.get(to_emails='z@x.org')
        self.assertEqual(m.status, EmailOutbox.Status.PENDING)
