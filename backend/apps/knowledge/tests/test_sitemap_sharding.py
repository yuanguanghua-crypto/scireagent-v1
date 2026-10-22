# -*- coding: utf-8 -*-
"""sitemap 分片的契约测试（对应 FAILURE_MODES 10.2 的实测结论）

## 为什么必须改
实测生产 `/sitemap.xml` = **42,779 个 URL / 2.72MB**，而 sitemap 协议上限是
**单文件 ≤ 50,000 URL / ≤ 50MB** ⇒ **只剩 17% 余量**，数据再涨 17% 搜索引擎就拒收
整个 sitemap。10 倍压测时响应到 **16.6MB / 7.6s**。

⇒ 改为 sitemap index + 按类型分片（每片 ≤45,000 URL），这是协议标准做法。

## 这组用例要钉住什么
1. `/sitemap.xml` 返回 **`<sitemapindex>`**，而不是 `<urlset>`
2. **分片不丢 URL**：所有分片里的 URL 总数 == 数据总量（这是最容易出错的地方）
3. 单片 URL 数 ≤ `SITEMAP_PAGE_SIZE`
4. 单片响应体积受控（防止哪天又涨回 16MB）
5. 非法 kind / 越界 page ⇒ **404**（不是空 urlset —— 空 urlset 会被当成"该片没内容"）
6. `robots.txt` 指向的 `/sitemap.xml` 仍然有效（兼容旧入口）
"""
import re
from unittest import mock

from django.test import TestCase

from apps.commerce.models import Product
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.knowledge.api.v1 import site_views
from apps.knowledge.models import Application, Method, Protocol
from apps.knowledge.tests.factories import ApplicationFactory

LOC = re.compile(r'<loc>(.*?)</loc>')


class SitemapIndexTests(TestCase):
    def setUp(self):
        self.client.defaults['SERVER_NAME'] = 'localhost'

    def test_index_is_sitemapindex_not_urlset(self):
        resp = self.client.get('/sitemap.xml')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('<sitemapindex', body)
        self.assertNotIn('<urlset', body, 'index 不应直接包含 urlset')

    def test_index_lists_static_and_each_kind(self):
        ApplicationFactory(status='active')
        resp = self.client.get('/sitemap.xml')
        locs = LOC.findall(resp.content.decode())
        self.assertTrue(any('/sitemap-static.xml' in u for u in locs))
        self.assertTrue(any('/sitemap-applications-1.xml' in u for u in locs),
                        f'应列出 applications 分片，实际 {locs}')
        self.assertTrue(any('/sitemap-products-1.xml' in u for u in locs))

    def test_robots_points_to_index(self):
        """robots.txt 指的还是 /sitemap.xml —— 该入口现在是 index，仍有效。"""
        resp = self.client.get('/robots.txt')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('/sitemap.xml', resp.content.decode())


class SitemapPartTests(TestCase):
    def setUp(self):
        self.client.defaults['SERVER_NAME'] = 'localhost'

    def test_static_part_returns_urlset(self):
        resp = self.client.get('/sitemap-static.xml')
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn('<urlset', body)
        self.assertEqual(len(LOC.findall(body)), len(site_views.SITEMAP_STATIC_PATHS))

    def test_part_contains_only_that_kind(self):
        ApplicationFactory(status='active')
        ProductFactory(status='active')
        resp = self.client.get('/sitemap-applications-1.xml')
        self.assertEqual(resp.status_code, 200)
        locs = LOC.findall(resp.content.decode())
        self.assertTrue(locs)
        self.assertTrue(all('/applications/' in u for u in locs),
                        f'applications 分片里混入了别的类型：{locs[:3]}')

    def test_pagination_splits_without_losing_urls(self):
        """★ 核心用例：把页大小压到 3，验证分片后 **URL 总数不丢**。

        这是改分片最容易犯的错——切片边界写错就会丢尾巴。
        """
        for _ in range(7):
            ApplicationFactory(status='active')

        with mock.patch.object(site_views, 'SITEMAP_PAGE_SIZE', 3):
            total_expected = site_views._sitemap_sources()['applications'].count()
            pages = -(-total_expected // 3)          # 向上取整
            self.assertGreater(pages, 1, '本用例需要多片才有意义')

            seen = []
            for page in range(1, pages + 1):
                resp = self.client.get(f'/sitemap-applications-{page}.xml')
                self.assertEqual(resp.status_code, 200, f'第 {page} 页失败')
                locs = LOC.findall(resp.content.decode())
                self.assertLessEqual(len(locs), 3, '单片不得超页大小')
                seen.extend(locs)

        self.assertEqual(len(seen), total_expected,
                         f'分片后 URL 总数应等于 {total_expected}，实际 {len(seen)}（丢了或重复）')
        self.assertEqual(len(set(seen)), len(seen), 'URL 不应重复')

    def test_unknown_kind_404(self):
        resp = self.client.get('/sitemap-nosuchkind-1.xml')
        self.assertEqual(resp.status_code, 404)

    def test_out_of_range_page_404(self):
        ApplicationFactory(status='active')
        resp = self.client.get('/sitemap-applications-9999.xml')
        self.assertEqual(resp.status_code, 404,
                         '越界页应 404 而非空 urlset（空 urlset 会被当成该片没内容）')

    def test_page_zero_404(self):
        resp = self.client.get('/sitemap-applications-0.xml')
        self.assertEqual(resp.status_code, 404)

    def test_part_response_size_bounded(self):
        """单片体积要有上限 —— 防止哪天又把 16MB 塞回一个文件。"""
        for _ in range(50):
            ApplicationFactory(status='active')
        resp = self.client.get('/sitemap-applications-1.xml')
        self.assertLess(len(resp.content), 5 * 1024 * 1024,
                        '单片响应应远小于 5MB')
