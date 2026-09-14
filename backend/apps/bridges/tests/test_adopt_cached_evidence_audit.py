"""独立对抗性验证（fresh eyes）—— 不修改作者原测试。

覆盖 adopt_cached_evidence 的：dry-run 零写入 / 预测=apply / 键一致性(含 namespace) /
长度守卫 / 过期缓存 / 参数边界 / 幂等 / 隐藏写路径 / 报告口径 / 代码质量风险。
"""
import io
import json
import os
import tempfile

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


def _cache(source, query_key, records, *, namespace='name', stale=False,
           expires_in_days=1, expires_at=None):
    kw = dict(source=source, query_key=query_key, query_namespace=namespace,
              data_json=json.dumps(records), is_stale=stale)
    if expires_at is not None:
        kw['expires_at'] = expires_at
    else:
        kw['expires_at'] = timezone.now() + timezone.timedelta(days=expires_in_days)
    return DataSourceCache.objects.create(**kw)


def _bioz(title, **kw):
    rec = {'article_title': title, 'authors': ['X'], 'journal': 'Nature',
           'pub_date': '2022-03-01', 'doi': '', 'pmid': ''}
    rec.update(kw)
    return rec


def _pub(title, **kw):
    rec = {'title': title, 'source': 'Cell', 'pubdate': '2021-07-15',
           'authors': ['Y'], 'doi': '', 'pmid': '', 'elocationid': ''}
    rec.update(kw)
    return rec


# ──────────────────────────────────────────────────────────────────────────
# 2. dry-run 真不写库（含多表 + updated_at）
# ──────────────────────────────────────────────────────────────────────────
class AuditDryRunNoWriteTest(TestCase):
    def test_dry_run_zero_write(self):
        p = ProductFactory(catalog_no='AD2-1')
        SKUFactory(product=p, sku_code='AD2-1-A')
        _cache('bioz', 'AD2-1', [_bioz('Dry A', doi='10.2/A')])
        _cache('pubmed', 'AD2-1-A', [_pub('Dry B', pmid='200')])
        before = dict(
            ref=Reference.objects.count(),
            link=ProductReference.objects.count(),
            cache=DataSourceCache.objects.count(),
            prod=Product.objects.count(),
        )
        snap = {m: m.objects.aggregate() for m in ()}
        # updated_at 快照
        p_upd_before = Product.objects.get(id=p.id).updated_at
        cache_rows = list(DataSourceCache.objects.all())
        cache_upd_before = {c.id: c.expires_at for c in cache_rows}

        out = io.StringIO()
        call_command('adopt_cached_evidence', stdout=out)

        after = dict(
            ref=Reference.objects.count(),
            link=ProductReference.objects.count(),
            cache=DataSourceCache.objects.count(),
            prod=Product.objects.count(),
        )
        self.assertEqual(before, after, f"dry-run 写库! {before} -> {after}")
        self.assertEqual(Product.objects.get(id=p.id).updated_at, p_upd_before)
        for c in DataSourceCache.objects.all():
            self.assertEqual(c.expires_at, cache_upd_before[c.id], "缓存被改")
        self.assertIn('dry-run', out.getvalue())


# ──────────────────────────────────────────────────────────────────────────
# 3. dry-run 预测 == --apply 实际（混合场景）
# ──────────────────────────────────────────────────────────────────────────
class AuditPredictionEqualsApplyTest(TestCase):
    def test_mixed_prediction(self):
        p1 = ProductFactory(catalog_no='AD3-1')
        p2 = ProductFactory(catalog_no='AD3-2')
        # P1
        _cache('bioz', 'AD3-1', [
            _bioz('A unique', doi='10.3/A'),                       # 新建
            _bioz('Same Title X', pmid='300'),                     # 新建(仅pmid)
            _bioz('Shared Cross', doi='10.3/SHARED'),              # 新建
        ])
        _cache('pubmed', 'AD3-1', [_pub('Pub P1', doi='10.3/PUB')])  # 新建(第4)
        # P2
        _cache('bioz', 'AD3-2', [
            _bioz('Shared Cross', doi='10.3/SHARED'),              # 跨产品同DOI -> 复用+新链
            _bioz('SAME title x'),                                 # 大小写不同 title -> 复用B+新链
            _bioz('F Title', pmid='300'),                          # 同PMID -> 复用B+新链
            _bioz('Only G', doi='10.3/G'),                         # 新建(第5)
        ])

        fd, path = tempfile.mkstemp(suffix='.jsonl')
        os.close(fd)
        try:
            call_command('adopt_cached_evidence', '--out', path)
            plan = [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]
            pred_refs = sum(1 for r in plan if r.get('ref_action') == 'plan_new')
            pred_links = sum(1 for r in plan if r.get('link_action') == 'create_link')

            ref_before = Reference.objects.count()
            link_before = ProductReference.objects.count()
            call_command('adopt_cached_evidence', '--apply')
            act_refs = Reference.objects.count() - ref_before
            act_links = ProductReference.objects.count() - link_before
        finally:
            os.remove(path)

        # 真实：P1 建4(A,B,SHARED,PUB)，P2 复用(SHARED,title,pmid)+新G；
        # P2 中 E/F 都链向同一复用引用(ref B) -> 其中一条计 reuse_link。
        # 预测 refs=5, links = P1 4 + P2(D,E,G 新链=3) = 7
        self.assertEqual(pred_refs, act_refs, f"refs 预测{pred_refs}!=实际{act_refs}")
        self.assertEqual(pred_links, act_links, f"links 预测{pred_links}!=实际{act_links}")
        self.assertEqual(act_refs, 5)
        self.assertEqual(act_links, 7)


# ──────────────────────────────────────────────────────────────────────────
# 4. 键一致性 + query_namespace 漏行风险
# ──────────────────────────────────────────────────────────────────────────
class AuditKeyAndNamespaceTest(TestCase):
    def test_namespace_not_filtered(self):
        p = ProductFactory(catalog_no='AD4-1')
        SKUFactory(product=p, sku_code='AD4-1-A')
        # 同 query_key 铺在多种 namespace 下（生产可能如此）
        _cache('bioz', 'AD4-1', [_bioz('Ns Name')], namespace='name')
        _cache('bioz', 'AD4-1', [_bioz('Ns Sku')], namespace='sku')
        _cache('bioz', 'AD4-1-A', [_bioz('Ns SkuA')], namespace='sku')
        # load_product_bioz 命中（不区分 namespace）
        lits = load_product_bioz(p)
        self.assertEqual(len(lits), 3, f"load_product_bioz 漏行: {len(lits)}")
        # 命令 dry-run 也命中 3 条（证明不漏）
        out = io.StringIO()
        call_command('adopt_cached_evidence', stdout=out)
        self.assertIn('records_unique（去产品内重后）：3', out.getvalue())

    def test_namespace_duplicate_deduped(self):
        # 同一 query_key 在 name 与 sku 下各一条“相同文章” -> 由 (doi,pmid,title) 去重折叠为 1
        p = ProductFactory(catalog_no='AD4-2')
        _cache('bioz', 'AD4-2', [_bioz('Dup N')], namespace='name')
        _cache('bioz', 'AD4-2', [_bioz('Dup N')], namespace='sku')
        out = io.StringIO()
        call_command('adopt_cached_evidence', stdout=out)
        # 不漏行(rows_hit=2) 也不膨胀(records_unique=1, links=1)
        self.assertIn('rows_hit（命中缓存行）：2', out.getvalue())
        self.assertIn('records_unique（去产品内重后）：1', out.getvalue())
        self.assertIn('refs_planned_new（计划新建）：1', out.getvalue())
        self.assertIn('links_to_create（计划新建）：1', out.getvalue())


# ──────────────────────────────────────────────────────────────────────────
# 5. 长度守卫
# ──────────────────────────────────────────────────────────────────────────
class AuditLengthGuardTest(TestCase):
    def test_length_guard(self):
        p = ProductFactory(catalog_no='AD5-1')
        _cache('bioz', 'AD5-1', [_bioz(
            'T' * 600, journal='J' * 300, doi='d' * 150, pmid='p' * 80)])
        # dry-run
        out = io.StringIO()
        call_command('adopt_cached_evidence', stdout=out)
        t = out.getvalue()
        self.assertIn('truncated_title：1', t)
        self.assertIn('truncated_journal：1', t)
        self.assertIn('dropped_long_doi：1', t)
        self.assertIn('dropped_long_pmid：1', t)
        # apply
        call_command('adopt_cached_evidence', '--apply')
        ref = Reference.objects.get()
        self.assertEqual(len(ref.title), 500)
        self.assertEqual(len(ref.journal), 255)
        self.assertIsNone(ref.doi)   # 过长被丢弃
        self.assertIsNone(ref.pmid)


# ──────────────────────────────────────────────────────────────────────────
# 6. 过期缓存两分支
# ──────────────────────────────────────────────────────────────────────────
class AuditStaleTest(TestCase):
    def test_expired_only_and_stale_only(self):
        p = ProductFactory(catalog_no='AD6-1')
        # 仅过期(expires_at 过去)但 is_stale=False
        _cache('bioz', 'AD6-1', [_bioz('Expired Only', doi='10.6/E')],
               expires_at=timezone.now() - timezone.timedelta(days=1))
        p2 = ProductFactory(catalog_no='AD6-2')
        # 仅 is_stale=True 但未过期
        _cache('bioz', 'AD6-2', [_bioz('Stale Only', doi='10.6/S')],
               stale=True, expires_in_days=5)
        out = io.StringIO()
        call_command('adopt_cached_evidence', stdout=out)
        t = out.getvalue()
        self.assertIn('rows_stale（过期仍用）：2', t)        # 两条都进 rows_stale
        self.assertIn('records_unique（去产品内重后）：2', t)  # 且都被使用


# ──────────────────────────────────────────────────────────────────────────
# 7. 参数边界
# ──────────────────────────────────────────────────────────────────────────
class AuditArgBoundariesTest(TestCase):
    def test_invalid_role_no_write(self):
        p = ProductFactory(catalog_no='AD7-1')
        _cache('bioz', 'AD7-1', [_bioz('X', doi='10.7/r')])
        rb = Reference.objects.count()
        with self.assertRaises(CommandError):
            call_command('adopt_cached_evidence', '--role', 'bogus')
        self.assertEqual(Reference.objects.count(), rb)

    def test_unknown_source_no_write(self):
        p = ProductFactory(catalog_no='AD7-2')
        _cache('bioz', 'AD7-2', [_bioz('X', doi='10.7/s')])
        rb = Reference.objects.count()
        with self.assertRaises(CommandError):
            call_command('adopt_cached_evidence', '--source', 'bogus')
        self.assertEqual(Reference.objects.count(), rb)

    def test_limit_zero(self):
        p = ProductFactory(catalog_no='AD7-3')
        _cache('bioz', 'AD7-3', [_bioz('X', doi='10.7/z')])
        out = io.StringIO()
        call_command('adopt_cached_evidence', '--limit', '0', stdout=out)
        self.assertIn('products_total（考虑产品总数）：0', out.getvalue())
        self.assertIn('refs_planned_new（计划新建）：0', out.getvalue())

    def test_only_products_missing(self):
        p = ProductFactory(catalog_no='AD7-4')
        _cache('bioz', 'AD7-4', [_bioz('X', doi='10.7/m')])
        out = io.StringIO()
        call_command('adopt_cached_evidence', '--only-products', 'NOPE', stdout=out)
        self.assertIn('products_total（考虑产品总数）：0', out.getvalue())

    def test_out_bad_dir(self):
        # --out 指向不存在目录：应在写库前抛 CommandError（无 DB 写入）。
        # 该缺陷已修（裸 FileNotFoundError → CommandError），故本用例断言修复后行为。
        p = ProductFactory(catalog_no='AD7-5')
        _cache('bioz', 'AD7-5', [_bioz('X', doi='10.7/d')])
        rb = Reference.objects.count()
        with self.assertRaises(CommandError):
            call_command('adopt_cached_evidence', '--out', '/no/such/dir/plan.jsonl')
        self.assertEqual(Reference.objects.count(), rb)  # 未写库


# ──────────────────────────────────────────────────────────────────────────
# 8. 幂等（apply 三次）
# ──────────────────────────────────────────────────────────────────────────
class AuditIdempotentTest(TestCase):
    def test_apply_3x(self):
        p = ProductFactory(catalog_no='AD8-1')
        _cache('bioz', 'AD8-1', [_bioz('Idem', doi='10.8/i')])
        call_command('adopt_cached_evidence', '--apply')
        ref1 = Reference.objects.count()
        link1 = ProductReference.objects.count()
        for _ in range(2):
            out = io.StringIO()
            call_command('adopt_cached_evidence', '--apply', stdout=out)
            self.assertIn('新建 Reference：预测 0 / 实际 0', out.getvalue())
            self.assertIn('新建关联 links：预测 0 / 实际 0', out.getvalue())
        self.assertEqual(Reference.objects.count(), ref1)
        self.assertEqual(ProductReference.objects.count(), link1)


# ──────────────────────────────────────────────────────────────────────────
# 10. 报告口径
# ──────────────────────────────────────────────────────────────────────────
class AuditReportMetricsTest(TestCase):
    def test_median_and_top20(self):
        cats = ['AD10-%d' % i for i in range(1, 5)]
        nrec = [1, 2, 3, 4]   # 有证据产品文献数 -> median 偶数应为 (2+3)/2=2.5
        for c, n in zip(cats, nrec):
            p = ProductFactory(catalog_no=c)
            _cache('bioz', c, [_bioz('R%d-%d' % (n, j), doi='10.10/%d-%d' % (n, j))
                               for j in range(n)])
        out = io.StringIO()
        call_command('adopt_cached_evidence', stdout=out)
        t = out.getvalue()
        self.assertIn('中位=2.5', t, "偶数个中位数应为均值 2.5")
        # Top20 应为降序：AD10-4(4) > AD10-3(3) > AD10-2(2) > AD10-1(1)
        order = [t.index('AD10-4'), t.index('AD10-3'),
                 t.index('AD10-2'), t.index('AD10-1')]
        self.assertEqual(order, sorted(order), "Top 排序非降序")
        # records_unique 自洽：sum per product unique = 1+2+3+4=10
        self.assertIn('records_unique（去产品内重后）：10', t)

    def test_raw_unique_dup_relation(self):
        p = ProductFactory(catalog_no='AD10-X')
        _cache('bioz', 'AD10-X', [
            _bioz('D1', doi='10.10/d1'),
            _bioz('D1', doi='10.10/d1'),   # 产品内完全重复
            _bioz('D2', doi='10.10/d2'),
        ])
        out = io.StringIO()
        call_command('adopt_cached_evidence', stdout=out)
        t = out.getvalue()
        self.assertIn('records_raw（原始记录数）：3', t)
        self.assertIn('dup_within_product（产品内重复）：1', t)
        self.assertIn('records_unique（去产品内重后）：2', t)

    def test_ref_buckets_identity(self):
        """文献三桶必须闭合：records_unique = 复用已有 + 复用计划 + 计划新建。

        跨产品共享同一篇新文献时，第二次出现走 restart 'reuse_planned' 分支——
        该分支此前不计数，导致报告口径不闭合（生产 dry-run 实测 174+154≠355）。
        """
        # 产品 A 与 B 指向同一篇新文献（DOI 相同）→ A 计划新建，B 复用计划
        for c in ('AD10-I1', 'AD10-I2'):
            p = ProductFactory(catalog_no=c)
            _cache('bioz', c, [_bioz('Shared', doi='10.10/shared')])
        out = io.StringIO()
        call_command('adopt_cached_evidence', stdout=out)
        t = out.getvalue()
        self.assertIn('refs_reused_from_db（复用已有）：0', t)
        self.assertIn('refs_reused_from_plan（复用本run计划新建）：1', t)
        self.assertIn('refs_planned_new（计划新建）：1', t)
        self.assertIn('records_unique（去产品内重后）：2', t)
        self.assertIn('（应为 2）', t, "口径自洽行缺失或不等")


# ──────────────────────────────────────────────────────────────────────────
# 9/11. 隐藏写路径 + 代码质量（静态 + 运行期）
# ──────────────────────────────────────────────────────────────────────────
class AuditHiddenWriteTest(TestCase):
    def test_no_direct_writes_in_command(self):
        import re
        src = open(__import__('apps.bridges.management.commands.adopt_cached_evidence',
                              fromlist=['x']).__file__, encoding='utf-8').read()
        # 命令体（非调用的 adopt_bioz_references）不应出现这些写操作
        for bad in ('.save(', 'update_or_create', 'DataSourceCache.objects.create',
                    'Reference.objects.create', 'ProductReference.objects.create'):
            self.assertNotIn(bad, src, f"命令内含隐藏写路径: {bad}")
        # 但必须调用 adopt_bioz_references
        self.assertIn('adopt_bioz_references', src)
