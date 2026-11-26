# -*- coding: utf-8 -*-
"""`GET /api/v1/applications/?status=` 的真实筛选中枢 —— A-141（2026-11-20 / S4）。

## 为什么后端要有这条测试
A-141 的现象在前端（`ApplicationIndex.vue` 的状态芯片点了没反应，已修）。
修的时候我做了一个**只能靠实测坐实**的推断：

    staff 传 `?status=draft` 到底能不能拿到草稿？

两条代码事实决定了答案，缺一条结论就反转：
1. `ApplicationFilter.Meta.fields` 含 `status`
   （`apps/knowledge/api/v1/filters.py:22`）⇒ django-filter 会认这个参数；
2. `apply_public_visibility` 对 staff **绕过** status 公开态过滤
   （`apps/knowledge/api/v1/fixture_visibility.py:84`
   `if statuses and not is_staff_request(request)`）⇒ 不会被先压成 active。

若第 2 条不成立，staff 点 Draft 会得到空表 —— 前端就得额外带
`include_unpublished=1`（MethodIndex 的写法 `buildParams()` 就是这么干的）。
所以这条测试同时钉住「前端该不该抄 MethodIndex 那套」。

## 另一个副产品：为什么芯片必须只给 staff（A-123 的前端守卫）
非 staff 的第 2 条不成立 ⇒ 先被压成 active、再按 draft 筛 ⇒ **恒为空**
且永远不会报错。给研究者一个点了必然空表的控件，比不给更糟。
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.knowledge.tests.factories import ApplicationFactory

URL = '/api/v1/applications/'


class ApplicationStatusFilterTest(TestCase):
    """staff 与非 staff 在同一参数上的行为差异（这是 A-141 修法的前提）。"""

    @classmethod
    def setUpTestData(cls):
        # 工厂默认 status='draft'（StatusMixin 默认值），这里全部显式写，不靠默认
        cls.draft = ApplicationFactory(name='AP Draft', status='draft')
        cls.active = ApplicationFactory(name='AP Active', status='active')
        cls.deprecated = ApplicationFactory(name='AP Deprecated', status='deprecated')
        cls.archived = ApplicationFactory(name='AP Archived', status='archived')

    def _client(self, staff=False, authenticated=False):
        c = APIClient()
        if staff or authenticated:
            c.force_authenticate(user=UserFactory(is_staff=staff))
        return c

    def _count(self, client, query=''):
        r = client.get(URL + query)
        assert r.status_code == 200, r.status_code
        return r.json()['meta']['pagination']['count'], r.json()['data']

    # -- staff：参数真的生效 -------------------------------------------------

    def test_staff_status_draft_returns_only_drafts(self):
        """A-141 的核心断言：点 Draft 必须真拿到草稿，不是空表。"""
        count, rows = self._count(self._client(staff=True), '?status=draft')
        self.assertEqual(count, 1)
        self.assertEqual([r['status'] for r in rows], ['draft'])

    def test_staff_status_active_returns_only_active(self):
        count, rows = self._count(self._client(staff=True), '?status=active')
        self.assertEqual(count, 1)
        self.assertEqual([r['status'] for r in rows], ['active'])

    def test_staff_status_deprecated_returns_only_deprecated(self):
        count, rows = self._count(self._client(staff=True), '?status=deprecated')
        self.assertEqual(count, 1)
        self.assertEqual([r['status'] for r in rows], ['deprecated'])

    def test_staff_without_status_sees_all_statuses(self):
        """「All」芯片不发 status ⇒ staff 看到全部四种状态（等价 include_unpublished）。"""
        count, rows = self._count(self._client(staff=True))
        self.assertEqual(count, 4)
        self.assertEqual(
            sorted({r['status'] for r in rows}),
            ['active', 'archived', 'deprecated', 'draft'],
        )

    def test_staff_include_unpublished_is_not_required(self):
        """显式钉住「不需要 include_unpublished」—— 与 Method 端点不同。

        哪天有人把 Application 也改成 MethodIndex 那套（list 端点先压公开态），
        这条会红，提醒必须同步改前端 buildParams。
        """
        plain, _ = self._count(self._client(staff=True), '?status=draft')
        explicit, _ = self._count(
            self._client(staff=True), '?status=draft&include_unpublished=1'
        )
        self.assertEqual(plain, explicit)
        self.assertEqual(plain, 1)

    def test_staff_unknown_status_is_rejected_not_silently_empty(self):
        """非法 status 走 400，不是"静默空表"、更不是 500。

        ★ 这条断言是**实测改过来的**：我原本按"筛不出东西就空表"写成 count==0，
        实测返回 400（django-filter 对 choices 字段做校验）。400 是更好的行为 ——
        拼错的参数能立刻暴露，而不是伪装成"没有数据"。
        """
        r = self._client(staff=True).get(URL + '?status=nonexistent')
        self.assertEqual(r.status_code, 400)

    # -- 非 staff / 匿名：同一参数恒为空（A-123 守卫的依据） -----------------

    def test_anonymous_status_draft_is_always_empty(self):
        """匿名先被压成 active 再按 draft 筛 ⇒ 空。所以芯片不能给非 staff。"""
        count, rows = self._count(self._client(), '?status=draft')
        self.assertEqual(count, 0)
        self.assertEqual(rows, [])

    def test_authenticated_non_staff_status_draft_is_always_empty(self):
        count, _ = self._count(self._client(authenticated=True), '?status=draft')
        self.assertEqual(count, 0)

    def test_anonymous_sees_only_active(self):
        count, rows = self._count(self._client())
        self.assertEqual(count, 1)
        self.assertEqual([r['status'] for r in rows], ['active'])

    def test_anonymous_cannot_escalate_with_include_unpublished(self):
        """`include_unpublished` 对非 staff 一律无效（后端先判身份）。"""
        count, _ = self._count(self._client(), '?include_unpublished=1')
        self.assertEqual(count, 1)
