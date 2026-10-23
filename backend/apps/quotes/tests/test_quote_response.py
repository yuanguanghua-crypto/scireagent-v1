"""运营填写报价 → 状态推进到 quoted + 通知客户。

此前 `QUOTED` 只在枚举里定义，全仓没有任何代码会写它（报价功能是断的）。
本测试锁住：状态机、权限、邮件内容、以及"邮件失败不回滚报价"。
"""
from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.notifications.models import EmailOutbox
from apps.quotes.models import QuoteRequest, QuoteRequestItem


class QuoteResponseTest(TestCase):
    def setUp(self):
        call_command('seed_email_templates', verbosity=0)
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.plain = UserFactory(is_staff=False)

        product = ProductFactory(catalog_no='SC9701', name='QuoteProbe')
        sku = SKUFactory(product=product, sku_code='SC9701-SKU')
        self.rfq = QuoteRequest.objects.create(
            contact_name='Buyer Lee', contact_email='buyer@lab.org',
            company_name='Lab Co', status=QuoteRequest.Status.PENDING,
        )
        QuoteRequestItem.objects.create(quote_request=self.rfq, product=product, sku=sku,
                                        quantity=3, note='bulk')
        self.url = f'/api/v1/quote-requests/{self.rfq.pk}/quote/'

    def test_staff_can_quote_and_customer_gets_mail(self):
        self.client.force_authenticate(self.staff)
        resp = self.client.post(self.url, {
            'quoted_total': '1250.00', 'quoted_currency': 'usd',
            'quoted_valid_until': '2026-11-30', 'quoted_note': 'Lead time 2 weeks',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

        self.rfq.refresh_from_db()
        self.assertEqual(self.rfq.status, QuoteRequest.Status.QUOTED, '状态必须推进到 quoted')
        self.assertEqual(self.rfq.quoted_total, Decimal('1250.00'))
        self.assertEqual(self.rfq.quoted_currency, 'USD', '币种应归一为大写')
        self.assertIsNotNone(self.rfq.quoted_at)

        mails = EmailOutbox.objects.filter(template_key='quote_ready')
        self.assertEqual(mails.count(), 1)
        m = mails.first()
        self.assertEqual(m.to_emails, 'buyer@lab.org')
        self.assertIn('1,250.00', m.body_text, '金额应带千分位')
        self.assertIn('USD', m.body_text)
        self.assertIn('Lead time 2 weeks', m.body_text)
        self.assertIn(f'#{self.rfq.pk}', m.subject)

    def test_non_staff_cannot_quote(self):
        self.client.force_authenticate(self.plain)
        resp = self.client.post(self.url, {'quoted_total': '1.00'}, format='json')
        self.assertIn(resp.status_code, (403,), '普通研究员不得填写报价')
        self.rfq.refresh_from_db()
        self.assertEqual(self.rfq.status, QuoteRequest.Status.PENDING)

    def test_anonymous_cannot_quote(self):
        resp = self.client.post(self.url, {'quoted_total': '1.00'}, format='json')
        self.assertIn(resp.status_code, (401, 403))

    def test_quote_without_amount_is_allowed(self):
        """允许"只回执不报价"——不必为了走流程编一个价格。"""
        self.client.force_authenticate(self.staff)
        resp = self.client.post(self.url, {'quoted_note': 'Please contact sales'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.rfq.refresh_from_db()
        self.assertEqual(self.rfq.status, QuoteRequest.Status.QUOTED)
        self.assertIsNone(self.rfq.quoted_total)
        self.assertEqual(EmailOutbox.objects.filter(template_key='quote_ready').count(), 1)

    def test_notify_customer_false_skips_mail(self):
        self.client.force_authenticate(self.staff)
        resp = self.client.post(self.url, {
            'quoted_total': '99.00', 'notify_customer': False,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(EmailOutbox.objects.filter(template_key='quote_ready').exists())

    @patch('apps.quotes.api.v1.views.EmailService.enqueue', side_effect=RuntimeError('smtp down'))
    def test_mail_failure_does_not_rollback_quote(self, _mock):
        self.client.force_authenticate(self.staff)
        resp = self.client.post(self.url, {'quoted_total': '500.00'}, format='json')
        self.assertEqual(resp.status_code, 200, '邮件失败不应让报价请求失败')
        self.rfq.refresh_from_db()
        self.assertEqual(self.rfq.status, QuoteRequest.Status.QUOTED)
        self.assertEqual(self.rfq.quoted_total, Decimal('500.00'))
        self.assertFalse(resp.data['data']['customer_notified'])
