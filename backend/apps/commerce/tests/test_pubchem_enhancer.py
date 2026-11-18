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
        # N-2：同义词必须含被查询名本身。真实 PubChem 对 CID 2244 返回的同义词表里
        # 就包含 "Aspirin"；旧 mock 只写 CAS 属不真实构造，会让名字回验误判为无关化合物。
        mock_compound.synonyms = ["Aspirin", "50-78-2"]
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
        self.assertEqual(result["properties"]["synonyms"], ["Aspirin", "50-78-2"])

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
                    "molecule_chembl_id": "CHEMBL521",
                    "pref_name": "IBUPROFEN",
                    "molecule_structures": {"canonical_smiles": "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O"},
                    "molecule_properties": {
                        "full_molformula": "C13H18O2", "full_mwt": 206.28,
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
        self.assertEqual(result["candidates"][1]["cid"], "CHEMBL521")

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


def _bioprocorpus_missing() -> bool:
    """BioProCorpus 语料是否缺失。

    ★ 2026-10-19：`backend/data/bioprocorpus/` 是**外部数据集，不入库**。
      实测本机与干净环境均为 0 个 json 文件 ⇒ 下面这批测试**从来没有真正跑过**
      （一直以 AssertionError: 0 not greater 失败）。
      这正是"5 failed 恒定项"的来源。

    ★ 为什么改成 skip 而不是留在失败：
      永远红的测试套件 = 没人看 = 等于没有测试。
      缺数据应当**显式 skip**（CI 输出里能看到 "skipped"），而不是伪装成 bug。
      若将来把语料放回 `backend/data/bioprocorpus/`，这些用例会自动恢复执行。
    """
    try:
        from apps.knowledge.services.protocol_recommender import BioProCorpusIndexer
        idx = BioProCorpusIndexer()
        idx.build()
        return len(idx._entries) == 0
    except Exception:
        return True


class ProtocolEnrichContentTest(TestCase):
    """BioProCorpus 富协议内容提取测试

    ⚠️ 依赖真实 BioProCorpus 语料（外部数据集，不入库）。缺语料时整类 skip。
    """

    def setUp(self):
        if _bioprocorpus_missing():
            self.skipTest(
                "缺 BioProCorpus 语料（backend/data/bioprocorpus/ 下 0 个 json）；"
                "这不是代码缺陷，把语料放回去即可恢复执行"
            )

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
        """L1 命中（未过期、已验证）时不调 PubChem 外部 API。"""
        from apps.documents.services.datasource_cache import set_cache
        cached = {"source": "pubchem", "found": True, "namespace": "name",
                  "cid": 2244, "identity_verified": True,
                  "properties": {"molecular_weight": 180.16}}
        set_cache("pubchem", "Aspirin|", "name", cached)

        result = self.enhancer.resolve_to_properties("Aspirin")

        self.assertTrue(result["found"])
        self.assertEqual(result["cid"], 2244)
        mock_get_compounds.assert_not_called()

    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    def test_l1_miss_fills_l1(self, mock_get_compounds):
        """L1 未命中 → 查 PubChem → 已验证（带 expected_cas）结果写入 L1 DataSourceCache。"""
        from apps.commerce.services.validators.pubchem_enhancer import PubChemEnhancer
        c = self._mock_compound()
        c.synonyms = ["50-78-2"]  # 含 CAS，配合 expected_cas 触发 identity_verified
        mock_get_compounds.return_value = [c]
        enhancer = PubChemEnhancer()

        result = enhancer.resolve_to_properties("Aspirin", expected_cas="50-78-2")

        self.assertTrue(result["found"])
        self.assertTrue(result["identity_verified"])
        from apps.documents.models import DataSourceCache
        entry = DataSourceCache.objects.get(
            source="pubchem", query_key="Aspirin|", query_namespace="name")
        self.assertEqual(entry.get_data()["cid"], 2244)
        self.assertFalse(entry.is_stale)

    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    def test_l1_miss_unverified_not_cached(self, mock_get_compounds):
        """修复 5：未验证（纯 name 查、无 expected_cas）结果不写 L1，避免固化错误。"""
        from apps.documents.models import DataSourceCache
        mock_get_compounds.return_value = [self._mock_compound()]
        result = self.enhancer.resolve_to_properties("Aspirin")
        self.assertTrue(result["found"])
        self.assertFalse(result.get("identity_verified"))
        self.assertFalse(DataSourceCache.objects.filter(
            source="pubchem", query_key="Aspirin", query_namespace="name").exists())

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


class PubChemGuardTest(TestCase):
    """任务2(b)：保留 SMILES 渲染，但根治 PubChem 模糊匹配到错误分子。

    RED→GREEN：
    - 身份(CAS)通过但分子式/MW 与文档(权威)不符 → 视为错误化合物，强制 requires_review，绝不自动套用。
    - name 模糊匹配(无 CAS)的候选必须携带 formula_mismatch/requires_review 标志，
      供前端 applyCandidate 据此拦截错误分子。
    """

    def setUp(self):
        self.enhancer = PubChemEnhancer()
        cache.clear()

    def _mock_compound(self, cid=2244):
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

    @patch("core.datasource_client.requests.request")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_cids")
    def test_verified_cas_but_formula_mismatch_requires_review(
        self, mock_get_cids, mock_get_compounds, mock_request
    ):
        """CAS 匹配(身份通过)但分子式与文档不符 → 错误化合物，requires_review=True。"""
        c = self._mock_compound(cid=2244)
        c.synonyms = ["12345-67-8"]
        c.molecular_formula = "C9H8O4"  # 故意与文档不符
        mock_get_compounds.return_value = [c]
        mock_get_cids.return_value = [2244]

        result = self.enhancer.resolve_to_properties(
            "Some Compound", namespace='name',
            expected_cas="12345-67-8", expected_formula="C12H19N4O14P3")

        self.assertTrue(result["found"])
        self.assertTrue(result["formula_mismatch"], "分子式与文档不符应标记 mismatch")
        # RED: 当前 verified 分支返回 requires_review=False；修复后应为 True
        self.assertTrue(
            result["requires_review"],
            "CAS 通过但分子式不符 = 错误化合物，必须 requires_review=True")
        self.assertFalse(result["identity_verified"])

    @patch("core.datasource_client.requests.request")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_cids")
    def test_name_only_match_candidate_carries_guard_flags(
        self, mock_get_cids, mock_get_compounds, mock_request
    ):
        """name 模糊匹配(无 CAS)的候选必须携带 formula_mismatch/requires_review 标志。"""
        c = self._mock_compound(cid=2244)
        c.molecular_formula = "C9H8O4"  # 与文档不符
        mock_get_compounds.return_value = [c]
        mock_get_cids.return_value = [2244]

        result = self.enhancer.resolve_to_properties(
            "5-Propargylamino-CTP", namespace='name',
            expected_formula="C12H19N4O14P3")

        self.assertFalse(result["identity_verified"])
        self.assertTrue(result["requires_review"])
        self.assertTrue(result["formula_mismatch"])
        # 候选必须携带守卫标志，前端 applyCandidate 才能据此拦截
        self.assertTrue(len(result["candidates"]) >= 1)
        cand = result["candidates"][0]
        self.assertTrue(cand.get("formula_mismatch"),
                        "候选必须携带 formula_mismatch 供前端拦截")
        self.assertTrue(cand.get("requires_review"),
                        "候选必须携带 requires_review 供前端拦截")


class PubChemNameReverseCheckTest(TestCase):
    """N-2：PubChem name 端点是模糊匹配，必须做名字回验。

    DS 复测实测：`XQZ-9987-NOMATCH` → CID 98586（N-叔丁基羟胺），
    完全无关的化合物被当作「找到了」，还带着 lipinski.passed=true 展示。
    修法：同义词可用时，查询名与返回化合物必须有任何可核对的公共词，否则判未找到。
    """

    def setUp(self):
        self.enhancer = PubChemEnhancer()
        cache.clear()

    def _mock(self, cid=98586, synonyms=None, iupac="2-methylpropan-2-amine oxide"):
        c = MagicMock()
        c.cid = cid
        c.molecular_formula = "C4H11NO"
        c.molecular_weight = 89.14
        c.iupac_name = iupac
        c.smiles = "CC(C)(C)NO"
        c.isomeric_smiles = "CC(C)(C)NO"
        c.inchi = "InChI=1S/C4H11NO/c1-4(2,3)5-6/h5-6H,1-3H3"
        c.inchikey = "FCCICDZQRBWVEH-UHFFFAOYSA-N"
        c.xlogp = 0.3
        c.tpsa = 32.3
        c.h_bond_donor_count = 2
        c.h_bond_acceptor_count = 2
        c.rotatable_bond_count = 1
        c.complexity = 42
        c.exact_mass = 89.084
        c.monoisotopic_mass = 89.084
        c.charge = 0
        c.heavy_atom_count = 6
        c.synonyms = synonyms if synonyms is not None else []
        return c

    @patch("core.datasource_client.requests.request")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    def test_unrelated_name_hit_becomes_not_found(self, mock_get_compounds, mock_request):
        """★ 核心回归：名字与返回化合物毫无公共词 ⇒ 判未找到，不得返回候选。"""
        mock_get_compounds.return_value = [self._mock(
            synonyms=["N-tert-Butylhydroxylamine", "2-Propanamine, 2-methyl-N-hydroxy-"])]
        result = self.enhancer.resolve_to_properties("XQZ-9987-NOMATCH", namespace="name")
        self.assertFalse(result["found"], "无关化合物必须判未找到（宁 miss 不错配）")
        self.assertEqual(result.get("name_verification"), "failed")
        self.assertIn("unrelated", result.get("search_hint", ""))

    @patch("core.datasource_client.requests.request")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    def test_related_name_hit_is_kept(self, mock_get_compounds, mock_request):
        """正向守卫：同义词里确实有该名字时必须保留（不能一刀切全判 miss）。"""
        mock_get_compounds.return_value = [self._mock(
            cid=2244, synonyms=["Aspirin", "Acetylsalicylic acid", "50-78-2"],
            iupac="2-acetyloxybenzoic acid")]
        result = self.enhancer.resolve_to_properties("Aspirin", namespace="name")
        self.assertTrue(result["found"])
        self.assertFalse(result["identity_verified"], "纯 name 匹配仍不得视为已验证")

    @patch("core.datasource_client.requests.request")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    def test_skipped_when_synonyms_unavailable(self, mock_get_compounds, mock_request):
        """同义词取不到 ⇒ 无从回验，放行（下游仍 requires_review，不会自动套用）。"""
        mock_get_compounds.return_value = [self._mock(synonyms=[], iupac="Ethanol")]
        result = self.enhancer.resolve_to_properties("XQZ-9987-NOMATCH", namespace="name")
        self.assertTrue(result["found"])
        self.assertTrue(result["requires_review"])
        self.assertFalse(result["identity_verified"])

    @patch("core.datasource_client.requests.request")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    def test_skipped_when_expected_cas_given(self, mock_get_compounds, mock_request):
        """给了 expected_cas 的查询由 CAS 比对把关，不被名字字面回验误杀。"""
        mock_get_compounds.return_value = [self._mock(
            cid=2244, synonyms=["50-78-2", "Acetylsalicylic acid"],
            iupac="2-acetyloxybenzoic acid")]
        result = self.enhancer.resolve_to_properties(
            "Some Totally Different Label", namespace="name", expected_cas="50-78-2")
        self.assertTrue(result["found"])
        self.assertTrue(result["identity_verified"])

    @patch("core.datasource_client.requests.request")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    def test_chinese_name_not_rejected(self, mock_get_compounds, mock_request):
        """纯中文名没有 ASCII 词可比 ⇒ 不因此误杀。"""
        mock_get_compounds.return_value = [self._mock(
            synonyms=["Ethanol", "64-17-5"], iupac="ethanol")]
        result = self.enhancer.resolve_to_properties("无水乙醇", namespace="name")
        self.assertTrue(result["found"])

    def test_reverse_check_unit(self):
        """_name_reverse_check 各分支直接单测（不经网络）。"""
        c_related = self._mock(synonyms=["5-Propargylamino-CTP", "Propargylamino-CTP"])
        c_unrelated = self._mock(synonyms=["N-tert-Butylhydroxylamine"])
        # 整串归一化命中（连字符/大小写无关）
        self.assertTrue(self.enhancer._name_reverse_check("5-propargylamino-ctp", c_related))
        # 单 token 命中
        self.assertTrue(self.enhancer._name_reverse_check("CTP labeling kit", c_related))
        # 毫无公共词
        self.assertFalse(self.enhancer._name_reverse_check("XQZ-9987-NOMATCH", c_unrelated))
        # 同义词不可用 → 放行
        self.assertTrue(self.enhancer._name_reverse_check(
            "XQZ-9987-NOMATCH", self._mock(synonyms=[])))
        # 无 ASCII token → 放行
        self.assertTrue(self.enhancer._name_reverse_check("无水乙醇", c_unrelated))


class LipinskiIdentityGateTest(TestCase):
    """N-2 后半：unverified 不得驱动 lipinski.passed。

    passed=False 与 passed=None 语义不同 —— 前者是「不合规」，后者是「未判定」。
    未核验身份却给出 PASS，等于给错分子做合规背书。
    """

    PROPS = {
        'molecular_weight': 180.16,
        'xlogp': 1.2,
        'h_bond_donor_count': 1,
        'h_bond_acceptor_count': 4,
        'rotatable_bond_count': 3,
    }

    def setUp(self):
        self.enhancer = PubChemEnhancer()

    def test_unverified_gives_no_verdict(self):
        out = self.enhancer.check_lipinski(self.PROPS, identity_verified=False)
        self.assertIsNone(out['passed'], "未核验身份不得给出 passed 结论")
        self.assertFalse(out['identity_verified'])
        self.assertTrue(out['caveat'], "必须说明这是未核验结果的参考值")
        self.assertEqual(out['violations'], [])

    def test_verified_passes(self):
        out = self.enhancer.check_lipinski(self.PROPS, identity_verified=True)
        self.assertIs(out['passed'], True)
        self.assertEqual(out['caveat'], '')

    def test_verified_fails_on_violation(self):
        out = self.enhancer.check_lipinski(
            dict(self.PROPS, molecular_weight=900), identity_verified=True)
        self.assertIs(out['passed'], False)
        self.assertTrue(any('Molecular weight' in v for v in out['violations']))

    def test_default_keeps_backward_compat(self):
        """既有调用不传 identity_verified 时行为不变（默认视为已核验）。"""
        out = self.enhancer.check_lipinski(self.PROPS)
        self.assertIs(out['passed'], True)
        self.assertTrue(out['identity_verified'])

    def test_empty_properties_still_carries_gate_fields(self):
        out = self.enhancer.check_lipinski({}, identity_verified=False)
        self.assertIn('identity_verified', out)
        self.assertIn('caveat', out)
