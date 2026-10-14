"""补 `/orders/{id}/confirm-quote/` 报价接受/拒绝端点（legacy 报价流）。

背景：`OrderDetailPage.vue` 调用 `respondToQuote(order.id, 'accept'|'reject')`，但该端点此前在后端缺失
（前端有、后端无，功能一直坏的）。本文件按 TDD 补端点 + 回归。
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Organization
from apps.transactions.models import Order, StatusLog

User = get_user_model()


class ConfirmQuoteTest(TestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(name='OrgA', org_type='academic')
        self.org_b = Organization.objects.create(name='OrgB', org_type='academic')
        self.owner = User.objects.create_user(
            username='owner', email='o@e.com', password='x',
            role='researcher', organization=self.org_a,
        )
        self.outsider = User.objects.create_user(
            username='outsider', email='x@e.com', password='x',
            role='researcher', organization=self.org_b,
        )

    def _order(self, status=Order.Status.QUOTED):
        return Order.objects.create(
            user=self.owner, organization=self.org_a,
            order_no=f'ORD-Q-{status}', po_number=None,
            status=status,
        )

    def _respond(self, user, order, action):
        c = APIClient()
        c.force_authenticate(user)
        return c.post(f'/api/v1/orders/{order.id}/confirm-quote/', {'action': action}, format='json')

    def test_accept_quote_confirms_order(self):
        order = self._order()
        r = self._respond(self.owner, order, 'accept')
        self.assertEqual(r.status_code, 200, r.content[:300])
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CONFIRMED, 'accept 应 quote_accepted → confirmed')
        self.assertTrue(
            StatusLog.objects.filter(order=order, to_status=Order.Status.CONFIRMED).exists(),
            '应写 StatusLog',
        )

    def test_reject_quote_rejects_order(self):
        order = self._order()
        r = self._respond(self.owner, order, 'reject')
        self.assertEqual(r.status_code, 200, r.content[:300])
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.QUOTE_REJECTED)

    def test_invalid_action_returns_400(self):
        order = self._order()
        r = self._respond(self.owner, order, 'maybe')
        self.assertEqual(r.status_code, 400)

    def test_order_not_quoted_returns_400(self):
        order = self._order(status=Order.Status.CONFIRMED)
        r = self._respond(self.owner, order, 'accept')
        self.assertEqual(r.status_code, 400, '非 quoted 状态不得应答')

    def test_unrelated_user_forbidden(self):
        order = self._order()
        r = self._respond(self.outsider, order, 'accept')
        self.assertEqual(r.status_code, 403)
