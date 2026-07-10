"""TDD: jena 数据索引服务（策略 B 本地索引常驻）

测试索引构建、多方式查询（catalog_no/cas/name）、单例语义。
用临时 fixture JSONL，不依赖真实大文件。
"""
import json
import os
import tempfile
from unittest.mock import patch

from django.test import TestCase

from apps.commerce.services.jena_index import (
    JenaIndex, JenaRecord, get_shared_jena_index,
)


def _write_jsonl(records, filename="jena_products_v2.jsonl"):
    """写临时 JSONL 到临时目录，返回目录路径"""
    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, filename)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return tmpdir


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
        "category_path": "Nucleotides & Nucleosides|Nucleotides by Structure|dNTPs",
        "application_tags": "PCR; qPCR; DNA Sequencing",
    },
    {
        "jena_catalog_no": "NU-1138",
        "product_name": "N1-Methylpseudo-UTP",
        "systematic_name": "N1-Methylpseudouridine-5'-triphosphate, Sodium salt",
        "cas_number": None,
        "purity": "≥ 95 % (HPLC)",
        "concentration": "100 mM",
        "category_path": "Nucleotides & Nucleosides|Modified Nucleotides",
    },
    {
        "jena_catalog_no": "CLK-084",
        "product_name": "5-Azidomethyl-dU",
        "systematic_name": "5-Azidomethyl-2'-deoxyuridine",
        "category_path": "Click Chemistry|Nucleosides",
    },
]


class JenaIndexBuildTest(TestCase):
    """索引构建"""

    def test_build_from_jsonl(self):
        """从 JSONL 构建索引，记录数正确"""
        tmpdir = _write_jsonl(FIXTURE_RECORDS)
        try:
            index = JenaIndex(data_dir=tmpdir)
            index.build()
            self.assertEqual(index.size(), 3)
        finally:
            import shutil
            shutil.rmtree(tmpdir)

    def test_build_skips_invalid_records(self):
        """缺 catalog_no 或 product_name 的记录跳过"""
        records = FIXTURE_RECORDS + [
            {"jena_catalog_no": "", "product_name": "NoCat"},
            {"jena_catalog_no": "NU-X", "product_name": ""},
            {"jena_catalog_no": "NU-Y", "product_name": "Valid", "cas_number": "123-45-6"},
        ]
        tmpdir = _write_jsonl(records)
        try:
            index = JenaIndex(data_dir=tmpdir)
            index.build()
            self.assertEqual(index.size(), 4)  # 3 fixture + 1 Valid
        finally:
            import shutil
            shutil.rmtree(tmpdir)

    def test_build_missing_file_empty_index(self):
        """文件不存在时索引为空，不抛异常"""
        index = JenaIndex(data_dir="/nonexistent/path")
        index.build()
        self.assertEqual(index.size(), 0)

    def test_list_sources(self):
        """列出产品线（category_path L1 去重）"""
        tmpdir = _write_jsonl(FIXTURE_RECORDS)
        try:
            index = JenaIndex(data_dir=tmpdir)
            index.build()
            sources = index.list_sources()
            self.assertIn("Nucleotides & Nucleosides", sources)
            self.assertIn("Click Chemistry", sources)
        finally:
            import shutil
            shutil.rmtree(tmpdir)


class JenaIndexLookupTest(TestCase):
    """多方式查询"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tmpdir = _write_jsonl(FIXTURE_RECORDS)
        cls.index = JenaIndex(data_dir=cls.tmpdir)
        cls.index.build()

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmpdir)
        super().tearDownClass()

    def test_lookup_by_catalog_no(self):
        """精确匹配 catalog_no（大小写不敏感）"""
        r = self.index.lookup_by_catalog_no("NU-1001")
        self.assertIsNotNone(r)
        self.assertEqual(r.product_name, "dATP - Solution")
        # 大小写不敏感
        r2 = self.index.lookup_by_catalog_no("nu-1001")
        self.assertIsNotNone(r2)

    def test_lookup_by_cas(self):
        """精确匹配 CAS（仅 NU-1001 有 CAS）"""
        r = self.index.lookup_by_cas("1927-31-7")
        self.assertIsNotNone(r)
        self.assertEqual(r.catalog_no, "NU-1001")
        # NU-1138 无 CAS，查不到
        r2 = self.index.lookup_by_cas("999-99-9")
        self.assertIsNone(r2)

    def test_find_by_name_exact_first(self):
        """name 查询：精确匹配优先于部分匹配"""
        # 精确
        results = self.index.find_by_name("dATP - Solution")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].product_name, "dATP - Solution")

    def test_find_by_name_partial(self):
        """name 查询：部分匹配（包含关系）"""
        results = self.index.find_by_name("dATP")
        self.assertGreater(len(results), 0)
        # 应命中 dATP - Solution
        names = [r.product_name for r in results]
        self.assertIn("dATP - Solution", names)

    def test_lookup_namespace_cas(self):
        """统一查询入口：namespace=cas"""
        r = self.index.lookup("1927-31-7", namespace="cas")
        self.assertIsNotNone(r)
        self.assertEqual(r.catalog_no, "NU-1001")

    def test_lookup_namespace_catalog_no(self):
        """统一查询入口：namespace=catalog_no"""
        r = self.index.lookup("CLK-084", namespace="catalog_no")
        self.assertIsNotNone(r)
        self.assertEqual(r.product_name, "5-Azidomethyl-dU")

    def test_lookup_namespace_name(self):
        """统一查询入口：namespace=name（默认）"""
        r = self.index.lookup("N1-Methylpseudo-UTP")
        self.assertIsNotNone(r)
        self.assertEqual(r.catalog_no, "NU-1138")

    def test_lookup_returns_none_when_no_match(self):
        """查不到返回 None"""
        self.assertIsNone(self.index.lookup("NonExistentXYZ", namespace="name"))
        self.assertIsNone(self.index.lookup_by_cas("000-00-0"))
        self.assertIsNone(self.index.lookup_by_catalog_no("ZZZ-999"))

    def test_systematic_name_is_anchor(self):
        """systematic_name 字段（跨源查询锚点）正确提取"""
        r = self.index.lookup_by_catalog_no("NU-1001")
        self.assertEqual(r.systematic_name, "2'-Deoxyadenosine-5'-triphosphate, Sodium salt")


class JenaSharedSingletonTest(TestCase):
    """进程级单例"""

    def test_shared_index_is_singleton(self):
        """get_shared_jena_index 多次调用返回同一实例"""
        # 用 patch 让单例指向测试索引
        tmpdir = _write_jsonl(FIXTURE_RECORDS)
        try:
            # 重置单例
            import apps.commerce.services.jena_index as mod
            old = mod._shared_index
            mod._shared_index = None
            with patch.object(mod, "JENA_DATA_DIR", tmpdir):
                i1 = get_shared_jena_index()
                i2 = get_shared_jena_index()
                self.assertIs(i1, i2)
                self.assertEqual(i1.size(), 3)
            mod._shared_index = old
        finally:
            import shutil
            shutil.rmtree(tmpdir)
