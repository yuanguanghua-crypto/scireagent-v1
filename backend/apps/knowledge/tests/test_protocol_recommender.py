"""TDD Phase 2: Protocol Recommender
Tests for BioProCorpus indexing, protocol retrieval, and product-to-protocol recommendations.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from apps.commerce.tests.factories import ProductFactory

from apps.knowledge.services.protocol_recommender import (
    BioProCorpusIndexer, ProtocolRetriever, ProtocolRecommender,
    get_shared_recommender, get_shared_retriever,
    expand_protocol_query, expand_protocol_query_tagged,
    core_name_tokens, _chemical_root_of, _merge_results,
)


class BioProCorpusIndexTest(TestCase):
    """BioProCorpus 索引构建测试"""

    # ── Cycle 5: Index Building ─────────────────────────────────

    def test_indexer_can_be_instantiated(self):
        """索引器可创建"""
        indexer = BioProCorpusIndexer(data_dir="/fake/path")
        self.assertIsNotNone(indexer)

    @patch("apps.knowledge.services.protocol_recommender.os.path.exists")
    @patch("apps.knowledge.services.protocol_recommender.os.listdir")
    @patch("apps.knowledge.services.protocol_recommender.open")
    def test_index_can_be_built_from_json(self, mock_open, mock_listdir, mock_exists):
        """从 BioProCorpus JSON 文件构建索引"""
        mock_exists.return_value = True
        mock_listdir.return_value = ["Bio-protocol.json"]
        mock_open.return_value.__enter__.return_value.read.return_value = (
            '[{"id":"p1","title":"Test Protocol","input":"step1\\nstep2","keywords":"test"}]'
        )
        indexer = BioProCorpusIndexer(data_dir="/fake/path")
        indexer.build()
        self.assertGreater(indexer.size(), 0)

    def test_index_scans_all_source_files(self):
        """索引可列出所有协议源"""
        indexer = BioProCorpusIndexer(data_dir="/fake/path")
        # 手动注入数据模拟索引构建
        indexer._entries = [
            {"id": "p1", "source": "Bio-protocol"},
            {"id": "p2", "source": "Protocol-exchange"},
            {"id": "p3", "source": "Protocol-io"},
        ]
        sources = indexer.list_sources()
        self.assertIn("Bio-protocol", sources)
        self.assertIn("Protocol-exchange", sources)
        self.assertIn("Protocol-io", sources)


class ProtocolRetrieverTest(TestCase):
    """语义检索测试"""

    # ── Cycle 6: Semantic Retrieval ─────────────────────────────

    def test_retriever_can_be_instantiated(self):
        """Retriever 可创建"""
        retriever = ProtocolRetriever()
        self.assertIsNotNone(retriever)

    def test_search_by_product_name_returns_top_k(self):
        """按产品名检索返回最相关的 K 条协议"""
        retriever = ProtocolRetriever()
        # 手动注入测试数据
        retriever.indexer._entries = [
            {"id": "p1", "title": "Click Chemistry with 5-Ethynyl-dUTP", "source": "Bio-protocol",
             "text": "This protocol uses 5-Ethynyl-dUTP for labeling.", "keywords": "click chemistry"},
            {"id": "p2", "title": "PCR Protocol", "source": "Protocol-exchange",
             "text": "Standard PCR amplification.", "keywords": "PCR"},
        ]
        results = retriever.search("5-Ethynyl-dUTP", top_k=3)
        self.assertLessEqual(len(results), 3)
        self.assertGreater(len(results), 0)
        self.assertGreater(results[0]["score"], 0)

    def test_search_results_ordered_by_score_desc(self):
        """检索结果按相关度从高到低排序"""
        retriever = ProtocolRetriever()
        retriever.indexer._entries = [
            {"id": "p1", "title": "Click Chemistry Protocol", "source": "Bio-protocol",
             "text": "Click chemistry click reaction click labeling click.", "keywords": "click chemistry"},
            {"id": "p2", "title": "PCR Protocol", "source": "Protocol-exchange",
             "text": "Standard PCR amplification.", "keywords": "PCR"},
        ]
        results = retriever.search("Click chemistry", top_k=5)
        self.assertGreater(len(results), 0)
        for i in range(len(results) - 1):
            self.assertGreaterEqual(results[i]["score"], results[i + 1]["score"])

    def test_search_no_match_returns_empty(self):
        """无匹配协议时返回空列表"""
        retriever = ProtocolRetriever()
        retriever.indexer._entries = [
            {"id": "p1", "title": "PCR Protocol", "source": "Bio-protocol",
             "text": "PCR amplification steps.", "keywords": "PCR"},
        ]
        results = retriever.search("XYZNonExistentProtocol", top_k=3)
        self.assertEqual(len(results), 0)


class ProtocolRecommenderTest(TestCase):
    """产品推荐协议测试"""

    # ── Cycle 7: Recommender ───────────────────────────────────

    def test_recommender_can_be_instantiated(self):
        """Recommender 可创建"""
        recommender = ProtocolRecommender()
        self.assertIsNotNone(recommender)

    def test_recommend_returns_relevant_protocols(self):
        """为给定产品推荐相关协议"""
        recommender = ProtocolRecommender()
        recommender.retriever.indexer._entries = [
            {"id": "p1", "title": "Click Chemistry Protocol", "source": "Bio-protocol",
             "text": "Using 5-Ethynyl-dUTP for click labeling.", "keywords": "click, Ethynyl"},
            {"id": "p2", "title": "PCR Protocol", "source": "Bio-protocol",
             "text": "Standard PCR.", "keywords": "PCR"},
        ]
        recommendations = recommender.recommend(product_name="5-Ethynyl-dUTP", top_k=3)
        self.assertGreater(len(recommendations), 0)
        for rec in recommendations:
            self.assertGreater(rec["relevance_score"], 0)

    def test_recommend_includes_match_context(self):
        """推荐结果包含匹配原因说明"""
        recommender = ProtocolRecommender()
        recommender.retriever.indexer._entries = [
            {"id": "p1", "title": "Copper Catalysis Protocol", "source": "Bio-protocol",
             "text": "Using CuSO4 as catalyst for click chemistry.", "keywords": "copper, CuSO4"},
        ]
        recs = recommender.recommend(product_name="CuSO4", top_k=1)
        self.assertIn("match_reason", recs[0])
        self.assertIsInstance(recs[0]["match_reason"], str)


class SharedSingletonTest(TestCase):
    """进程级共享单例测试（见 docs/DATASOURCE_RELIABILITY.md §7）

    验证 get_shared_retriever / get_shared_recommender 的单例语义，
    以及 recommender 复用 retriever 索引（避免两份 175MB 索引常驻）。
    """

    def test_shared_retriever_is_singleton(self):
        """get_shared_retriever 多次调用返回同一实例"""
        r1 = get_shared_retriever()
        r2 = get_shared_retriever()
        self.assertIs(r1, r2)

    def test_shared_recommender_is_singleton(self):
        """get_shared_recommender 多次调用返回同一实例"""
        m1 = get_shared_recommender()
        m2 = get_shared_recommender()
        self.assertIs(m1, m2)

    def test_shared_recommender_reuses_shared_retriever(self):
        """recommender 单例复用 retriever 单例（共享同一份索引）"""
        self.assertIs(get_shared_recommender().retriever, get_shared_retriever())


class ProtocolQueryExpansionTest(TestCase):
    """TDD #4：协议查询扩展增强。

    原始 search 只拿产品名整体检索，冷门精确名（如 5-Propargylamino-CTP）
    常返回 0。扩展：产品名碎片化（CTP / Propargyl）+ jena 分类路径领域关键词
    （nucleotide / labeling / click chemistry）+ 同义词，多查询合并去重。
    """

    def test_expand_includes_name_and_fragments(self):
        """扩展包含原始名 + 碎片化有意义的片段（CTP 等）"""
        qs = expand_protocol_query("5-Propargylamino-CTP")
        self.assertIn("5-Propargylamino-CTP", qs)
        self.assertIn("CTP", qs)
        self.assertTrue(any("propargyl" in q.lower() for q in qs), "fragment 'propargyl' missing")

    def test_expand_from_category_path_keywords(self):
        """从 jena 分类路径抽取领域关键词（nucleotide / labeling）"""
        path = ("Probes & Epigenetics | RNA/cRNA Labeling | "
                "Amine-modified Nucleotides | 5-Propargylamino-CTP")
        qs = expand_protocol_query("5-Propargylamino-CTP", category_path=path)
        self.assertIn("nucleotide", qs)
        self.assertIn("labeling", qs)

    def test_expand_short_fragments_dropped(self):
        """过短/无意义片段（'5'、'd'）应被丢弃，避免噪声"""
        qs = expand_protocol_query("5-dX")
        self.assertNotIn("5", qs)
        self.assertNotIn("d", qs)

    def test_expand_dedup_preserves_order(self):
        """同义重复（synonyms 与 name 片段相同）应去重"""
        qs = expand_protocol_query("CTP", synonyms=["ctp", "CTP"])
        self.assertEqual(qs, ["CTP"])

    def test_merge_dedup_by_id_keeps_max_score(self):
        """合并：同 id 取最高分，按分降序，截断 top_k"""
        r1 = [{"id": "p1", "title": "A", "source": "s", "score": 1.0}]
        r2 = [
            {"id": "p1", "title": "A", "source": "s", "score": 3.0},
            {"id": "p2", "title": "B", "source": "s", "score": 2.0},
        ]
        merged = _merge_results([r1, r2], top_k=10)
        self.assertEqual([m["id"] for m in merged], ["p1", "p2"])
        self.assertEqual(merged[0]["score"], 3.0)

    def test_recommend_expanded_finds_protocols_for_obscure_name(self):
        """SC8001 这类冷门精确名：扩展后必须能命中协议（原 search 返回 0）"""
        recommender = ProtocolRecommender()
        recommender.retriever.indexer._entries = [
            {"id": "p1", "title": "Click Chemistry Protocol", "source": "Bio-protocol",
             "text": "Using CTP for click labeling.", "keywords": "click chemistry, CTP"},
            {"id": "p2", "title": "RNA Labeling", "source": "Bio-protocol",
             "text": "nucleotide labeling.", "keywords": "RNA"},
        ]
        recs = recommender.recommend_expanded(
            "5-Propargylamino-CTP",
            category_path=("Probes & Epigenetics | RNA/cRNA Labeling | "
                           "Amine-modified Nucleotides | 5-Propargylamino-CTP"),
            top_k=5,
        )
        self.assertGreater(len(recs), 0, "expanded query should find protocols for SC8001")
        for rec in recs:
            self.assertGreater(rec["score"], 0)
            self.assertIn("matched_query", rec)


# ════════════════════════════════════════════════════════════════
# N-1：碎片化召回收紧 + 核心 token 回验 + match_reason
# ════════════════════════════════════════════════════════════════
class FragmentGateTest(TestCase):
    """DS 复测 `DS-A203-probe` 把 A203 / probe 当独立检索词，召回 5 条无关协议。

    修法：① 碎片必须过化学词根门；② 来自产品名的命中须含核心 token；
         ③ 每条结果写 match_reason + match_confidence。铁律：宁 miss 不错配。
    """

    # ── ① 化学词根门 ────────────────────────────────
    def test_generic_words_not_used_as_queries(self):
        """'probe' / 'A203' 都不得成为独立检索词（A203 只有编号、无化学身份）。"""
        qs = expand_protocol_query("DS-A203-probe")
        self.assertEqual(qs, ["DS-A203-probe"])

    def test_chemical_fragments_survive(self):
        """化学词根仍要保留：CTP 精确、Propargylamino 归到词根 propargyl。"""
        qs = expand_protocol_query("5-Propargylamino-CTP")
        self.assertIn("CTP", qs)
        self.assertTrue(any("propargyl" in q.lower() for q in qs))

    def test_other_generic_suffixes_dropped(self):
        """kit / solution / grade / hplc 这类通用词一律不当检索词。"""
        qs = expand_protocol_query("Biotin-Kit-Solution-Grade-HPLC")
        self.assertIn("Biotin", qs)
        for bad in ("Kit", "Solution", "Grade", "HPLC"):
            self.assertNotIn(bad, qs)

    def test_short_chemical_roots_are_exact_only(self):
        """长度 ≤4 的词根只做精确匹配，避免 amp→amplification 这类误扩。"""
        self.assertEqual(_chemical_root_of("CTP"), "CTP")
        self.assertIsNone(_chemical_root_of("amplification"))
        self.assertIsNone(_chemical_root_of("digital"))

    def test_long_root_allows_short_modifier_tail(self):
        """长度 ≥5 的词根允许带 ≤8 字符后缀：Biotinylated → biotin。"""
        self.assertEqual(_chemical_root_of("Biotinylated"), "biotin")
        self.assertEqual(
            _chemical_root_of("Propargylamino").lower(), "propargylamino")

    def test_tagged_expansion_marks_kinds(self):
        """tagged 版本必须区分 name / fragment / category / synonym。"""
        tagged = expand_protocol_query_tagged(
            "5-Propargylamino-CTP",
            category_path="RNA/cRNA Labeling | Amine-modified Nucleotides",
        )
        kinds = {t["kind"] for t in tagged}
        self.assertEqual(kinds, {"name", "fragment", "category"})

    # ── ② 核心 token 回验 ───────────────────────────
    def test_core_tokens_for_garbage_name(self):
        """'DS-A203-probe' 的核心 token 只有 a203（probe 非化学词根）。"""
        self.assertEqual(core_name_tokens("DS-A203-probe"), ["a203"])

    def test_core_tokens_for_real_product_name(self):
        """真实产品名取到化学词根 + 无编号 token。"""
        toks = core_name_tokens("5-Propargylamino-CTP")
        self.assertIn("ctp", toks)
        self.assertTrue(any("propargyl" in t for t in toks))

    def test_gate_drops_protocols_without_core_token(self):
        """★ 核心回归：整体名按通用词（labeling/reagent）命中的协议，
        若正文不含任何化学核心 token（propargyl）⇒ 判为错配丢弃。"""
        recommender = ProtocolRecommender()
        recommender.retriever.indexer._entries = [
            {"id": "noise", "title": "RNA Labeling Protocol", "source": "Bio-protocol",
             "text": "General labeling procedure for nucleic acids.", "keywords": "RNA"},
            {"id": "hit", "title": "Propargyl Labeling of DNA", "source": "Bio-protocol",
             "text": "Propargyl labeling chemistry.", "keywords": "propargyl"},
        ]
        recs = recommender.recommend_expanded("Propargyl labeling reagent", top_k=5)
        ids = [r["id"] for r in recs]
        self.assertNotIn("noise", ids, "不含核心 token propargyl，必须丢弃")
        self.assertIn("hit", ids, "含核心 token 的协议必须保留")

    def test_gate_exempts_category_sourced_results(self):
        """分类路径关键词来源豁免：产品自身分类命中不需过名字闸门。"""
        recommender = ProtocolRecommender()
        recommender.retriever.indexer._entries = [
            {"id": "cat", "title": "RNA Labeling Protocol", "source": "Bio-protocol",
             "text": "nucleotide labeling procedure.", "keywords": "RNA"},
        ]
        # 无分类路径 ⇒ 只靠产品名字面命中 ⇒ 被闸门丢掉
        self.assertEqual(
            recommender.recommend_expanded("Propargyl labeling reagent", top_k=5), [])
        # 给了分类路径 ⇒ 分类关键词命中且豁免 ⇒ 保留
        recs = recommender.recommend_expanded(
            "Propargyl labeling reagent",
            category_path="RNA Labeling | Nucleotides", top_k=5,
        )
        self.assertEqual([r["id"] for r in recs], ["cat"])

    def test_escape_hatch_disables_gate(self):
        """enforce_core_tokens=False 仅供排障对比，用于证明闸门确实生效。"""
        recommender = ProtocolRecommender()
        recommender.retriever.indexer._entries = [
            {"id": "noise", "title": "RNA Labeling Protocol", "source": "Bio-protocol",
             "text": "General labeling procedure.", "keywords": "RNA"},
        ]
        self.assertEqual(
            recommender.recommend_expanded("Propargyl labeling reagent", top_k=5), [])
        loose = recommender.recommend_expanded(
            "Propargyl labeling reagent", top_k=5, enforce_core_tokens=False)
        self.assertEqual([r["id"] for r in loose], ["noise"])

    # ── ③ match_reason / 置信度 ──────────────────────
    def test_match_reason_and_confidence_present(self):
        """每条结果必须带 match_reason / match_kind / match_confidence。"""
        recommender = ProtocolRecommender()
        recommender.retriever.indexer._entries = [
            {"id": "p1", "title": "Click Chemistry Protocol", "source": "Bio-protocol",
             "text": "Using CTP for click labeling.", "keywords": "click chemistry, CTP"},
        ]
        recs = recommender.recommend_expanded("5-Propargylamino-CTP", top_k=5)
        self.assertTrue(recs)
        for rec in recs:
            self.assertTrue(rec["match_reason"])
            self.assertIn(rec["match_kind"], ("name", "fragment", "category", "synonym"))
            self.assertIn(rec["match_confidence"], ("high", "medium", "low"))

    def test_fragment_sourced_result_is_low_confidence(self):
        """碎片猜出来的命中必须标 low，整体名命中标 high。"""
        recommender = ProtocolRecommender()
        recommender.retriever.indexer._entries = [
            {"id": "frag", "title": "CTP Labeling", "source": "Bio-protocol",
             "text": "labeling with CTP.", "keywords": "CTP"},
        ]
        recs = recommender.recommend_expanded("Unobtainium-CTP", top_k=5)
        self.assertTrue(recs)
        self.assertEqual(recs[0]["match_kind"], "fragment")
        self.assertEqual(recs[0]["match_confidence"], "low")
