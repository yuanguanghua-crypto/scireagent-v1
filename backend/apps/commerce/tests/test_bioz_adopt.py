"""TDD: Bioz 文献落库管线 — POST /api/v1/products/<pk>/adopt-bioz-refs/

把 Bioz enrich 返回的 references 数组落库到 Reference + ProductReference，
去重逻辑：DOI > PMID > title 降级查重；关联按 (product, reference, role) 去重。
"""
from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from apps.commerce.models import Product
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.models import Reference
from apps.bridges.models import ProductReference

User = get_user_model()


def _ref(**over):
    base = {
        "article_title": "Structure of ThiM from Vitamin B1 biosynthetic pathway",
        "authors": "Smith J, Lee K",
        "journal": "Scientific Reports",
        "pub_date": "2023-01-15",
        "doi": "10.1038/s41598-023-12345-6",
        "pmid": "36653210",
        "techniques": "X-ray crystallography",
    }
    base.update(over)
    return base


def _ref_authors_list(**over):
    """authors 为 list 的真实 bioz 形态。"""
    base = _ref()
    base["authors"] = ["Smith J", "Lee K", "Patel R"]
    base.update(over)
    return base


class BiozAdoptAuthTest(TestCase):
    """adopt-bioz-refs 端点权限。"""

    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory()
        self.user = User.objects.create_user(username="u", password="p")
        self.admin = User.objects.create_superuser(
            username="admin", password="p", email="a@test.com")

    def test_requires_auth(self):
        resp = self.client.post(
            f"/api/v1/products/{self.product.id}/adopt-bioz-refs/",
            {"references": []}, format="json")
        self.assertEqual(resp.status_code, 401)

    def test_regular_user_denied(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(
            f"/api/v1/products/{self.product.id}/adopt-bioz-refs/",
            {"references": []}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_admin_allowed(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            f"/api/v1/products/{self.product.id}/adopt-bioz-refs/",
            {"references": []}, format="json")
        self.assertEqual(resp.status_code, 200)


class BiozAdoptCoreTest(TestCase):
    """落库核心行为。"""

    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory()
        self.admin = User.objects.create_superuser(
            username="admin", password="p", email="a@test.com")
        self.client.force_authenticate(user=self.admin)

    def _post(self, refs, **extra):
        payload = {"references": refs, "citation_role": "supporting"}
        payload.update(extra)
        return self.client.post(
            f"/api/v1/products/{self.product.id}/adopt-bioz-refs/",
            payload, format="json")

    def test_creates_reference_and_link(self):
        """单条文献：创建 Reference + ProductReference。"""
        resp = self._post([_ref()])
        self.assertEqual(resp.status_code, 200)
        data = resp.data["data"]
        self.assertEqual(data["adopted"], 1)
        self.assertEqual(Reference.objects.count(), 1)
        self.assertEqual(ProductReference.objects.count(), 1)
        r = Reference.objects.first()
        self.assertEqual(r.title, _ref()["article_title"])
        self.assertEqual(r.doi, _ref()["doi"])
        self.assertEqual(r.pmid, _ref()["pmid"])
        self.assertEqual(r.journal, "Scientific Reports")
        self.assertEqual(r.year, 2023)
        self.assertEqual(r.source_type, "journal")

    def test_dedup_by_doi_reuses_existing(self):
        """同 DOI 第二次 Adopt：复用 Reference，不重复创建，关联也不重复。"""
        self._post([_ref()])
        resp = self._post([_ref()])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Reference.objects.count(), 1)
        self.assertEqual(ProductReference.objects.count(), 1)
        self.assertEqual(resp.data["data"]["skipped"], 1)

    def test_dedup_by_pmid_when_no_doi(self):
        """无 DOI 时按 PMID 去重。"""
        ref = _ref(doi="")
        self._post([ref])
        resp = self._post([ref])
        self.assertEqual(Reference.objects.count(), 1)
        self.assertEqual(resp.data["data"]["skipped"], 1)

    def test_dedup_by_title_when_no_doi_pmid(self):
        """无 DOI/PMID 时按 title 去重。"""
        ref = _ref(doi="", pmid="")
        self._post([ref])
        resp = self._post([ref])
        self.assertEqual(Reference.objects.count(), 1)
        self.assertEqual(resp.data["data"]["skipped"], 1)

    def test_link_dedup_independent_of_reference_dedup(self):
        """同一 Reference 关联到不同产品：各建独立 ProductReference。"""
        p2 = ProductFactory()
        self._post([_ref()])
        # p2 adopt 同一文献
        resp = self.client.post(
            f"/api/v1/products/{p2.id}/adopt-bioz-refs/",
            {"references": [_ref()], "citation_role": "supporting"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Reference.objects.count(), 1)  # Reference 复用
        self.assertEqual(ProductReference.objects.count(), 2)  # 关联各一

    def test_batch_mixed(self):
        """批量：部分新建 + 部分去重。"""
        self._post([_ref()])
        refs = [
            _ref(),  # 已存在 → skipped
            _ref(doi="10.9999/new", pmid="9991", article_title="New paper"),  # 新建
            _ref(doi="", pmid="9992", article_title="No id paper"),  # 新建
        ]
        resp = self._post(refs)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["data"]["adopted"], 2)
        self.assertEqual(resp.data["data"]["skipped"], 1)
        self.assertEqual(Reference.objects.count(), 3)

    def test_year_extract_from_various_formats(self):
        """pub_date 多格式：YYYY-MM-DD / YYYY / null。"""
        refs = [
            _ref(doi="10.1/a", pmid="1001", article_title="Paper A", pub_date="2021-06-15"),
            _ref(doi="10.2/b", pmid="1002", article_title="Paper B", pub_date="2019"),
            _ref(doi="10.3/c", pmid="1003", article_title="Paper C", pub_date=""),
        ]
        self._post(refs)
        # 无序集合比较（doi=10.1→2021, 10.2→2019, 10.3→None）
        year_by_doi = dict(Reference.objects.filter(
            doi__in=["10.1/a", "10.2/b", "10.3/c"]).values_list("doi", "year"))
        self.assertEqual(year_by_doi, {"10.1/a": 2021, "10.2/b": 2019, "10.3/c": None})

    def test_missing_title_skipped_with_error(self):
        """无 title 的条目：跳过并记录 error，不中断整体。"""
        refs = [
            {"doi": "10.1/x", "article_title": ""},  # 无 title
            _ref(doi="10.2/y"),  # 正常
        ]
        resp = self._post(refs)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["data"]["adopted"], 1)
        self.assertTrue(len(resp.data["data"]["errors"]) >= 1)
        self.assertEqual(Reference.objects.count(), 1)

    def test_authors_list_joined_to_string(self):
        """bioz 真实返回 authors 为 list → 落库为逗号字符串。"""
        resp = self._post([_ref_authors_list()])
        self.assertEqual(resp.status_code, 200)
        r = Reference.objects.first()
        self.assertEqual(r.authors, "Smith J, Lee K, Patel R")

    def test_citation_role_default_supporting(self):
        """未传 citation_role 时默认 supporting。"""
        resp = self.client.post(
            f"/api/v1/products/{self.product.id}/adopt-bioz-refs/",
            {"references": [_ref()]}, format="json")
        self.assertEqual(resp.status_code, 200)
        pr = ProductReference.objects.first()
        self.assertEqual(pr.citation_role, "supporting")

    def test_citation_role_custom(self):
        """传 citation_role=primary 生效。"""
        resp = self.client.post(
            f"/api/v1/products/{self.product.id}/adopt-bioz-refs/",
            {"references": [_ref()], "citation_role": "primary"}, format="json")
        self.assertEqual(resp.status_code, 200)
        pr = ProductReference.objects.first()
        self.assertEqual(pr.citation_role, "primary")

    def test_nonexistent_product_404(self):
        """产品不存在 → 404。"""
        resp = self.client.post(
            "/api/v1/products/999999/adopt-bioz-refs/",
            {"references": []}, format="json")
        self.assertEqual(resp.status_code, 404)

    def test_empty_references(self):
        """空 references 列表：0 adopted，无副作用。"""
        resp = self._post([])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["data"]["adopted"], 0)
        self.assertEqual(Reference.objects.count(), 0)
