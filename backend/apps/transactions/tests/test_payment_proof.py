# -*- coding: utf-8 -*-
"""客户上传电汇付款凭证（`POST /invoices/<id>/payment-proof/`）—— 2026-10-29。

这条链路的关键不是"能传文件"，而是三个约束不能被绕过：
  · 客户只能建 PENDING（钱到没到账只有财务知道，客户说"我汇了"不算）；
  · 只能传自己的发票（且不泄露别人的发票是否存在）；
  · 同一张发票同时只能有一条待核验（否则运营分不清哪条是最终版）。
另外还有一条安全要求：**付款凭证 URL 只有内部人员能拿到**。
"""
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Organization, User
from apps.commerce.models import Product, SKU
from apps.transactions.models import Invoice, Order, PaymentRecord


def _pdf(name='proof.pdf', size=1024):
    return SimpleUploadedFile(name, b'%PDF-1.4' + b'0' * size, content_type='application/pdf')


class ProofBase(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Lab', org_type='academic')
        self.customer = User.objects.create_user(
            username='pf_cust', password='x', email='c@lab.edu',
            organization=self.org, role='researcher')
        self.other = User.objects.create_user(
            username='pf_other', password='x', email='o@lab.edu',
            organization=self.org, role='researcher')
        self.proc = User.objects.create_user(
            username='pf_proc', password='x', email='p@lab.edu',
            organization=self.org, role='procurement', is_staff=True)
        self.product = Product.objects.create(name='Pseudo-UTP', slug='pseudo-utp-pf')
        self.sku = SKU.objects.create(
            product=self.product, sku_code='SC9900-1', price=Decimal('100.00'))
        self.order = Order.objects.create(
            user=self.customer, order_no='ORD-PF-1',
            status=Order.Status.INVOICED, grand_total=Decimal('500.00'),
            currency='USD')
        self.invoice = Invoice.objects.create(
            order=self.order, invoice_no='INV-PF-1',
            status=Invoice.Status.ISSUED,
            due_date=timezone.now().date(),
            grand_total=Decimal('500.00'), subtotal=Decimal('500.00'),
            currency='USD')
        self.url = f'/api/v1/invoices/{self.invoice.pk}/payment-proof/'
        self.client = APIClient()

    def _post(self, user=None, amount='500.00', file_=None, reference='BANK-1'):
        self.client.force_authenticate(user=user or self.customer)
        data = {'amount': amount, 'reference': reference}
        if file_ is not False:
            data['proof_file'] = file_ or _pdf()
        return self.client.post(self.url, data, format='multipart')


class UploadProofTest(ProofBase):
    def test_customer_upload_creates_pending(self):
        r = self._post()
        self.assertEqual(r.status_code, 200, r.content[:400])
        p = PaymentRecord.objects.get()
        self.assertEqual(p.status, PaymentRecord.Status.PENDING,
                         '客户上传只能是待核验，绝不能直接 verified')
        self.assertEqual(p.invoice_id, self.invoice.pk)
        self.assertEqual(p.amount, Decimal('500.00'))
        self.assertEqual(p.reference, 'BANK-1')
        self.assertTrue(p.proof_file)
        self.assertIsNone(p.verified_by)

    def test_partial_payment_allowed(self):
        r = self._post(amount='200.00')
        self.assertEqual(r.status_code, 200, r.content[:400])
        self.assertEqual(PaymentRecord.objects.get().amount, Decimal('200.00'))

    def test_amount_over_balance_rejected(self):
        r = self._post(amount='500.01')
        self.assertEqual(r.status_code, 400, r.content[:400])
        self.assertEqual(r.json()['meta']['error']['code'], 'AMOUNT_EXCEEDS_BALANCE')
        self.assertEqual(PaymentRecord.objects.count(), 0)

    def test_zero_amount_rejected(self):
        r = self._post(amount='0')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['meta']['error']['code'], 'VALIDATION_ERROR')

    def test_missing_file_rejected(self):
        r = self._post(file_=False)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['meta']['error']['code'], 'VALIDATION_ERROR')

    def test_bad_file_type_rejected(self):
        bad = SimpleUploadedFile('proof.exe', b'MZ', content_type='application/octet-stream')
        r = self._post(file_=bad)
        self.assertEqual(r.status_code, 400, r.content[:400])
        self.assertEqual(r.json()['meta']['error']['code'], 'BAD_FILE_TYPE')
        self.assertEqual(PaymentRecord.objects.count(), 0)

    def test_cannot_upload_for_someone_elses_invoice(self):
        r = self._post(user=self.other)
        self.assertEqual(r.status_code, 404,
                         '别人的发票必须是 404（404 不泄露"这个 id 存在"）')
        self.assertEqual(PaymentRecord.objects.count(), 0)

    def test_rejects_when_invoice_not_payable(self):
        self.invoice.status = Invoice.Status.DRAFT
        self.invoice.save(update_fields=['status'])
        r = self._post()
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['meta']['error']['code'], 'INVOICE_NOT_PAYABLE')

    def test_second_pending_is_rejected(self):
        self.assertEqual(self._post().status_code, 200)
        r = self._post()
        self.assertEqual(r.status_code, 409, r.content[:400])
        self.assertEqual(r.json()['meta']['error']['code'], 'PROOF_PENDING_EXISTS')
        self.assertEqual(PaymentRecord.objects.count(), 1)

    def test_can_resubmit_after_rejected(self):
        """运营拒掉之后客户可以重新上传 —— 否则一次传错就再也补不了。"""
        self.assertEqual(self._post().status_code, 200)
        PaymentRecord.objects.update(status=PaymentRecord.Status.REJECTED)
        r = self._post()
        self.assertEqual(r.status_code, 200, r.content[:400])
        self.assertEqual(PaymentRecord.objects.count(), 2)

    def test_anonymous_rejected(self):
        r = APIClient().post(self.url, {'amount': '1.00'}, format='multipart')
        self.assertIn(r.status_code, (401, 403))


class ProofVisibilityTest(ProofBase):
    """付款凭证含银行账号/户名，URL 不能给外部用户。"""

    def setUp(self):
        super().setUp()
        self.assertEqual(self._post().status_code, 200)
        self.payment = PaymentRecord.objects.get()

    def _order_detail(self, user):
        self.client.force_authenticate(user=user)
        r = self.client.get(f'/api/v1/orders/{self.order.pk}/')
        self.assertEqual(r.status_code, 200, r.content[:400])
        inv = r.json()['data']['invoice']
        return inv['payments'][0]

    def test_customer_gets_no_url_but_sees_flag(self):
        row = self._order_detail(self.customer)
        self.assertIsNone(row['proof_file'], '客户不该拿到凭证 URL')
        self.assertTrue(row['has_proof'], '但要能看到"已上传"')
        self.assertEqual(row['status'], 'pending')

    def test_internal_staff_gets_url(self):
        row = self._order_detail(self.proc)
        self.assertIsNotNone(row['proof_file'], '内部人员必须能下载凭证')
        self.assertIn('payment_proofs', row['proof_file'])
