"""TDD Phase 1: Product Validator
Tests for product structure validation against external sources (PubChem, BioProCorpus).
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from apps.commerce.models import Product
from apps.commerce.tests.factories import ProductFactory


from apps.commerce.services.validators.product_validator import (
    ProductValidator, ValidationReport, PubChemClient,
)


class ProductValidatorTest(TestCase):
    """Core validator structure and instantiation."""

    # ── Cycle 1: Basic Structure ─────────────────────────────────

    def test_validator_can_be_instantiated(self):
        """校验器对象可创建"""
        validator = ProductValidator()
        self.assertIsNotNone(validator)

    def test_validate_returns_report_object(self):
        """调用 validate 返回 ValidationReport 实例"""
        validator = ProductValidator()
        product = ProductFactory(name="Test Compound")
        report = validator.validate(product)
        self.assertIsInstance(report, ValidationReport)
        self.assertEqual(report.status, "completed")


class PubChemClientTest(TestCase):
    """PubChem API 客户端测试（经 core.datasource_client.request_with_resilience）"""

    def test_pubchem_client_can_be_instantiated(self):
        """PubChemClient 可创建"""
        client = PubChemClient()
        self.assertIsNotNone(client)

    @patch("core.datasource_client.requests.request")
    def test_lookup_by_cas_success(self, mock_request):
        """通过 CAS 号查到化合物"""
        mock_request.return_value = MagicMock(status_code=200, json=lambda: {
            "PC_Compounds": [{"id": {"id": {"cid": 3672}}}]
        })
        client = PubChemClient()
        result = client.lookup_by_cas("156-57-0")
        self.assertIsNotNone(result)
        self.assertEqual(result["cid"], 3672)

    @patch("core.datasource_client.requests.request")
    def test_lookup_by_cas_not_found(self, mock_request):
        """无效 CAS 返回 None 不抛异常"""
        mock_request.return_value = MagicMock(status_code=404)
        client = PubChemClient()
        result = client.lookup_by_cas("000-00-0")
        self.assertIsNone(result)

    @patch("core.datasource_client.requests.request")
    def test_lookup_by_cas_network_error_returns_none(self, mock_request):
        """网络错误返回 None（被 PubChemClient 的 except 兜底）"""
        mock_request.side_effect = ConnectionError("Network error")
        client = PubChemClient()
        result = client.lookup_by_cas("156-57-0")
        self.assertIsNone(result)

    @patch("core.datasource_client.requests.request")
    def test_compare_smiles_match(self, mock_request):
        """SMILES 比对一致时返回 True"""
        mock_request.side_effect = [
            MagicMock(status_code=200, json=lambda: {
                "PC_Compounds": [{"id": {"id": {"cid": 3672}}}]
            }),
            MagicMock(status_code=200, json=lambda: {
                "PropertyTable": {"Properties": [{"CanonicalSMILES": "CCO"}]}
            }),
        ]
        client = PubChemClient()
        result = client.compare_smiles("CCO", cas="64-17-5")
        self.assertTrue(result["match"])
        self.assertEqual(result["cid"], 3672)

    @patch("core.datasource_client.requests.request")
    def test_compare_smiles_mismatch(self, mock_request):
        """SMILES 不一致时标记差异"""
        mock_request.side_effect = [
            MagicMock(status_code=200, json=lambda: {
                "PC_Compounds": [{"id": {"id": {"cid": 3672}}}]
            }),
            MagicMock(status_code=200, json=lambda: {
                "PropertyTable": {"Properties": [{"CanonicalSMILES": "CCO"}]}
            }),
        ]
        client = PubChemClient()
        result = client.compare_smiles("CCX", cas="64-17-5")
        self.assertFalse(result["match"])
        self.assertIn("smiles", result.get("mismatch_fields", []))


class BioProCorpusValidatorTest(TestCase):
    """BioProCorpus 交叉引用测试"""

    @patch("apps.commerce.services.validators.product_validator.BioProCorpusLookup")
    def test_product_found_in_bioprocorpus(self, mock_lookup):
        """产品名称在 BioProCorpus 中有匹配的协议"""
        mock_lookup.return_value.search.return_value = [
            {"title": "Click Chemistry with 5-Ethynyl-dUTP", "source": "Bio-protocol", "score": 0.85},
        ]
        product = ProductFactory(name="5-Ethynyl-dUTP")
        validator = ProductValidator()
        report = validator.validate(product)
        self.assertGreater(len(report.matched_protocols), 0)
        self.assertIn("5-Ethynyl", report.matched_protocols[0]["title"])

    @patch("apps.commerce.services.validators.product_validator.BioProCorpusLookup")
    def test_no_match_in_bioprocorpus(self, mock_lookup):
        """未匹配到时 matched_protocols 为空列表"""
        mock_lookup.return_value.search.return_value = []
        product = ProductFactory(name="XyzNonExistentCompound999")
        validator = ProductValidator()
        report = validator.validate(product)
        self.assertEqual(len(report.matched_protocols), 0)

    def test_bioprocorpus_lookup_returns_results_for_real_keyword(self):
        """真实索引：已知关键词返回非空匹配（验证不再是空壳）"""
        from apps.commerce.services.validators.product_validator import BioProCorpusLookup
        lookup = BioProCorpusLookup()
        results = lookup.search("Polyhydroxybutyrate", top_k=3)
        self.assertGreater(len(results), 0)
        self.assertIn('title', results[0])
        self.assertIn('source', results[0])

    def test_bioprocorpus_lookup_empty_query_returns_empty(self):
        """空 query 返回空列表"""
        from apps.commerce.services.validators.product_validator import BioProCorpusLookup
        lookup = BioProCorpusLookup()
        self.assertEqual(lookup.search(""), [])
        self.assertEqual(lookup.search(None), [])


class FullValidationTest(TestCase):
    """完整校验端到端测试"""

    @patch("apps.commerce.services.validators.product_validator.BioProCorpusLookup")
    @patch("core.datasource_client.requests.request")
    def test_validate_aggregates_all_checks(self, mock_request, mock_biocorpus):
        """validate 方法聚合所有维度校验结果"""
        mock_request.return_value = MagicMock(status_code=200, json=lambda: {
            "PC_Compounds": [{"id": {"id": {"cid": 3672}}}]
        })
        mock_biocorpus.return_value.search.return_value = [
            {"title": "Protocol for Ethanol", "source": "Bio-protocol", "score": 0.75},
        ]
        product = ProductFactory(cas="64-17-5", smiles="CCO", name="Ethanol")
        validator = ProductValidator()
        report = validator.validate(product)
        self.assertEqual(report.status, "completed")
        self.assertIsNotNone(report.pubchem_result)
        self.assertIsNotNone(report.bioprocorpus_result)

    def test_report_has_overall_verdict(self):
        """报告包含总体判定"""
        validator = ProductValidator()
        product = ProductFactory(name="Test Compound")
        report = validator.validate(product)
        self.assertIn(report.overall_match, [True, False])
