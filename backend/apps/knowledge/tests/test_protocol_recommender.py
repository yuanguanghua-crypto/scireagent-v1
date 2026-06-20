"""TDD Phase 2: Protocol Recommender
Tests for BioProCorpus indexing, protocol retrieval, and product-to-protocol recommendations.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from apps.commerce.tests.factories import ProductFactory

from apps.knowledge.services.protocol_recommender import (
    BioProCorpusIndexer, ProtocolRetriever, ProtocolRecommender,
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
