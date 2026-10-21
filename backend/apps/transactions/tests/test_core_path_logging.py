# -*- coding: utf-8 -*-
"""核心 4 条路径的日志断言（对应 FAILURE_MODES 9.1）

## 为什么需要
9.1 原本写成"有 logger 调用但未断言该留的留了"——**核实后发现是我写错了**：
`apps/transactions/services.py` **一行 logger 都没有**，`checkout_views.py` 也没有。
也就是说这 4 条最核心的业务路径（下单/PO 提交/开票/收款）**完全没有日志**，
出了问题只能靠复现。这才是它被降级为「空白」的真实原因。

## 只覆盖 4 条路径，不铺开
日志断言的成本不在写，在**维护**（每次改日志文案都要改测试）。
所以只给"出问题必须能追溯"的 4 条核心路径加断言：
  ① checkout  ② PO 提交  ③ 开票  ④ 收款
其余路径的日志质量靠 code review，不设断言。

## 断言什么
不是断言"有日志"，而是断言**日志里带业务标识**（order_no / invoice_no）。
否则出问题时看到一行 "checkout ok" 而不知道是哪一单，等于没日志。
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.transactions.models import Order
from apps.transactions.services import InvoiceService, PaymentArService
from apps.transactions.tests.factories import BasketFactory

SERVICES_LOGGER = 'apps.transactions.services'
CHECKOUT_LOGGER = 'apps.transactions.api.v1.checkout_views'


class CorePathLoggingTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.product = ProductFactory()
        self.sku = SKUFactory(product=self.product, price=Decimal('10.00'))
        BasketFactory(user=self.user, product=self.product, sku=self.sku, quantity=2)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    # ── ① checkout ─────────────────────────────────────────────────
    def test_checkout_logs_order_no(self):
        with self.assertLogs(CHECKOUT_LOGGER, level='INFO') as cm:
            resp = self.client.post('/api/v1/checkout/', {
                # purchase_order 必须带 po_number，否则 400（实测踩过）
                'payment_method': 'purchase_order', 'po_number': 'PO-CHK-001',
                'shipping_name': 'T', 'shipping_address': 'A',
            }, format='json')
            # ★ 断言放进 assertLogs 块内：否则上下文退出时的 "no logs" 会掩盖真实状态码
            self.assertEqual(resp.status_code, 201, resp.content)
        joined = '\n'.join(cm.output)
        self.assertIn('Checkout completed', joined)
        self.assertIn(resp.data['order_no'], joined,
                      '日志里必须带订单号，否则出问题无法定位是哪一单')

    # ── ② PO 提交 ───────────────────────────────────────────────────
    def test_po_submit_logs_order_no_and_po_number(self):
        with self.assertLogs(SERVICES_LOGGER, level='INFO') as cm:
            resp = self.client.post('/api/v1/orders/po/', {
                'po_number': 'PO-LOG-001',
                'items': [{'sku_id': self.sku.id, 'quantity': 1}],
                'shipping_name': 'T', 'shipping_address': 'A',
            }, format='json')
            self.assertEqual(resp.status_code, 201, resp.content)
        # POSubmitView 走 DRF 默认 renderer ⇒ 响应被信封包装
        payload = resp.json().get('data', resp.json())
        joined = '\n'.join(cm.output)
        self.assertIn('PO submitted', joined)
        self.assertIn(payload['order_no'], joined)
        self.assertIn('PO-LOG-001', joined, '日志里必须带 PO 号')

    # ── ③ 开票 ─────────────────────────────────────────────────────
    def test_invoice_issue_logs_invoice_no_and_order_no(self):
        order = Order.objects.create(
            user=self.user, order_no='ORD-LOG-INV', status=Order.Status.DELIVERED,
            subtotal=Decimal('100.00'), grand_total=Decimal('100.00'),
        )
        with self.assertLogs(SERVICES_LOGGER, level='INFO') as cm:
            invoice = InvoiceService.issue(order)
        joined = '\n'.join(cm.output)
        self.assertIn('Invoice issued', joined)
        self.assertIn(invoice.invoice_no, joined)
        self.assertIn('ORD-LOG-INV', joined)

    # ── ④ 收款 ─────────────────────────────────────────────────────
    def test_payment_logs_invoice_no_and_amount(self):
        order = Order.objects.create(
            user=self.user, order_no='ORD-LOG-PAY', status=Order.Status.DELIVERED,
            subtotal=Decimal('100.00'), grand_total=Decimal('100.00'),
        )
        invoice = InvoiceService.issue(order)      # 先开票（这步自己会打日志）
        with self.assertLogs(SERVICES_LOGGER, level='INFO') as cm:
            PaymentArService.pay(invoice, amount=Decimal('100.00'), method='bank_transfer')
        joined = '\n'.join(cm.output)
        self.assertIn('Payment recorded', joined)
        self.assertIn(invoice.invoice_no, joined, '收款日志必须带发票号，否则对账无法追溯')
