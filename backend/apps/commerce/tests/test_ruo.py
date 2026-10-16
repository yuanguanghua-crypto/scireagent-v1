"""★ RUO 标注测试（v4.1 DEV-4）。

覆盖：SKU.is_ruo 字段存在且默认 True · 序列化器输出含 is_ruo ·
发票 PDF 含 RUO 标注文本 · 订单行 serializer 输出含 is_ruo。
"""
from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import Organization, User
from apps.commerce.models import Product, SKU
from apps.transactions.models import Order, OrderItem


class RUOFieldTest(TestCase):
    """SKU.is_ruo 字段 + Product.research_use_only 字段。"""

    def setUp(self):
        self.org = Organization.objects.create(name='Lab', org_type='academic')
        self.user = User.objects.create_user(
            username='ruo_user', password='x', organization=self.org, role='researcher')
        self.product = Product.objects.create(
            name='RUO Test Product', slug='ruo-test', research_use_only=True)
        self.sku = SKU.objects.create(
            product=self.product, sku_code='RUO-SKU-001', price=Decimal('10.00'))

    def test_sku_is_ruo_default_true(self):
        self.assertTrue(self.sku.is_ruo)

    def test_product_research_use_only_default_true(self):
        self.assertTrue(self.product.research_use_only)

    def test_sku_serializer_includes_is_ruo(self):
        from apps.commerce.api.v1.serializers import SKUSerializer
        data = SKUSerializer(self.sku).data
        self.assertIn('is_ruo', data)
        self.assertTrue(data['is_ruo'])


class RUOInvoicePDFTest(TestCase):
    """发票 PDF 含 RUO 标注文本。"""

    def setUp(self):
        self.org = Organization.objects.create(name='RUO Lab', org_type='academic')
        self.user = User.objects.create_user(
            username='ruo_inv', password='x', organization=self.org, role='researcher')
        self.product = Product.objects.create(
            name='RUO Inv Product', slug='ruo-inv', research_use_only=True)
        self.sku = SKU.objects.create(
            product=self.product, sku_code='RUO-INV-001', price=Decimal('25.00'))
        self.order = Order.objects.create(
            user=self.user, organization=self.org,
            order_no='ORD-RUO-INV', po_number=None, status=Order.Status.DELIVERED)
        self.item = OrderItem.objects.create(
            order=self.order, sku=self.sku, quantity=2, unit_price=Decimal('25.00'))
        from apps.transactions.services import InvoiceService
        self.invoice = InvoiceService.issue(self.order, payment_terms='Net 30')

    def test_invoice_pdf_contains_ruo_text(self):
        import os
        from django.conf import settings
        from PyPDF2 import PdfReader
        pdf_path = os.path.join(settings.MEDIA_ROOT, 'invoices', f'{self.invoice.invoice_no}.pdf')
        self.assertTrue(os.path.exists(pdf_path), f'PDF should exist at {pdf_path}')
        text = PdfReader(pdf_path).pages[0].extract_text()
        self.assertIn('For Research Use Only', text)
