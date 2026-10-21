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


class OrderOrganizationFilterTest(TestCase):
    """D1 回归：`/api/v1/orders/?organization_id=<id>` 必须真的按机构过滤。

    缺陷现场（2026-10-21 全站测试发现，P0）：
      `/ops/po/organizations` 的「订单查看」传给后端 `organization_id`（`api/adminPo.js:94`），
      而 `OrderViewSet.filterset_fields` 只有 `['status']` ⇒ **该参数被静默丢弃**，
      右侧表格显示的是**全库订单**（实测 937/983 单，与所选机构无关）⇒ 跨机构订单可见。
    """

    def setUp(self):
        self.org_a = _org('FilterOrgA')
        self.org_b = _org('FilterOrgB')
        self.staff = _user('f_staff', 'admin', self.org_a)
        self.staff.is_staff = True
        self.staff.save(update_fields=['is_staff'])
        self.researcher_a = _user('f_ra', 'researcher', self.org_a)
        self.researcher_b = _user('f_rb', 'researcher', self.org_b)
        self.order_a = Order.objects.create(
            user=self.researcher_a, organization=self.org_a,
            order_no='ORD-FLT-A', po_number=None, status=Order.Status.PO_RECEIVED,
        )
        self.order_b = Order.objects.create(
            user=self.researcher_b, organization=self.org_b,
            order_no='ORD-FLT-B', po_number=None, status=Order.Status.PO_RECEIVED,
        )

    def _ids(self, user, params=None):
        c = APIClient()
        c.force_authenticate(user)
        r = c.get('/api/v1/orders/', params or {})
        self.assertEqual(r.status_code, 200, r.content[:300])
        data = r.json()['data']
        results = data.get('results') if isinstance(data, dict) else data
        return {o['id'] for o in (results or [])}

    def test_no_filter_returns_all_for_staff(self):
        """无过滤时 staff 仍能看到全部（对照组，防修成"只看自己机构"）。"""
        self.assertEqual(self._ids(self.staff), {self.order_a.id, self.order_b.id})

    def test_filter_by_organization_id_narrows(self):
        """按 organization_id 过滤 ⇒ 只剩该机构的订单。"""
        self.assertEqual(
            self._ids(self.staff, {'organization_id': self.org_a.id}),
            {self.order_a.id},
            'organization_id 过滤失效：参数被静默丢弃，返回了全库订单',
        )
        self.assertEqual(
            self._ids(self.staff, {'organization_id': self.org_b.id}),
            {self.order_b.id},
        )

    def test_filter_by_organization_alias_also_works(self):
        """`organization=` 这个规范名也应生效（后端同时接受两种写法）。"""
        self.assertEqual(
            self._ids(self.staff, {'organization': self.org_b.id}),
            {self.order_b.id},
        )

    def test_unknown_org_filter_is_rejected_not_ignored(self):
        """过滤一个不存在的机构 ⇒ **400 校验错误**，而不是"静默忽略、回落全库"。

        ★ 这是实测行为，不是我的偏好：FK 过滤被 django-filter 生成为 `ModelChoiceFilter`，
        非法 pk 会被 DRF 挡在 400。**关键是它绝不能变成"把参数当没传、返回全库"**——
        那正是本缺陷最危险的形态（运营以为筛了，其实看的是全部）。
        """
        c = APIClient()
        c.force_authenticate(self.staff)
        r = c.get('/api/v1/orders/', {'organization_id': 99999999})
        self.assertEqual(r.status_code, 400, '非法机构 id 必须被拒绝，不能静默回落全库')
        self.assertIn('organization_id', str(r.json().get('meta', {})))

    def test_customer_cannot_widen_scope_via_org_param(self):
        """★ 安全反向断言：客户传别的机构 id 也不能越权看到别人的订单。

        `get_queryset` 先按 user 收窄，过滤只在其上再收窄 ⇒ 加这个参数**不会**造成提权。
        这条断言就是防止将来有人把过滤搬到 `get_queryset` 之前。
        """
        self.assertEqual(self._ids(self.researcher_a, {'organization_id': self.org_b.id}), set())
        # 客户查自己机构仍能看到自己的单（不被误伤）
        self.assertEqual(
            self._ids(self.researcher_a, {'organization_id': self.org_a.id}),
            {self.order_a.id},
        )
