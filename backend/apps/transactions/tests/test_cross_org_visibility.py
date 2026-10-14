"""跨机构可见性 —— procurement/admin 应能列出所有订单（审核台），客户只能看自己的。

背景：`OrderViewSet.get_queryset` 现为 `is_staff → all; else filter(user=user)`，
导致 procurement（非 staff）在审核台看到空列表（他们自己不下单）。本文件钉住修复。
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Organization
from apps.transactions.models import Order

User = get_user_model()


def _org(name):
    return Organization.objects.create(name=name, org_type='academic')


def _user(username, role, org):
    return User.objects.create_user(
        username=username, email=f'{username}@example.com', password='x',
        role=role, organization=org,
    )


class CrossOrgVisibilityTest(TestCase):
    def setUp(self):
        self.org_a = _org('OrgA')
        self.org_b = _org('OrgB')
        self.researcher_a = _user('ra', 'researcher', self.org_a)
        self.researcher_b = _user('rb', 'researcher', self.org_b)
        self.proc = _user('proc', 'procurement', self.org_a)  # 非 staff
        self.order_a = Order.objects.create(
            user=self.researcher_a, organization=self.org_a,
            order_no='ORD-VIS-A', po_number=None, status=Order.Status.PO_RECEIVED,
        )
        self.order_b = Order.objects.create(
            user=self.researcher_b, organization=self.org_b,
            order_no='ORD-VIS-B', po_number=None, status=Order.Status.PO_RECEIVED,
        )

    def _list_ids(self, user):
        c = APIClient()
        c.force_authenticate(user)
        r = c.get('/api/v1/orders/')
        self.assertEqual(r.status_code, 200, r.content[:300])
        data = r.json()['data']
        results = data.get('results') if isinstance(data, dict) else data
        return {o['id'] for o in (results or [])}

    def test_procurement_sees_all_orders(self):
        """采购员（非 staff）应跨机构看到所有订单（审核台）。"""
        ids = self._list_ids(self.proc)
        self.assertEqual(ids, {self.order_a.id, self.order_b.id}, '采购员应看到所有机构的订单')

    def test_researcher_sees_only_own(self):
        """客户仍只能看自己的订单（不被误伤）。"""
        ids = self._list_ids(self.researcher_a)
        self.assertEqual(ids, {self.order_a.id}, '客户只能看自己的订单')
