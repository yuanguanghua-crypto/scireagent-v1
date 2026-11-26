"""审计日志的两个筛选缺陷（S5 P-3 / A-165 + A-166）。

## A-165：`operator=system` 返回 0
UI 把「无操作人」渲染成 "system"（`AuditLogPage.vue:147`：`{{ r.username || 'system' }}`），
但后端只做 `user__username__icontains='system'` —— NULL 的 join 不产生行 ⇒ **永远 0 条**。
生产实测（2026-11-26，241 条）：`user IS NULL` = **22 条**，`username 含 system` = **0 条**。

## A-166：搜编号后缀返回 0
UI 的 Object 列是**两段拼出来的**（`AuditLogPage.vue:143-144`）：
    <span>{{ r.object_repr }}</span><span>#{{ r.object_id }}</span>
⇒ 运营看到的 "TEST-UTP-20261110-03 #5454" 里，`5454` 是 `object_id`，
   `object_repr` 中**不含 '#'**（生产实测：`object_repr__icontains='#'` = **0 条**，
   全部形如 'DS-A043-588100' 这种纯名称）。后端只搜 `object_repr` ⇒ 搜编号永远 0。
生产实测：`object_id=5454` 有 **30 条**审计记录。

## 本文件钉住
① `username=system` 命中 `user IS NULL` 那批；大小写不敏感；
② 其它用户名仍按 icontains（不能把 system 的特例扩散成"谁都查不到"）；
③ `search` 是纯数字（允许前导 `#`）时**同时**按 `object_id` 精确匹配；
④ `search` 是名称时仍按 `object_repr` 模糊匹配（两条路都要能用）；
⑤ `search` 非数字时**不得**去碰 `object_id`（否则 'abc' 会 500 或误命中）。
"""
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.models import AuditLog, Product
from apps.commerce.tests.factories import ProductFactory

URL = '/api/v1/ops/audit-logs/'


class AuditLogFilterTestBase(TestCase):
    def setUp(self):
        self.admin = UserFactory(is_staff=True, username='audit_operator')
        self.other = UserFactory(is_staff=True, username='scire02')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.ct = ContentType.objects.get_for_model(Product)

    def _mk(self, object_repr, object_id, user='admin', action=AuditLog.ACTION_UPDATE):
        """`user='admin'` 用 self.admin；`user=None` 造「无操作人」记录（UI 显示为 system）。"""
        actor = self.admin if user == 'admin' else (self.other if user == 'other' else None)
        return AuditLog.objects.create(
            user=actor, action=action, content_type=self.ct,
            object_id=object_id, object_repr=object_repr, snapshot={},
        )

    def _rows(self, **params):
        r = self.client.get(URL, params)
        self.assertEqual(r.status_code, 200, r.content[:300])
        return r.json()['data']


class OperatorSystemFilterTest(AuditLogFilterTestBase):
    """A-165"""

    def setUp(self):
        super().setUp()
        self.null1 = self._mk('Alpha Probe', 5461, user=None)
        self.null2 = self._mk('Beta Probe', 5462, user=None)
        self.mine = self._mk('Gamma Probe', 5463, user='admin')
        self.others = self._mk('Delta Probe', 5464, user='other')

    def test_system_matches_null_user_rows(self):
        """★ 核心：输入 system ⇒ 命中 user IS NULL 那批（UI 上就显示成 system）。"""
        ids = {r['id'] for r in self._rows(username='system')}
        self.assertEqual(ids, {self.null1.id, self.null2.id})

    def test_system_is_case_insensitive(self):
        self.assertEqual(
            {r['id'] for r in self._rows(username='SYSTEM')},
            {self.null1.id, self.null2.id},
        )

    def test_system_count_equals_orm_count(self):
        """验收线：接口命中数 == 直接数 ORM 的 `user__isnull=True` 数。"""
        api = len(self._rows(username='system'))
        self.assertEqual(api, AuditLog.objects.filter(user__isnull=True).count())

    def test_real_username_still_works(self):
        """不能把 system 的特例扩散成"谁都查不到"。"""
        ids = {r['id'] for r in self._rows(username='scire02')}
        self.assertEqual(ids, {self.others.id})

    def test_partial_username_still_works(self):
        ids = {r['id'] for r in self._rows(username='audit_op')}
        self.assertEqual(ids, {self.mine.id})

    def test_no_param_returns_all(self):
        self.assertEqual(len(self._rows()), 4)


class ObjectSearchFilterTest(AuditLogFilterTestBase):
    """A-166"""

    def setUp(self):
        super().setUp()
        # 生产上的真实形态：object_repr 是纯名称，**不含** '#' 也不含 id
        self.a = self._mk('TEST-UTP-20261110-03', 5454)
        self.b = self._mk('TEST-UTP-20261110-03', 5455)
        self.c = self._mk('DS-A043-588100', 5466)

    def test_search_by_numeric_id_matches_object_id(self):
        """★ 核心：搜 5454 ⇒ 命中 object_id=5454 的那条（UI 上显示为 "... #5454"）。"""
        ids = {r['id'] for r in self._rows(search='5454')}
        self.assertIn(self.a.id, ids)
        self.assertNotIn(self.b.id, ids, '5455 不应被 5454 命中')

    def test_search_by_hash_prefixed_id(self):
        """用户可能直接照界面复制 "#5454"。"""
        ids = {r['id'] for r in self._rows(search='#5454')}
        self.assertIn(self.a.id, ids)

    def test_search_by_name_still_matches_object_repr(self):
        """④ 名称检索不能因为加 id 通道而失效。"""
        ids = {r['id'] for r in self._rows(search='DS-A043')}
        self.assertEqual(ids, {self.c.id})

    def test_non_numeric_search_does_not_touch_object_id(self):
        """⑤ 'abc' 不能走进 int() 分支（否则 ValueError ⇒ 500）。"""
        r = self.client.get(URL, {'search': 'abc'})
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(r.json()['data'], [])

    def test_numeric_search_does_not_match_unrelated_repr(self):
        """数字搜索也不能靠 `object_repr__icontains` 误伤别的记录：
        这里 588100 含 '588'，搜 5466 只应命中按 id 的那条。"""
        ids = {r['id'] for r in self._rows(search='5466')}
        self.assertEqual(ids, {self.c.id})

    def test_object_id_count_equals_orm_count(self):
        """验收线：搜某个 id 的命中数 == ORM `object_id=<id>` 的条数（+ repr 命中）。"""
        # 再给 5454 加一条，验证不会去重/丢失
        extra = self._mk('另一个名字', 5454)
        ids = {r['id'] for r in self._rows(search='5454')}
        self.assertIn(extra.id, ids)
        self.assertEqual(len(ids), AuditLog.objects.filter(object_id=5454).count())
