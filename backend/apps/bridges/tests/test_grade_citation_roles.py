"""TDD for grade_citation_roles 管理命令（按缓存来源给 citation_role 分级）。

契约（见 apps/bridges/management/commands/grade_citation_roles.py）：
- 规则：bioz 命中且上下文含 catalog_number → primary；bioz 命中但上下文无 → supporting；
  仅 pubmed 命中 → background；两者都无 → 保持不动。
- 命中口径：doi → pmid → title 级联（任一命中）。
- 必须 UPDATE 现有行，不得新建（unique_together 含 citation_role）。
- 默认 dry-run 不写库；--apply 才写。
"""
import io
import json
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.bridges.models import ProductReference
from apps.commerce.models import Product
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.documents.models import DataSourceCache
from apps.knowledge.models import Reference

CMD = 'grade_citation_roles'


def _cache(source, key, records):
    return DataSourceCache.objects.create(
        source=source, query_key=key, query_namespace='sku',
        data_json=json.dumps(records),
        expires_at=timezone.now() + timedelta(days=5))


def _bioz(title, *, doi='', pmid='', catalog_number='', long=''):
    return {'article_title': title, 'authors': [], 'journal': '', 'doi': doi,
            'pmid': pmid, 'pub_date': '', 'catalog_number': catalog_number,
            'long': long, 'medium': '', 'short': ''}


def _pm(title, *, doi='', pmid=''):
    return {'title': title, 'source': '', 'doi': doi, 'pmid': pmid,
            'pubdate': '', 'authors': []}


class GradeCitationRolesTests(TestCase):
    def setUp(self):
        self.prod = ProductFactory(catalog_no='SC8001', name='P1')
        SKUFactory(product=self.prod, sku_code='SC8001-1')

    def _run(self, *args, **opts):
        out = io.StringIO()
        call_command(CMD, *args, stdout=out, stderr=out, **opts)
        return out.getvalue()

    def _link(self, title, *, doi=None, pmid=None, role='supporting'):
        ref = Reference.objects.create(title=title, doi=doi, pmid=pmid,
                                       authors='', journal='', year=None)
        return ProductReference.objects.create(
            product=self.prod, reference=ref, citation_role=role)

    # 1. bioz 命中 + 上下文含货号 → primary
    def test_bioz_with_catalog_in_context_is_primary(self):
        pr = self._link('Paper A', pmid='111')
        _cache('bioz', 'SC8001', [
            _bioz('Paper A', pmid='111', catalog_number='NU-100',
                  long='cells were labeled with Jena NU-100 (5 mg)')])
        self._run('--apply')
        pr.refresh_from_db()
        self.assertEqual(pr.citation_role, 'primary')

    # 2. bioz 命中但上下文不含货号 → supporting
    def test_bioz_without_catalog_in_context_is_supporting(self):
        pr = self._link('Paper B', pmid='222')
        _cache('bioz', 'SC8001', [
            _bioz('Paper B', pmid='222', catalog_number='NU-100',
                  long='a generic sentence without the code')])
        self._run('--apply')
        pr.refresh_from_db()
        self.assertEqual(pr.citation_role, 'supporting')

    # 3. 仅 pubmed 命中 → background
    def test_pubmed_only_is_background(self):
        pr = self._link('Paper C', pmid='333')
        _cache('pubmed', 'SC8001', [_pm('Paper C', pmid='333')])
        self._run('--apply')
        pr.refresh_from_db()
        self.assertEqual(pr.citation_role, 'background')

    # 4. 两者都不命中 → 保持不动
    def test_no_match_leaves_unchanged(self):
        pr = self._link('Paper D', pmid='444')
        self._run('--apply')
        pr.refresh_from_db()
        self.assertEqual(pr.citation_role, 'supporting')

    # 5. dry-run 绝不写库
    def test_dry_run_never_writes(self):
        pr = self._link('Paper E', pmid='555')
        _cache('bioz', 'SC8001', [
            _bioz('Paper E', pmid='555', catalog_number='NU-1', long='... NU-1 ...')])
        out = self._run()
        pr.refresh_from_db()
        self.assertEqual(pr.citation_role, 'supporting')
        self.assertIn('[dry-run]', out)

    # 6. 级联匹配：标题不同但 pmid 相同也能命中
    def test_match_by_pmid_when_title_differs(self):
        pr = self._link('Title In DB', pmid='666')
        _cache('bioz', 'SC8001', [
            _bioz('Different Title', pmid='666', catalog_number='NU-9',
                  long='used NU-9 reagent')])
        self._run('--apply')
        pr.refresh_from_db()
        self.assertEqual(pr.citation_role, 'primary')

    # 7. UPDATE 不新建：行数不变
    def test_update_not_insert(self):
        self._link('Paper F', pmid='777')
        _cache('pubmed', 'SC8001', [_pm('Paper F', pmid='777')])
        before = ProductReference.objects.count()
        self._run('--apply')
        self.assertEqual(ProductReference.objects.count(), before)

    # 8. --only-products 过滤
    def test_only_products_filter(self):
        other = ProductFactory(catalog_no='SC9999', name='P2')
        SKUFactory(product=other, sku_code='SC9999-1')
        ref = Reference.objects.create(title='Paper G', pmid='888')
        pr_other = ProductReference.objects.create(
            product=other, reference=ref, citation_role='supporting')
        _cache('pubmed', 'SC9999', [_pm('Paper G', pmid='888')])
        self._run('--apply', only_products='SC8001')
        pr_other.refresh_from_db()
        self.assertEqual(pr_other.citation_role, 'supporting')  # 被过滤，未动

    # 9. 当前已是目标角色 → 不重复更新（plan 为空）
    def test_already_correct_role_not_reupdated(self):
        pr = self._link('Paper H', pmid='999', role='background')
        _cache('pubmed', 'SC8001', [_pm('Paper H', pmid='999')])
        out = self._run()
        self.assertIn('将更新行数] 0', out)
        pr.refresh_from_db()
        self.assertEqual(pr.citation_role, 'background')
