"""
TDD for adopt_cached_evidence 管理命令（批量把外部文献缓存落库为产品级证据）。

契约（见 apps/bridges/management/commands/adopt_cached_evidence.py）：
- 默认 dry-run：绝不写库。
- --apply：逐产品调 adopt_bioz_references（唯一写入口），落库 Reference + ProductReference。
- 复用 bioz_adopter 的 _find_existing / _extract_year，dry-run 与 apply 规则一致。
- 键解析复刻 load_product_bioz：_product_evidence_keys = [catalog_no] + [sku_code...]（去空/保序/去重）。
- 确定性顺序：产品 id 升序 → source 参数顺序 → 记录缓存原始顺序。
- 预测（dry-run）的 refs_planned_new / links_to_create 必须等于 --apply 实际新增。

17 个用例覆盖：dry-run 不写库、bioz/pubmed 计数与归一化、键一致性、DOI/PMID/title
复用、关联已存在不重复建、--apply 真建+幂等、过期仍用、预测准确性、空标题跳过、
标题超长截断、--limit/--only-products、--source 过滤、--out 生成 JSONL、非法 role 报错。
"""
import io
import json
from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from apps.bridges.models import ProductReference
from apps.bridges.services.relevance import load_product_bioz
from apps.commerce.models import Product, SKU
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.documents.models import DataSourceCache
from apps.knowledge.models import Reference
from apps.knowledge.tests.factories import ReferenceFactory


def _make_cache(source, query_key, records, *, stale=False, expires_in_days=1):
    """构造一条 DataSourceCache（data_json 为 records 列表）。"""
    expires = timezone.now() + timedelta(days=expires_in_days)
    return DataSourceCache.objects.create(
        source=source,
        query_key=query_key,
        query_namespace='name',
        data_json=json.dumps(records),
        expires_at=expires,
        is_stale=stale,
    )


def _bioz_rec(title, **kw):
    rec = {
        'article_title': title,
        'authors': ['Smith, J.', 'Doe, A.'],
        'journal': 'Nature',
        'pub_date': '2022-03-01',
        'doi': '',
        'pmid': '',
    }
    rec.update(kw)
    return rec


def _pubmed_rec(title, **kw):
    rec = {
        'title': title,
        'source': 'Cell',
        'pubdate': '2021-07-15',
        'authors': ['Lee, K.'],
        'doi': '',
        'pmid': '',
        'elocationid': '',
    }
    rec.update(kw)
    return rec


class AdoptDryRunNoWriteTest(TestCase):
    """1. dry-run 绝不写库。"""

    def test_dry_run_does_not_write(self):
        p = ProductFactory(catalog_no='SC9001')
        _make_cache('bioz', 'SC9001', [_bioz_rec('Paper A', doi='10.1/A')])

        ref_before = Reference.objects.count()
        link_before = ProductReference.objects.count()

        out = io.StringIO()
        call_command('adopt_cached_evidence', stdout=out)

        self.assertEqual(Reference.objects.count(), ref_before)
        self.assertEqual(ProductReference.objects.count(), link_before)
        self.assertIn('dry-run', out.getvalue())


class AdoptBiozCountsTest(TestCase):
    """2. dry-run 在 bioz 缓存夹具上输出正确计数。"""

    def test_dry_run_bioz_counts(self):
        p = ProductFactory(catalog_no='SC9002')
        # 3 条记录：1 条重复（同 doi）-> dup_within_product；其余 2 条 unique
        _make_cache('bioz', 'SC9002', [
            _bioz_rec('A', doi='10.1/A'),
            _bioz_rec('B', doi='10.1/B'),
            _bioz_rec('A', doi='10.1/A'),  # 重复
        ])

        out = io.StringIO()
        call_command('adopt_cached_evidence', stdout=out)
        text = out.getvalue()

        self.assertIn('rows_hit（命中缓存行）：1', text)
        self.assertIn('records_raw（原始记录数）：3', text)
        self.assertIn('dup_within_product（产品内重复）：1', text)
        self.assertIn('records_unique（去产品内重后）：2', text)
        self.assertIn('refs_planned_new（计划新建）：2', text)
        self.assertIn('links_to_create（计划新建）：2', text)
        self.assertIn('products_with_evidence（有证据）：1', text)


class AdoptPubmedNormalizationTest(TestCase):
    """3. pubmed 记录正确归一化（title→article_title、source→journal、pubdate→year）。"""

    def test_pubmed_normalization_in_plan(self):
        p = ProductFactory(catalog_no='SC9003')
        _make_cache('pubmed', 'SC9003', [
            _pubmed_rec('PubMed Paper', pmid='38123456', doi='10.2/P'),
        ])

        import tempfile, os
        fd, path = tempfile.mkstemp(suffix='.jsonl')
        os.close(fd)
        try:
            call_command('adopt_cached_evidence', '--out', path)
            with open(path, encoding='utf-8') as f:
                lines = [json.loads(l) for l in f if l.strip()]
            self.assertEqual(len(lines), 1)
            rec = lines[0]
            self.assertEqual(rec['article_title'], 'PubMed Paper')
            self.assertEqual(rec['journal'], 'Cell')   # source -> journal
            self.assertEqual(rec['pmid'], '38123456')
            self.assertEqual(rec['year'], 2021)         # pubdate -> year
            self.assertEqual(rec['source'], 'pubmed')
        finally:
            os.remove(path)


class AdoptKeyConsistencyTest(TestCase):
    """4. 键一致性：catalog_no + 2 SKU 下，load_product_bioz 能命中按本命令 keys 铺的缓存。"""

    def test_keys_match_load_product_bioz(self):
        p = ProductFactory(catalog_no='SC8001')
        SKUFactory(product=p, sku_code='SC8001-A')
        SKUFactory(product=p, sku_code='SC8001-B')

        # 按 _product_evidence_keys = [SC8001, SC8001-A, SC8001-B] 铺缓存
        _make_cache('bioz', 'SC8001', [_bioz_rec('By Cat')])
        _make_cache('bioz', 'SC8001-A', [_bioz_rec('By Sku A')])
        _make_cache('bioz', 'SC8001-B', [_bioz_rec('By Sku B')])
        _make_cache('pubmed', 'SC8001', [_pubmed_rec('Pub By Cat', pmid='1')])

        # load_product_bioz 应能命中这 4 条（证明键集合一致）
        lits = load_product_bioz(p)
        titles = {d.get('article_title') for d in lits}
        self.assertEqual(len(lits), 4)
        self.assertEqual(titles, {'By Cat', 'By Sku A', 'By Sku B', 'Pub By Cat'})

        # 本命令 dry-run 也应统计到 4 条 unique
        out = io.StringIO()
        call_command('adopt_cached_evidence', stdout=out)
        self.assertIn('records_unique（去产品内重后）：4', out.getvalue())


class AdoptReuseByDoiTest(TestCase):
    """5. 按 DOI 复用已有 Reference。"""

    def test_reuse_by_doi(self):
        ref = ReferenceFactory(doi='10.5/existing', title='Existing DOI Paper')
        p = ProductFactory(catalog_no='SC9101')
        _make_cache('bioz', 'SC9101', [_bioz_rec('Existing DOI Paper', doi='10.5/existing')])

        out = io.StringIO()
        call_command('adopt_cached_evidence', stdout=out)
        text = out.getvalue()

        self.assertIn('refs_reused_from_db（复用已有）：1', text)
        self.assertIn('refs_planned_new（计划新建）：0', text)
        # 关联应被创建（复用引用 + 新建链接）
        self.assertIn('links_to_create（计划新建）：1', text)


class AdoptReuseByPmidTest(TestCase):
    """6. 按 PMID 复用。"""

    def test_reuse_by_pmid(self):
        ReferenceFactory(pmid='39999999', title='Existing PMID Paper')
        p = ProductFactory(catalog_no='SC9102')
        _make_cache('pubmed', 'SC9102', [_pubmed_rec('Existing PMID Paper', pmid='39999999')])

        out = io.StringIO()
        call_command('adopt_cached_evidence', stdout=out)
        text = out.getvalue()

        self.assertIn('refs_reused_from_db（复用已有）：1', text)
        self.assertIn('refs_planned_new（计划新建）：0', text)
        self.assertIn('links_to_create（计划新建）：1', text)


class AdoptReuseByTitleTest(TestCase):
    """7. 按 title（大小写不敏感）复用。"""

    def test_reuse_by_title_case_insensitive(self):
        ReferenceFactory(title='Mixed Case Title Paper', doi='', pmid='')
        p = ProductFactory(catalog_no='SC9103')
        # 缓存里标题大小写不同，应命中已有
        _make_cache('bioz', 'SC9103', [_bioz_rec('MIXED case title paper', doi='', pmid='')])

        out = io.StringIO()
        call_command('adopt_cached_evidence', stdout=out)
        text = out.getvalue()

        self.assertIn('refs_reused_from_db（复用已有）：1', text)
        self.assertIn('refs_planned_new（计划新建）：0', text)


class AdoptLinkAlreadyExistsTest(TestCase):
    """8. 关联已存在 → 计 links_already_exist，不重复建。"""

    def test_link_already_exists(self):
        ref = ReferenceFactory(doi='10.6/linked', title='Already Linked')
        p = ProductFactory(catalog_no='SC9104')
        ProductReference.objects.create(
            product=p, reference=ref, citation_role='supporting'
        )
        _make_cache('bioz', 'SC9104', [_bioz_rec('Already Linked', doi='10.6/linked')])

        out = io.StringIO()
        call_command('adopt_cached_evidence', stdout=out)
        text = out.getvalue()

        self.assertIn('links_already_exist（已存在）：1', text)
        self.assertIn('links_to_create（计划新建）：0', text)


class AdoptApplyCreatesTest(TestCase):
    """9. --apply 真的建出 Reference + ProductReference（role 正确）。"""

    def test_apply_creates(self):
        p = ProductFactory(catalog_no='SC9201')
        _make_cache('bioz', 'SC9201', [_bioz_rec('Apply Paper', doi='10.7/apply')])

        ref_before = Reference.objects.count()
        link_before = ProductReference.objects.count()

        call_command('adopt_cached_evidence', '--apply')

        self.assertEqual(Reference.objects.count(), ref_before + 1)
        self.assertEqual(ProductReference.objects.count(), link_before + 1)
        link = ProductReference.objects.get(product=p)
        self.assertEqual(link.citation_role, 'supporting')
        ref = link.reference
        self.assertEqual(ref.doi, '10.7/apply')
        self.assertEqual(ref.title, 'Apply Paper')

    def test_apply_custom_role(self):
        p = ProductFactory(catalog_no='SC9202')
        _make_cache('bioz', 'SC9202', [_bioz_rec('Primary Paper', doi='10.7/primary')])
        call_command('adopt_cached_evidence', '--apply', '--role', 'primary')
        link = ProductReference.objects.get(product=p)
        self.assertEqual(link.citation_role, 'primary')


class AdoptApplyIdempotentTest(TestCase):
    """10. --apply 幂等（连跑两次，第二次 refs_planned_new=0、links_to_create=0）。"""

    def test_apply_idempotent(self):
        p = ProductFactory(catalog_no='SC9301')
        _make_cache('bioz', 'SC9301', [_bioz_rec('Idem Paper', doi='10.8/idem')])

        call_command('adopt_cached_evidence', '--apply')
        ref_after_first = Reference.objects.count()
        link_after_first = ProductReference.objects.count()

        out = io.StringIO()
        call_command('adopt_cached_evidence', '--apply', stdout=out)
        text = out.getvalue()

        # 第二次没有任何新增
        self.assertIn('新建 Reference：预测 0 / 实际 0', text)
        self.assertIn('新建关联 links：预测 0 / 实际 0', text)
        self.assertEqual(Reference.objects.count(), ref_after_first)
        self.assertEqual(ProductReference.objects.count(), link_after_first)


class AdoptStaleUsedTest(TestCase):
    """11. 过期缓存条目仍被使用且计 rows_stale。"""

    def test_stale_entry_still_used(self):
        p = ProductFactory(catalog_no='SC9401')
        # 已过期（expires_at 在过去）+ is_stale
        _make_cache('bioz', 'SC9401', [_bioz_rec('Stale Paper', doi='10.9/stale')],
                    stale=True, expires_in_days=-5)

        out = io.StringIO()
        call_command('adopt_cached_evidence', stdout=out)
        text = out.getvalue()

        self.assertIn('rows_stale（过期仍用）：1', text)
        self.assertIn('records_unique（去产品内重后）：1', text)
        self.assertIn('refs_planned_new（计划新建）：1', text)


class AdoptPredictionAccuracyTest(TestCase):
    """12. 预测准确性：dry-run 的 refs_planned_new/links_to_create 与 --apply 实际新增相等。"""

    def test_prediction_matches_apply(self):
        p1 = ProductFactory(catalog_no='SC9501')
        p2 = ProductFactory(catalog_no='SC9502')
        # p1: 2 条 unique（不同 doi）；p2: 复用 p1 的一条（同 doi 跨产品复用）
        _make_cache('bioz', 'SC9501', [
            _bioz_rec('Shared Paper', doi='10.10/shared'),
            _bioz_rec('Only P1', doi='10.10/only1'),
        ])
        _make_cache('bioz', 'SC9502', [
            _bioz_rec('Shared Paper', doi='10.10/shared'),
        ])

        import tempfile, os
        fd, path = tempfile.mkstemp(suffix='.jsonl')
        os.close(fd)
        try:
            # dry-run 先出计划
            call_command('adopt_cached_evidence', '--out', path)
            with open(path, encoding='utf-8') as f:
                plan = [json.loads(l) for l in f if l.strip()]
            expected_new_refs = sum(1 for r in plan if r.get('ref_action') == 'plan_new')
            expected_new_links = sum(1 for r in plan if r.get('link_action') == 'create_link')

            # 同库再 apply
            ref_before = Reference.objects.count()
            link_before = ProductReference.objects.count()
            call_command('adopt_cached_evidence', '--apply')
            actual_new_refs = Reference.objects.count() - ref_before
            actual_new_links = ProductReference.objects.count() - link_before

            self.assertEqual(expected_new_refs, actual_new_refs)
            self.assertEqual(expected_new_links, actual_new_links)
            # shared 引用被两产品各链接一次 -> 2 链接；only1 一次 -> 1 链接；共 3 链接
            self.assertEqual(actual_new_refs, 2)
            self.assertEqual(actual_new_links, 3)
        finally:
            os.remove(path)


class AdoptSkipNoTitleTest(TestCase):
    """13. 空 title 跳过并计数。"""

    def test_skip_no_title(self):
        p = ProductFactory(catalog_no='SC9601')
        # 一条空标题 + 一条有效
        _make_cache('bioz', 'SC9601', [
            {'article_title': '', 'authors': [], 'journal': 'X', 'pub_date': '', 'doi': '', 'pmid': ''},
            _bioz_rec('Has Title', doi='10.11/has'),
        ])

        out = io.StringIO()
        call_command('adopt_cached_evidence', stdout=out)
        text = out.getvalue()

        self.assertIn('skipped_no_title（空标题跳过）：1', text)
        self.assertIn('records_raw（原始记录数）：1', text)
        self.assertIn('refs_planned_new（计划新建）：1', text)


class AdoptLongTitleTruncateTest(TestCase):
    """14. title 超 500 字符被截断且不抛异常。"""

    def test_long_title_truncated(self):
        p = ProductFactory(catalog_no='SC9701')
        long_title = 'X' * 600
        _make_cache('bioz', 'SC9701', [_bioz_rec(long_title, doi='10.12/long')])

        out = io.StringIO()
        call_command('adopt_cached_evidence', '--apply', stdout=out)

        ref = Reference.objects.get(doi='10.12/long')
        self.assertEqual(len(ref.title), 500)
        self.assertIn('truncated_title：1', out.getvalue())


class AdoptLimitAndOnlyProductsTest(TestCase):
    """15. --limit 与 --only-products 生效。"""

    def test_limit_and_only_products(self):
        # 3 个产品都铺缓存
        for cat in ('SC9801', 'SC9802', 'SC9803'):
            p = ProductFactory(catalog_no=cat)
            _make_cache('bioz', cat, [_bioz_rec(f'Paper {cat}', doi=f'10.13/{cat}')])

        # --limit 2
        out = io.StringIO()
        call_command('adopt_cached_evidence', '--limit', '2', stdout=out)
        self.assertIn('products_total（考虑产品总数）：2', out.getvalue())
        self.assertIn('records_unique（去产品内重后）：2', out.getvalue())

        # --only-products SC9803
        out = io.StringIO()
        call_command('adopt_cached_evidence', '--only-products', 'SC9803', stdout=out)
        self.assertIn('products_total（考虑产品总数）：1', out.getvalue())
        self.assertIn('records_unique（去产品内重后）：1', out.getvalue())


class AdoptSourceFilterTest(TestCase):
    """16. --source bioz 时不处理 pubmed。"""

    def test_source_bioz_only_skips_pubmed(self):
        p = ProductFactory(catalog_no='SC9901')
        _make_cache('bioz', 'SC9901', [_bioz_rec('Bioz Only', doi='10.14/bioz')])
        _make_cache('pubmed', 'SC9901', [_pubmed_rec('Pubmed Only', pmid='41000000')])

        out = io.StringIO()
        call_command('adopt_cached_evidence', '--source', 'bioz', stdout=out)
        text = out.getvalue()

        self.assertIn('records_unique（去产品内重后）：1', text)
        self.assertIn('分源拆分', text)
        self.assertIn('bioz：1', text)
        self.assertIn('pubmed：0', text)
        # 计划里不应出现 pubmed 记录
        self.assertNotIn('"source": "pubmed"', text)


class AdoptOutJsonlTest(TestCase):
    """17. --out 在 dry-run 下也生成 JSONL。"""

    def test_out_generated_in_dry_run(self):
        p = ProductFactory(catalog_no='SC9902')
        _make_cache('bioz', 'SC9902', [_bioz_rec('Plan Paper', doi='10.15/plan')])

        import tempfile, os
        fd, path = tempfile.mkstemp(suffix='.jsonl')
        os.close(fd)
        try:
            call_command('adopt_cached_evidence', '--out', path)
            self.assertTrue(os.path.exists(path))
            with open(path, encoding='utf-8') as f:
                lines = [json.loads(l) for l in f if l.strip()]
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0]['mode'], 'preview')
            self.assertTrue(lines[0]['dry_run'])
            # 仍未写库
            self.assertEqual(Reference.objects.count(), 0)
        finally:
            os.remove(path)


class AdoptInvalidRoleTest(TestCase):
    """附加：非法 --role 报错退出。"""

    def test_invalid_role_raises(self):
        p = ProductFactory(catalog_no='SC9903')
        _make_cache('bioz', 'SC9903', [_bioz_rec('X', doi='10.16/x')])
        with self.assertRaises(CommandError):
            call_command('adopt_cached_evidence', '--role', 'bogus')
