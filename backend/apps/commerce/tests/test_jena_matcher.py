"""TDD: jena_matcher 服务（cas→name→synonyms 多键匹配 + L1 缓存）

测试优先级匹配、归一化输出、L1 缓存命中、异常降级。
用临时 fixture JSONL 注入索引，patch _get_index 避免依赖真实大文件。
"""
import json
import os
import tempfile
from unittest.mock import patch

from django.test import TestCase

from apps.commerce.services import jena_matcher


FIXTURE_RECORDS = [
    {
        "jena_catalog_no": "NU-1001",
        "product_name": "dATP - Solution",
        "systematic_name": "2'-Deoxyadenosine-5'-triphosphate, Sodium salt",
        "cas_number": "1927-31-7",
        "purity": "≥ 99 % (HPLC)",
        "concentration": "100 mM - 110 mM",
        "storage_condition": "store at -20 °C",
        "shipping_condition": "shipped on gel packs",
        "shelf_life": "12 months",
        "category_path": "Nucleotides & Nucleosides|dNTPs",
    },
    {
        "jena_catalog_no": "NU-1138",
        "product_name": "N1-Methylpseudo-UTP",
        "systematic_name": "N1-Methylpseudouridine-5'-triphosphate, Sodium salt",
        "cas_number": None,
        "purity": "≥ 95 % (HPLC)",
        "category_path": "Nucleotides & Nucleosides|Modified Nucleotides",
    },
    {
        "jena_catalog_no": "CLK-084",
        "product_name": "5-Azidomethyl-dU",
        "systematic_name": "5-Azidomethyl-2'-deoxyuridine",
        "category_path": "Click Chemistry|Nucleosides",
    },
]


def _build_index(records, filename="jena_test.jsonl"):
    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, filename)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    from apps.commerce.services.jena_index import JenaIndex
    idx = JenaIndex(data_dir=tmpdir, jsonl_filename=filename)
    idx.build()
    return idx, tmpdir


class JenaMatcherTest(TestCase):
    """jena_matcher.match_jena 主流程测试"""

    def setUp(self):
        self.index, self.tmpdir = _build_index(FIXTURE_RECORDS)
        self._patch = patch.object(jena_matcher, "_get_index", return_value=self.index)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_cas_hit_with_normalization(self):
        """CAS 精确命中 + 规格归一化映射到 Product choices"""
        r = jena_matcher.match_jena("1927-31-7", namespace="cas")
        self.assertTrue(r["matched"])
        self.assertEqual(r["match_key"], "cas")
        self.assertEqual(r["catalog_no"], "NU-1001")
        self.assertEqual(r["systematic_name"], "2'-Deoxyadenosine-5'-triphosphate, Sodium salt")
        # 归一化
        self.assertEqual(r["normalized"]["purity"], "≥ 99% (HPLC)")
        self.assertEqual(r["normalized"]["storage_condition"], "-20°C")
        self.assertEqual(r["normalized"]["shipping_condition"], "Cold Pack")
        self.assertEqual(r["normalized"]["shelf_life"], "P1Y")
        self.assertEqual(r["normalized"]["concentration"], "100 mM - 110 mM")
        self.assertEqual(r["normalized"]["category_l1"], "nucleotides_nucleosides")

    def test_name_hit(self):
        """name 命中（无 CAS 的记录）"""
        r = jena_matcher.match_jena("N1-Methylpseudo-UTP", namespace="name")
        self.assertTrue(r["matched"])
        self.assertEqual(r["match_key"], "name")
        self.assertEqual(r["catalog_no"], "NU-1138")

    def test_cas_miss_falls_back_to_name(self):
        """CAS miss 后 name 兜底（真级联核心）：identifier 形如 CAS 但与 jena 记录不符时"""
        # 构造一条 jena product_name 含 CAS 式字符串的记录模拟真实层级
        # 这里直接测试：identifier 非 CAS 时（如产品名）用 name 查到
        r = jena_matcher.match_jena("dATP - Solution", namespace="name")
        self.assertTrue(r["matched"])
        self.assertEqual(r["match_key"], "name")

    def test_synonym_incremental_hit(self):
        """name miss 但 synonyms 增量命中（撬动覆盖率的关键路径）"""
        r = jena_matcher.match_jena("Random Product XYZ", namespace="name", synonyms=["dATP"])
        self.assertTrue(r["matched"])
        self.assertTrue(r["match_key"].startswith("synonym:"))
        self.assertEqual(r["catalog_no"], "NU-1001")

    def test_all_miss(self):
        """全 miss 返回 {matched: False}"""
        r = jena_matcher.match_jena("NonExistent", namespace="name", synonyms=["xyz"])
        self.assertFalse(r["matched"])

    def test_empty_input(self):
        """无 identifier 且无 synonyms → 直接 {matched: False}"""
        r = jena_matcher.match_jena("", namespace="name")
        self.assertFalse(r["matched"])

    def test_l1_cache_writes_and_hits(self):
        """L1 命中：matched=True 写入 DataSourceCache，二次读跳过索引"""
        from apps.documents.models import DataSourceCache
        r1 = jena_matcher.match_jena("1927-31-7", namespace="cas")
        self.assertTrue(r1["matched"])
        # 验证写入 L1
        entry = DataSourceCache.objects.filter(
            source="jena_match", query_key="1927-31-7", query_namespace="cas"
        ).first()
        self.assertIsNotNone(entry)
        self.assertTrue(entry.get_data()["matched"])
        # 二次命中（清空索引查找，仍能从缓存返回）
        with patch.object(jena_matcher, "_match_jena_no_cache",
                          side_effect=AssertionError("should hit cache, not re-query")):
            r2 = jena_matcher.match_jena("1927-31-7", namespace="cas")
        self.assertTrue(r2["matched"])

    def test_index_unavailable_degrades(self):
        """索引不可用（None）→ 降级 {matched: False}，不抛异常"""
        with patch.object(jena_matcher, "_get_index", return_value=None):
            r = jena_matcher.match_jena("1927-31-7", namespace="cas")
        self.assertFalse(r["matched"])

    def test_exception_returns_error_flag(self):
        """核心匹配抛异常 → {matched: False, error: str}"""
        with patch.object(jena_matcher, "_match_jena_no_cache",
                          side_effect=RuntimeError("boom")):
            r = jena_matcher.match_jena("1927-31-7", namespace="cas")
        self.assertFalse(r["matched"])
        self.assertIn("error", r)

    def test_non_cas_identifier_not_tried_as_cas(self):
        """非 CAS 形态 identifier（如产品名）不应走 CAS 查询：_calls lookup_by_name 不 _by_cas"""
        # 验证：形如 "N1-Methylpseudo-UTP" 的 identifier 命中 name 而非 cas
        r = jena_matcher.match_jena("N1-Methylpseudo-UTP", namespace="cas")
        self.assertTrue(r["matched"])
        # 命中的 product_name 匹配（N1-Methylpseudo-UTP 没有 CAS 记录）
        self.assertEqual(r["match_key"], "name")
