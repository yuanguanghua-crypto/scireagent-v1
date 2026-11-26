"""用户列表「admin」筛选的口径（S5 P-3 / A-092）。

## 缺陷
本页下拉只有 4 个 role 值，而后端此前是 `filter(role='admin')` —— **只认名义角色**。
但"能进后台"有三条互相独立的通道：
  a) `role='admin'`
  b) `is_staff=True`
  c) `is_superuser=True`

生产实测（2026-11-26，32 个用户）：
  · `role='admin'` 只有 **1 个** —— `smoke`（`s@e.com`，冒烟测试账号）
  · 真正能进后台的是 **3 个** —— `admin`(id=1)、`scire02`(16)、`scire03`(17)，
    而这 3 个的 `role` **全是 `researcher`**
⇒ 运营选「admin」筛出来的是唯一那个假账号，三个真管理员一个都看不到。

## 本文件钉住
① 口径合一：选 admin ⇒ a ∪ b ∪ c 全命中；
② 不能反向污染：选 `researcher` 时仍**精确**按 role 字段（否则把 staff 混进来就成了另一种错）；
③ 验收线 = 命中数必须等于「用同一条件直接数 ORM」的数（不是"看着像对"）；
④ 响应里带上 `is_staff` / `is_superuser`，让这个口径在界面上自解释。
"""
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory

User = get_user_model()
LIST_URL = '/api/v1/ops/users/'


class AdminRoleFilterTest(TestCase):
    def setUp(self):
        # 执行者本身是 staff + role=admin（能进本页）
        self.operator = UserFactory(username='ops_operator', is_staff=True, role='admin')
        self.client = APIClient()
        self.client.force_authenticate(self.operator)

        # 名义 admin（有 role='admin' 但无 staff 权限）—— 生产上的 `smoke`
        self.nominal = UserFactory(username='nominal_admin', role='admin')
        # 真·管理员但 role=researcher（走 is_staff 通道）—— 生产上的 scire02/03
        self.staff_only = UserFactory(username='staff_only', role='researcher', is_staff=True)
        # superuser 但 role=researcher —— 生产上的 admin(id=1)
        self.super_only = UserFactory(
            username='super_only', role='researcher', is_staff=True, is_superuser=True)
        # 普通研究员（不该被 admin 筛选命中）
        self.plain = UserFactory(username='plain_researcher', role='researcher')
        # 采购（不该被 admin 筛选命中）
        self.proc = UserFactory(username='plain_procurement', role='procurement')

    def _names(self, **params):
        r = self.client.get(LIST_URL, params)
        self.assertEqual(r.status_code, 200, r.content[:300])
        return {row['username'] for row in r.json()['data']}

    # ── ① 口径合一 ─────────────────────────────────────────────
    def test_role_admin_matches_nominal_admin(self):
        self.assertIn('nominal_admin', self._names(role='admin'))

    def test_role_admin_matches_staff_without_admin_role(self):
        """★ 核心：能进后台的 researcher（is_staff 通道）必须被 admin 筛出来。"""
        self.assertIn('staff_only', self._names(role='admin'))

    def test_role_admin_matches_superuser_without_admin_role(self):
        self.assertIn('super_only', self._names(role='admin'))

    def test_role_admin_excludes_plain_researcher_and_procurement(self):
        names = self._names(role='admin')
        self.assertNotIn('plain_researcher', names)
        self.assertNotIn('plain_procurement', names)

    # ── ② 不反向污染 ───────────────────────────────────────────
    def test_role_researcher_stays_exact(self):
        """选 researcher 时必须仍按 `role` 精确筛 —— staff 的 researcher 也算 researcher，
        但 procurement / nominal_admin 不能混进来。"""
        names = self._names(role='researcher')
        self.assertIn('plain_researcher', names)
        # staff_only 的 role 就是 researcher，按字段语义应当出现
        self.assertIn('staff_only', names)
        self.assertNotIn('plain_procurement', names)
        self.assertNotIn('nominal_admin', names)

    def test_role_procurement_stays_exact(self):
        names = self._names(role='procurement')
        self.assertIn('plain_procurement', names)
        self.assertNotIn('nominal_admin', names)
        self.assertNotIn('staff_only', names)

    # ── ③ 验收线：命中数 == ORM 直接数 ─────────────────────────
    def test_admin_count_equals_orm_count(self):
        """★ 验收线：接口命中数必须等于「同一条件直接数 ORM」的数。"""
        api_count = len(self._names(role='admin'))
        orm_count = User.objects.filter(
            Q(role='admin') | Q(is_staff=True) | Q(is_superuser=True)
        ).count()
        self.assertEqual(api_count, orm_count)

    def test_admin_filter_actually_catches_more_than_before(self):
        """对照旧实现：`filter(role='admin')` 的条数严格小于新口径 —— 证明修的是真缺口。"""
        old = User.objects.filter(role='admin').count()
        new = len(self._names(role='admin'))
        self.assertGreater(new, old,
                           '新口径的命中数应严格多于旧的 filter(role="admin")')

    # ── ④ 响应字段支撑界面自解释 ───────────────────────────────
    def test_rows_expose_staff_and_superuser_flags(self):
        r = self.client.get(LIST_URL, {'role': 'admin'})
        rows = {row['username']: row for row in r.json()['data']}
        self.assertTrue(rows['staff_only']['is_staff'])
        self.assertFalse(rows['nominal_admin']['is_staff'])
        self.assertIn('is_superuser', rows['super_only'])
        self.assertTrue(rows['super_only']['is_superuser'])
