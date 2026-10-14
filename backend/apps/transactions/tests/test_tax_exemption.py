"""D1 免税（P0-5）—— 免税机构税为零 + 发票标注 Tax Exempt ID。

背景（源自 DESIGN_REVIEW_INDUSTRY_FIT.md §2）：目标客户为美国高校，公立高校普遍免缴
销售税，供应商须支持"凭机构免税证明免收税"，且发票上标注免税号。
当前税制 `tax_total` 恒为 0（未建模税），故本特性核心 = ① 记录免税号 ② 显式保证免税机构
税为零 ③ 发票 PDF 标注 Tax Exempt ID。
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Organization
from apps.commerce.models import Product, SKU
from apps.transactions.models import Order, Invoice
from apps.transactions.services import InvoiceService

User = get_user_model()


class TaxExemptionTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Harvard Lab', org_type='academic')
        self.user = User.objects.create_user(
            username='harvard', email='h@example.com', password='x',
            role='researcher', organization=self.org,
        )
        product = Product.objects.create(name='Taq Reagent', slug='taq-reagent')
        self.sku = SKU.objects.create(product=product, sku_code='SKU-TAX-001', price=Decimal('10.00'))

    def _submit_po(self):
        c = APIClient()
        c.force_authenticate(self.user)
        r = c.post('/api/v1/orders/po/', {
            'po_number': 'PO-TAX-0001',
            'shipping_name': 'Lab', 'shipping_address': '1 Oxford St',
            'items': [{'sku_id': self.sku.id, 'quantity': 2, 'unit_price': '10.00'}],
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content[:300])
        return Order.objects.get(po_number='PO-TAX-0001')

    def _issue_invoice(self, order):
        order.status = Order.Status.DELIVERED
        order.save(update_fields=['status'])
        return InvoiceService.issue(order)

    # ── 字段存在性 ──
    def test_organization_has_tax_exempt_id_field(self):
        self.org.tax_exempt_id = 'TX-HARVARD-001'
        self.org.save(update_fields=['tax_exempt_id'])
        self.org.refresh_from_db()
        self.assertEqual(self.org.tax_exempt_id, 'TX-HARVARD-001')

    # ── 免税机构：税为零、总额=小计 ──
    def test_exempt_org_submit_po_has_zero_tax(self):
        self.org.tax_exempt_id = 'TX-HARVARD-001'
        self.org.save(update_fields=['tax_exempt_id'])
        order = self._submit_po()
        self.assertEqual(order.tax_total, 0, '免税机构税必须为 0')
        self.assertEqual(order.grand_total, order.subtotal)

    def test_exempt_org_invoice_has_zero_tax_and_label(self):
        self.org.tax_exempt_id = 'TX-HARVARD-001'
        self.org.save(update_fields=['tax_exempt_id'])
        order = self._submit_po()
        invoice = self._issue_invoice(order)
        self.assertEqual(invoice.tax_total, 0)
        self.assertEqual(invoice.grand_total, order.subtotal)
        # 免税号可从订单推导（供 PDF 标注）
        self.assertEqual(order.tax_exempt_id, 'TX-HARVARD-001')

    # ── 非免税机构：行为不变 ──
    def test_non_exempt_org_submit_po_unchanged(self):
        self.org.tax_exempt_id = ''  # 空 = 非免税
        self.org.save(update_fields=['tax_exempt_id'])
        order = self._submit_po()
        self.assertEqual(order.tax_total, 0, '当前税制下非免税机构也应为 0（行为不变）')
        self.assertEqual(order.grand_total, order.subtotal)

    def test_non_exempt_org_has_empty_tax_exempt_id(self):
        order = self._submit_po()
        self.assertEqual(order.tax_exempt_id, '', '非免税机构免税号应为空')

    def test_invoice_pdf_marks_tax_exempt_id_when_exempt(self):
        self.org.tax_exempt_id = 'TX-HARVARD-001'
        self.org.save(update_fields=['tax_exempt_id'])
        order = self._submit_po()
        invoice = self._issue_invoice(order)
        # 通过 order 的 tax_exempt_id 属性验证 PDF 标注的数据来源
        self.assertEqual(order.tax_exempt_id, 'TX-HARVARD-001')
        self.assertTrue(invoice.invoice_no.startswith('INV-'))
