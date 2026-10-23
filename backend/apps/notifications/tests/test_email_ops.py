"""邮件模板编辑 + 投递队列操作。

关键点：
- 模板 key 是代码契约，不能改（改了 enqueue 就找不到模板）
- 预览必须能发现"占位符写错但渲染不报错"的情况（_SafeDict 会吞掉未知键）
- 试发只能发给管理员自己，否则这个端点就是滥发通道
- 已 sent 的邮件不允许重试（会重复打扰收件人）
"""
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import EmailOutbox, EmailTemplate

BASE = '/api/v1/ops/email-templates/'
OUTBOX = '/api/v1/ops/email-outbox/'


class TmplBase(TestCase):
    def setUp(self):
        call_command('seed_email_templates', verbosity=0)
        self.admin = UserFactory(is_staff=True, email='ops-admin@lab.org')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)


class TemplateListTest(TmplBase):
    def test_list_returns_all_seeded(self):
        rows = self.client.get(BASE).json()['data']
        keys = {r['key'] for r in rows}
        self.assertIn('email_verification', keys)
        self.assertIn('password_reset', keys)
        self.assertGreaterEqual(len(rows), 10)
        self.assertNotIn('body_html', rows[0], '列表不带正文，避免响应过大')

    def test_detail_has_bodies(self):
        d = self.client.get(f'{BASE}email_verification/').json()['data']
        self.assertIn('body_html', d)
        self.assertIn('body_text', d)
        self.assertTrue(d['subject'])

    def test_unknown_key_404(self):
        self.assertEqual(self.client.get(f'{BASE}nope_not_a_template/').status_code, 404)


class TemplateUpdateTest(TmplBase):
    def test_update_subject(self):
        r = self.client.patch(f'{BASE}order_confirmed/',
                              {'subject': 'Your order {order_no} is confirmed'},
                              format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(EmailTemplate.objects.get(key='order_confirmed').subject,
                         'Your order {order_no} is confirmed')

    def test_cannot_change_key(self):
        r = self.client.patch(f'{BASE}order_confirmed/', {'key': 'hacked'}, format='json')
        self.assertEqual(r.status_code, 400, 'key 是代码契约，必须拒绝')
        self.assertTrue(EmailTemplate.objects.filter(key='order_confirmed').exists())

    def test_empty_payload_rejected(self):
        self.assertEqual(
            self.client.patch(f'{BASE}order_confirmed/', {}, format='json').status_code, 400)


class TemplatePreviewTest(TmplBase):
    def test_preview_detects_missing_ctx_keys(self):
        """_SafeDict 会静默把缺失键渲染成空串 —— 预览必须把它报出来。"""
        r = self.client.post(
            f'{BASE}rfq_submitted/preview/',
            {'ctx': {'rfq_id': 7}},     # 缺 contact_name / items_count
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        d = r.json()['data']
        missing = set(d['text']['missing_in_ctx']) | set(d['html']['missing_in_ctx'])
        self.assertIn('contact_name', missing)
        self.assertIn('items_count', missing)
        self.assertTrue(any('缺少' in w for w in d['warnings']))

    def test_preview_falls_back_to_last_outbox_ctx(self):
        EmailOutbox.objects.create(
            to_emails='x@y.z', subject='s', body_text='b',
            template_key='rfq_submitted',
            context_json={'rfq_id': 42, 'contact_name': 'Real Buyer', 'items_count': 3},
        )
        d = self.client.post(f'{BASE}rfq_submitted/preview/', {}, format='json').json()['data']
        self.assertEqual(d['ctx_source'], 'last_outbox_record')
        self.assertIn('Real Buyer', d['text']['rendered'])
        self.assertIn('#42', d['text']['rendered'])

    def test_preview_with_overrides_does_not_persist(self):
        before = EmailTemplate.objects.get(key='order_confirmed').subject
        d = self.client.post(
            f'{BASE}order_confirmed/preview/',
            {'ctx': {'order_no': 'SC-1'}, 'subject_override': 'DRAFT SUBJECT {order_no}'},
            format='json',
        ).json()['data']
        self.assertIn('DRAFT SUBJECT SC-1', d['subject']['rendered'])
        self.assertEqual(EmailTemplate.objects.get(key='order_confirmed').subject, before,
                         '预览不能写库')


class TemplateSendTestTest(TmplBase):
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_sends_only_to_self(self):
        r = self.client.post(f'{BASE}order_confirmed/send-test/',
                             {'ctx': {'order_no': 'SC-9'}}, format='json')
        self.assertEqual(r.status_code, 200)
        d = r.json()['data']
        self.assertEqual(d['to'], 'ops-admin@lab.org', '收件人固定为自己，不接受前端指定')

        mail = EmailOutbox.objects.filter(template_key='order_confirmed').latest('id')
        self.assertEqual(mail.to_emails, 'ops-admin@lab.org')
        self.assertIn('SC-9', mail.subject + mail.body_text)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_ignores_recipient_in_payload(self):
        """即使请求里带了 to，也必须忽略 —— 否则就是滥发通道。"""
        r = self.client.post(f'{BASE}order_confirmed/send-test/',
                             {'to': 'victim@example.com', 'ctx': {'order_no': 'X'}},
                             format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['data']['to'], 'ops-admin@lab.org')
        self.assertFalse(EmailOutbox.objects.filter(to_emails='victim@example.com').exists())

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_refuses_when_channel_unavailable(self):
        r = self.client.post(f'{BASE}order_confirmed/send-test/', {}, format='json')
        self.assertEqual(r.status_code, 400, '通道不可用时不该假装发了')

    def test_refuses_when_user_has_no_email(self):
        self.admin.email = ''
        self.admin.save(update_fields=['email'])
        r = self.client.post(f'{BASE}order_confirmed/send-test/', {}, format='json')
        self.assertEqual(r.status_code, 400)


class OutboxTest(TmplBase):
    def _mk(self, **kw):
        defaults = dict(to_emails='customer@uni.edu', subject='s', body_text='b')
        defaults.update(kw)
        return EmailOutbox.objects.create(**defaults)

    def test_list_masks_recipient(self):
        self._mk()
        rows = self.client.get(OUTBOX).json()['data']
        self.assertEqual(rows[0]['to_emails'], '***@uni.edu')

    def test_filter_by_status(self):
        self._mk()
        self._mk(status=EmailOutbox.Status.FAILED, last_error='boom')
        rows = self.client.get(OUTBOX, {'status': 'failed'}).json()['data']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['status'], 'failed')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_retry_resets_state(self):
        m = self._mk(status=EmailOutbox.Status.FAILED, retry_count=5, last_error='x')
        r = self.client.post(f'{OUTBOX}{m.pk}/retry/')
        self.assertEqual(r.status_code, 200)
        m.refresh_from_db()
        self.assertEqual(m.status, EmailOutbox.Status.PENDING)
        self.assertEqual(m.retry_count, 0)
        self.assertIsNone(m.next_retry_at)
        self.assertEqual(m.last_error, '')

    def test_cannot_retry_sent(self):
        m = self._mk(status=EmailOutbox.Status.SENT)
        r = self.client.post(f'{OUTBOX}{m.pk}/retry/')
        self.assertEqual(r.status_code, 400, '已发送的不能重试，会重复打扰收件人')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_retry_refused_when_channel_down(self):
        m = self._mk(status=EmailOutbox.Status.FAILED)
        r = self.client.post(f'{OUTBOX}{m.pk}/retry/')
        self.assertEqual(r.status_code, 400)

    def test_discard_marks_failed(self):
        m = self._mk(status=EmailOutbox.Status.PENDING)
        r = self.client.post(f'{OUTBOX}{m.pk}/discard/')
        self.assertEqual(r.status_code, 200)
        m.refresh_from_db()
        self.assertEqual(m.status, EmailOutbox.Status.FAILED)
        self.assertIsNone(m.next_retry_at)

    def test_unknown_action_rejected(self):
        m = self._mk()
        self.assertEqual(self.client.post(f'{OUTBOX}{m.pk}/nuke/').status_code, 400)
