"""★ 2026-10-08 P2 可选增强闸门：`recompute_product` 改**真批量 upsert**后的等价性。

背景：B8 只消掉了"N 次提交"（268 次 commit → 1 次），循环体里**每个协议仍 2 条 SQL**
（`update_or_create` = SELECT + INSERT/UPDATE）。改为 `bulk_create(update_conflicts=True)`
后每批 1 条 UPSERT。本文件锁死改动**不引入任何行为变化**：

1. **写入值正确**：库中每行的 `relevance_score / score_a / score_b / tier / basis / literature_count`
   与**独立重算**的 `fuse_relevance(compute_axis_a…)` 一致
2. **★ `score_c` 保留语义**（R2 铁律）：`embedding_available()` 为假时**绝不抹平**库中已算好的 `score_c`
3. **时间戳语义**：二次重算 ⇒ `updated_at` 前进、`created_at` **不变**
4. **幂等**：重复重算 ⇒ 行数不变、无重复行
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.bridges.models import MethodProtocol, ProductMethod, ProductProtocol
from apps.bridges.services import relevance as REL
from apps.commerce.models import Product
from apps.knowledge.models import Method, Protocol

User = get_user_model()
USAGE = ('fluorescently labeled nucleotide analog used for direct enzymatic '
         'labeling and imaging of nucleotide probes')
PROTO_TEXTS = [
    'labeling of nucleotide analogs with fluorescent dyes for imaging',
    'click chemistry conjugation of labeled nucleotide probes',
    'imaging and detection of fluorescent labeled nucleotide analogs',
]


class RecomputeBulkUpsertTest(TestCase):
    def setUp(self):
        REL._load_vocab()
        self.method = Method.objects.create(name='Bulk method', slug='bulk-method', status='active')
        self.protocols = []
        for i, txt in enumerate(PROTO_TEXTS):
            p = Protocol.objects.create(
                name=f'Bulk protocol {i}', slug=f'bulk-proto-{i}', status='published', objective=txt)
            MethodProtocol.objects.create(method=self.method, protocol=p)
            self.protocols.append(p)

    def _mk_product(self, cat):
        p = Product.objects.create(name=f'Bulk {cat}', catalog_no=cat, slug=cat.lower(), usage=USAGE)
        ProductMethod.objects.create(product=p, method=self.method)
        return p

    def test_written_values_match_independent_recompute(self):
        """库中写入值 == 独立重算值（证明批量写没写错列/写错值）。"""
        prod = self._mk_product('E2E-BULK-1')
        with patch('apps.bridges.services.embedding_backend.embedding_available', return_value=False):
            n = REL.recompute_product(prod)
        self.assertEqual(n, len(self.protocols), '应写入桥可达且非零证据的全部协议')
        rows = ProductProtocol.objects.filter(product=prod)
        self.assertEqual(rows.count(), len(self.protocols))

        for row in rows:
            proto = row.protocol
            s_a = REL.compute_axis_a(prod, proto)
            s_b, lit_n = REL.compute_axis_b(prod, proto, bioz_lits={})
            fused = REL.fuse_relevance(score_a=s_a, score_b=s_b, score_c=row.score_c)
            self.assertAlmostEqual(row.score_a, fused['score_a'], places=6, msg='score_a')
            self.assertAlmostEqual(row.score_b, fused['score_b'], places=6, msg='score_b')
            self.assertAlmostEqual(row.relevance_score, fused['relevance_score'], places=6, msg='总分')
            self.assertEqual(row.tier, fused['tier'], 'tier')
            self.assertEqual(row.relevance_basis, fused['relevance_basis'], 'basis')
            self.assertEqual(row.literature_count, lit_n, 'literature_count')
            self.assertEqual(row.link_source, ProductProtocol.LinkSource.INHERITED, 'link_source')

    def test_score_c_preserved_when_embedding_unavailable(self):
        """★ R2 铁律：算不出轴C 时**绝不抹平**库中现值（离线作业算好的 score_c）。"""
        prod = self._mk_product('E2E-BULK-2')
        with patch('apps.bridges.services.embedding_backend.embedding_available', return_value=False):
            REL.recompute_product(prod)
        # 模拟"离线作业已回填 score_c"
        sentinel = 0.77
        ProductProtocol.objects.filter(product=prod).update(score_c=sentinel)
        # 再以 compute_c=False 重算 ⇒ 必须保留 0.77（而不是被写成 NULL）
        with patch('apps.bridges.services.embedding_backend.embedding_available', return_value=False):
            REL.recompute_product(prod)
        kept = list(ProductProtocol.objects.filter(product=prod).values_list('score_c', flat=True))
        self.assertEqual(kept, [sentinel] * len(self.protocols),
                         'compute_c=False 时必须保留库中 score_c（不得抹平）')

    def test_timestamps_and_idempotency(self):
        """二次重算：`updated_at` 前进、`created_at` 不变、行数不变（幂等）。"""
        prod = self._mk_product('E2E-BULK-3')
        with patch('apps.bridges.services.embedding_backend.embedding_available', return_value=False):
            REL.recompute_product(prod)
        created_before = list(ProductProtocol.objects.filter(product=prod)
                              .order_by('protocol_id').values_list('created_at', flat=True))
        first_updated = list(ProductProtocol.objects.filter(product=prod)
                             .order_by('protocol_id').values_list('updated_at', flat=True))

        with patch('apps.bridges.services.embedding_backend.embedding_available', return_value=False):
            n2 = REL.recompute_product(prod)   # 第二次 ⇒ 全 UPDATE 路径
        self.assertEqual(n2, len(self.protocols), '幂等：行数不变')
        self.assertEqual(ProductProtocol.objects.filter(product=prod).count(), len(self.protocols),
                         '幂等：无重复行（唯一约束 + update_conflicts 生效）')
        after = list(ProductProtocol.objects.filter(product=prod)
                     .order_by('protocol_id').values_list('created_at', 'updated_at'))
        self.assertEqual([r[0] for r in after], created_before, 'created_at 必须保持不变')
        self.assertTrue(all(r[1] >= u for r, u in zip(after, first_updated)),
                        'updated_at 不得回退')
