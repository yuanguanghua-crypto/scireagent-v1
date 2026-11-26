"""S5 P-4 的四条后端护栏：A-159 / A-257 / A-262 / A-167。

## 每条钉住什么

**A-159（拒审必须写理由）**
改前 `reason = request.data.get('reason', '')` 直接进状态机 note ⇒ 空原因也能把 PO 单
推进到 CANCELLED（QA Batch 15 实测：原因留空未被拦截、订单移出待审列表）。
拒审是**不可逆跃迁**，理由是采购方唯一能拿到的书面依据。

**A-257（重复核销 409，不是 500）**
改前 `invoice.order.transition_to('paid')` 在订单已 paid 时抛
`InvalidTransitionError`，且**未捕获** ⇒ 500。
触发路径：先 `POST /invoices/{id}/pay/`（该端点自动核销），再调 verify。

**A-262（取消订单要作废未签收的发货记录）**
改前两个取消端点只 `transition_to` + `release_for_order`，完全不碰 ShippingRecord
⇒ QA Batch 21 实测：订单已 Cancelled，Shipment 仍 `shipped`，详情页照旧显示在途。

**A-167（发票列表端点存在）**
改前 `/api/v1/invoices/` 是 Resolver404 ⇒ 运营对账拿不到发票 id，只能进容器跑 ORM。
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Organization
from apps.commerce.models import Product, SKU
from apps.transactions.models import (
    Invoice, Order, PaymentRecord, ShippingRecord, StatusLog,
)

User = get_user_model()


def _org(name='P4Org'):
    return Organization.objects.create(name=name, org_type='academic')


def _user(username, role='procurement', org=None, is_staff=False):
    return User.objects.create_user(
        username=username, email=f'{username}@example.com', password='x',
        role=role, organization=org, is_staff=is_staff,
    )


def _order(user, org, no, status=Order.Status.PO_RECEIVED):
    return Order.objects.create(
        user=user, organization=org, order_no=no, po_number=None, status=status,
    )


class _Base(TestCase):
    def setUp(self):
        self.org = _org()
        self.proc = _user('p4_proc')
        self.proc.organization = self.org
        self.proc.save(update_fields=['organization'])
        self.admin = _user('p4_admin', role='admin', is_staff=True)
        self.customer = _user('p4_cust', role='researcher')
        self.customer.organization = self.org
        self.customer.save(update_fields=['organization'])
        self.client = APIClient()


# ── A-159 拒审必须写理由 ─────────────────────────────────────
class RejectReasonRequiredTest(_Base):
    def setUp(self):
        super().setUp()
        self.order = _order(self.customer, self.org, 'ORD-P4-R1')
        self.client.force_authenticate(self.proc)

    def test_empty_reason_is_400(self):
        r = self.client.post(f'/api/v1/orders/{self.order.id}/reject/', {}, format='json')
        self.assertEqual(r.status_code, 400, r.content[:300])
        self.assertEqual(r.json()['meta']['error']['code'], 'REASON_REQUIRED')

    def test_blank_spaces_reason_is_400(self):
        """纯空格等同空 —— 不能靠打几个空格绕过。"""
        r = self.client.post(f'/api/v1/orders/{self.order.id}/reject/',
                             {'reason': '   '}, format='json')
        self.assertEqual(r.status_code, 400, r.content[:300])

    def test_rejected_order_state_unchanged_and_no_log(self):
        """被拦时：订单状态不变、且**不能留下**状态日志（不能"校验失败但已推进"）。"""
        before = StatusLog.objects.filter(order=self.order).count()
        self.client.post(f'/api/v1/orders/{self.order.id}/reject/', {}, format='json')
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PO_RECEIVED)
        self.assertEqual(StatusLog.objects.filter(order=self.order).count(), before)

    def test_with_reason_succeeds_and_persists_note(self):
        r = self.client.post(f'/api/v1/orders/{self.order.id}/reject/',
                             {'reason': '价格超预算'}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        log = StatusLog.objects.filter(order=self.order).order_by('-id').first()
        self.assertIn('价格超预算', log.note)


# ── A-257 重复核销 409 ──────────────────────────────────────
class VerifyPaymentIdempotentTest(_Base):
    def setUp(self):
        super().setUp()
        self.order = _order(self.customer, self.org, 'ORD-P4-V1', Order.Status.DELIVERED)
        self.invoice = Invoice.objects.create(
            order=self.order, invoice_no='INV-P4-001', status=Invoice.Status.ISSUED,
            due_date=date.today() + timedelta(days=30), grand_total=Decimal('100.00'),
        )
        self.pay = PaymentRecord.objects.create(
            invoice=self.invoice, method=PaymentRecord.Method.values[0],
            amount=Decimal('100.00'), status=PaymentRecord.Status.VERIFIED,
        )
        self.client.force_authenticate(self.admin)

    def _verify(self, action='verify'):
        return self.client.post(
            f'/api/v1/admin/invoices/{self.invoice.id}/verify-payment/',
            {'payment_id': self.pay.id, 'action': action}, format='json')

    def test_already_verified_returns_409_not_500(self):
        """★ 核心：QA 实测的 500 场景必须变成 409。"""
        r = self._verify()
        self.assertEqual(r.status_code, 409, f'应为 409，实得 {r.status_code}: {r.content[:300]}')
        self.assertEqual(r.json()['meta']['error']['code'], 'ALREADY_VERIFIED')

    def test_invoice_already_paid_returns_409(self):
        self.invoice.status = Invoice.Status.PAID
        self.invoice.save(update_fields=['status'])
        self.pay.status = PaymentRecord.Status.PENDING
        self.pay.save(update_fields=['status'])
        r = self._verify()
        self.assertEqual(r.status_code, 409, r.content[:300])
        self.assertEqual(r.json()['meta']['error']['code'], 'INVOICE_ALREADY_PAID')

    def test_409_does_not_mutate_state(self):
        """409 之后发票/付款记录状态都不能被动过。"""
        self._verify()
        self.invoice.refresh_from_db()
        self.pay.refresh_from_db()
        self.assertEqual(self.pay.status, PaymentRecord.Status.VERIFIED)
        self.assertNotEqual(self.invoice.status, Invoice.Status.PAID,
                            '已 verified 的重复核销不应把发票改成 paid')

    def test_first_verify_still_works(self):
        """正常路径不能被这次收紧打坏。"""
        self.pay.status = PaymentRecord.Status.PENDING
        self.pay.save(update_fields=['status'])
        self.order.status = Order.Status.INVOICED
        self.order.save(update_fields=['status'])
        r = self._verify()
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.pay.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(self.pay.status, PaymentRecord.Status.VERIFIED)
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)


# ── A-262 取消订单作废发货记录 ───────────────────────────────
class CancelVoidsShipmentsTest(_Base):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.proc)

    def _ship(self, order, status):
        return ShippingRecord.objects.create(order=order, status=status)

    def test_cancel_voids_unreceived_shipments(self):
        order = _order(self.customer, self.org, 'ORD-P4-C1', Order.Status.SHIPPED)
        prep = self._ship(order, ShippingRecord.Status.PREPARING)
        ship = self._ship(order, ShippingRecord.Status.SHIPPED)
        transit = self._ship(order, ShippingRecord.Status.IN_TRANSIT)

        r = self.client.post(f'/api/v1/orders/{order.id}/cancel/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])

        for s in (prep, ship, transit):
            s.refresh_from_db()
            self.assertEqual(s.status, ShippingRecord.Status.CANCELLED,
                             f'shipment {s.id} 应被作废')

    def test_cancel_keeps_delivered_shipments(self):
        """已签收是物理事实，取消订单不能把它抹成 cancelled（对账时那是签收证据）。"""
        order = _order(self.customer, self.org, 'ORD-P4-C2', Order.Status.SHIPPED)
        done = self._ship(order, ShippingRecord.Status.DELIVERED)

        self.client.post(f'/api/v1/orders/{order.id}/cancel/', {}, format='json')
        done.refresh_from_db()
        self.assertEqual(done.status, ShippingRecord.Status.DELIVERED)

    def test_cancel_does_not_touch_other_orders_shipments(self):
        """只作废本单的 —— 不能误伤别的订单。"""
        mine = _order(self.customer, self.org, 'ORD-P4-C3', Order.Status.SHIPPED)
        other = _order(self.customer, self.org, 'ORD-P4-C4', Order.Status.SHIPPED)
        m = self._ship(mine, ShippingRecord.Status.SHIPPED)
        o = self._ship(other, ShippingRecord.Status.SHIPPED)

        self.client.post(f'/api/v1/orders/{mine.id}/cancel/', {}, format='json')
        m.refresh_from_db()
        o.refresh_from_db()
        self.assertEqual(m.status, ShippingRecord.Status.CANCELLED)
        self.assertEqual(o.status, ShippingRecord.Status.SHIPPED)

    def test_reject_also_voids(self):
        """拒审与取消同一条路径（都进 CANCELLED），不能只修一个。"""
        order = _order(self.customer, self.org, 'ORD-P4-C5', Order.Status.PO_RECEIVED)
        s = self._ship(order, ShippingRecord.Status.PREPARING)
        r = self.client.post(f'/api/v1/orders/{order.id}/reject/',
                             {'reason': '规格不符'}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        s.refresh_from_db()
        self.assertEqual(s.status, ShippingRecord.Status.CANCELLED)


# ── A-167 发票列表端点 ─────────────────────────────────────
class InvoiceListEndpointTest(_Base):
    def setUp(self):
        super().setUp()
        self.o1 = _order(self.customer, self.org, 'ORD-P4-L1', Order.Status.INVOICED)
        self.o2 = _order(self.proc, self.org, 'ORD-P4-L2', Order.Status.INVOICED)
        self.inv1 = Invoice.objects.create(
            order=self.o1, invoice_no='INV-P4-L1', status=Invoice.Status.ISSUED,
            due_date=date.today(), grand_total=Decimal('10.00'))
        self.inv2 = Invoice.objects.create(
            order=self.o2, invoice_no='INV-P4-L2', status=Invoice.Status.PAID,
            due_date=date.today(), grand_total=Decimal('20.00'))

    def test_route_exists(self):
        """★ 改前这里是 Resolver404。"""
        self.client.force_authenticate(self.admin)
        r = self.client.get('/api/v1/invoices/')
        self.assertEqual(r.status_code, 200, r.content[:300])

    def test_internal_sees_all(self):
        self.client.force_authenticate(self.admin)
        rows = self.client.get('/api/v1/invoices/').json()['data']
        self.assertEqual({x['invoice_no'] for x in rows}, {'INV-P4-L1', 'INV-P4-L2'})

    def test_customer_sees_only_own(self):
        """发票含金额与付款记录，跨客户可见就是财务数据事故。"""
        self.client.force_authenticate(self.customer)
        rows = self.client.get('/api/v1/invoices/').json()['data']
        self.assertEqual({x['invoice_no'] for x in rows}, {'INV-P4-L1'})

    def test_filter_by_status(self):
        self.client.force_authenticate(self.admin)
        rows = self.client.get('/api/v1/invoices/', {'status': 'paid'}).json()['data']
        self.assertEqual({x['invoice_no'] for x in rows}, {'INV-P4-L2'})

    def test_invalid_status_returns_400(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get('/api/v1/invoices/', {'status': 'bogus'})
        self.assertEqual(r.status_code, 400, r.content[:300])

    def test_filter_by_order(self):
        self.client.force_authenticate(self.admin)
        rows = self.client.get('/api/v1/invoices/', {'order': self.o1.id}).json()['data']
        self.assertEqual({x['invoice_no'] for x in rows}, {'INV-P4-L1'})

    def test_pagination_meta(self):
        self.client.force_authenticate(self.admin)
        b = self.client.get('/api/v1/invoices/', {'page_size': 1}).json()
        self.assertEqual(len(b['data']), 1)
        self.assertEqual(b['meta']['pagination']['count'], 2)
        self.assertTrue(b['meta']['pagination']['next'])

    def test_anonymous_denied(self):
        r = APIClient().get('/api/v1/invoices/')
        self.assertIn(r.status_code, (401, 403))
