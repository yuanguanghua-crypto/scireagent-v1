from django.test import TestCase
from rest_framework.test import APIClient
from apps.knowledge.tests.factories import (
    ApplicationFactory, MethodFactory, ProtocolFactory, ReferenceFactory
)
from apps.commerce.tests.factories import ProductFactory, SKUFactory


class SiteHomeAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_home_endpoint(self):
        resp = self.client.get('/api/v1/site/home')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertIn('hero', data['data'])
        self.assertIn('featured_applications', data['data'])

    def test_home_hero_fields(self):
        resp = self.client.get('/api/v1/site/home')
        hero = resp.json()['data']['hero']
        self.assertIn('title', hero)
        self.assertIn('subtitle', hero)

    def test_home_featured_applications(self):
        ApplicationFactory(status='active')
        ApplicationFactory(status='draft')  # should not appear
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        self.assertEqual(len(data['featured_applications']), 1)

    def test_home_featured_methods(self):
        MethodFactory(status='active')
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        self.assertIn('featured_methods', data)
        self.assertEqual(len(data['featured_methods']), 1)

    def test_home_featured_products(self):
        ProductFactory(status='active')
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()['data']
        self.assertIn('featured_products', data)
        self.assertEqual(len(data['featured_products']), 1)

    def test_home_featured_application_fields(self):
        ApplicationFactory(status='active', name='RNA Labeling')
        resp = self.client.get('/api/v1/site/home')
        app_data = resp.json()['data']['featured_applications'][0]
        self.assertIn('id', app_data)
        self.assertIn('name', app_data)
        self.assertIn('slug', app_data)
        self.assertIn('summary', app_data)

    def test_home_envelope_format(self):
        resp = self.client.get('/api/v1/site/home')
        data = resp.json()
        self.assertIn('success', data)
        self.assertIn('data', data)
        self.assertIn('meta', data)

    def test_home_stats_and_featured_exclude_archived(self):
        """S2 路径 5/6：首页推荐位与统计（product/sku）排除归档产品。"""
        live = ProductFactory(status='active', display_priority=100)
        SKUFactory(product=live)
        SKUFactory(product=live)
        arch = ProductFactory(status='active', display_priority=200, archived=True)
        SKUFactory(product=arch)
        data = self.client.get('/api/v1/site/home').json()['data']
        # 推荐位不含归档产品
        self.assertNotIn(arch.id, [p['id'] for p in data['featured_products']])
        # 统计只计未归档产品（1 条 live）与其 SKU（2 条）
        self.assertEqual(data['stats']['products'], 1)
        self.assertEqual(data['stats']['skus'], 2)


class SiteNavigationAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_navigation_endpoint(self):
        resp = self.client.get('/api/v1/site/navigation')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertIn('primary', data['data'])

    def test_navigation_primary_items(self):
        resp = self.client.get('/api/v1/site/navigation')
        primary = resp.json()['data']['primary']
        labels = [item['label'] for item in primary]
        self.assertIn('Home', labels)
        self.assertIn('Applications', labels)
        self.assertIn('Methods', labels)

    def test_navigation_applications(self):
        ApplicationFactory(status='active', name='RNA Labeling')
        ApplicationFactory(status='draft', name='Draft App')
        resp = self.client.get('/api/v1/site/navigation')
        apps = resp.json()['data']['applications']
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]['name'], 'RNA Labeling')

    # ── 2026-10-21 L7 性能：单次响应 2.78MB（全部 active application）→ 加 limit ──
    def test_navigation_is_capped_by_default(self):
        """★ 核心回归：不能把全部 application 塞进一次响应。

        修复前实测 28,566 条 ⇒ 2.78MB / p95 267ms，而前端**零消费方**
        （`stores/app.js` 的 fetchNavigation 全仓无调用）⇒ 纯浪费 + 匿名可放大。
        """
        from apps.knowledge.api.v1.site_views import NAV_APPLICATION_LIMIT

        ApplicationFactory.create_batch(NAV_APPLICATION_LIMIT + 5, status='active')
        body = self.client.get('/api/v1/site/navigation').json()

        apps = body['data']['applications']
        self.assertEqual(len(apps), NAV_APPLICATION_LIMIT,
                         f'默认应截断到 {NAV_APPLICATION_LIMIT} 条，实际 {len(apps)}')
        # total 必须如实（否则调用方不知道被截断）
        self.assertEqual(body['meta']['application_total'], NAV_APPLICATION_LIMIT + 5)
        self.assertTrue(body['meta']['applications_truncated'])

    def test_navigation_limit_param_respected(self):
        ApplicationFactory.create_batch(10, status='active')
        body = self.client.get('/api/v1/site/navigation?limit=3').json()
        self.assertEqual(len(body['data']['applications']), 3)
        self.assertEqual(body['meta']['application_total'], 10)
        self.assertTrue(body['meta']['applications_truncated'])

    def test_navigation_limit_is_clamped(self):
        """`?limit=999999` 不能把放大点重新打开。"""
        from apps.knowledge.api.v1.site_views import NAV_APPLICATION_LIMIT_MAX

        ApplicationFactory.create_batch(5, status='active')
        body = self.client.get('/api/v1/site/navigation?limit=999999').json()
        self.assertLessEqual(body['meta']['application_limit'], NAV_APPLICATION_LIMIT_MAX)
        # 数据量不足上限时不该丢数据
        self.assertEqual(len(body['data']['applications']), 5)

    def test_navigation_invalid_limit_falls_back(self):
        ApplicationFactory.create_batch(3, status='active')
        for bad in ('abc', '0', '-7', '', 'null'):
            body = self.client.get(f'/api/v1/site/navigation?limit={bad}').json()
            self.assertGreaterEqual(len(body['data']['applications']), 1,
                                    f'limit={bad!r} 应回落默认值而不是返回空/报错')

    def test_navigation_not_truncated_flag_when_small(self):
        ApplicationFactory.create_batch(2, status='active')
        body = self.client.get('/api/v1/site/navigation').json()
        self.assertFalse(body['meta']['applications_truncated'])
        self.assertEqual(body['meta']['application_total'], 2)


class SearchAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_search_empty_query(self):
        resp = self.client.get('/api/v1/search')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data'], [])

    def test_search_products(self):
        ProductFactory(name='Cy3-NHS Ester')
        ProductFactory(name='Cy5-NHS Ester')
        resp = self.client.get('/api/v1/search?q=Cy3')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['data']), 1)
        self.assertEqual(data['data'][0]['type'], 'product')

    def test_search_methods(self):
        MethodFactory(name='Sanger Sequencing', status='active')
        MethodFactory(name='PCR Amplification', status='active')
        resp = self.client.get('/api/v1/search?q=Sanger')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['data']), 1)

    def test_search_applications(self):
        ApplicationFactory(name='RNA Labeling', status='active')
        resp = self.client.get('/api/v1/search?q=RNA')
        data = resp.json()
        self.assertTrue(len(data['data']) > 0)
        self.assertEqual(data['data'][0]['type'], 'application')

    def test_search_protocols(self):
        ProtocolFactory(name='DNA Extraction Protocol', status='published')
        resp = self.client.get('/api/v1/search?q=Extraction')
        data = resp.json()
        self.assertTrue(len(data['data']) > 0)

    def test_search_references(self):
        ReferenceFactory(title='Nature Paper on CRISPR')
        resp = self.client.get('/api/v1/search?q=CRISPR')
        data = resp.json()
        self.assertTrue(len(data['data']) > 0)

    def test_search_multiple_types(self):
        ProductFactory(name='Cy3-NHS', status='active')
        MethodFactory(name='Cy3 Labeling Method', status='active')
        resp = self.client.get('/api/v1/search?q=Cy3')
        data = resp.json()
        types = [r['type'] for r in data['data']]
        self.assertIn('product', types)
        self.assertIn('method', types)

    def test_search_no_results(self):
        ProductFactory(name='Cy3-NHS')
        resp = self.client.get('/api/v1/search?q=NonExistent')
        self.assertEqual(resp.json()['data'], [])

    def test_search_meta(self):
        resp = self.client.get('/api/v1/search?q=test')
        meta = resp.json()['meta']
        self.assertIn('query', meta)
        self.assertEqual(meta['query'], 'test')

    def test_search_type_filter(self):
        ProductFactory(name='Cy3-NHS')
        MethodFactory(name='Cy3 Labeling')
        resp = self.client.get('/api/v1/search?q=Cy3&type=product')
        data = resp.json()['data']
        for result in data:
            self.assertEqual(result['type'], 'product')

    def test_search_suggest(self):
        ProductFactory(name='Cy3-NHS')
        resp = self.client.get('/api/v1/search/suggest?q=Cy3')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

    def test_search_suggest_short_query(self):
        resp = self.client.get('/api/v1/search/suggest?q=C')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data'], [])

    def test_search_suggest_fields(self):
        ProductFactory(name='Cy3-NHS')
        MethodFactory(name='Cy3 Labeling')
        resp = self.client.get('/api/v1/search/suggest?q=Cy3')
        suggestions = resp.json()['data']
        self.assertTrue(len(suggestions) > 0)
        for s in suggestions:
            self.assertIn('type', s)
            self.assertIn('id', s)
            self.assertIn('text', s)


class SitemapAPITest(TestCase):
    """sitemap 已改为 **index + 分片**（2026-10-22）。

    ⚠️ 本类断言**整体改写过**（契约变更，不是"改到绿"）：
    旧版断言 `/api/v1/sitemap.xml` 直接含 `/applications/`、`/products/` 等实体 URL
    —— 那是"单一 urlset"的契约。实测该文件已达 **42,779 URL / 2.72MB**，
    而协议上限是单文件 **50,000 URL**（仅剩 17% 余量），10 倍数据下到 **16.6MB**。
    ⇒ 改为 sitemap index + 按类型分片。

    这里**保留每个用例的原意图**（某类型是否被收录、draft/archived 是否被排除），
    只把请求目标从 index 换到对应分片。新增 `test_sitemap_index_returns_sitemapindex`
    钉住新契约本身。
    """

    def setUp(self):
        self.client = APIClient()

    def _part(self, kind, page=1):
        return self.client.get(f'/sitemap-{kind}-{page}.xml')

    def test_sitemap_index_returns_sitemapindex(self):
        """新契约：入口返回 sitemapindex，实体 URL 在分片里。"""
        resp = self.client.get('/api/v1/sitemap.xml')
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('<?xml', content)
        self.assertIn('<sitemapindex', content)
        self.assertNotIn('<urlset', content)

    def test_sitemap_contains_applications(self):
        ApplicationFactory(status='active')
        self.assertIn('/applications/', self._part('applications').content.decode())

    def test_sitemap_contains_methods(self):
        MethodFactory(status='active')
        self.assertIn('/methods/', self._part('methods').content.decode())

    def test_sitemap_contains_products(self):
        ProductFactory(status='active')
        self.assertIn('/products/', self._part('products').content.decode())

    def test_sitemap_contains_protocols(self):
        ProtocolFactory(status='published')
        self.assertIn('/protocols/', self._part('protocols').content.decode())

    def test_sitemap_excludes_draft(self):
        ApplicationFactory(status='draft')
        self.assertNotIn('/applications/', self._part('applications').content.decode())

    def test_sitemap_content_type(self):
        resp = self.client.get('/api/v1/sitemap.xml')
        self.assertEqual(resp.get('Content-Type'), 'application/xml')

    def test_sitemap_static_part_contains_home(self):
        """原 `test_sitemap_always_contains_home` 的意图：首页必须在 sitemap 里。

        新结构下首页在 static 分片。
        """
        content = self.client.get('/sitemap-static.xml').content.decode()
        self.assertIn('<url>', content)
        self.assertIn('/</loc>', content)

    def test_sitemap_excludes_archived_products(self):
        """S2 路径 8：sitemap 不含归档产品 URL；未归档 active 产品仍在。"""
        live = ProductFactory(status='active')
        arch = ProductFactory(status='active', archived=True)
        content = self._part('products').content.decode()
        self.assertIn(f'/products/{live.id}</loc>', content)
        self.assertNotIn(f'/products/{arch.id}</loc>', content)
