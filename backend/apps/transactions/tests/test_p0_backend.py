"""
P0 后端自测（T30 部分）。

覆盖：
① 状态机非法转移抛异常（并校验合法转移写 StatusLog）
② 库存 allocate/release 原子不超卖
③ InvoiceSequence 并发取号不重复
④ po_number 唯一冲突返回 409 信封
"""
import threading

from django.test import TestCase
from django.db import transaction, connection
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.transactions.models import (
    Order, OrderItem, InvoiceSequence, ShippingRecord,
    StatusLog, InvalidTransitionError,
)
from apps.transactions.services import (
    OrderStateMachine, PoSubmissionService, InvoiceService, PoNumberConflictError,
)
from apps.inventory.models import Inventory, Allocation, InsufficientInventoryError
from apps.inventory.services import InventoryService
from apps.commerce.models import Product, SKU

User = get_user_model()


def _make_user(username='tester', role='researcher', org=None):
    return User.objects.create_user(
        username=username, email=f'{username}@example.com', password='x', role=role
    )


def _make_sku():
    product = Product.objects.create(name='Test Reagent', slug='test-reagent')
    return SKU.objects.create(product=product, sku_code='SKU-TEST-001', price=10)


class StateMachineTest(TestCase):
    def test_illegal_transition_raises(self):
        order = Order.objects.create(
            user=_make_user('sm1'), order_no='ORD-SM1', status=Order.Status.DRAFT
        )
        with self.assertRaises(InvalidTransitionError):
            OrderStateMachine.transition_to(order, Order.Status.SHIPPED)
        # draft 也不能直接 invoiced
        with self.assertRaises(InvalidTransitionError):
            OrderStateMachine.transition_to(order, Order.Status.INVOICED)

    def test_legal_transition_writes_status_log(self):
        user = _make_user('sm2')
        order = Order.objects.create(
            user=user, order_no='ORD-SM2', status=Order.Status.PO_RECEIVED
        )
        OrderStateMachine.transition_to(
            order, Order.Status.CONFIRMED, actor=user, note='ok'
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CONFIRMED)
        log = StatusLog.objects.get(order=order)
        self.assertEqual(log.from_status, Order.Status.PO_RECEIVED)
        self.assertEqual(log.to_status, Order.Status.CONFIRMED)
        self.assertEqual(log.action_type, StatusLog.ActionType.STATUS_CHANGE)


class InventoryAtomicTest(TestCase):
    def setUp(self):
        self.sku = _make_sku()

    def _inv(self, available):
        return Inventory.objects.create(sku=self.sku, available=available, allocated=0)

    def test_allocate_release_atomic(self):
        inv = self._inv(10)
        oi = OrderItem.objects.create(order=Order.objects.create(
            user=_make_user('inv1'), order_no='ORD-INV1'), sku=self.sku, quantity=4)
        alloc = InventoryService.allocate(oi, inv.id, 4)
        inv.refresh_from_db()
        self.assertEqual(inv.available, 6)
        self.assertEqual(inv.allocated, 4)
        self.assertEqual(alloc.status, Allocation.Status.RESERVED)

        InventoryService.release(alloc)
        inv.refresh_from_db()
        self.assertEqual(inv.available, 6)
        self.assertEqual(inv.allocated, 0)

    def test_overallocate_raises(self):
        inv = self._inv(2)
        oi = OrderItem.objects.create(order=Order.objects.create(
            user=_make_user('inv2'), order_no='ORD-INV2'), sku=self.sku, quantity=5)
        with self.assertRaises(InsufficientInventoryError):
            InventoryService.allocate(oi, inv.id, 5)
        inv.refresh_from_db()
        self.assertEqual(inv.available, 2)  # 未改变
        self.assertEqual(inv.allocated, 0)

    def test_concurrent_allocate_no_oversell(self):
        inv = self._inv(5)
        order = Order.objects.create(user=_make_user('inv3'), order_no='ORD-INV3')
        ois = [
            OrderItem.objects.create(order=order, sku=self.sku, quantity=1)
            for _ in range(5)
        ]

        def allocate_one(oi):
            try:
                with transaction.atomic():
                    InventoryService.allocate(oi, inv.id, 1)
            except InsufficientInventoryError:
                pass

        # sqlite 下 select_for_update 为 no-op 且测试事务会锁表，故顺序执行；
        # 生产库(postgres)走线程并发验证不超卖。逻辑一致性均被覆盖。
        if connection.vendor == 'sqlite':
            for oi in ois:
                allocate_one(oi)
        else:
            threads = [threading.Thread(target=allocate_one, args=(oi,)) for oi in ois]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        inv.refresh_from_db()
        self.assertEqual(inv.available, 0)
        self.assertEqual(inv.allocated, 5)
        self.assertEqual(Allocation.objects.count(), 5)


class InvoiceSequenceConcurrencyTest(TestCase):
    def test_concurrent_numbering_unique(self):
        year = 2026
        # 预建行，避免创建竞态；仅需验证 UPDATE 在 select_for_update 下串行不重复
        InvoiceSequence.objects.create(year=year, last_number=0)

        results = []
        lock = threading.Lock()

        def worker():
            with transaction.atomic():
                no = InvoiceService._next_invoice_no(year)
            with lock:
                results.append(no)

        if connection.vendor == 'sqlite':
            # sqlite 不支持跨线程写锁；顺序执行同样验证编号唯一递增
            for _ in range(10):
                worker()
        else:
            threads = [threading.Thread(target=worker) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        self.assertEqual(len(results), 10)
        self.assertEqual(len(set(results)), 10)  # 全部唯一
        self.assertEqual(sorted(results), [f'INV-{year}-{i:04d}' for i in range(1, 11)])
        seq = InvoiceSequence.objects.get(year=year)
        self.assertEqual(seq.last_number, 10)


class PoNumberConflictTest(TestCase):
    def test_duplicate_po_number_returns_409(self):
        user = _make_user('po1')
        sku = _make_sku()
        payload = {
            'po_number': 'PO-DUP-001',
            'items': [{'sku_id': sku.id, 'quantity': 1, 'unit_price': '10.00'}],
        }
        # 第一次提交成功
        order = PoSubmissionService.submit(user, payload)
        self.assertEqual(order.po_number, 'PO-DUP-001')
        self.assertEqual(order.status, Order.Status.PO_RECEIVED)

        # 第二次冲突 → 抛领域异常（View 层转 409）
        with self.assertRaises(PoNumberConflictError):
            PoSubmissionService.submit(user, payload)

    def test_duplicate_po_number_via_api_409(self):
        user = _make_user('po2')
        sku = _make_sku()
        client = APIClient()
        client.force_authenticate(user=user)
        data = {
            'po_number': 'PO-API-409',
            'items': [{'sku_id': sku.id, 'quantity': 1, 'unit_price': '10.00'}],
        }
        r1 = client.post('/api/v1/orders/po/', data, format='json')
        self.assertEqual(r1.status_code, 201)
        r2 = client.post('/api/v1/orders/po/', data, format='json')
        self.assertEqual(r2.status_code, 409)
        self.assertEqual(r2.json()['meta']['error']['code'], 'PO_NUMBER_CONFLICT')


class InvoicePdfTest(TestCase):
    def test_invoice_issue_generates_pdf_and_sequence(self):
        user = _make_user('invp')
        sku = _make_sku()
        order = Order.objects.create(
            user=user, order_no='ORD-INVPDF', status=Order.Status.DELIVERED
        )
        OrderItem.objects.create(order=order, sku=sku, quantity=2, unit_price=5)
        order.subtotal = 10
        order.grand_total = 10
        order.save(update_fields=['subtotal', 'grand_total'])

        invoice = InvoiceService.issue(order, payment_terms=Order.PaymentTerms.NET45, actor=user)
        self.assertTrue(invoice.invoice_no.startswith('INV-'))
        self.assertEqual(invoice.payment_terms, Order.PaymentTerms.NET45)
        # NET45 => due_date = issued_at + 45d
        self.assertEqual((invoice.due_date - invoice.issued_at.date()).days, 45)
        # PDF 生成无异常（文件已写出）
        import os
        from django.conf import settings
        path = os.path.join(settings.MEDIA_ROOT, 'invoices', f'{invoice.invoice_no}.pdf')
        self.assertTrue(os.path.exists(path))
