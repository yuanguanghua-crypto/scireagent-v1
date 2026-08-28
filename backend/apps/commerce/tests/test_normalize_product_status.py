"""
A2 数据卫生测试 — published 非法状态清洗 + 死分支删除。

背景（2026-08-28 实测）：
- Product 状态机（core/models.py StatusMixin）= draft/active/deprecated/archived，
  **无 published**；但 dev 库存在 13 条 status='published'（全部 archived=True，
  SC8xxx docx 导入品）——历史遗留脏状态。
- 6 处代码把 'published' 混入 Product/Application 状态过滤（死泄漏）：
  commerce/views.py:289 + product_relationship_service.py L24/L33/L77/L126/L139。
- 注意：Protocol.PublicationStatus 与 COA 的 published 是合法枚举，不在清理范围。

清洗映射（宁缺毋滥）：
  非法状态 + archived=True  → 'archived'（归档标志优先，绝不复活已归档产品）
  非法状态 + archived=False → 'draft'（不得自动上站，需人工定夺）
"""
from django.core.management import call_command
from io import StringIO

from rest_framework.test import APITestCase

from apps.commerce.models import Product
from apps.commerce.tests.factories import ProductFactory


class NormalizeProductStatusTests(APITestCase):
    """management command normalize_product_status（dry-run 默认 / --apply 执行）。"""

    def _make_published(self, slug, archived=True):
        """直写非法状态（Django 模型 save 不校验 choices，可落库）。"""
        return ProductFactory(slug=slug, status='published', archived=archived)

    def test_published_archived_maps_to_archived_on_apply(self):
        p = self._make_published('norm-pub-arch', archived=True)
        call_command('normalize_product_status', apply=True, stdout=StringIO())
        p.refresh_from_db()
        self.assertEqual(p.status, 'archived')
        self.assertTrue(p.archived)

    def test_published_not_archived_maps_to_draft_on_apply(self):
        p = self._make_published('norm-pub-live', archived=False)
        call_command('normalize_product_status', apply=True, stdout=StringIO())
        p.refresh_from_db()
        self.assertEqual(p.status, 'draft')

    def test_dry_run_does_not_change(self):
        p = self._make_published('norm-dryrun', archived=True)
        out = StringIO()
        call_command('normalize_product_status', stdout=out)
        p.refresh_from_db()
        self.assertEqual(p.status, 'published')
        self.assertIn('published', out.getvalue())  # 报告中列出目标行

    def test_idempotent_second_run_zero_changes(self):
        self._make_published('norm-idem-1', archived=True)
        call_command('normalize_product_status', apply=True, stdout=StringIO())
        out = StringIO()
        call_command('normalize_product_status', apply=True, stdout=out)
        self.assertIn('0', out.getvalue())  # 第二次 0 条待清洗
        self.assertEqual(
            Product.objects.exclude(
                status__in=['draft', 'active', 'deprecated', 'archived']).count(), 0)

    def test_legal_statuses_untouched(self):
        keep = [
            ProductFactory(slug='norm-legal-draft', status='draft'),
            ProductFactory(slug='norm-legal-active', status='active'),
            ProductFactory(slug='norm-legal-deprecated', status='deprecated'),
            ProductFactory(slug='norm-legal-archived', status='archived', archived=True),
        ]
        call_command('normalize_product_status', apply=True, stdout=StringIO())
        for p in keep:
            p.refresh_from_db()
        self.assertEqual([p.status for p in keep],
                         ['draft', 'active', 'deprecated', 'archived'])


class PublishedDeadBranchTests(APITestCase):
    """死分支删除：Product/Application 过滤不再接受 'published'。"""

    def test_detail_view_rejects_published_status_product(self):
        """detail 视图只认 active：published 脏状态产品 → 404（修复前 200）。"""
        p = ProductFactory(slug='db-detail-pub', status='published')
        resp = self.client.get(f'/api/v1/products/{p.id}/detail/')
        self.assertEqual(resp.status_code, 404)

    def test_detail_view_accepts_active_product(self):
        p = ProductFactory(slug='db-detail-active', status='active')
        resp = self.client.get(f'/api/v1/products/{p.id}/detail/')
        self.assertEqual(resp.status_code, 200)

    def test_related_products_excludes_published_status_neighbors(self):
        """同分类关联推荐不混入 published 脏状态产品（修复前会混入）。"""
        from apps.commerce.tests.factories import ProductClassFactory
        pc = ProductClassFactory()
        base = ProductFactory(slug='db-rel-base', status='active', product_class=pc)
        ProductFactory(slug='db-rel-active-nb', status='active', product_class=pc)
        ProductFactory(slug='db-rel-pub-nb', status='published', product_class=pc)
        from apps.commerce.services.product_relationship_service import get_related_products
        related = get_related_products(base)
        related_ids = {r['id'] for r in related}
        self.assertIn(
            Product.objects.get(slug='db-rel-active-nb').id, related_ids)
        self.assertNotIn(
            Product.objects.get(slug='db-rel-pub-nb').id, related_ids)
