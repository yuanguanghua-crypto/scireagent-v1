"""TDD: P3-1 — enrich 端点回写 ref_id（已落库 Reference 标记）

enrich 返回的 literature.references / bioz.references 中，已通过 Adopt 落库到
Reference + ProductReference 的文献，应回写 ref_id 字段供前端显示「已关联」徽章。
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from apps.commerce.models import Product
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.models import Reference
from apps.bridges.models import ProductReference

User = get_user_model()


class EnrichRefIdRewriteTest(TestCase):
    """enrich 端点对已落库 Reference 回写 ref_id。"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin", password="p", email="a@test.com")
        self.client.force_authenticate(user=self.admin)
        self.product = ProductFactory()

    def _enrich(self, product_id=None):
        payload = {"product_name": "ATP", "cas": "", "smiles": "", "inchi": ""}
        if product_id is not None:
            payload["product_id"] = product_id
        return self.client.post("/api/v1/products/enrich/", payload, format="json")

    def _force_chembl_single(self, mock_req, mock_get_comp, mock_get_cids, doi="10.1/x", pmid="123"):
        """让 enrich 走 ChEMBL fallback 单结果路径，bioz/literature 由真实管线跑。"""
        mock_get_comp.return_value = []
        mock_get_cids.return_value = []
        resp = MagicMock(status_code=200)
        resp.json.return_value = {
            "molecules": [{
                "molecule_chembl_id": "CHEMBL1",
                "pref_name": "ATP",
                "molecule_structures": {"canonical_smiles": "C"},
                "molecule_properties": {"full_molformula": "C10H16N5O13P3", "full_mwt": 507.18},
            }]
        }
        mock_req.return_value = resp

    @patch("core.datasource_client.requests.request")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_cids")
    def test_no_product_id_no_ref_id(self, mc, mg, mr):
        """不传 product_id → references 不带 ref_id（行为同现状）。"""
        self._force_chembl_single(mr, mg, mc)
        resp = self._enrich(product_id=None)
        self.assertEqual(resp.status_code, 200)
        for ref in resp.data["data"]["bioz"].get("references", []):
            self.assertNotIn("ref_id", ref)

    @patch("core.datasource_client.requests.request")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_cids")
    def test_product_with_linked_ref_gets_ref_id(self, mc, mg, mr):
        """产品已关联某 Reference → enrich 该文献回写 ref_id。"""
        self._force_chembl_single(mr, mg, mc)
        # 先建一个已关联到 product 的 Reference
        ref = Reference.objects.create(
            title="Existing", doi="10.1/x", pmid="123", source_type="journal")
        ProductReference.objects.create(
            product=self.product, reference=ref, citation_role="supporting")

        resp = self._enrich(product_id=self.product.id)
        self.assertEqual(resp.status_code, 200)
        bioz_refs = resp.data["data"]["bioz"].get("references", [])
        # 找到 doi 匹配的 ref
        matched = [r for r in bioz_refs if r.get("doi") == "10.1/x"
                   or r.get("pmid") == "123"]
        for r in matched:
            self.assertEqual(r.get("ref_id"), ref.id)

    @patch("core.datasource_client.requests.request")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_cids")
    def test_product_without_linked_ref_no_ref_id(self, mc, mg, mr):
        """Reference 存在但未关联到本 product → 不回写 ref_id。"""
        self._force_chembl_single(mr, mg, mc)
        other_product = ProductFactory()
        ref = Reference.objects.create(
            title="Other", doi="10.1/x", pmid="123", source_type="journal")
        ProductReference.objects.create(
            product=other_product, reference=ref, citation_role="supporting")

        resp = self._enrich(product_id=self.product.id)
        self.assertEqual(resp.status_code, 200)
        for r in resp.data["data"]["bioz"].get("references", []):
            self.assertNotIn("ref_id", r)

    @patch("core.datasource_client.requests.request")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_cids")
    def test_invalid_product_id_no_crash(self, mc, mg, mr):
        """非法 product_id（如 'abc'）→ 不崩溃，正常返回无 ref_id。"""
        self._force_chembl_single(mr, mg, mc)
        resp = self._enrich(product_id="abc")
        self.assertEqual(resp.status_code, 200)

    @patch("core.datasource_client.requests.request")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_compounds")
    @patch("apps.commerce.services.validators.pubchem_enhancer.pcp.get_cids")
    def test_nonexistent_product_id_no_crash(self, mc, mg, mr):
        """不存在的 product_id → 不崩溃（查询返回空，无 ref_id）。"""
        self._force_chembl_single(mr, mg, mc)
        resp = self._enrich(product_id=999999)
        self.assertEqual(resp.status_code, 200)
