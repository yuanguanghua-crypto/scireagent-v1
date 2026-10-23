"""RFQ 邮件通知测试 —— 客户回执 + 运营提醒 + 邮件异常不影响获客。

对应 2026-10-23 的缺口：客户提交询价后收不到任何回执，运营也不知道。
"""
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.notifications.models import EmailOutbox, EmailTemplate


class RfqEmailOnSubmitTest(TestCase):
    def setUp(self):
        # 模板必须先存在，否则 enqueue 出来的是空 subject/body（本期修的就是这个）
        from django.core.management import call_command
        call_command('seed_email_templates', verbosity=0)

        self.client = APIClient()
        self.url = '/api/v1/quote-requests/'
        self.payload = {
            'contact_name': 'Alice Chen',
            'contact_email': 'alice@lab.example.org',
            'company_name': 'Example Lab',
            'country': 'US',
            'note': 'Need bulk pricing',
            'items': [{'quantity': 2, 'note': 'custom oligo'}],
        }

    def test_customer_receipt_enqueued_with_rendered_content(self):
        resp = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(resp.status_code, 201)
        rfq_id = resp.data.get('id')

        mails = EmailOutbox.objects.filter(template_key='rfq_submitted')
        self.assertEqual(mails.count(), 1, '客户回执应入队一封')
        m = mails.first()
        self.assertEqual(m.to_emails, 'alice@lab.example.org')
        # 关键：内容不是空的（模板缺失时这里会是空串）
        self.assertTrue(m.subject.strip(), 'subject 不能为空')
        self.assertIn(f'#{rfq_id}', m.subject)
        self.assertTrue(m.body_text.strip(), 'body 不能为空')
        self.assertIn('Alice Chen', m.body_text)
        self.assertEqual(m.status, EmailOutbox.Status.PENDING)

    @override_settings(RFQ_NOTIFICATION_EMAILS=['ops@scireagent.com', 'sales@scireagent.com'])
    def test_internal_notification_sent_to_configured_recipients(self):
        resp = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(resp.status_code, 201)
        mails = EmailOutbox.objects.filter(template_key='rfq_received_internal')
        self.assertEqual(mails.count(), 1)
        m = mails.first()
        self.assertIn('ops@scireagent.com', m.to_emails)
        self.assertIn('sales@scireagent.com', m.to_emails)
        self.assertIn('Example Lab', m.body_text)

    @override_settings(RFQ_NOTIFICATION_EMAILS=[])
    def test_no_internal_notification_when_unconfigured(self):
        resp = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(EmailOutbox.objects.filter(template_key='rfq_received_internal').exists(),
                         '未配置收件人时不应产生内部通知')

    @patch('apps.quotes.api.v1.views.EmailService.enqueue', side_effect=RuntimeError('smtp down'))
    def test_email_failure_does_not_block_submission(self, _mock):
        """获客入口不能被邮件故障拖死 —— 必须仍然 201，线索不能丢。"""
        resp = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(resp.status_code, 201, '邮件异常时仍须创建成功')
        self.assertTrue(resp.data.get('id'))
