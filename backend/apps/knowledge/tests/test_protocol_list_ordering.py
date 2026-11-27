"""协议列表必须**稳定有序**（A-213，2026-11-27）。

## 改前
`ProtocolViewSet` 没有 `ordering`，`Protocol` 模型也没有 `Meta.ordering`
⇒ 列表顺序由数据库自由决定。QA 实测（Batch 16）：「12xxx 号记录穿插在低 ID 之间，
12763 在 231 之后、12768 在 263 之后…… 共 17 例」，且翻页成员不稳定。

和 A-078（订单列表只按 `created_at` 排、没有兜底键）是同一个病：**排序不是全序**。

## 本文件钉两条
① 视图必须显式声明 `ordering`（不依赖数据库默认行为 —— 这是"意图"层面的锁）；
② 列表返回的 id 严格升序（行为层面的锁；在 PG 上能抓出退化）。
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.knowledge.api.v1.views import ProtocolViewSet
from apps.knowledge.tests.factories import ProtocolFactory


class ProtocolListOrderingTest(TestCase):
    def setUp(self):
        self.staff = UserFactory(is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        # 造一批，故意让"创建顺序"与"id 顺序"一致但名称顺序打乱 ——
        # 若排序退化成按 name，本用例会红。
        for i, name in enumerate(['Zeta', 'Alpha', 'Mike', 'Beta', 'Yankee']):
            ProtocolFactory(name=f'{name}-{i}')

    def test_viewset_declares_explicit_ordering(self):
        assert list(ProtocolViewSet.ordering) == ['id'], (
            '★ 视图必须显式给排序；没有它，PG 对"无 ORDER BY"的查询不保证顺序，'
            '列表与翻页都会漂（A-213 的根因）'
        )

    def test_list_returns_ascending_ids(self):
        r = self.client.get('/api/v1/protocols/', {'page_size': 20})
        self.assertEqual(r.status_code, 200, r.content[:300])
        rows = r.json()['data']
        ids = [row['id'] for row in rows]
        self.assertEqual(ids, sorted(ids), f'协议列表 id 必须升序，实得 {ids}')

    def test_order_is_stable_across_calls(self):
        first = [r['id'] for r in self.client.get('/api/v1/protocols/', {'page_size': 20}).json()['data']]
        for _ in range(2):
            again = [r['id'] for r in self.client.get('/api/v1/protocols/', {'page_size': 20}).json()['data']]
            self.assertEqual(first, again, '同一查询多次调用顺序必须一致')

    def test_client_can_still_override_ordering(self):
        r = self.client.get('/api/v1/protocols/', {'page_size': 20, 'ordering': 'name'})
        self.assertEqual(r.status_code, 200)
        names = [row['name'] for row in r.json()['data']]
        self.assertEqual(names, sorted(names), f'?ordering=name 应当生效，实得 {names}')
