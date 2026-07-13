"""TDD Phase 2: Protocol Recommender
Tests for BioProCorpus indexing, protocol retrieval, and product-to-protocol recommendations.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from apps.commerce.tests.factories import ProductFactory

from apps.knowledge.services.protocol_recommender import (
    BioProCorpusIndexer, ProtocolRetriever, ProtocolRecommender,
    get_shared_recommender, get_shared_retriever,
    expand_protocol_query, _merge_results,
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
