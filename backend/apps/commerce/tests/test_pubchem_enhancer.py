"""TDD: PubChemEnhancer + ChEMBL fallback + RDKit rendering

Tests for:
- RDKit SMILES canonicalization, SVG rendering
- ChEMBL REST API fallback when PubChem misses CAS
- Schema consistency between PubChem and ChEMBL responses
"""
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.core.cache import cache

User = get_user_model()

from apps.commerce.services.validators.pubchem_enhancer import PubChemEnhancer


class RDKitAvailabilityTest(TestCase):
    """RDKit 安装验证"""

    def test_rdkit_imports_successfully(self):
        """RDKit 可导入且基础 API 正常"""
        from rdkit import Chem
        from rdkit.Chem import Draw
        self.assertTrue(hasattr(Chem, 'MolFromSmiles'))
        self.assertTrue(hasattr(Chem, 'MolToSmiles'))
        self.assertTrue(hasattr(Draw, 'MolDraw2DSVG'))

    def test_smiles_canonicalize_basic(self):
        """SMILES 标准化：简单分子"""
        from rdkit import Chem
        m = Chem.MolFromSmiles('CCO')
        self.assertIsNotNone(m)
        canonical = Chem.MolToSmiles(m, canonical=True)
        self.assertEqual(canonical, 'CCO')

    def test_smiles_canonicalize_stereochemistry(self):
        """SMILES 标准化：含立体化学的复杂 SMILES"""
        from rdkit import Chem
        smiles = "C1C[C@@H](O[C@@H]1COP(=O)(O)OP(=O)(O)OP(=O)(O)O)N2C=CC(=O)NC2=O"
        m = Chem.MolFromSmiles(smiles)
        self.assertIsNotNone(m)
        canonical = Chem.MolToSmiles(m, canonical=True)
        self.assertIsNotNone(canonical)
        self.assertGreater(len(canonical), 5)

    def test_smiles_invalid_returns_none(self):
        """无效 SMILES 返回 None 不抛异常"""
        from rdkit import Chem
        m = Chem.MolFromSmiles('NOT_A_VALID_SMILES_STRING_XYZ')
        self.assertIsNone(m)

    def test_svg_render_basic_molecule(self):
        """RDKit MolDraw2DSVG 生成出版级 SVG"""
        from rdkit import Chem
        from rdkit.Chem.Draw import MolDraw2DSVG
        m = Chem.MolFromSmiles('CC(=O)OC1=CC=CC=C1C(=O)O')  # Aspirin
        self.assertIsNotNone(m)
        drawer = MolDraw2DSVG(400, 300)
        drawer.DrawMolecule(m)
        drawer.FinishDrawing()
        svg = drawer.GetDrawingText()
        self.assertIn('<svg', svg)
        self.assertIn('</svg>', svg)

    def test_svg_render_complex_nucleotide(self):
        """RDKit 渲染复杂核苷酸 SMILES（含 @, /, 等特殊字符）"""
        from rdkit import Chem
        from rdkit.Chem.Draw import MolDraw2DSVG
        smiles = "C1C[C@@H](O[C@@H]1COP(=O)(O)OP(=O)(O)OP(=O)(O)O)N2C=C(C(=O)NC2=O)/C=C/NC(=O)CCCNC(=O)CCCCCNC(=O)CCCC[C@H]3C4[C@H](CS3)NC(=O)N4"
        m = Chem.MolFromSmiles(smiles)
        self.assertIsNotNone(m, f"RDKit should parse: {smiles[:60]}")
        drawer = MolDraw2DSVG(500, 400)
        drawer.DrawMolecule(m)
        drawer.FinishDrawing()
        svg = drawer.GetDrawingText()
        self.assertGreater(len(svg), 1000)

    def test_tanimoto_similarity_identical_molecules(self):
        """Tanimoto 相似度：同一分子"""
        from rdkit import Chem
        from rdkit.Chem import DataStructs
        from rdkit.Chem.rdMolDescriptors import GetMorganFingerprintAsBitVect
        m1 = Chem.MolFromSmiles('CCO')
        m2 = Chem.MolFromSmiles('CCO')
        fp1 = GetMorganFingerprintAsBitVect(m1, 2)
        fp2 = GetMorganFingerprintAsBitVect(m2, 2)
        sim = DataStructs.TanimotoSimilarity(fp1, fp2)
        self.assertAlmostEqual(sim, 1.0, places=1)

    def test_tanimoto_similarity_different_molecules(self):
        """Tanimoto 相似度：不同分子"""
        from rdkit import Chem
        from rdkit.Chem import DataStructs
        from rdkit.Chem.rdMolDescriptors import GetMorganFingerprintAsBitVect
        m1 = Chem.MolFromSmiles('CCO')  # ethanol
        m2 = Chem.MolFromSmiles('CC(=O)OC1=CC=CC=C1C(=O)O')  # aspirin
        fp1 = GetMorganFingerprintAsBitVect(m1, 2)
        fp2 = GetMorganFingerprintAsBitVect(m2, 2)
        sim = DataStructs.TanimotoSimilarity(fp1, fp2)
        self.assertLess(sim, 0.5)


class ChEMBLFallbackTest(TestCase):
    """ChEMBL REST API fallback 测试"""

    def setUp(self):
        self.enhancer = PubChemEnhancer()
        cache.clear()  # L2 Redis/LocMem 隔离（L1 DataSourceCache 由 TestCase 事务回滚隔离）

    @patch("core.datasource_client.requests.request")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_cids")
    def test_pubchem_not_found_falls_back_to_chembl(
        self, mock_get_cids, mock_get_compounds, mock_request
    ):
        """PubChem 搜不到 → ChEMBL REST API fallback → 返回统一 schema"""
        # PubChem 全失败
        mock_get_compounds.return_value = []
        mock_get_cids.return_value = []

        # ChEMBL 搜索成功
        mock_chm_response = MagicMock(status_code=200)
        mock_chm_response.json.return_value = {
            "molecules": [{
                "molecule_chembl_id": "CHEMBL25",
                "pref_name": "ASPIRIN",
                "molecule_structures": {
                    "canonical_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O"
                },
                "molecule_properties": {
                    "full_molformula": "C9H8O4",
                    "full_mwt": 180.16,
                    "alogp": 1.2,
                    "psa": 63.6,
                    "hbd": 1,
                    "hba": 4,
                    "rtb": 3,
                }
            }]
        }
        mock_request.return_value = mock_chm_response

        result = self.enhancer.resolve_to_properties("Aspirin")

        self.assertTrue(result["found"])
        self.assertEqual(result["source"], "chembl")
        self.assertEqual(result["cid"], "CHEMBL25")
        self.assertEqual(result["properties"]["molecular_formula"], "C9H8O4")
        self.assertAlmostEqual(result["properties"]["molecular_weight"], 180.16)
        self.assertEqual(result["properties"]["canonical_smiles"], "CC(=O)OC1=CC=CC=C1C(=O)O")
        # ChEMBL 路径无 synonyms（留空 list）
        self.assertEqual(result["properties"]["synonyms"], [])

    @patch("core.datasource_client.requests.request")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_cids")
    def test_chembl_not_found_returns_unified_not_found(
        self, mock_get_cids, mock_get_compounds, mock_request
    ):
        """PubChem + ChEMBL 都搜不到 → found: False + hint"""
        mock_get_compounds.return_value = []
        mock_get_cids.return_value = []

        mock_chm_response = MagicMock(status_code=200)
        mock_chm_response.json.return_value = {"molecules": []}
        mock_request.return_value = mock_chm_response

        result = self.enhancer.resolve_to_properties("NonExistentCompoundXYZ123")

        self.assertFalse(result["found"])
        self.assertIn("search_hint", result)

    @patch("core.datasource_client.requests.request")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_cids")
    def test_chembl_network_error_graceful_degradation(
        self, mock_get_cids, mock_get_compounds, mock_request
    ):
        """ChEMBL API 网络错误 → 不抛异常，返回 found: False"""
        mock_get_compounds.return_value = []
        mock_get_cids.return_value = []
        mock_request.side_effect = ConnectionError("Network timeout")

        result = self.enhancer.resolve_to_properties("SomeCompound")
        self.assertFalse(result["found"])

    @patch("core.datasource_client.requests.request")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_cids")
    def test_pubchem_success_skips_chembl(
        self, mock_get_cids, mock_get_compounds, mock_request
    ):
        """PubChem 搜索成功 → 不调 ChEMBL"""
        # Mock PubChem success
        mock_compound = MagicMock()
        mock_compound.cid = 2244
        mock_compound.molecular_formula = "C9H8O4"
        mock_compound.molecular_weight = 180.16
        mock_compound.iupac_name = "2-acetyloxybenzoic acid"
        mock_compound.xlogp = 1.2
        mock_compound.tpsa = 63.6
        mock_compound.inchi = "InChI=1S/C9H8O4/..."
        mock_compound.inchikey = "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"
        mock_compound.h_bond_donor_count = 1
        mock_compound.h_bond_acceptor_count = 4
        mock_compound.rotatable_bond_count = 3
        mock_compound.synonyms = ["50-78-2"]
        # pubchempy 1.0.5 用 smiles 代替 canonical_smiles
        mock_compound.smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"

        mock_get_compounds.return_value = [mock_compound]

        result = self.enhancer.resolve_to_properties("Aspirin")

        self.assertTrue(result["found"])
        self.assertEqual(result["source"], "pubchem")
        self.assertEqual(result["cid"], 2244)

        # ChEMBL 不应该被调用
        mock_request.assert_not_called()

        # synonyms 透传（Phase A：供 jena_matcher 增量匹配）
        self.assertEqual(result["properties"]["synonyms"], ["50-78-2"])

    @patch("core.datasource_client.requests.request")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_cids")
    def test_chembl_multiple_candidates_returns_list(
        self, mock_get_cids, mock_get_compounds, mock_request
    ):
        """ChEMBL 返回多个匹配 → candidates 列表"""
        mock_get_compounds.return_value = []
        mock_get_cids.return_value = []

        mock_chm_response = MagicMock(status_code=200)
        mock_chm_response.json.return_value = {
            "molecules": [
                {
                    "molecule_chembl_id": "CHEMBL25",
                    "pref_name": "ASPIRIN",
                    "molecule_structures": {"canonical_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O"},
                    "molecule_properties": {
                        "full_molformula": "C9H8O4", "full_mwt": 180.16,
                    }
                },
                {
                    "molecule_chembl_id": "CHEMBL1200",
                    "pref_name": "SALICYLIC ACID",
                    "molecule_structures": {"canonical_smiles": "O=C(O)C1=CC=CC=C1O"},
                    "molecule_properties": {
                        "full_molformula": "C7H6O3", "full_mwt": 138.12,
                    }
                },
            ]
        }
        mock_request.return_value = mock_chm_response

        result = self.enhancer.resolve_to_properties("aspirin")

        self.assertTrue(result["found"])
        self.assertEqual(result["source"], "chembl")
        self.assertEqual(len(result["candidates"]), 2)
        self.assertEqual(result["candidates"][0]["cid"], "CHEMBL25")
        self.assertEqual(result["candidates"][1]["cid"], "CHEMBL1200")

    # ── cas_resolved 语义修复（P4）──────────────────────────
    # 历史坑：L454 把 canonical_smiles 塞进 cas_resolved，下游误把 SMILES 当 CAS。

    @patch("core.datasource_client.requests.request")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_cids")
    def test_chembl_single_result_cas_resolved_is_none(self, mock_get_cids, mock_get_compounds, mock_request):
        """ChEMBL 单结果：cas_resolved 必须为 None（不能冒充 SMILES）。"""
        mock_get_compounds.return_value = []
        mock_get_cids.return_value = []
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "molecules": [{
                "molecule_chembl_id": "CHEMBL25",
                "pref_name": "ASPIRIN",
                "molecule_structures": {"canonical_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O"},
                "molecule_properties": {"full_molformula": "C9H8O4", "full_mwt": 180.16},
            }]
        }
        mock_request.return_value = mock_resp

        result = self.enhancer.resolve_to_properties("Aspirin")

        self.assertTrue(result["found"])
        self.assertEqual(result["source"], "chembl")
        self.assertIsNone(result.get("cas_resolved"),
                          "cas_resolved 不能用 SMILES 冒充，必须为 None")

    @patch("core.datasource_client.requests.request")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_cids")
    def test_chembl_properties_smiles_not_polluting_cas(self, mock_get_cids, mock_get_compounds, mock_request):
        """修复后 SMILES 仍在 properties 中返回，且不等于 cas_resolved。"""
        mock_get_compounds.return_value = []
        mock_get_cids.return_value = []
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "molecules": [{
                "molecule_chembl_id": "CHEMBL25",
                "pref_name": "ASPIRIN",
                "molecule_structures": {"canonical_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O"},
                "molecule_properties": {"full_molformula": "C9H8O4", "full_mwt": 180.16},
            }]
        }
        mock_request.return_value = mock_resp

        result = self.enhancer.resolve_to_properties("Aspirin")

        self.assertTrue(result["properties"]["canonical_smiles"])
        # cas_resolved 要么 None，要么绝不等于 canonical_smiles
        if result.get("cas_resolved") is not None:
            self.assertNotEqual(result["cas_resolved"],
                                result["properties"]["canonical_smiles"])


class RDKitRendererTest(TestCase):
    """RDKit 出版级结构渲染测试"""

    def test_render_svg_basic(self):
        """SMILES → SVG 基本渲染"""
        from apps.commerce.services.validators.rdkit_renderer import RDKitRenderer
        renderer = RDKitRenderer()
        svg = renderer.render_svg("CCO", width=300, height=200)
        self.assertIn("<svg", svg)
        self.assertIn("</svg>", svg)
        self.assertGreater(len(svg), 500)

    def test_render_svg_complex_nucleotide(self):
        """复杂核苷酸 SMILES 渲染"""
        from apps.commerce.services.validators.rdkit_renderer import RDKitRenderer
        renderer = RDKitRenderer()
        smiles = "C1C[C@@H](O[C@@H]1COP(=O)(O)OP(=O)(O)OP(=O)(O)O)N2C=C(C(=O)NC2=O)/C=C/NC(=O)CCCNC(=O)CCCCCNC(=O)CCCC[C@H]3C4[C@H](CS3)NC(=O)N4"
        svg = renderer.render_svg(smiles, width=600, height=500)
        self.assertIn("<svg", svg)
        self.assertGreater(len(svg), 1000)

    def test_render_svg_invalid_smiles_returns_empty(self):
        """无效 SMILES 返回空字符串"""
        from apps.commerce.services.validators.rdkit_renderer import RDKitRenderer
        renderer = RDKitRenderer()
        svg = renderer.render_svg("NOT_VALID_SMILES_XYZ")
        self.assertEqual(svg, "")

    def test_validate_smiles_valid(self):
        """有效 SMILES 校验"""
        from apps.commerce.services.validators.rdkit_renderer import RDKitRenderer
        result = RDKitRenderer.validate_smiles("CC(=O)OC1=CC=CC=C1C(=O)O")
        self.assertTrue(result["valid"])
        self.assertIsNotNone(result["canonical"])

    def test_validate_smiles_invalid(self):
        """无效 SMILES 校验"""
        from apps.commerce.services.validators.rdkit_renderer import RDKitRenderer
        result = RDKitRenderer.validate_smiles("XXXX")
        self.assertFalse(result["valid"])
        self.assertIn("Cannot parse", result["error"])


class ProtocolEnrichContentTest(TestCase):
    """BioProCorpus 富协议内容提取测试"""

    def test_search_with_content_returns_reagents(self):
        """include_content=True 时返回试剂列表"""
        from apps.knowledge.services.protocol_recommender import ProtocolRetriever
        retriever = ProtocolRetriever()
        results = retriever.search("click chemistry", top_k=5, include_content=True)
        self.assertGreater(len(results), 0)
        # At least one result has reagent or equipment content (Bio-protocol uses # Reagents)
        has_content = any(r.get("reagents") or r.get("equipment") for r in results)
        self.assertTrue(has_content, "Expected at least one result with reagents or equipment content")

    def test_search_with_content_returns_equipment(self):
        """include_content=True 时返回设备列表"""
        from apps.knowledge.services.protocol_recommender import ProtocolRetriever
        retriever = ProtocolRetriever()
        results = retriever.search("nucleotide labeling", top_k=3, include_content=True)
        self.assertGreater(len(results), 0)
        has_equipment = any(r.get("equipment") for r in results)
        self.assertTrue(has_equipment, "Expected at least one result with equipment content")

    def test_search_with_content_returns_steps(self):
        """include_content=True 时返回层级步骤"""
        from apps.knowledge.services.protocol_recommender import ProtocolRetriever
        retriever = ProtocolRetriever()
        results = retriever.search("CuAAC", top_k=3, include_content=True)
        self.assertGreater(len(results), 0)
        has_steps = any(len(r.get("steps", [])) > 0 for r in results)
        self.assertTrue(has_steps, "Expected at least one result with protocol steps")

    def test_search_without_content_does_not_return_extra_fields(self):
        """include_content=False（默认）时不返回多余字段"""
        from apps.knowledge.services.protocol_recommender import ProtocolRetriever
        retriever = ProtocolRetriever()
        results = retriever.search("click chemistry", top_k=2, include_content=False)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertNotIn("reagents", r)
            self.assertNotIn("steps", r)

    def test_extract_section_parses_markdown_correctly(self):
        """_extract_section 正确解析 Markdown 章节"""
        from apps.knowledge.services.protocol_recommender import ProtocolRetriever
        text = "# Reagents\n1. NaCl (Sigma, S9888)\n2. Tris-HCl (pH 7.5)\n\n# Equipment\n1. Centrifuge\n2. Thermocycler"
        result = ProtocolRetriever._extract_section(text, "Reagents")
        self.assertIn("NaCl", result)
        self.assertIn("Tris-HCl", result)
        self.assertNotIn("Centrifuge", result)

    def test_extract_steps_handles_hierarchical_protocol(self):
        """_extract_steps 正确解析层级协议"""
        from apps.knowledge.services.protocol_recommender import ProtocolRetriever
        hierarchical = {
            "1": {"title": "Preparation"},
            "1.1": "Add 10 uL of enzyme to the reaction mix.",
            "1.2": "Incubate at 37C for 30 min.",
            "2": {"title": "Purification"},
            "2.1": "Purify using column chromatography.",
        }
        steps = ProtocolRetriever._extract_steps(hierarchical)
        self.assertEqual(len(steps), 3)
        self.assertEqual(steps[0]["step_no"], "1.1")
        self.assertEqual(steps[0]["title"], "Preparation")
        self.assertIn("enzyme", steps[0]["body"])
        self.assertEqual(steps[2]["step_no"], "2.1")
        self.assertEqual(steps[2]["title"], "Purification")


class ProductRenderStructureAPITest(TestCase):
    """POST /api/v1/products/render-structure/ 测试"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin_render", password="pass123", email="ar@test.com"
        )
        self.client.force_authenticate(user=self.admin)

    def test_render_structure_returns_svg(self):
        """渲染 SMILES → SVG"""
        resp = self.client.post("/api/v1/products/render-structure/", {"smiles": "CCO"}, format="json")
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertIn("<svg", data["data"]["svg"])
        self.assertEqual(data["data"]["format"], "svg")

    def test_render_structure_returns_canonical_smiles(self):
        """渲染同时返回 canonical SMILES"""
        resp = self.client.post("/api/v1/products/render-structure/", {"smiles": "CC(=O)OC1=CC=CC=C1C(=O)O"}, format="json")
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertNotEqual(data["data"].get("canonical_smiles", ""), "")

    def test_render_structure_invalid_smiles(self):
        """无效 SMILES → error"""
        resp = self.client.post("/api/v1/products/render-structure/", {"smiles": "XXXX"}, format="json")
        data = resp.json()
        self.assertFalse(data["success"])


class L1DataSourceCacheIntegrationTest(TestCase):
    """resolve_to_properties 的 L1 DataSourceCache 集成（DATASOURCE_RELIABILITY.md §2.A 分层）"""

    def setUp(self):
        self.enhancer = PubChemEnhancer()
        cache.clear()

    def _mock_compound(self, cid=2244):
        """构造可 JSON 序列化的 Compound mock（所有 _extract_properties_from_compound 用到的属性都要设值，
        否则 getattr(MagicMock, ...) 返回 MagicMock 对象，json.dumps 会失败）。"""
        c = MagicMock()
        c.cid = cid
        c.molecular_formula = "C9H8O4"
        c.molecular_weight = 180.16
        c.iupac_name = "2-acetyloxybenzoic acid"
        c.smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
        c.isomeric_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"
        c.inchi = "InChI=1S/C9H8O4/c10-8(11)6-4-2-1-3-5(6)9(12)13-7(8)14/h1-4H,(H,10,11)"
        c.inchikey = "BSYNRYMUTXBXSQ-UHFFFAOYSA-N"
        c.xlogp = 1.2
        c.tpsa = 63.6
        c.h_bond_donor_count = 1
        c.h_bond_acceptor_count = 4
        c.rotatable_bond_count = 3
        c.complexity = 250
        c.exact_mass = 180.0423
        c.monoisotopic_mass = 180.0423
        c.charge = 0
        c.heavy_atom_count = 13
        c.synonyms = []
        return c

    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    def test_l1_hit_skips_external(self, mock_get_compounds):
        """L1 命中（未过期）时不调 PubChem 外部 API。"""
        from apps.documents.services.datasource_cache import set_cache
        cached = {"source": "pubchem", "found": True, "namespace": "name",
                  "cid": 2244, "properties": {"molecular_weight": 180.16}}
        set_cache("pubchem", "Aspirin", "name", cached)

        result = self.enhancer.resolve_to_properties("Aspirin")

        self.assertTrue(result["found"])
        self.assertEqual(result["cid"], 2244)
        mock_get_compounds.assert_not_called()

    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    def test_l1_miss_fills_l1(self, mock_get_compounds):
        """L1 未命中 → 查 PubChem → 成功结果写入 L1 DataSourceCache。"""
        from apps.commerce.services.validators.pubchem_enhancer import PubChemEnhancer
        mock_get_compounds.return_value = [self._mock_compound()]
        enhancer = PubChemEnhancer()

        result = enhancer.resolve_to_properties("Aspirin")

        self.assertTrue(result["found"])
        from apps.documents.models import DataSourceCache
        entry = DataSourceCache.objects.get(
            source="pubchem", query_key="Aspirin", query_namespace="name")
        self.assertEqual(entry.get_data()["cid"], 2244)
        self.assertFalse(entry.is_stale)

    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    def test_l1_expired_treated_as_miss(self, mock_get_compounds):
        """L1 过期（非 allow_stale）→ 视为 miss，查外部并刷新 L1。"""
        from datetime import timedelta
        from django.utils import timezone
        from apps.documents.services.datasource_cache import set_cache
        from apps.documents.models import DataSourceCache
        set_cache("pubchem", "Aspirin", "name",
                  {"source": "pubchem", "found": True, "cid": 999})
        DataSourceCache.objects.filter(source="pubchem", query_key="Aspirin").update(
            expires_at=timezone.now() - timedelta(seconds=1))

        mock_get_compounds.return_value = [self._mock_compound(cid=2244)]

        from apps.commerce.services.validators.pubchem_enhancer import PubChemEnhancer
        result = PubChemEnhancer().resolve_to_properties("Aspirin")
        self.assertEqual(result["cid"], 2244)  # 来自外部，非过期 999
        mock_get_compounds.assert_called_once()
