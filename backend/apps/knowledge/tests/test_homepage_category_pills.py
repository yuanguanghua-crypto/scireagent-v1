"""首页分类胶囊 → `/products?category_l1=` 的端到端一致性闸门。

## 为什么单独成文件

2026-10-30 首页全链路走查实测到的**用户可见错误**：
点首页三条分类胶囊，**一条都没有真正过滤**，全部落到 69 个产品上；
其中 Click Chemistry / Molecular Biology 明明显示 "0"，点进去却有 69 个。

根因是**两套 slug 各走各的**：
- `site_home` 的 `CATEGORY_META` 只给了展示用 slug（`nucleotides` / `click-chemistry`）
- `/products?category_l1=` 与 `/api/v1/categories` 认的是 ProductClass 的真实 L1 slug
  （`nucleotides_nucleosides` / `click_chemistry` / `molecular_biology`）
- `CategoryPills.vue` 照展示 slug 拼 URL ⇒ 后端 `get_descendant_product_class_ids`
  查不到 ⇒ **静默返回全量**，不报错、不告警

修复：`site_home` 的每个分类追加 `class_slug`，前端用它拼 URL。
本文件锁定「**胶囊上显示的数字 == 点进去实际拿到的条数**」这一条不变量 ——
只要有人把两个 slug 再拆开、或在任何一侧改了过滤口径，这里就红。
"""
from django.test import TestCase

from apps.commerce.models import Product
from apps.commerce.tests.factories import ProductClassFactory, ProductFactory

HOME_URL = '/api/v1/site/home'
CATEGORIES_URL = '/api/v1/categories'
PRODUCTS_URL = '/api/v1/products/'


class HomeCategoryPillsContractTest(TestCase):
    """胶囊数字、class_slug、点击后的实际条数，三者必须一致。"""

    def setUp(self):
        # 三个 L1 与 site_views.CATEGORY_META 的键严格对应
        self.l1_nuc = ProductClassFactory(
            name='Nucleotides & Nucleosides', slug='nucleotides_nucleosides')
        self.l2_nuc = ProductClassFactory(
            name='Fluorescent Nucleotides', slug='fluorescent-nucleotides', parent=self.l1_nuc)
        self.l1_click = ProductClassFactory(
            name='Click Chemistry', slug='click_chemistry')

        # 2 个可见产品（L1 直挂 + L2 后代）+ 1 个 draft + 1 个夹具
        ProductFactory(name='Pill Nuc Direct', slug='pill-nuc-direct',
                       status='active', product_class=self.l1_nuc)
        ProductFactory(name='Pill Nuc Child', slug='pill-nuc-child',
                       status='active', product_class=self.l2_nuc)
        ProductFactory(name='Pill Nuc Draft', slug='pill-nuc-draft',
                       status=Product.Status.DRAFT, product_class=self.l1_nuc)
        ProductFactory(name='Pill Nuc Fixture', slug='pill-nuc-fixture',
                       status='active', product_class=self.l1_nuc, is_test_fixture=True)

    def _home_categories(self):
        resp = self.client.get(HOME_URL)
        self.assertEqual(resp.status_code, 200)
        return resp.json()['data']['categories']

    # ── 契约 1：必须带 class_slug，且是真 L1 slug ───────────────
    def test_every_pill_has_class_slug(self):
        for cat in self._home_categories():
            self.assertIn('class_slug', cat, f'{cat.get("name")} 缺少 class_slug')
            self.assertTrue(cat['class_slug'], f'{cat.get("name")} 的 class_slug 为空')

    def test_class_slug_matches_categories_endpoint_keys(self):
        """`class_slug` 必须落在 `/api/v1/categories` 的键空间里。

        例外：某个 L1 在该库中**根本没建**（例如只配了 2 个分类的环境）时，
        它不在 keys 里是正常的 —— 此时 count=0 且点进去也是 0，契约仍然成立
        （由 `test_pill_count_equals_click_through_total` 覆盖）。
        这里只要求「该 L1 存在时，两边的 slug 必须是同一个」。
        """
        keys = set(self.client.get(CATEGORIES_URL).json().keys())
        known = {c['class_slug'] for c in self._home_categories()} & keys
        self.assertTrue(known, '没有任何 class_slug 命中 /api/v1/categories 的键，slug 体系已脱节')
        for cat in self._home_categories():
            if cat['class_slug'] not in keys:
                # 该 L1 未配置：必须表现为 0，而不能回落到全量
                self.assertEqual(cat['count'], 0,
                                 f'{cat["name"]} 的 L1 不存在却有 {cat["count"]} 个产品')

    # ── 契约 2：胶囊数字 == 点进去的条数（本次 bug 的核心不变量）──
    def test_pill_count_equals_click_through_total(self):
        for cat in self._home_categories():
            resp = self.client.get(PRODUCTS_URL, {'category_l1': cat['class_slug']})
            self.assertEqual(resp.status_code, 200)
            total = resp.json()['meta']['pagination']['count']
            self.assertEqual(
                total, cat['count'],
                f'{cat["name"]}：胶囊显示 {cat["count"]}，'
                f'点进 ?category_l1={cat["class_slug"]} 实际 {total}',
            )

    # ── 契约 3：数字本身的口径（draft / 夹具都不算）──────────────
    def test_pill_count_excludes_draft_and_fixture(self):
        nuc = next(c for c in self._home_categories() if c['name'] == 'Nucleotides')
        # 2 个可见（direct + child）；draft 与 is_test_fixture 都不计
        self.assertEqual(nuc['count'], 2, 'draft 或测试夹具被算进了胶囊数字')

    def test_empty_category_stays_zero(self):
        """0 产品的分类必须报 0（而不是因为参数失效回落到全量）。"""
        click = next(c for c in self._home_categories() if c['name'] == 'Click Chemistry')
        self.assertEqual(click['count'], 0)
        resp = self.client.get(PRODUCTS_URL, {'category_l1': click['class_slug']})
        self.assertEqual(resp.json()['meta']['pagination']['count'], 0)
