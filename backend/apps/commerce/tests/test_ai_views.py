"""TDD: AI Tool API Endpoints

AUTO MATCH (enrich) 现已合并原 AI Tools 的 Validate 能力（chemical 段返回
mismatches / similar_compounds）。本文件测试保留的独立端点 + enrich 合并后的校验字段。
（原 /validate/、/recommend-protocols/、/recommend-literature/ 及其 -unsaved 端点已删除。）
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APIClient

from apps.commerce.models import Product
from apps.commerce.tests.factories import ProductFactory
from django.contrib.auth import get_user_model

User = get_user_model()


def _fake_validation_report(mismatches=None, similar_compounds=None):
    """构造 ProductValidator.validate 的假报告（仅 enrich 合并测试用）。"""
    report = MagicMock()
    report.status = "completed"
    report.pubchem_cid = None
    report.overall_match = True
    report.mismatches = mismatches or []
    report.similar_compounds = similar_compounds or []
    return report


class AIViewsAuthTest(TestCase):
    """保留的 AI 端点需要 admin 认证。"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin", password="adminpass123", email="admin@test.com"
        )

    def test_batch_validate_requires_auth(self):
        resp = self.client.post("/api/v1/products/batch-validate/", {"product_ids": [1]})
        self.assertEqual(resp.status_code, 401)

    def test_batch_recommend_literature_requires_auth(self):
        resp = self.client.post("/api/v1/products/batch-recommend-literature/", {"product_ids": [1]})
        self.assertEqual(resp.status_code, 401)

    def test_render_structure_requires_auth(self):
        resp = self.client.post("/api/v1/products/render-structure/", {"smiles": "CCO"})
        self.assertEqual(resp.status_code, 401)

    def test_import_protocol_requires_auth(self):
        resp = self.client.post("/api/v1/products/import-protocol/", {"protocol_title": "X"})
        self.assertEqual(resp.status_code, 401)

    def test_admin_user_allowed_batch_validate(self):
        self.client.force_authenticate(user=self.admin)
        with patch("core.datasource_client.requests.request") as mock_request:
            mock_request.return_value = MagicMock(status_code=404, headers={})
            mock_request.return_value.raise_for_status = lambda: None
            resp = self.client.post("/api/v1/products/batch-validate/", {"product_ids": [1]})
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.json()["success"])


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
        ids = [p.id for p in self.products]
        with patch("core.datasource_client.requests.request") as mock_request:
            mock_request.return_value = MagicMock(status_code=404, headers={})
            mock_request.return_value.raise_for_status = lambda: None
            resp = self.client.post("/api/v1/products/batch-validate/", {"product_ids": ids}, format="json")
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["data"]), 3)
        for r in data["data"]:
            self.assertIn("product_id", r)
            self.assertIn("validation", r)

    def test_batch_validate_empty_list(self):
        resp = self.client.post("/api/v1/products/batch-validate/", {"product_ids": []}, format="json")
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["data"]), 0)

    def test_batch_validate_skips_nonexistent_ids(self):
        real_id = self.products[0].id
        with patch("core.datasource_client.requests.request") as mock_request:
            mock_request.return_value = MagicMock(status_code=404, headers={})
            mock_request.return_value.raise_for_status = lambda: None
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
        resp = self.client.post(
            "/api/v1/products/batch-recommend-literature/",
            {"product_ids": []}, format="json"
        )
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["data"]), 0)


class ProductEnrichAPITest(TestCase):
    """一站式 enrich 端点测试 — POST /api/v1/products/enrich/（含合并的 AI Tools 校验能力）"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin_enrich", password="pass123", email="ae@test.com"
        )
        self.client.force_authenticate(user=self.admin)

    @patch("apps.commerce.services.validators.product_validator.ProductValidator.validate")
    @patch("apps.commerce.services.validators.pubchem_enhancer.PubChemEnhancer.resolve_to_properties")
    @patch("apps.knowledge.services.literature_recommender.LiteratureRecommender.recommend")
    @patch("apps.knowledge.services.protocol_recommender.ProtocolRecommender.recommend_expanded")
    def test_enrich_returns_all_sections(self, mock_proto, mock_lit, mock_chem, mock_validate):
        """一站式 enrich 返回 chemical + literature + protocols + jena + bioz，且 chemical 含合并的校验字段"""
        mock_validate.return_value = _fake_validation_report()
        mock_chem.return_value = {
            "source": "pubchem", "found": True, "cid": 2244,
            "properties": {
                "canonical_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O",
                "molecular_formula": "C9H8O4",
                "molecular_weight": 180.16,
                "synonyms": ["50-78-2", "2-Acetoxybenzoic acid"],
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
            {"id": "p1", "source": "Bio-protocol", "title": "Aspirin synthesis", "score": 1.0,
             "matched_query": "aspirin"},
        ]

        resp = self.client.post(
            "/api/v1/products/enrich/",
            {"product_name": "Aspirin"}, format="json"
        )
        data = resp.json()
        self.assertTrue(data["success"])
        result = data["data"]

        self.assertIn("chemical", result)
        self.assertTrue(result["chemical"]["found"])
        self.assertEqual(result["chemical"]["cid"], 2244)
        # 合并的 AI Tools 校验字段
        self.assertIn("mismatches", result["chemical"])
        self.assertIn("similar_compounds", result["chemical"])

        self.assertIn("literature", result)
        self.assertIn("applications", result["literature"])
        self.assertIn("protocols", result)
        self.assertEqual(len(result["protocols"]), 1)
        self.assertIn("jena", result, "enrich 返回应含 jena section")
        self.assertIsInstance(result["jena"], dict)
        self.assertIn("matched", result["jena"])
        self.assertIn("bioz", result, "enrich 返回应含 bioz section")
        self.assertIsInstance(result["bioz"], dict)
        self.assertIn("queried", result["bioz"])

    @patch("apps.commerce.services.validators.product_validator.ProductValidator.validate")
    @patch("apps.commerce.services.validators.pubchem_enhancer.PubChemEnhancer.resolve_to_properties")
    @patch("apps.knowledge.services.literature_recommender.LiteratureRecommender.recommend")
    @patch("apps.knowledge.services.protocol_recommender.ProtocolRecommender.recommend_expanded")
    def test_enrich_returns_validation_fields(self, mock_proto, mock_lit, mock_chem, mock_validate):
        """合并后：chemical 段返回真实的 mismatches 与 similar_compounds（原 AI Tools Validate 独有）"""
        mock_chem.return_value = {
            "source": "pubchem", "found": True, "cid": 2244,
            "properties": {"canonical_smiles": "CC(=O)O", "molecular_formula": "C2H4O2"},
            "cas_resolved": "64-19-7", "candidates": [],
        }
        mock_lit.return_value = {
            "applications": [], "methods": [], "references": [], "protocols": [],
            "matched_apps": [], "matched_methods": [],
            "unmatched_app_keywords": [], "unmatched_method_keywords": [],
        }
        mock_proto.return_value = []
        mock_validate.return_value = _fake_validation_report(
            mismatches=[{"field": "smiles", "expected": "X", "actual": "Y"}],
            similar_compounds=[{"cid": 123, "name": "Acetic acid derivative"}],
        )

        resp = self.client.post(
            "/api/v1/products/enrich/",
            {"product_name": "Acetic acid", "cas": "64-19-7", "smiles": "CC(=O)O"}, format="json"
        )
        data = resp.json()
        self.assertTrue(data["success"])
        chem = data["data"]["chemical"]
        self.assertEqual(len(chem["mismatches"]), 1)
        self.assertEqual(chem["mismatches"][0]["field"], "smiles")
        self.assertEqual(len(chem["similar_compounds"]), 1)
        self.assertEqual(chem["similar_compounds"][0]["cid"], 123)

    @patch("apps.commerce.services.validators.product_validator.ProductValidator.validate")
    @patch("apps.commerce.services.validators.pubchem_enhancer.PubChemEnhancer.resolve_to_properties")
    @patch("apps.knowledge.services.literature_recommender.LiteratureRecommender.recommend")
    @patch("apps.knowledge.services.protocol_recommender.ProtocolRecommender.recommend_expanded")
    def test_enrich_jena_matches_by_name_not_hijacked_by_cas_resolved(
        self, mock_proto, mock_lit, mock_chem, mock_validate
    ):
        """回归：仅填 name（无用户 CAS）时，jena 必须按名字匹配，绝不能用
        PubChem 误解析的 cas_resolved 当主键。

        生产 bug：N6-Benzyl-ATPγS 被 PubChem 误解为 toluene（CAS 2154-56-5，
        不在 jena 中），旧逻辑用该错误 CAS 当 jena 主键 → 永远 not matched，
        而真正能命中 NU-241 的名字反而轮不到。修复后应按名匹配到 NU-241。
        """
        mock_validate.return_value = _fake_validation_report()
        # PubChem 把 N6-Benzyl-ATPγS 误解析成 toluene（CAS 2154-56-5）
        mock_chem.return_value = {
            "source": "pubchem", "found": True, "cid": 123147,
            "properties": {"synonyms": ["N6-Benzyl-ATP-gamma-S"]},
            "cas_resolved": "2154-56-5",   # 错误 CAS，不能用于 jena 主键
            "candidates": [{"cid": 123147, "cas": "2154-56-5"}],
        }
        mock_lit.return_value = {
            "applications": [], "methods": [], "references": [], "protocols": [],
            "matched_apps": [], "matched_methods": [],
            "unmatched_app_keywords": [], "unmatched_method_keywords": [],
        }
        mock_proto.return_value = []

        resp = self.client.post(
            "/api/v1/products/enrich/",
            {"product_name": "N6-Benzyl-ATPγS"}, format="json"  # 仅 name，无 cas
        )
        data = resp.json()
        self.assertTrue(data["success"])
        jena = data["data"]["jena"]
        self.assertTrue(
            jena["matched"],
            "jena 应按名字 N6-Benzyl-ATPγS 匹配到 NU-241，而非被 toluene CAS 劫持",
        )
        self.assertEqual(jena["catalog_no"], "NU-241")
        self.assertEqual(jena["cas_number"], "944834-42-8")

    @patch("apps.commerce.services.validators.product_validator.ProductValidator.validate")
    def test_enrich_empty_name_returns_graceful(self, mock_validate):
        """空 product_name 不报错，返回空结果（且不触发 validator）"""
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
        self.assertIn("jena", result)
        self.assertIn("bioz", result)
        mock_validate.assert_not_called()

    @patch("apps.knowledge.services.bioz_pipeline.fetch_bioz_evidence")
    @patch("apps.commerce.services.validators.product_validator.ProductValidator.validate")
    @patch("apps.commerce.services.validators.pubchem_enhancer.PubChemEnhancer.resolve_to_properties")
    @patch("apps.knowledge.services.literature_recommender.LiteratureRecommender.recommend")
    @patch("apps.knowledge.services.protocol_recommender.ProtocolRecommender.recommend_expanded")
    def test_enrich_bioz_section_when_jena_hits(self, mock_proto, mock_lit, mock_chem, mock_validate, mock_bioz):
        mock_validate.return_value = _fake_validation_report()
        mock_chem.return_value = {
            "source": "pubchem", "found": True, "cid": 2244,
            "properties": {"synonyms": ["50-78-2"]},
            "cas_resolved": "50-78-2", "candidates": [],
        }
        mock_lit.return_value = {
            "applications": [], "methods": [], "references": [], "protocols": [],
            "matched_apps": [], "matched_methods": [],
            "unmatched_app_keywords": [], "unmatched_method_keywords": [],
        }
        mock_proto.return_value = []
        mock_bioz.return_value = {
            "queried": True, "vendor": "Jena Bioscience", "catalog_no": "NU-1138",
            "equivalence": "exact", "needs_review": False,
            "disclaimer": "文献基于同化学实体匹配...",
            "total": 1,
            "references": [{"article_title": "Test paper", "journal": "Nature"}],
        }

        resp = self.client.post(
            "/api/v1/products/enrich/",
            {"product_name": "dATP Solution", "cas": "1927-31-7"}, format="json"
        )
        data = resp.json()
        self.assertTrue(data["success"])
        bioz = data["data"]["bioz"]
        self.assertTrue(bioz["queried"])
        self.assertEqual(bioz["catalog_no"], "NU-1138")
        self.assertEqual(bioz["equivalence"], "exact")
        self.assertIn("disclaimer", bioz)
        self.assertEqual(len(bioz["references"]), 1)

    @patch("apps.knowledge.services.bioz_pipeline.fetch_bioz_evidence")
    @patch("apps.commerce.services.validators.product_validator.ProductValidator.validate")
    @patch("apps.commerce.services.validators.pubchem_enhancer.PubChemEnhancer.resolve_to_properties")
    @patch("apps.knowledge.services.literature_recommender.LiteratureRecommender.recommend")
    @patch("apps.knowledge.services.protocol_recommender.ProtocolRecommender.recommend_expanded")
    def test_enrich_bioz_failure_does_not_block(self, mock_proto, mock_lit, mock_chem, mock_validate, mock_bioz):
        mock_validate.return_value = _fake_validation_report()
        mock_chem.return_value = {
            "source": "pubchem", "found": True, "cid": 2244,
            "properties": {}, "cas_resolved": "50-78-2", "candidates": [],
        }
        mock_lit.return_value = {
            "applications": [], "methods": [], "references": [], "protocols": [],
            "matched_apps": [], "matched_methods": [],
            "unmatched_app_keywords": [], "unmatched_method_keywords": [],
        }
        mock_proto.return_value = []
        mock_bioz.side_effect = RuntimeError("bioz boom")

        resp = self.client.post(
            "/api/v1/products/enrich/",
            {"product_name": "Aspirin", "cas": "50-78-2"}, format="json"
        )
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["data"]["chemical"]["found"])
        self.assertIn("bioz", data["data"])

    def test_enrich_requires_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post(
            "/api/v1/products/enrich/",
            {"product_name": "Aspirin"}, format="json"
        )
        self.assertEqual(resp.status_code, 401)

    @patch("apps.commerce.services.validators.product_validator.ProductValidator.validate")
    @patch("apps.commerce.services.validators.pubchem_enhancer.PubChemEnhancer.resolve_to_properties")
    @patch("apps.knowledge.services.literature_recommender.LiteratureRecommender.recommend")
    @patch("apps.knowledge.services.protocol_recommender.ProtocolRecommender.recommend_expanded")
    def test_enrich_cas_searching(self, mock_proto, mock_lit, mock_chem, mock_validate):
        mock_validate.return_value = _fake_validation_report()
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
        resp = self.client.post("/api/v1/products/import-protocol/", payload, format="json")
        data = resp.json()
        self.assertTrue(data["success"], f"Import failed: {data}")
        result = data["data"]
        self.assertIsNotNone(result["method_id"])
        self.assertIsNotNone(result["protocol_id"])
        self.assertEqual(result["step_count"], 2)

    def test_import_protocol_idempotent(self):
        payload = {
            "protocol_title": "Idempotent Test Protocol",
            "protocol_url": "https://doi.org/10.21769/Test.unique123",
            "steps": [{"step_no": "1", "title": "Step 1", "body": "Do something."}],
        }
        resp1 = self.client.post("/api/v1/products/import-protocol/", payload, format="json")
        resp2 = self.client.post("/api/v1/products/import-protocol/", payload, format="json")
        self.assertEqual(resp1.json()["data"]["protocol_id"], resp2.json()["data"]["protocol_id"])

    def test_import_protocol_requires_auth(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post("/api/v1/products/import-protocol/", {"protocol_title": "Test"}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_import_protocol_no_title_returns_error(self):
        resp = self.client.post("/api/v1/products/import-protocol/", {"steps": []}, format="json")
        data = resp.json()
        self.assertFalse(data["success"])

    def test_import_protocol_creates_methodprotocol_bridge(self):
        from apps.bridges.models import MethodProtocol
        from apps.knowledge.models import Method, Protocol

        payload = {
            "method_name": "CuAAC Click Chemistry",
            "protocol_title": "CuAAC Bridge Test Protocol",
            "protocol_url": "https://doi.org/10.21769/BridgeTest.5555",
        }
        resp = self.client.post("/api/v1/products/import-protocol/", payload, format="json")
        data = resp.json()["data"]
        method = Method.objects.get(pk=data["method_id"])
        protocol = Protocol.objects.get(pk=data["protocol_id"])
        self.assertTrue(
            MethodProtocol.objects.filter(method=method, protocol=protocol).exists(),
            "MethodProtocol bridge must be created when importing a protocol",
        )

    def test_import_protocol_links_method_to_product_via_product_id(self):
        from apps.commerce.tests.factories import ProductFactory
        from apps.commerce.api.v1.serializers import ProductDetailSerializer
        from apps.bridges.models import ProductMethod, MethodProtocol
        from apps.knowledge.models import Method, Protocol

        product = ProductFactory()
        payload = {
            "method_name": "RNA Labeling",
            "protocol_title": "RNA Labeling Protocol Link",
            "protocol_url": "https://doi.org/10.21769/LinkTest.8888",
            "product_id": product.id,
        }
        resp = self.client.post("/api/v1/products/import-protocol/", payload, format="json")
        data = resp.json()["data"]
        method = Method.objects.get(pk=data["method_id"])
        protocol = Protocol.objects.get(pk=data["protocol_id"])

        self.assertTrue(
            ProductMethod.objects.filter(product=product, method=method).exists(),
            "Method must be linked to the product via ProductMethod",
        )
        self.assertTrue(
            MethodProtocol.objects.filter(method=method, protocol=protocol).exists(),
            "MethodProtocol bridge must be created",
        )
        serialized = ProductDetailSerializer(product).data
        self.assertIn(
            protocol.id, serialized["protocol_ids"],
            "Product protocol_ids must include the imported protocol after bridging",
        )

    def test_serializer_sync_protocol_bridges_creates_methodprotocol(self):
        from apps.commerce.tests.factories import ProductFactory
        from apps.commerce.api.v1.serializers import ProductCreateUpdateSerializer
        from apps.bridges.models import ProductMethod, MethodProtocol
        from apps.knowledge.models import Method, Protocol

        product = ProductFactory()
        method = Method.objects.create(name="Sync M", slug="sync-m", status="active")
        protocol = Protocol.objects.create(
            method=method, name="Sync P", slug="sync-p", status="published"
        )
        ProductMethod.objects.create(product=product, method=method)

        ser = ProductCreateUpdateSerializer(instance=product)
        ser._sync_protocol_bridges(product, [protocol.id])

        self.assertTrue(
            MethodProtocol.objects.filter(method=method, protocol=protocol).exists(),
            "_sync_protocol_bridges must create MethodProtocol for given protocol_ids",
        )
        ser._sync_protocol_bridges(product, [protocol.id])
        self.assertEqual(
            MethodProtocol.objects.filter(method=method, protocol=protocol).count(), 1
        )
