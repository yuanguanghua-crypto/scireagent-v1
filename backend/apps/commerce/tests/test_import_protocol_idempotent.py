"""R0-e 回归：/api/v1/products/import-protocol/ 幂等与既有语料保护。

背景（2026-08-10 数据污染事故）：
  该端点原先用 `Protocol.objects.filter(slug=..., method=method)` **双条件**查重。
  BioProCorpus 导入的原件 method_id 全为 NULL，而 Method 解析逻辑对「协议标题式长句」
  必然新建 Method，两者永不相等 → 查重恒失败 → 每次导入重复新建 Protocol/Method，
  且 `ProtocolStep.objects.filter(protocol=...).delete()` 会改写既有协议步骤。
  10 个产品的导入测试即产生 42 条重复 Protocol + 16 条重复 Method，并覆盖既有语料。

  更进一步（D7）：即便改成 slug 全局查重也依然无效 —— 两端 slug 生成规则不一致，
  语料原件是 slugify(name)，导入端却取 DOI 尾段（BioProtoc.xxxx），且语料 references 为空，
  DOI 无法作为对齐键。实测今日 42 条重复协议 100% 与既有记录同名，却无一 slug 相同。

本文件锁死修复后的不变量：
  1. 同一协议重复导入 → 实体数不增（幂等）
  2. 查重必须能命中 method 为 NULL 的语料库原件（name 首选，slug 兜底）
  3. 既有协议的步骤绝不被删除/改写
  4. 既有协议的正文字段只补空、不覆盖
  5. 解析不到既有 Method 时绝不新建（须显式 allow_create_method 才可）
  6. name 查重在两端 slug 规则不一致时仍然生效
  7. 新建协议的 slug 与语料规则对齐，DOI 存入 references
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.bridges.models import MethodProtocol, ProductMethod
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.models import Method, Protocol, ProtocolStep

User = get_user_model()

URL = "/api/v1/products/import-protocol/"


def _payload(**over):
    data = {
        "method_name": "Purification of 5-hydroxymethylcytosine carbamoyltransferase and in vitro assays",
        "protocol_title": "Carbamoyltransferase Enzyme Assay",
        "protocol_url": "https://www.protocols.io/view/carbamoyltransferase-enzyme-assay-abc123",
        "objective": "Convert 5hmC to 5cmC in vitro.",
        "reagents": "SAM, buffer",
        "equipment": "Thermocycler",
        "materials": "DNA substrate",
        "steps": [
            {"title": "Prepare reaction", "body": "Mix enzyme and substrate."},
            {"title": "Incubate", "body": "37 C for 1 h."},
        ],
    }
    data.update(over)
    return data


class ImportProtocolIdempotencyTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username="admin-import", password="adminpass123", email="ai@test.com"
        )
        self.client.force_authenticate(user=self.admin)

    def _counts(self):
        return {
            "protocol": Protocol.objects.count(),
            "method": Method.objects.count(),
            "step": ProtocolStep.objects.count(),
            "method_protocol": MethodProtocol.objects.count(),
            "product_method": ProductMethod.objects.count(),
        }

    # 1) 同一协议连续导入两次 —— 实体数与链接数均不得增加
    def test_repeat_import_creates_no_duplicates(self):
        product = ProductFactory()
        first = self.client.post(URL, _payload(product_id=product.id), format="json")
        self.assertEqual(first.status_code, 200, first.content)
        after_first = self._counts()
        first_pid = first.json()["data"]["protocol_id"]
        self.assertFalse(first.json()["data"]["protocol_reused"])

        second = self.client.post(URL, _payload(product_id=product.id), format="json")
        self.assertEqual(second.status_code, 200, second.content)
        after_second = self._counts()

        self.assertEqual(
            after_first, after_second,
            f"重复导入产生了新实体/新链接：{after_first} -> {after_second}",
        )
        self.assertEqual(second.json()["data"]["protocol_id"], first_pid)
        self.assertTrue(second.json()["data"]["protocol_reused"])

    # 2) slug 查重必须命中语料库原件（method 为 NULL）——这正是原双条件查重失效的场景。
    #    这里刻意让 name 不同，只有 DOI 尾段 slug 相同，以单独覆盖 slug 兼容路径。
    def test_slug_dedup_matches_corpus_original_with_null_method(self):
        corpus = Protocol.objects.create(
            method=None,                                   # BioProCorpus 原件特征
            name="Legacy Corpus Record With Different Name",
            slug="carbamoyltransferase-enzyme-assay-abc123",
            status="published",
        )
        before = Protocol.objects.count()

        resp = self.client.post(URL, _payload(), format="json")
        self.assertEqual(resp.status_code, 200, resp.content)

        self.assertEqual(Protocol.objects.count(), before, "命中语料库原件时不得新建 Protocol")
        self.assertEqual(resp.json()["data"]["protocol_id"], corpus.id)
        self.assertTrue(resp.json()["data"]["protocol_reused"])

    # 3) 既有步骤绝不被删除或改写（原 D4：filter(...).delete() 后重建）
    def test_existing_steps_are_never_destroyed(self):
        corpus = Protocol.objects.create(
            method=None,
            name="Carbamoyltransferase Enzyme Assay",
            slug="carbamoyltransferase-enzyme-assay-abc123",
            status="published",
        )
        for i in range(3):
            ProtocolStep.objects.create(
                protocol=corpus, step_no=i + 1,
                title=f"ORIGINAL {i + 1}", body=f"original body {i + 1}",
            )
        original_ids = list(
            ProtocolStep.objects.filter(protocol=corpus).order_by("step_no").values_list("id", flat=True)
        )

        resp = self.client.post(URL, _payload(), format="json")
        self.assertEqual(resp.status_code, 200, resp.content)

        steps = list(ProtocolStep.objects.filter(protocol=corpus).order_by("step_no"))
        self.assertEqual(len(steps), 3, "既有协议的步骤数被改写")
        self.assertEqual([s.id for s in steps], original_ids, "既有步骤被删除重建（主键变了）")
        self.assertEqual([s.title for s in steps], ["ORIGINAL 1", "ORIGINAL 2", "ORIGINAL 3"])
        self.assertEqual(resp.json()["data"]["step_count"], 0)

    # 3b) 既有协议一步都没有时，允许补齐（补空不覆盖）
    def test_steps_backfilled_when_existing_protocol_has_none(self):
        corpus = Protocol.objects.create(
            method=None,
            name="Carbamoyltransferase Enzyme Assay",
            slug="carbamoyltransferase-enzyme-assay-abc123",
            status="published",
        )
        resp = self.client.post(URL, _payload(), format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(ProtocolStep.objects.filter(protocol=corpus).count(), 2)

    # 4) 既有正文只补空、不覆盖
    def test_existing_text_fields_are_not_overwritten(self):
        corpus = Protocol.objects.create(
            method=None,
            name="Carbamoyltransferase Enzyme Assay",
            slug="carbamoyltransferase-enzyme-assay-abc123",
            objective="ORIGINAL OBJECTIVE",
            reagents="",
            status="published",
        )
        resp = self.client.post(URL, _payload(), format="json")
        self.assertEqual(resp.status_code, 200, resp.content)

        corpus.refresh_from_db()
        self.assertEqual(corpus.objective, "ORIGINAL OBJECTIVE", "既有 objective 被覆盖")
        self.assertEqual(corpus.reagents, "SAM, buffer", "空字段应被补齐")

    # 5) D1 止血：解析不到既有 Method 时**绝不新建**（默认策略）
    def test_no_method_is_auto_created_from_title_like_sentence(self):
        resp = self.client.post(URL, _payload(), format="json")
        self.assertEqual(resp.status_code, 200, resp.content)

        self.assertEqual(
            Method.objects.count(), 0,
            "协议标题式长句不得被造成 Method（今日 #58–73 共 16 条垃圾方法的成因）",
        )
        self.assertIsNone(resp.json()["data"]["method_id"])
        self.assertEqual(Protocol.objects.get(pk=resp.json()["data"]["protocol_id"]).method_id, None)

    # 5b) 显式 opt-in 才允许新建，且不得靠 -1/-2 后缀制造同义重复
    def test_method_created_only_with_explicit_opt_in_and_slug_reused(self):
        self.client.post(URL, _payload(allow_create_method=True), format="json")
        self.assertEqual(Method.objects.count(), 1)
        method_count = Method.objects.count()

        # 同一 method_name，但不同协议 → 应复用同一个 Method
        self.client.post(URL, _payload(
            allow_create_method=True,
            protocol_title="Carbamoyltransferase Enzyme Assay v2",
            protocol_url="https://www.protocols.io/view/carbamoyltransferase-enzyme-assay-v2-xyz789",
        ), format="json")

        self.assertEqual(Method.objects.count(), method_count, "同名 Method 被重复创建")
        self.assertFalse(
            Method.objects.filter(slug__regex=r"-\d+$").exists(),
            "出现 -1/-2 后缀 slug，说明 Method 仍在制造同义重复",
        )

    # 6) D7 回归：语料原件 slug=slugify(name)，导入端旧逻辑 slug=DOI 尾段 —— 两端规则不一致。
    #    实测今日 42 条重复协议 100% 同名但 slug 无一相同，故 name 必须作为首选查重键。
    def test_name_dedup_when_slug_rules_differ(self):
        corpus = Protocol.objects.create(
            method=None,
            name="An Improved Protocol for the Matrigel Duplex Assay",
            slug="an-improved-protocol-for-the-matrigel-duplex-assay",  # slugify(name)
            status="published",
        )
        before = Protocol.objects.count()

        resp = self.client.post(URL, _payload(
            protocol_title="An Improved Protocol for the Matrigel Duplex Assay",
            protocol_url="https://doi.org/10.21769/BioProtoc.4899",     # slug 尾段 = BioProtoc.4899
        ), format="json")
        self.assertEqual(resp.status_code, 200, resp.content)

        self.assertEqual(Protocol.objects.count(), before, "slug 规则不一致时仍重复建库（D7 未修复）")
        self.assertEqual(resp.json()["data"]["protocol_id"], corpus.id)
        self.assertTrue(resp.json()["data"]["protocol_reused"])

    # 7) 新建协议的 slug 必须与语料对齐（slugify(name)），使后续 slug 查重也能生效
    def test_new_protocol_slug_aligns_with_corpus_rule(self):
        resp = self.client.post(URL, _payload(
            protocol_title="Brand New Assay For Testing",
            protocol_url="https://doi.org/10.21769/BioProtoc.9999",
        ), format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        p = Protocol.objects.get(pk=resp.json()["data"]["protocol_id"])
        self.assertEqual(p.slug, "brand-new-assay-for-testing")
        self.assertEqual(p.references, "https://doi.org/10.21769/BioProtoc.9999", "DOI 应存入 references")
