"""TDD: PubMed 文献检索模块
Tests for PubMed client and literature-based protocol recommender.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.services.pubmed_client import PubMedClient
from apps.knowledge.services.literature_recommender import LiteratureRecommender


class PubMedClientTest(TestCase):
    """PubMed API 客户端"""

    def test_client_can_be_instantiated(self):
        """PubMedClient 可创建"""
        client = PubMedClient()
        self.assertIsNotNone(client)

    @patch("apps.knowledge.services.pubmed_client.requests")
    def test_search_by_product_multi_strategy(self, mock_requests):
        """多策略搜索返回去重文献列表"""
        # mock 4 个搜索策略的响应（策略 1-3 空，策略 4 有结果）
        empty_resp = MagicMock(status_code=200, json=lambda: {
            "esearchresult": {"idlist": [], "count": "0"}
        })
        found_resp = MagicMock(status_code=200, json=lambda: {
            "esearchresult": {"idlist": ["111"], "count": "1"}
        })
        detail_resp = MagicMock(status_code=200, json=lambda: {
            "result": {
                "111": {
                    "uid": "111",
                    "title": "Using 5-Ethynyl-dUTP for cell proliferation",
                    "source": "Cell Reports",
                    "pubdate": "2025",
                    "authors": [{"name": "Brown A"}],
                },
                "uids": ["111"],
            }
        })
        # 4 个 ESearch + 1 个 ESummary
        mock_requests.get.side_effect = [
            empty_resp, empty_resp, empty_resp, found_resp, detail_resp
        ]
        client = PubMedClient()
        results = client.search_by_product(
            product_name="5-Ethynyl-dUTP",
            cas="111289-87-3",
            max_results=3,
        )
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["pmid"], "111")

    @patch("apps.knowledge.services.pubmed_client.requests")
    def test_search_no_results(self, mock_requests):
        """无结果返回空列表"""
        empty_resp = MagicMock(status_code=200, json=lambda: {
            "esearchresult": {"idlist": [], "count": "0"}
        })
        # 所有策略都返回空
        mock_requests.get.side_effect = [empty_resp, empty_resp, empty_resp, empty_resp]
        client = PubMedClient()
        results = client.search_by_product("XYZFakeCompound999", max_results=5)
        self.assertEqual(len(results), 0)

    def test_build_query_returns_list(self):
        """_build_query 返回搜索策略列表"""
        queries = PubMedClient()._build_query("5-Ethynyl-dUTP", "111289-87-3")
        self.assertIsInstance(queries, list)
        self.assertGreater(len(queries), 0)

    def test_build_query_no_cas(self):
        """无 CAS 时不包含 CAS 查询"""
        queries = PubMedClient()._build_query("TestProduct", None)
        # 应该生成第 1-3 种策略，没有第 4 种（CAS）
        self.assertGreater(len(queries), 0)

    def test_build_query_with_cas(self):
        """有 CAS 时生成 CAS 搜索策略"""
        queries = PubMedClient()._build_query("TestProduct", "123-45-6")
        # 应该包含 CAS 查询
        has_cas_query = any("123-45-6" in q for q in queries)
        self.assertTrue(has_cas_query, "CAS number should appear in one of the query strategies")

    def test_product_synonyms_exists(self):
        """常见产品有别名映射"""
        syns = PubMedClient()._get_synonyms("5-Ethynyl-dUTP")
        self.assertIn("EdU", syns)


class LiteratureRecommenderTest(TestCase):
    """文献驱动的知识链推荐器"""

    def test_recommender_can_be_instantiated(self):
        """LiteratureRecommender 可创建"""
        recommender = LiteratureRecommender()
        self.assertIsNotNone(recommender)

    @patch("apps.knowledge.services.literature_recommender.PubMedClient.search_by_product")
    def test_recommend_extracts_application(self, mock_search):
        """推荐器从文献提取应用场景"""
        mock_search.return_value = [
            {
                "pmid": "12345",
                "title": "Cell proliferation detection using 5-Ethynyl-dUTP",
                "source": "Nature Methods",
                "pubdate": "2024",
                "authors": ["Smith J"],
            },
            {
                "pmid": "67890",
                "title": "DNA damage repair study with EdU labeling",
                "source": "Cell",
                "pubdate": "2023",
                "authors": ["Lee K", "Wang L"],
            },
        ]
        recommender = LiteratureRecommender()
        product = ProductFactory(name="5-Ethynyl-dUTP", cas="111289-87-3")
        result = recommender.recommend(product, top_k=3)
        self.assertIsNotNone(result)
        self.assertIn("applications", result)
        self.assertIn("references", result)
        self.assertGreater(len(result["references"]), 0)
        all_apps = " ".join(result["applications"]).lower()
        self.assertTrue("cell" in all_apps or "dna" in all_apps or "label" in all_apps)

    @patch("apps.knowledge.services.literature_recommender.PubMedClient.search_by_product")
    def test_recommend_formats_references(self, mock_search):
        """推荐器输出引用格式的文献列表"""
        mock_search.return_value = [
            {"pmid": "12345", "title": "Title A", "source": "Journal A",
             "pubdate": "2024", "authors": ["Author A"], "doi": "10.1000/a"},
            {"pmid": "67890", "title": "Title B", "source": "Journal B",
             "pubdate": "2023", "authors": ["Author B", "Author C"]},
        ]
        recommender = LiteratureRecommender()
        product = ProductFactory(name="TestProduct", cas="00-00-0")
        result = recommender.recommend(product, top_k=2)
        for ref in result["references"]:
            self.assertIn("pmid", ref)
            self.assertIn("citation", ref)
            self.assertIn("title", ref)

    def test_no_product_name_returns_empty(self):
        """无产品名时返回空"""
        recommender = LiteratureRecommender()
        product = ProductFactory(name="", cas="")
        result = recommender.recommend(product)
        self.assertEqual(len(result["references"]), 0)
