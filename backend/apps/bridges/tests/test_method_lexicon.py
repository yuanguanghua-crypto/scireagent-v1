# -*- coding: utf-8 -*-
"""P0#2 L1 词典匹配测试。

策略（用户决策 2026-09-01）：只做 L1 词典（不做 embedding），效果不行再走 LLM 提取。
铁律：宁 miss 不错配 —— STRONG 命中（>=2 特征词）才建桥；token 精确匹配非子串；
匹配文本仅用 Protocol.name（objective 噪音大，会放大误报）。
定稿（2026-09-01）：top5 特征词 + 跨方法共用词剔除（K=2）+ 扩充 STOP（先词干后 STOP，
修复复数停用词漏网 assays->assay）。
"""
from django.test import TestCase

from apps.bridges.models import MethodProtocol
from apps.bridges.services.method_lexicon import (
    _tokens, build_lexicon, match_protocol, annotate_orphan_protocols,
)
from apps.knowledge.tests.factories import MethodFactory, ProtocolFactory
from apps.bridges.tests.factories import MethodProtocolFactory


class BuildLexiconTest(TestCase):
    def test_discovers_strong_tokens_from_lexicon_auto(self):
        """从 lexicon_auto 历史桥挖掘特征词（PCR -> pcr/amplification 类）。"""
        method = MethodFactory(name='PCR')
        p1 = ProtocolFactory(name='PCR amplification of genomic DNA using primer pairs')
        p2 = ProtocolFactory(name='Amplification with PCR for bacterial 16S')
        MethodProtocolFactory(method=method, protocol=p1, evidence_source='lexicon_auto')
        MethodProtocolFactory(method=method, protocol=p2, evidence_source='lexicon_auto')
        lexicon = build_lexicon()
        self.assertIn(method.id, lexicon)
        self.assertIn('pcr', lexicon[method.id])

    def test_excludes_non_lexicon_sources(self):
        """manual_curated/legacy 桥不参与词典挖掘（词典=历史 lexicon_auto 同源）。"""
        method = MethodFactory(name='Western Blot')
        p = ProtocolFactory(name='western blotting of whole-cell lysates')
        MethodProtocolFactory(method=method, protocol=p, evidence_source='manual_curated')
        lexicon = build_lexicon()
        self.assertNotIn(method.id, lexicon)

    def test_cross_method_shared_words_excluded(self):
        """跨方法共用词（dna/pcr 同时进两个 Method 的 top 列表）被剔除（K=2）。"""
        m1 = MethodFactory(name='PCR')
        m2 = MethodFactory(name='Gel Electrophoresis')
        MethodProtocolFactory(
            method=m1, protocol=ProtocolFactory(name='PCR amplification of genomic DNA'),
            evidence_source='lexicon_auto',
        )
        MethodProtocolFactory(
            method=m1, protocol=ProtocolFactory(name='DNA amplification for sequencing'),
            evidence_source='lexicon_auto',
        )
        MethodProtocolFactory(
            method=m2, protocol=ProtocolFactory(name='DNA gel electrophoresis for separation'),
            evidence_source='lexicon_auto',
        )
        MethodProtocolFactory(
            method=m2, protocol=ProtocolFactory(name='agarose gel electrophoresis of PCR products'),
            evidence_source='lexicon_auto',
        )
        lexicon = build_lexicon()
        self.assertNotIn('dna', lexicon[m1.id])
        self.assertNotIn('dna', lexicon[m2.id])
        self.assertIn('amplification', lexicon[m1.id])
        self.assertIn('gel', lexicon[m2.id])


class MatchProtocolTest(TestCase):
    def test_strong_hit_two_tokens(self):
        """>=2 特征词命中（STRONG）。"""
        lexicon = {101: ['pcr', 'amplification', 'primer']}
        hits = match_protocol('PCR amplification protocol', lexicon)
        self.assertEqual(hits, [(101, 2)])

    def test_single_token_not_strong(self):
        """1 个特征词不构成 STRONG（宁 miss 不错配）。"""
        lexicon = {101: ['pcr', 'amplification', 'primer']}
        hits = match_protocol('general PCR introduction', lexicon)
        self.assertEqual(hits, [])

    def test_no_hit(self):
        lexicon = {101: ['pcr', 'amplification']}
        self.assertEqual(match_protocol('fruit ripening treatment', lexicon), [])

    def test_token_match_not_substring(self):
        """token 精确匹配：'rnaseq' 不得命中 'rna'。"""
        lexicon = {101: ['rna', 'isolation']}
        self.assertEqual(match_protocol('total rnaseq library', lexicon), [])

    def test_plural_stopword_never_feature(self):
        """复数停用词经词干化后必须被剔除（assays->assay 漏网已修复）。

        旧实现 STOP 检查在词干化之前：'assays' 先通过检查、词干化后变 'assay'，
        导致停用词进入词典/参与匹配，In vitro Assays 类协议误命中 Ubiquitination。
        """
        self.assertEqual(_tokens('PCR assays and protocols'), ['pcr'])
        self.assertEqual(_tokens('in vitro assay for protein detection'), ['protein'])
        # 匹配层回归：vitro/assay 即使出现在词典里也永远无法驱动 STRONG 命中
        lexicon = {101: ['vitro', 'assay', 'protein']}
        self.assertEqual(match_protocol('in vitro assay for protein detection', lexicon), [])

    def test_expanded_stopwords_generic_descriptors(self):
        """扩充 STOP（frozen/fresh/blood/serum 等语料伪影词）不进入特征词集合。"""
        self.assertEqual(_tokens('fresh frozen liver samples'), ['liver'])
        self.assertEqual(_tokens('serum from blood samples'), [])


class AnnotateOrphanProtocolsTest(TestCase):
    def setUp(self):
        self.method = MethodFactory(name='PCR')
        # 历史桥：喂词典（PCR -> pcr/amplification/primer）
        MethodProtocolFactory(
            method=self.method,
            protocol=ProtocolFactory(name='PCR amplification using standard primer sets'),
            evidence_source='lexicon_auto',
        )

    def test_dry_run_writes_nothing(self):
        """dry-run 只统计不落库。"""
        ProtocolFactory(name='PCR amplification of plasmid DNA with two primers')  # 悬空 STRONG
        stats = annotate_orphan_protocols(apply=False)
        self.assertEqual(stats['matched'], 1)
        self.assertEqual(stats['created'], 0)
        self.assertEqual(MethodProtocol.objects.count(), 1)  # 只有历史 1 条

    def test_apply_creates_bridge(self):
        """apply 落库：evidence_source=lexicon_auto, status=active, explicit=False。"""
        orphan = ProtocolFactory(name='PCR amplification of plasmid DNA with two primers')
        stats = annotate_orphan_protocols(apply=True)
        self.assertEqual(stats['created'], 1)
        mp = MethodProtocol.objects.get(method=self.method, protocol=orphan)
        self.assertEqual(mp.evidence_source, 'lexicon_auto')
        self.assertEqual(mp.status, 'active')
        self.assertFalse(mp.explicit)

    def test_skips_already_linked(self):
        """已关联协议不重复匹配。"""
        linked = ProtocolFactory(name='PCR amplification of plasmid DNA with two primers')
        MethodProtocolFactory(method=self.method, protocol=linked, evidence_source='lexicon_auto')
        stats = annotate_orphan_protocols(apply=True)
        self.assertEqual(stats['matched'], 0)
        self.assertEqual(stats['created'], 0)

    def test_no_hit_stays_orphan(self):
        ProtocolFactory(name='Banana ripening under ethylene treatment')
        stats = annotate_orphan_protocols(apply=True)
        self.assertEqual(stats['matched'], 0)
        self.assertEqual(stats['created'], 0)
