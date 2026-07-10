"""
PO 门户 gap 端点自测（补齐 3 个 P0 未实现端点）。

覆盖：
① Address list/create 经认证可用且按机构过滤；写需 procurement/admin。
② 发票 PDF 下载端点对存在的 Invoice 返回 200 + application/pdf。
③ PO 附件下载端点返回 200（及文件缺失返回 404 信封）。
"""
import os
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.models import Organization, Address
from apps.transactions.models import (
    Order, OrderItem, Invoice, PoAttachment,
)
from apps.transactions.services import InvoiceService
from apps.commerce.models import Product, SKU

User = get_user_model()


def _make_org(name='Org'):
    return Organization.objects.create(name=name, org_type='academic')


def _make_user(username, role='researcher', org=None, is_staff=False):
    return User.objects.create_user(
        username=username, email=f'{username}@example.com', password='x',
        role=role, organization=org, is_staff=is_staff,
    )


def _make_sku():
    product = Product.objects.create(name='Test Reagent', slug='test-reagent')
    return SKU.objects.create(product=product, sku_code='SKU-TEST-001', price=10)


class AddressGapTest(TestCase):
    def setUp(self):
        self.org_a = _make_org('OrgA')
        self.org_b = _make_org('OrgB')
        self.researcher = _make_user('addr_researcher', 'researcher', self.org_a)
        self.proc = _make_user('addr_proc', 'procurement', self.org_a)
        self.client = APIClient()

    def test_list_filtered_by_org(self):
        Address.objects.create(organization=self.org_a, type='shipping', line1='A1')
        Address.objects.create(organization=self.org_b, type='shipping', line1='B1')
        self.client.force_authenticate(self.researcher)
        r = self.client.get('/api/v1/addresses/')
        self.assertEqual(r.status_code, 200)
        data = r.json()['data']
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['line1'], 'A1')
        # 信封结构
        self.assertTrue(r.json()['success'])

    def test_create_requires_procurement(self):
        # 普通研究员（读可，写不可）
        self.client.force_authenticate(self.researcher)
        r = self.client.post(
            '/api/v1/addresses/', {'type': 'shipping', 'line1': 'X'}, format='json'
        )
        self.assertEqual(r.status_code, 403)
        # 采购可创建；organization 由后端按 user.organization 推入
        self.client.force_authenticate(self.proc)
        r = self.client.post('/api/v1/addresses/', {
            'type': 'billing', 'line1': 'Line1', 'city': 'C', 'country': 'US',
        }, format='json')
        self.assertEqual(r.status_code, 201)
        obj = Address.objects.get(line1='Line1')
        self.assertEqual(obj.organization_id, self.org_a.id)
        self.assertEqual(r.json()['data']['organization_id'], self.org_a.id)

    def test_update_and_destroy(self):
        self.client.force_authenticate(self.proc)
        r = self.client.post(
            '/api/v1/addresses/', {'type': 'shipping', 'line1': 'L'}, format='json'
        )
        aid = r.json()['data']['id']
        # PUT 全量更新
        r = self.client.put(
            f'/api/v1/addresses/{aid}/',
            {'type': 'shipping', 'line1': 'L2', 'country': 'US'},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Address.objects.get(id=aid).line1, 'L2')
        # DELETE
        r = self.client.delete(f'/api/v1/addresses/{aid}/')
        self.assertIn(r.status_code, (200, 204))
        self.assertFalse(Address.objects.filter(id=aid).exists())


class InvoicePdfDownloadGapTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.org = _make_org('OrgInv')
        self.user = _make_user('inv_user', 'researcher', self.org)
        self.proc = _make_user('inv_proc', 'procurement', self.org)
        self.sku = _make_sku()
        self.order = Order.objects.create(
            user=self.user, organization=self.org,
            order_no='ORD-INVDL', status=Order.Status.DELIVERED,
        )
        OrderItem.objects.create(order=self.order, sku=self.sku, quantity=1, unit_price=5)
        self.order.subtotal = 5
        self.order.grand_total = 5
        self.order.save(update_fields=['subtotal', 'grand_total'])
        self.client = APIClient()

    def test_download_returns_pdf(self):
        with override_settings(MEDIA_ROOT=self.tmp):
            invoice = InvoiceService.issue(self.order, actor=self.proc)
            self.client.force_authenticate(self.user)
            r = self.client.get(f'/api/v1/invoices/{invoice.id}/pdf/')
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r['Content-Type'], 'application/pdf')
            body = b''.join(r.streaming_content)
            self.assertTrue(body.startswith(b'%PDF'))

    def test_missing_pdf_returns_404_envelope(self):
        # 未生成 PDF 文件的发票 → 404 信封
        with override_settings(MEDIA_ROOT=self.tmp):
            invoice = Invoice.objects.create(
                order=self.order, invoice_no='INV-MISSING-0001',
                status=Invoice.Status.ISSUED, due_date='2099-01-01',
            )
            self.client.force_authenticate(self.user)
            r = self.client.get(f'/api/v1/invoices/{invoice.id}/pdf/')
            self.assertEqual(r.status_code, 404)
            self.assertFalse(r.json()['success'])


class PoAttachmentDownloadGapTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.org = _make_org('OrgAtt')
        self.user = _make_user('att_user', 'researcher', self.org)
        self.proc = _make_user('att_proc', 'procurement', self.org)
        self.order = Order.objects.create(
            user=self.user, organization=self.org,
            order_no='ORD-ATTDL', status=Order.Status.PO_RECEIVED,
        )
        self.client = APIClient()

    def test_download_returns_200(self):
        with override_settings(MEDIA_ROOT=self.tmp):
            att = PoAttachment.objects.create(
                order=self.order,
                file=SimpleUploadedFile('po.txt', b'hello-attachment', content_type='text/plain'),
                original_filename='po.txt', mime_type='text/plain',
                file_size=len(b'hello-attachment'), uploaded_by=self.user,
            )
            self.client.force_authenticate(self.user)
            r = self.client.get(f'/api/v1/orders/attachments/{att.id}/download/')
            self.assertEqual(r.status_code, 200)
            self.assertEqual(b''.join(r.streaming_content), b'hello-attachment')

    def test_missing_attachment_returns_404_envelope(self):
        self.client.force_authenticate(self.proc)
        # 不存在的附件 pk → 404 信封
        r = self.client.get('/api/v1/orders/attachments/999999/download/')
        self.assertEqual(r.status_code, 404)
        self.assertFalse(r.json()['success'])
