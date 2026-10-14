"""D2 部分付款（P1-6）—— balance_due 派生属性 + 部分核销 + 短付原因。

背景（ARCH §8.2 #3 已拍板）：部分付款核销是 AR 标准实务。`PaymentRecord` 已支持多笔，
本特性核心 = `Invoice.balance_due` 派生属性（grand_total - 已核销额，下限 0）。
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Organization
from apps.transactions.models import Order, Invoice, PaymentRecord
from apps.transactions.services import PaymentArService

User = get_user_model()


class PartialPaymentTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Lab', org_type='academic')
        self.user = User.objects.create_user(
            username='finance', email='f@example.com', password='x',
            role='procurement', organization=self.org,
        )
        self.order = Order.objects.create(
            user=self.user, organization=self.org,
            order_no='ORD-PP-0001', status=Order.Status.INVOICED,
            subtotal=Decimal('200.00'), grand_total=Decimal('200.00'),
        )
        self.invoice = Invoice.objects.create(
            order=self.order, invoice_no='INV-PP-0001', status=Invoice.Status.ISSUED,
            issued_at=None, due_date='2099-01-01',
            subtotal=Decimal('200.00'), grand_total=Decimal('200.00'),
        )

    def _pay(self, amount, notes='', reference=''):
        return PaymentArService.pay(
            self.invoice, amount=Decimal(amount), method='wire',
            actor=self.user, notes=notes, reference=reference,
        )

    # ── ① 部分付款后 balance_due 正确递减 ──
    def test_balance_due_decreases_after_partial_payment(self):
        self._pay('80.00')
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.amount_paid, Decimal('80.00'))
        self.assertEqual(self.invoice.balance_due, Decimal('120.00'))
        self.assertEqual(self.invoice.status, Invoice.Status.ISSUED, '部分付款不应转 PAID')

    # ── ② 多笔部分付款累计，全额转 PAID ──
    def test_multiple_partial_payments_accumulate_then_paid(self):
        self._pay('80.00')
        self._pay('120.00')
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.amount_paid, Decimal('200.00'))
        self.assertEqual(self.invoice.balance_due, Decimal('0.00'))
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)

    # ── ② 一次性全额 → PAID ──
    def test_full_payment_marks_paid(self):
        self._pay('200.00')
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        self.assertEqual(self.invoice.balance_due, Decimal('0.00'))
        self.assertIsNotNone(self.invoice.paid_at)

    # ── ③ 短付原因可记录（notes 落到 PaymentRecord）──
    def test_short_pay_notes_recorded(self):
        self._pay('80.00', notes='客户短付，余额下月结清')
        pr = PaymentRecord.objects.filter(invoice=self.invoice).latest('id')
        self.assertEqual(pr.notes, '客户短付，余额下月结清')

    # ── 超额付款钳制到 0（不出现负余额）──
    def test_overpayment_clamps_balance_due_to_zero(self):
        self._pay('250.00')
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.balance_due, Decimal('0.00'), '余额不得为负')
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)

    # ── 无付款时 balance_due = grand_total ──
    def test_no_payment_balance_equals_grand_total(self):
        self.assertEqual(self.invoice.amount_paid, Decimal('0.00'))
        self.assertEqual(self.invoice.balance_due, Decimal('200.00'))
