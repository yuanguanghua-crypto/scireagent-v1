"""TDD: AI Tool API Endpoints
Tests for product validation, protocol recommendation, and literature recommendation API endpoints.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APIClient

from apps.commerce.models import Product
from apps.commerce.tests.factories import ProductFactory
from django.contrib.auth import get_user_model

User = get_user_model()


class AIViewsAuthTest(TestCase):
    """All AI tool endpoints require admin authentication."""

    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory(name="Test Compound", cas="64-17-5", smiles="CCO")
        self.user = User.objects.create_user(
            username="testuser", password="testpass123"
        )
        self.admin = User.objects.create_superuser(
            username="admin", password="adminpass123", email="admin@test.com"
        )

    def test_validate_requires_auth(self):
        """POST /api/v1/products/<pk>/validate/ 需要认证"""
        resp = self.client.post(f"/api/v1/products/{self.product.id}/validate/")
        self.assertEqual(resp.status_code, 401)

    def test_recommend_protocols_requires_auth(self):
        """POST /api/v1/products/<pk>/recommend-protocols/ 需要认证"""
        resp = self.client.post(f"/api/v1/products/{self.product.id}/recommend-protocols/")
        self.assertEqual(resp.status_code, 401)

    def test_recommend_literature_requires_auth(self):
        """POST /api/v1/products/<pk>/recommend-literature/ 需要认证"""
        resp = self.client.post(f"/api/v1/products/{self.product.id}/recommend-literature/")
        self.assertEqual(resp.status_code, 401)

    def test_batch_validate_requires_auth(self):
        """POST /api/v1/products/batch-validate/ 需要认证"""
        resp = self.client.post("/api/v1/products/batch-validate/", {"product_ids": [1]})
        self.assertEqual(resp.status_code, 401)

    def test_batch_recommend_literature_requires_auth(self):
        """POST /api/v1/products/batch-recommend-literature/ 需要认证"""
        resp = self.client.post("/api/v1/products/batch-recommend-literature/", {"product_ids": [1]})
        self.assertEqual(resp.status_code, 401)

    def test_regular_user_denied_access(self):
        """普通用户不应有权限访问 AI 工具"""
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(f"/api/v1/products/{self.product.id}/validate/")
        self.assertEqual(resp.status_code, 403)

    def test_admin_user_allowed(self):
        """管理员可以访问 AI 工具"""
        self.client.force_authenticate(user=self.admin)
        # 因为会调用外部服务，这里用 mock 避免实际网络请求
        with patch("apps.commerce.services.validators.product_validator.BioProCorpusLookup.search", return_value=[]):
            with patch("apps.commerce.services.validators.product_validator.requests.get") as mock_get:
                mock_get.return_value.status_code = 404
                resp = self.client.post(f"/api/v1/products/{self.product.id}/validate/")
                self.assertEqual(resp.status_code, 200)
                self.assertTrue(resp.json()["success"])


class ProductValidateAPITest(TestCase):
    """产品校验 API 测试"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin2", password="adminpass123", email="admin2@test.com"
        )
        self.client.force_authenticate(user=self.admin)
        self.product = ProductFactory(
            name="Ethanol", cas="64-17-5", smiles="CCO", formula="C2H6O"
        )

    def test_validate_returns_envelope_format(self):
        """校验 API 返回 envelope 格式"""
        with patch("apps.commerce.services.validators.product_validator.requests.get") as mock_get:
            mock_get.return_value.status_code = 404
            resp = self.client.post(f"/api/v1/products/{self.product.id}/validate/")
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertIn("data", data)
        self.assertIn("meta", data)

    def test_validate_returns_product_info(self):
        """校验 API 返回产品基本信息"""
        with patch("apps.commerce.services.validators.product_validator.requests.get") as mock_get:
            mock_get.return_value.status_code = 404
            resp = self.client.post(f"/api/v1/products/{self.product.id}/validate/")
        result = resp.json()["data"]
        self.assertEqual(result["product"]["name"], "Ethanol")
        self.assertEqual(result["product"]["cas"], "64-17-5")

    def test_validate_returns_pubchem_section(self):
        """校验 API 返回 PubChem 校验结果"""
        with patch("apps.commerce.services.validators.product_validator.requests.get") as mock_get:
            mock_get.return_value.status_code = 404
            resp = self.client.post(f"/api/v1/products/{self.product.id}/validate/")
        result = resp.json()["data"]
        self.assertIn("pubchem", result)

    def test_validate_returns_bioprocorpus_section(self):
        """校验 API 返回 BioProCorpus 检索结果"""
        with patch("apps.commerce.services.validators.product_validator.requests.get") as mock_get:
            mock_get.return_value.status_code = 404
            resp = self.client.post(f"/api/v1/products/{self.product.id}/validate/")
        result = resp.json()["data"]
        self.assertIn("bioprocorpus", result)

    def test_validate_returns_overall_match(self):
        """校验 API 返回 overall_match 判定"""
        with patch("apps.commerce.services.validators.product_validator.requests.get") as mock_get:
            mock_get.return_value.status_code = 404
            resp = self.client.post(f"/api/v1/products/{self.product.id}/validate/")
        result = resp.json()["data"]
        self.assertIn("overall_match", result)

    def test_validate_nonexistent_product_returns_404(self):
        """校验不存在产品返回 404"""
        resp = self.client.post("/api/v1/products/99999/validate/")
        self.assertEqual(resp.status_code, 404)


class ProductRecommendProtocolsAPITest(TestCase):
    """协议推荐 API 测试"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin3", password="adminpass123", email="admin3@test.com"
        )
        self.client.force_authenticate(user=self.admin)
        self.product = ProductFactory(name="Click Chemistry Reagent")

    @patch("apps.knowledge.services.protocol_recommender.ProtocolRetriever.search")
    def test_recommend_protocols_returns_list(self, mock_search):
        """协议推荐 API 返回列表"""
        mock_search.return_value = [
            {"id": "P1", "title": "Click Chemistry Protocol", "source": "Bio-protocol", "score": 3.5, "text_snippet": "..."}
        ]
        resp = self.client.post(f"/api/v1/products/{self.product.id}/recommend-protocols/")
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertIsInstance(data["data"], list)
        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["data"][0]["protocol"]["title"], "Click Chemistry Protocol")

    @patch("apps.knowledge.services.protocol_recommender.ProtocolRetriever.search")
    def test_recommend_protocols_has_relevance_score(self, mock_search):
        """协议推荐包含相关度分数"""
        mock_search.return_value = [
            {"id": "P1", "title": "Test Protocol", "source": "Bio-protocol", "score": 4.2, "text_snippet": "..."}
        ]
        resp = self.client.post(f"/api/v1/products/{self.product.id}/recommend-protocols/")
        result = resp.json()["data"][0]
        self.assertIn("relevance_score", result)

    @patch("apps.knowledge.services.protocol_recommender.ProtocolRetriever.search")
    def test_recommend_protocols_empty_result(self, mock_search):
        """无匹配协议时返回空列表"""
        mock_search.return_value = []
        resp = self.client.post(f"/api/v1/products/{self.product.id}/recommend-protocols/")
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["data"]), 0)

    def test_recommend_protocols_nonexistent_product_returns_404(self):
        """不存在的产品返回 404"""
        resp = self.client.post("/api/v1/products/99999/recommend-protocols/")
        self.assertEqual(resp.status_code, 404)


class ProductRecommendLiteratureAPITest(TestCase):
    """文献推荐 API 测试"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin4", password="adminpass123", email="admin4@test.com"
        )
        self.client.force_authenticate(user=self.admin)
        self.product = ProductFactory(name="dATP Labeling Reagent", cas="73449-06-6")

    @patch("apps.knowledge.services.literature_recommender.LiteratureRecommender.recommend")
    def test_recommend_literature_returns_all_sections(self, mock_recommend):
        """文献推荐 API 返回 applications/methods/references/protocols 四个 section"""
        mock_recommend.return_value = {
            "applications": ["dna_labeling", "imaging"],
            "methods": ["click_chemistry", "labeling"],
            "references": [
                {
                    "pmid": "12345678",
                    "title": "DNA labeling with modified dATP",
                    "source": "Nucleic Acids Res",
                    "pubdate": "2024",
                    "authors": ["Smith J", "Jones K"],
                    "doi": "10.1234/xyz",
                    "citation": "Smith J, Jones K (2024). DNA labeling with modified dATP. Nucleic Acids Res.",
                }
            ],
            "protocols": [],
        }
        resp = self.client.post(f"/api/v1/products/{self.product.id}/recommend-literature/")
        data = resp.json()
        self.assertTrue(data["success"])
        result = data["data"]
        self.assertIn("applications", result)
        self.assertIn("methods", result)
        self.assertIn("references", result)
        self.assertIn("protocols", result)
        self.assertEqual(len(result["applications"]), 2)
        self.assertEqual(len(result["references"]), 1)

    @patch("apps.knowledge.services.literature_recommender.LiteratureRecommender.recommend")
    def test_recommend_literature_empty_result(self, mock_recommend):
        """无文献时返回空结果"""
        mock_recommend.return_value = {
            "applications": [], "methods": [], "references": [], "protocols": []
        }
        resp = self.client.post(f"/api/v1/products/{self.product.id}/recommend-literature/")
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["data"]["references"]), 0)

    def test_recommend_literature_nonexistent_product_returns_404(self):
        """不存在的产品返回 404"""
        resp = self.client.post("/api/v1/products/99999/recommend-literature/")
        self.assertEqual(resp.status_code, 404)


class BatchValidateAPITest(TestCase):
    """批量校验 API 测试"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin5", password="adminpass123", email="admin5@test.com"
        )
        self.client.force_authenticate(user=self.admin)
        self.products = [
            ProductFactory(name=f"Product {i}", cas=f"{10000+i:05d}-00-0", smiles="CCO")
            for i in range(3)
        ]

    def test_batch_validate_returns_results_for_all_ids(self):
        """批量校验返回所有产品的结果"""
        ids = [p.id for p in self.products]
        with patch("apps.commerce.services.validators.product_validator.requests.get") as mock_get:
            mock_get.return_value.status_code = 404
            resp = self.client.post("/api/v1/products/batch-validate/", {"product_ids": ids}, format="json")
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["data"]), 3)
        for r in data["data"]:
            self.assertIn("product_id", r)
            self.assertIn("validation", r)

    def test_batch_validate_empty_list(self):
        """空产品列表返回空数组"""
        resp = self.client.post("/api/v1/products/batch-validate/", {"product_ids": []}, format="json")
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["data"]), 0)

    def test_batch_validate_skips_nonexistent_ids(self):
        """不存在的 ID 被跳过"""
        real_id = self.products[0].id
        with patch("apps.commerce.services.validators.product_validator.requests.get") as mock_get:
            mock_get.return_value.status_code = 404
            resp = self.client.post(
                "/api/v1/products/batch-validate/",
                {"product_ids": [real_id, 99999]}, format="json"
            )
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["data"][0]["product_id"], real_id)


class BatchRecommendLiteratureAPITest(TestCase):
    """批量文献推荐 API 测试"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin6", password="adminpass123", email="admin6@test.com"
        )
        self.client.force_authenticate(user=self.admin)
        self.products = [
            ProductFactory(name=f"Reagent {i}", cas=f"{20000+i:05d}-00-0")
            for i in range(2)
        ]

    @patch("apps.knowledge.services.literature_recommender.LiteratureRecommender.recommend")
    def test_batch_literature_returns_results(self, mock_recommend):
        """批量文献推荐返回所有产品结果"""
        mock_recommend.return_value = {
            "applications": ["imaging"], "methods": ["pcr"],
            "references": [], "protocols": []
        }
        ids = [p.id for p in self.products]
        resp = self.client.post(
            "/api/v1/products/batch-recommend-literature/",
            {"product_ids": ids}, format="json"
        )
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["data"]), 2)

    def test_batch_literature_empty_list(self):
        """空列表返回空数组"""
        resp = self.client.post(
            "/api/v1/products/batch-recommend-literature/",
            {"product_ids": []}, format="json"
        )
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["data"]), 0)


class UnsavedProductAIViewsTest(TestCase):
    """AI 工具 unsaved 端点 — 新建页无需 productId。

    三个服务都只依赖 name/cas/smiles 字段，不访问数据库。
    """

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin_unsaved", password="pass123", email="au@test.com"
        )
        self.client.force_authenticate(user=self.admin)

    def test_validate_unsaved_requires_name(self):
        """缺 name → error 响应"""
        resp = self.client.post("/api/v1/products/validate-unsaved/", {}, format="json")
        data = resp.json()
        self.assertFalse(data["success"])

    def test_validate_unsaved_with_name_only(self):
        """只传 name（无 CAS）→ 返回 completed，不触发 PubChem 网络请求"""
        with patch("apps.commerce.services.validators.product_validator.BioProCorpusLookup.search", return_value=[]):
            resp = self.client.post(
                "/api/v1/products/validate-unsaved/",
                {"name": "Test Compound"}, format="json"
            )
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["status"], "completed")
        self.assertEqual(data["data"]["product"]["name"], "Test Compound")
        self.assertIsNone(data["data"]["product"]["id"])

    @patch("apps.knowledge.services.protocol_recommender.ProtocolRetriever.search")
    def test_recommend_protocols_unsaved_returns_list(self, mock_search):
        """recommend-protocols-unsaved 用 name 返回推荐列表"""
        mock_search.return_value = [
            {"id": "P1", "title": "Click Chemistry Protocol",
             "source": "Bio-protocol", "score": 2.0, "text_snippet": "..."}
        ]
        resp = self.client.post(
            "/api/v1/products/recommend-protocols-unsaved/",
            {"name": "Click Chemistry Reagent"}, format="json"
        )
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["data"][0]["protocol"]["title"], "Click Chemistry Protocol")

    @patch("apps.knowledge.services.literature_recommender.LiteratureRecommender.recommend")
    def test_recommend_literature_unsaved_returns_sections(self, mock_recommend):
        """recommend-literature-unsaved 用 name 返回四 section 结构"""
        mock_recommend.return_value = {
            "applications": ["imaging"], "methods": ["pcr"],
            "references": [], "protocols": [],
            "matched_methods": [], "matched_apps": [],
            "unmatched_method_keywords": [], "unmatched_app_keywords": [],
        }
        resp = self.client.post(
            "/api/v1/products/recommend-literature-unsaved/",
            {"name": "dATP Labeling Reagent"}, format="json"
        )
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertIn("applications", data["data"])
        self.assertIn("references", data["data"])

    def test_unsaved_views_require_admin(self):
        """非 admin 用户 → 403"""
        user = User.objects.create_user(username="normal_user", password="pass123")
        self.client.force_authenticate(user=user)
        resp = self.client.post(
            "/api/v1/products/validate-unsaved/",
            {"name": "X"}, format="json"
        )
        self.assertEqual(resp.status_code, 403)


class ProductEnrichAPITest(TestCase):
    """一站式 enrich 端点测试 — POST /api/v1/products/enrich/"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin_enrich", password="pass123", email="ae@test.com"
        )
        self.client.force_authenticate(user=self.admin)

    @patch("apps.commerce.services.validators.pubchem_enhancer.PubChemEnhancer.resolve_to_properties")
    @patch("apps.knowledge.services.literature_recommender.LiteratureRecommender.recommend")
    @patch("apps.knowledge.services.protocol_recommender.ProtocolRecommender.recommend")
    def test_enrich_returns_all_sections(self, mock_proto, mock_lit, mock_chem):
        """一站式 enrich 返回 chemical + literature + protocols"""
        mock_chem.return_value = {
            "source": "pubchem", "found": True, "cid": 2244,
            "properties": {
                "canonical_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
                "molecular_formula": "C9H8O4",
                "molecular_weight": 180.16,
            },
            "cas_resolved": "50-78-2",
            "candidates": [],
        }
        mock_lit.return_value = {
            "applications": ["imaging"], "methods": ["pcr"],
            "references": [], "protocols": [],
            "matched_apps": [], "matched_methods": [],
            "unmatched_app_keywords": [], "unmatched_method_keywords": [],
        }
        mock_proto.return_value = [
            {"protocol": {"title": "Aspirin synthesis", "source": "Bio-protocol"}},
        ]

        resp = self.client.post(
            "/api/v1/products/enrich/",
            {"product_name": "Aspirin"}, format="json"
        )
        data = resp.json()
        self.assertTrue(data["success"])
        result = data["data"]

        # Chemical
        self.assertIn("chemical", result)
        self.assertTrue(result["chemical"]["found"])
        self.assertEqual(result["chemical"]["cid"], 2244)

        # Literature
        self.assertIn("literature", result)
        self.assertIn("applications", result["literature"])

        # Protocols
        self.assertIn("protocols", result)
        self.assertEqual(len(result["protocols"]), 1)

    def test_enrich_empty_name_returns_graceful(self):
        """空 product_name 不报错，返回空结果"""
        resp = self.client.post(
            "/api/v1/products/enrich/",
            {"product_name": ""}, format="json"
        )
        data = resp.json()
        self.assertTrue(data["success"])
        result = data["data"]
        self.assertFalse(result["chemical"].get("found", False))
        self.assertEqual(result["literature"]["references"], [])
        self.assertEqual(result["protocols"], [])

    def test_enrich_requires_auth(self):
        """enrich 端点需要认证"""
        self.client.force_authenticate(user=None)  # remove auth
        resp = self.client.post(
            "/api/v1/products/enrich/",
            {"product_name": "Aspirin"}, format="json"
        )
        self.assertEqual(resp.status_code, 401)

    @patch("apps.commerce.services.validators.pubchem_enhancer.PubChemEnhancer.resolve_to_properties")
    @patch("apps.knowledge.services.literature_recommender.LiteratureRecommender.recommend")
    @patch("apps.knowledge.services.protocol_recommender.ProtocolRecommender.recommend")
    def test_enrich_cas_searching(self, mock_proto, mock_lit, mock_chem):
        """传 CAS 时用 CAS 搜索（更精确）"""
        mock_chem.return_value = {
            "source": "pubchem", "found": True, "cid": 2244,
            "properties": {"molecular_formula": "C9H8O4", "molecular_weight": 180.16},
            "cas_resolved": "50-78-2", "candidates": [],
        }
        mock_lit.return_value = {
            "applications": [], "methods": [], "references": [], "protocols": [],
            "matched_apps": [], "matched_methods": [],
            "unmatched_app_keywords": [], "unmatched_method_keywords": [],
        }
        mock_proto.return_value = []

        resp = self.client.post(
            "/api/v1/products/enrich/",
            {"product_name": "Aspirin", "cas": "50-78-2"}, format="json"
        )
        data = resp.json()
        self.assertTrue(data["success"])

        # CAS 应作为 primary identifier 传给 resolve_to_properties
        call_args = mock_chem.call_args
        self.assertEqual(call_args[0][0], "50-78-2")


class ProductImportProtocolAPITest(TestCase):
    """POST /api/v1/products/import-protocol/ 测试"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin_import_p", password="pass123", email="aip@test.com"
        )
        self.client.force_authenticate(user=self.admin)

    def test_import_protocol_creates_method_and_protocol(self):
        """导入协议 → 创建 Method + Protocol + Steps"""
        payload = {
            "method_name": "CuAAC Click Chemistry",
            "protocol_title": "CuAAC RNA Fluorescent Labeling Protocol",
            "protocol_url": "https://doi.org/10.21769/BioProtoc.9999",
            "objective": "Label RNA with fluorescent dyes using CuAAC click chemistry.",
            "reagents": "1. CuSO4 (Sigma, C8027)\n2. Ascorbic acid (Sigma, A5960)",
            "equipment": "1. Thermocycler\n2. Fluorescence Microscope",
            "steps": [
                {"step_no": "1.1", "title": "Preparation", "body": "Prepare reaction mix."},
                {"step_no": "1.2", "title": "Incubation", "body": "Incubate at 37C for 30 min."},
            ],
        }
        resp = self.client.post(
            "/api/v1/products/import-protocol/",
            payload, format="json"
        )
        data = resp.json()
        self.assertTrue(data["success"], f"Import failed: {data}")
        result = data["data"]
        self.assertIsNotNone(result["method_id"])
        self.assertIsNotNone(result["protocol_id"])
        self.assertEqual(result["step_count"], 2)

    def test_import_protocol_idempotent(self):
        """同一 DOI 导入两次 → 不重复创建 Protocol"""
        payload = {
            "protocol_title": "Idempotent Test Protocol",
            "protocol_url": "https://doi.org/10.21769/Test.unique123",
            "steps": [{"step_no": "1", "title": "Step 1", "body": "Do something."}],
        }
        resp1 = self.client.post("/api/v1/products/import-protocol/", payload, format="json")
        resp2 = self.client.post("/api/v1/products/import-protocol/", payload, format="json")
        self.assertEqual(resp1.json()["data"]["protocol_id"], resp2.json()["data"]["protocol_id"])

    def test_import_protocol_requires_auth(self):
        """import-protocol 需要认证"""
        self.client.force_authenticate(user=None)
        resp = self.client.post(
            "/api/v1/products/import-protocol/",
            {"protocol_title": "Test"}, format="json"
        )
        self.assertEqual(resp.status_code, 401)

    def test_import_protocol_no_title_returns_error(self):
        """缺 protocol_title → error"""
        resp = self.client.post(
            "/api/v1/products/import-protocol/",
            {"steps": []}, format="json"
        )
        data = resp.json()
        self.assertFalse(data["success"])
