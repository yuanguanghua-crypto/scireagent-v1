"""A-171：客户可自助取消**自己的**订单（仅生产开始前）。

## 被钉住的四条授权边界

1. **自己的 + confirmed / po_received** → 允许（这是 QA 报缺失的能力）
2. **进入 in_production 之后** → 拒绝（物料与排产已动，需人工核算）
3. **别人的单** → **404**（不是 403：避免用状态码差异探测订单号是否存在）
4. **运营/管理员** → 不受客户那套白名单限制（回归：`CancelOrderView` 原本
   只服务运营端，各阶段可取消，别被这次改动收紧）

## 为什么放在 transactions 而不是新端点
`POST /orders/<id>/cancel/` 已经是"取消订单"的唯一入口，运营端与客户端的
差别只是**授权范围**。新增端点会让说明书里的端点数口径（`audit_manual_numbers.py`
在审）跟着变，而能力本身没有增加 —— 同义动作不该有两个 URL。
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Organization
from apps.transactions.models import Order

User = get_user_model()


def _user(username, *, role='researcher', is_staff=False, org=None):
    u = User.objects.create_user(
        username=username, password='testpass123',
        email=f'{username}@example.com', role=role,
        is_staff=is_staff, email_verified=True,
    )
    if org:
        u.organization = org
        u.save(update_fields=['organization'])
    return u


def _order(user, org, order_no, status):
    return Order.objects.create(
        user=user, organization=org, order_no=order_no, status=status,
        payment_method='purchase_order', po_number=f'PO-{order_no}',
        grand_total=Decimal('999.99'),
    )


class CustomerCancelOrderTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='A171 Org', org_type='academic')
        self.customer = _user('a171_customer', org=self.org)
        self.other = _user('a171_other', org=self.org)
        self.proc = _user('a171_proc', role='procurement', is_staff=True, org=self.org)

    def _cancel(self, order, as_user=None, payload=None):
        if as_user is not None:
            self.client.force_authenticate(as_user)
        return self.client.post(
            f'/api/v1/orders/{order.id}/cancel/', payload or {}, format='json')

    # ── 允许 ──
    def test_customer_cancels_own_confirmed(self):
        o = _order(self.customer, self.org, 'ORD-A171-1', Order.Status.CONFIRMED)
        r = self._cancel(o, self.customer)
        self.assertEqual(r.status_code, 200, r.content[:300])
        o.refresh_from_db()
        self.assertEqual(o.status, Order.Status.CANCELLED)

    def test_customer_cancels_own_po_received(self):
        o = _order(self.customer, self.org, 'ORD-A171-2', Order.Status.PO_RECEIVED)
        r = self._cancel(o, self.customer)
        self.assertEqual(r.status_code, 200, r.content[:300])
        o.refresh_from_db()
        self.assertEqual(o.status, Order.Status.CANCELLED)

    # ── 拒绝（状态）──
    def test_customer_cannot_cancel_after_production(self):
        for i, st in enumerate([Order.Status.IN_PRODUCTION, Order.Status.SHIPPED,
                                Order.Status.DELIVERED, Order.Status.INVOICED]):
            o = _order(self.customer, self.org, f'ORD-A171-S{i}', st)
            r = self._cancel(o, self.customer)
            self.assertEqual(r.status_code, 400, f'{st} 应被拒: {r.content[:200]}')
            o.refresh_from_db()
            self.assertEqual(o.status, st, f'{st} 状态不应被改变')
            body = r.json()
            self.assertEqual(body['meta']['error']['code'], 'CANCEL_NOT_ALLOWED')

    # ── 拒绝（归属）──
    def test_customer_cannot_cancel_someone_elses_order(self):
        o = _order(self.other, self.org, 'ORD-A171-3', Order.Status.CONFIRMED)
        r = self._cancel(o, self.customer)
        # 404 而非 403：不泄露该订单号是否存在
        self.assertEqual(r.status_code, 404)
        o.refresh_from_db()
        self.assertEqual(o.status, Order.Status.CONFIRMED)

    def test_anonymous_cannot_cancel(self):
        o = _order(self.customer, self.org, 'ORD-A171-4', Order.Status.CONFIRMED)
        self.client.force_authenticate(None)
        r = self.client.post(f'/api/v1/orders/{o.id}/cancel/', {}, format='json')
        self.assertIn(r.status_code, (401, 403))
        o.refresh_from_db()
        self.assertEqual(o.status, Order.Status.CONFIRMED)

    # ── 运营侧不被收紧（回归）──
    def test_staff_still_cancels_shipped(self):
        o = _order(self.customer, self.org, 'ORD-A171-5', Order.Status.SHIPPED)
        r = self._cancel(o, self.proc)
        self.assertEqual(r.status_code, 200, r.content[:300])
        o.refresh_from_db()
        self.assertEqual(o.status, Order.Status.CANCELLED)

    def test_staff_cancels_other_peoples_order(self):
        """运营本来就能取消任何人的单 —— 归属检查只针对客户自助。"""
        o = _order(self.customer, self.org, 'ORD-A171-6', Order.Status.CONFIRMED)
        r = self._cancel(o, self.proc)
        self.assertEqual(r.status_code, 200, r.content[:300])
