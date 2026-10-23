"""COA/SDS 发布后的客户通知。

覆盖三条容易出错的规则：
  1. **默认关闭**（DOC_NOTIFY_CUSTOMERS=False）—— 防止一次修订群发几十个客户
  2. **一人一封** —— B2B 场景下收件人列表互相可见是隐私事故
  3. **同一客户多笔订单只发一封** —— 去重
"""
from datetime import date

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.transactions.tests.factories import OrderFactory, OrderItemFactory
from apps.documents.models import Batch, Coa, SdsRevision
from apps.documents.services.notify import (
    customer_emails_for_product,
    customer_emails_for_sku,
    notify_coa_published,
    notify_sds_published,
)
from apps.notifications.models import EmailOutbox


class DocNotifyBase(TestCase):
    def setUp(self):
        call_command('seed_email_templates', verbosity=0)
        self.product = ProductFactory(catalog_no='SC9901', name='NotifyTest', cas='123-45-1')
        self.sku = SKUFactory(product=self.product, sku_code='SC9901-SKU')
        self.batch = Batch.objects.create(
            sku=self.sku, lot_number='LOT-N1', produced_at=date(2026, 1, 1)
        )
        self.coa = Coa.objects.create(
            batch=self.batch, doc_id='COA-N-001',
            product_name='NotifyTest', catalog_number='SC9901',
        )

    def _order(self, email):
        o = OrderFactory(shipping_email=email)
        OrderItemFactory(order=o, product=self.product, sku=self.sku)
        return o


class CoaNotifyTest(DocNotifyBase):
    @override_settings(DOC_NOTIFY_CUSTOMERS=False)
    def test_disabled_sends_nothing(self):
        self._order('buyer@lab.org')
        n = notify_coa_published(self.coa)
        self.assertEqual(n, 0)
        self.assertFalse(EmailOutbox.objects.filter(template_key='coa_published').exists())

    @override_settings(DOC_NOTIFY_CUSTOMERS=True)
    def test_notifies_each_buyer_separately(self):
        self._order('a@lab.org')
        self._order('b@lab.org')
        n = notify_coa_published(self.coa)
        self.assertEqual(n, 2)

        mails = list(EmailOutbox.objects.filter(template_key='coa_published'))
        self.assertEqual(len(mails), 2)
        for m in mails:
            self.assertNotIn(',', m.to_emails, '一人一封，收件人不能并列（隐私）')
            self.assertTrue(m.subject.strip(), 'subject 不能为空')
            self.assertIn('COA-N-001', m.body_text)
            self.assertIn('LOT-N1', m.body_text)

    @override_settings(DOC_NOTIFY_CUSTOMERS=True)
    def test_dedupe_same_customer_two_orders(self):
        self._order('same@lab.org')
        self._order('same@lab.org')
        n = notify_coa_published(self.coa)
        self.assertEqual(n, 1, '同一客户两笔订单只应收到一封')

    @override_settings(DOC_NOTIFY_CUSTOMERS=True)
    def test_no_buyers_no_mail(self):
        n = notify_coa_published(self.coa)
        self.assertEqual(n, 0)
        self.assertFalse(EmailOutbox.objects.filter(template_key='coa_published').exists())


class SdsNotifyTest(DocNotifyBase):
    def setUp(self):
        super().setUp()
        self.sds = SdsRevision.objects.create(
            product=self.product, revision_no=1, revised_at=date(2026, 2, 1),
        )

    @override_settings(DOC_NOTIFY_CUSTOMERS=True)
    def test_notifies_product_buyers(self):
        self._order('sds@lab.org')
        n = notify_sds_published(self.sds)
        self.assertEqual(n, 1)
        m = EmailOutbox.objects.filter(template_key='sds_published').first()
        self.assertIsNotNone(m)
        self.assertIn('NotifyTest', m.body_text)

    @override_settings(DOC_NOTIFY_CUSTOMERS=False)
    def test_disabled_sends_nothing(self):
        self._order('sds2@lab.org')
        self.assertEqual(notify_sds_published(self.sds), 0)
        self.assertFalse(EmailOutbox.objects.filter(template_key='sds_published').exists())


class CustomerLookupTest(DocNotifyBase):
    @override_settings(DOC_NOTIFY_WINDOW_DAYS=365)
    def test_lookup_by_sku_and_product(self):
        self._order('lookup@lab.org')
        self.assertIn('lookup@lab.org', customer_emails_for_sku(self.sku.pk))
        self.assertIn('lookup@lab.org', customer_emails_for_product(self.product.pk))

    @override_settings(DOC_NOTIFY_CUSTOMERS=True)
    def test_empty_email_is_ignored(self):
        o = OrderFactory(shipping_email='')
        OrderItemFactory(order=o, product=self.product, sku=self.sku)
        n = notify_coa_published(self.coa)
        self.assertEqual(n, 0, '空邮箱不应产生邮件')
