"""公开读路径排除「测试夹具」产品（is_test_fixture=True）—— commerce 侧。

## 背景

2026-10-30 首页全链路走查实测：前台 `/products` 报 69 个结果，其中
`E2E PO Test Product`(id=5460) 与 `Product 0`(id=2432) 是 e2e 残留，
真实产品只有 67 个。连带把首页三处数字顶偏：
- StatsBar `products` = 69（应 67）
- 分类胶囊 `Nucleotides` = 67 而分类总数 67+0+0=67 ≠ 69
- `/api/v1/categories` 的 count 更是 105（完全没过滤）

ResearchGoal / Application / Method / Protocol 早就有 `is_test_fixture`，
只有 Product 缺（本次 migration `commerce.0019` 补上）。

## 口径（有意的不对称，勿"统一"掉）

| 请求者 | list 是否含夹具 | 为什么 |
|---|---|---|
| 匿名 / 普通用户 | **排除** | 前台商品列表不能出现测试数据 |
| staff | **包含** | `seed_e2e_po_fixture.py` 要求该夹具 `status=active` 且能被
`/products?search=` 搜到，否则 PoSubmit 页选不到商品、采购 e2e 挂；运营清理也需要看见 |

详情（retrieve / detail）**不挡**夹具：与 archived 同一条红线 —— 详情类动作若被过滤，
restore / hard-delete / 后台编辑就取不到对象。
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory


class ProductFixtureVisibilityTest(TestCase):
    """is_test_fixture=True 的产品：匿名不可见，staff 可见，详情不挡。"""

    def setUp(self):
        self.anon = APIClient()
        self.staff_client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.staff_client.force_authenticate(user=self.staff)

        self.real = ProductFactory(
            name='Zzfixture Real Reagent', slug='zzfixture-real', status='active')
        self.fixture = ProductFactory(
            name='Zzfixture E2E Residue', slug='zzfixture-e2e',
            status='active', is_test_fixture=True)

    # ── 匿名：排除 ──────────────────────────────────────────
    def test_anonymous_list_excludes_fixture(self):
        resp = self.anon.get('/api/v1/products/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = [p['name'] for p in resp.json()['data']]
        self.assertNotIn(self.fixture.name, names)
        self.assertIn(self.real.name, names)

    def test_anonymous_search_excludes_fixture(self):
        """搜索路径同样要排除（PoSubmit 走的就是 ?search=，夹具不能泄到前台）。"""
        resp = self.anon.get('/api/v1/products/?search=Zzfixture')
        names = [p['name'] for p in resp.json()['data']]
        self.assertNotIn(self.fixture.name, names)
        self.assertIn(self.real.name, names)

    def test_anonymous_category_l1_excludes_fixture(self):
        """分类过滤路径（首页胶囊走这条）也不能带出夹具。"""
        from apps.commerce.tests.factories import ProductClassFactory
        l1 = ProductClassFactory(name='Zzfixture L1', slug='zzfixture_l1')
        real2 = ProductFactory(name='Zzfixture Cat Real', slug='zzfixture-cat-real',
                               status='active', product_class=l1)
        fix2 = ProductFactory(name='Zzfixture Cat Fix', slug='zzfixture-cat-fix',
                              status='active', product_class=l1, is_test_fixture=True)
        resp = self.anon.get('/api/v1/products/?category_l1=zzfixture_l1')
        names = [p['name'] for p in resp.json()['data']]
        self.assertNotIn(fix2.name, names)
        self.assertIn(real2.name, names)

    # ── staff：保留（保障 PO 提交页 / e2e / 清理）─────────────
    def test_staff_list_includes_fixture(self):
        """★ 有意不对称：staff 必须能搜到夹具，否则采购 e2e 的 PoSubmit 选不到商品。"""
        resp = self.staff_client.get('/api/v1/products/?search=Zzfixture E2E')
        names = [p['name'] for p in resp.json()['data']]
        self.assertIn(self.fixture.name, names)

    # ── 详情：不挡（与 archived 同一红线）────────────────────
    def test_fixture_detail_still_reachable(self):
        """详情类动作若被过滤，restore / 后台编辑 / hard-delete 会取不到对象。"""
        resp = self.anon.get(f'/api/v1/products/{self.fixture.pk}/detail/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = resp.json()
        # /detail/ 的响应比 retrieve 多包一层：{data: {product: {...}, ...}}
        self.assertEqual(payload['data']['product']['id'], self.fixture.pk)

    def test_fixture_retrieve_still_reachable(self):
        """retrieve 同样不能被夹具过滤挡住（回收站 / 编辑页依赖）。"""
        resp = self.anon.get(f'/api/v1/products/{self.fixture.pk}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()['data']['id'], self.fixture.pk)
