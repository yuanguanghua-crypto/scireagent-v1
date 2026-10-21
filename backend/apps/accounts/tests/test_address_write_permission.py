# -*- coding: utf-8 -*-
"""机构地址簿的写权限 —— 从「内部角色」放开到「本机构成员」（2026-10-21 L7）

## 为什么改
`AddressPermission`（`accounts/api/v1/views.py:314-326`）原先把**写**权限
绑在 `IsProcurementOrAdmin` 上。而一旦注册不再允许自选 `procurement`
（见 `test_membership_guard.py`），客户侧的采购经理就**能看不能改**自己机构的
地址簿 —— `/po/addresses`（`router/index.js:205`，客户侧页面）直接 403，
打断真实业务流程。

## 为什么放开是安全的（先看行级隔离，再看权限）
`AddressViewSet` 的隔离在三处，权限只是最外层：
1. `get_queryset()` 按 `request.user.organization_id` 收窄，无机构返回 `.none()`
2. `create()` 强制 `serializer.save(organization=request.user.organization)`，
   **客户端传什么 organization 都不算**
3. `update`/`destroy` 走 `self.get_object()` ⇒ 必然经过第 1 条

所以"本机构成员可写"的实际语义是：**只能改自己机构那一小撮行**。
读权限本来就是"任意已登录用户 + 本机构过滤"，写权限与读权限对齐，
增量风险仅是"同机构成员可改彼此的地址"——这本来就是机构内协作。

## ⚠️ 依赖关系（别忘）
这条放开的**前提**是"不能自助加入任意机构"已经堵住
（`test_membership_guard.py::OrganizationJoinDomainGuardTests`）。
否则攻击者先 join 别人的机构、再改该机构的收货地址，等于把洞放大。
两个改动必须同批上线。
"""
from rest_framework.test import APITestCase

from apps.accounts.models import Address, Organization, User
from apps.accounts.tests.factories import UserFactory


class AddressWritePermissionTests(APITestCase):
    URL = '/api/v1/addresses/'

    def setUp(self):
        self.org = Organization.objects.create(name='Org A', status='active')
        self.other_org = Organization.objects.create(name='Org B', status='active')
        self.address = Address.objects.create(
            organization=self.org, attention='Main', line1='1 A St',
            city='Boston', postal_code='02115', country='United States',
        )
        self.other_address = Address.objects.create(
            organization=self.other_org, attention='Other', line1='9 B St',
            city='X', postal_code='0', country='United States',
        )

    def _login(self, role, org=None):
        u = UserFactory(role=role)
        if org is not None:
            u.organization = org
            u.save(update_fields=['organization'])
        self.client.force_authenticate(user=u)
        return u

    # ── 本机构成员（researcher）应当能维护自己的地址簿 ──
    def test_researcher_can_create_address_in_own_org(self):
        self._login(User.Role.RESEARCHER, self.org)
        resp = self.client.post(self.URL, {
            'attention': 'Lab', 'line1': '2 A St', 'city': 'Boston',
            'postal_code': '02115', 'country': 'United States',
        }, format='json')
        self.assertEqual(resp.status_code, 201, f'本机构成员的地址写权限被挡：{resp.content}')
        self.assertEqual(Address.objects.filter(organization=self.org).count(), 2)

    def test_researcher_can_update_own_org_address(self):
        self._login(User.Role.RESEARCHER, self.org)
        resp = self.client.patch(f'{self.URL}{self.address.id}/',
                                 {'city': 'Cambridge'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.address.refresh_from_db()
        self.assertEqual(self.address.city, 'Cambridge')

    def test_researcher_can_delete_own_org_address(self):
        self._login(User.Role.RESEARCHER, self.org)
        resp = self.client.delete(f'{self.URL}{self.address.id}/')
        self.assertIn(resp.status_code, (200, 204), resp.content)
        self.assertFalse(Address.objects.filter(id=self.address.id).exists())

    # ── 反向：不得跨机构 ──
    def test_cannot_update_other_org_address(self):
        self._login(User.Role.RESEARCHER, self.org)
        resp = self.client.patch(f'{self.URL}{self.other_address.id}/',
                                 {'city': 'Hacked'}, format='json')
        self.assertEqual(resp.status_code, 404,
                         f'跨机构改地址必须 404，实际 {resp.status_code}')
        self.other_address.refresh_from_db()
        self.assertNotEqual(self.other_address.city, 'Hacked')

    def test_cannot_delete_other_org_address(self):
        self._login(User.Role.RESEARCHER, self.org)
        resp = self.client.delete(f'{self.URL}{self.other_address.id}/')
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(Address.objects.filter(id=self.other_address.id).exists(),
                        '跨机构删除必须无效')

    def test_create_ignores_client_supplied_organization(self):
        """客户端传别的机构 id 也不得生效 —— organization 由登录身份决定。"""
        self._login(User.Role.RESEARCHER, self.org)
        resp = self.client.post(self.URL, {
            'attention': 'Sneaky', 'line1': '3 A St', 'city': 'Boston',
            'postal_code': '02115', 'country': 'United States',
            'organization': self.other_org.id, 'organization_id': self.other_org.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        created = Address.objects.get(attention='Sneaky')
        self.assertEqual(created.organization_id, self.org.id,
                         '地址被写进了客户端指定的机构 ⇒ 越权写')

    # ── 边界 ──
    def test_user_without_org_cannot_create(self):
        self._login(User.Role.RESEARCHER, None)
        resp = self.client.post(self.URL, {
            'attention': 'X', 'line1': '1 X', 'city': 'X',
            'postal_code': '0', 'country': 'X',
        }, format='json')
        self.assertEqual(resp.status_code, 400, '无机构用户不该能建地址')

    def test_anonymous_write_denied(self):
        self.client.force_authenticate(None)
        for payload in ({'attention': 'X', 'line1': '1 X', 'city': 'X',
                         'postal_code': '0', 'country': 'X'},):
            resp = self.client.post(self.URL, payload, format='json')
            self.assertIn(resp.status_code, (401, 403))

    # ── 回归：内部角色仍然能写（不能因为改权限把它们弄坏） ──
    def test_procurement_still_can_write(self):
        self._login(User.Role.PROCUREMENT, self.org)
        resp = self.client.post(self.URL, {
            'attention': 'PO', 'line1': '4 A St', 'city': 'Boston',
            'postal_code': '02115', 'country': 'United States',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
