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
    JenaIndex, JenaRecord, get_shared_jena_index, map_category_l1,
    classify_concentration, _ADOPTED_L1,
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
    # ── L10 歧义复现 fixture ──
    {
        "jena_catalog_no": "NU-2001",
        "product_name": "ATP",                         # 规范名（精确匹配）
        "systematic_name": "Adenosine 5'-triphosphate",
        "category_path": "Nucleotides & Nucleosides|Nucleotides by Structure|NTPs",
    },
    {
        "jena_catalog_no": "NU-2002",
        "product_name": "2'-MeSe-ATP",                 # 衍生物（子串命中 ATP）
        "systematic_name": "2'-Methylseleno-ATP",
        "category_path": "Nucleotides & Nucleosides|Modified Nucleotides",
    },
    {
        "jena_catalog_no": "NU-2003",
        "product_name": "ATP, disodium salt",          # 另一 ATP 子串命中
        "systematic_name": "Adenosine 5'-triphosphate disodium salt",
        "category_path": "Nucleotides & Nucleosides|Nucleotides by Structure|NTPs",
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
            self.assertEqual(index.size(), 6)  # 3 原 fixture + 3 L10 歧义 fixture
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
            self.assertEqual(index.size(), 7)  # 6 fixture + 1 Valid
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


class JenaMatcherL10Test(TestCase):
    """L10 修正：catalog 精确优先 + name 子串歧义检测（不盲取首条）。

    复现今天账本的 ATP→2'-MeSe-ATP 错配：旧实现按 JSONL 迭代顺序取首条部分匹配，
    查 "ATP" 可能返回衍生物 2'-MeSe-ATP。修正后应精确优先、歧义返回 None。
    """

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

    def test_exact_name_beats_partial_substring(self):
        """查询 'ATP' 应返回精确名 'ATP'（NU-2001），而非衍生物 2'-MeSe-ATP"""
        r = self.index.lookup("ATP", namespace="name")
        self.assertIsNotNone(r)
        self.assertEqual(r.catalog_no, "NU-2001")

    def test_ambiguous_substring_returns_none(self):
        """无精确名、仅多条子串命中 → 歧义，返回 None（不盲取首条）"""
        slim = [rec for rec in FIXTURE_RECORDS if rec["jena_catalog_no"] != "NU-2001"]
        slim_dir = _write_jsonl(slim, filename="slim.jsonl")
        try:
            idx = JenaIndex(data_dir=slim_dir, jsonl_filename="slim.jsonl")
            idx.build()
            # 'ATP' 仍子串命中 NU-2002 / NU-2003 / NU-1001（dATP 含 'atp'），无精确 → 歧义
            self.assertIsNone(idx.lookup("ATP", namespace="name"))
        finally:
            import shutil
            shutil.rmtree(slim_dir)

    def test_catalog_like_identifier_prefers_catalog_lookup(self):
        """name 命名空间下传入 catalog 形态标识符，应精确命中 catalog"""
        r = self.index.lookup("NU-1001", namespace="name")
        self.assertIsNotNone(r)
        self.assertEqual(r.catalog_no, "NU-1001")
        self.assertEqual(r.product_name, "dATP - Solution")

    def test_single_partial_still_matches(self):
        """唯一子串命中仍返回（低歧义）"""
        r = self.index.lookup("Azidomethyl", namespace="name")
        self.assertIsNotNone(r)
        self.assertEqual(r.catalog_no, "CLK-084")

    def test_ranking_canonical_before_derivative(self):
        """find_by_name 列表：规范短名应排在衍生物之前（词边界+短名）"""
        results = self.index.find_by_name("ATP", limit=10)
        names = [r.product_name for r in results]
        # 精确 'ATP' 必在第一
        self.assertEqual(names[0], "ATP")
        # 衍生物 2'-MeSe-ATP 与 ATP, disodium salt 均在列表中
        self.assertIn("2'-MeSe-ATP", names)
        self.assertIn("ATP, disodium salt", names)


class JenaSharedSingletonTest(TestCase):
    """进程级单例"""

    def test_shared_index_is_singleton(self):
        """get_shared_jena_index 多次调用返回同一实例（进程级单例）。

        v2.0 共享索引是 MultiVendorIndex，从模块级 _SUPPLIER_DIR 加载全部供应商
        JSONL（而非旧的 JENA_DATA_DIR）。测试用 patch 把 _SUPPLIER_DIR 指向临时
        fixture 目录，既验证单例身份，也验证其确实从配置目录构建了索引。
        """
        # 默认文件名 jena_products_v2.jsonl → vendor 解析为 "jena"，6 条记录
        tmpdir = _write_jsonl(FIXTURE_RECORDS)
        import apps.commerce.services.jena_index as mod
        old_index = mod._shared_index
        old_dir = mod._SUPPLIER_DIR
        mod._shared_index = None
        mod._shared_index_meta = None
        try:
            with patch.object(mod, "_SUPPLIER_DIR", tmpdir):
                i1 = get_shared_jena_index()
                i2 = get_shared_jena_index()
                self.assertIs(i1, i2)
                self.assertEqual(i1.size(), 6)
        finally:
            mod._shared_index = old_index
            mod._SUPPLIER_DIR = old_dir
            import shutil
            shutil.rmtree(tmpdir)


class MapCategoryL1Test(TestCase):
    """map_category_l1：jena category_path → 平台 CategoryL1（扫描全部分类段）

    TDD 回归：旧实现只取第一段，导致 SC8001 这类
    '正确 L1 藏在深层段' 的记录归不到分类（Category 空）。
    """

    def test_map_scans_all_segments_not_just_first(self):
        """SC8001 真实路径：关键词在深层段也能命中 nucleotides_nucleosides"""
        path = ("Probes & Epigenetics | RNA/cRNA Labeling | "
                "Amine Labeling of RNA/cRNA | Amine-modified Nucleotides | 5-Propargylamino-CTP")
        self.assertEqual(map_category_l1(path), "nucleotides_nucleosides")

    def test_map_first_segment_still_matches(self):
        """第一段命中仍正常（原行为不退化）"""
        self.assertEqual(map_category_l1("Nucleotides & Nucleosides|dNTPs"), "nucleotides_nucleosides")

    def test_map_click_chemistry_in_deep_segment(self):
        """click chemistry 在第二段也能命中"""
        self.assertEqual(map_category_l1("Probes & Epigenetics | Click Chemistry | Nucleosides"),
                         "click_chemistry")

    def test_map_molecular_biology_deep(self):
        self.assertEqual(map_category_l1("X | Y | Molecular Biology Reagents"), "molecular_biology")

    def test_map_no_match_returns_empty(self):
        self.assertEqual(map_category_l1("Unknown Cat|A|B"), "")

    def test_map_empty_path_returns_empty(self):
        self.assertEqual(map_category_l1(""), "")
        self.assertEqual(map_category_l1(None), "")

    # ── P1-3：未采纳产品线 + 幻影 slug fail-safe ──
    def test_map_unadopted_lines_return_empty(self):
        """5 条平台 v1 未采纳的 jena 产品线一律归空（产品决策，非缺陷）。

        绝不可映射到 CATEGORY_TREE 里不存在的 slug（SC8001 幻影 slug bug）。
        """
        for path in (
            "Proteins | Recombinant Enzymes",
            "Probes & Epigenetics | DNA Methylation",
            "RNA Technologies | mRNA",
            "Crystallography & Cryo-EM | Screens",
            "LEXSY Expression | Cell Lines",
        ):
            self.assertEqual(map_category_l1(path), "", f"未采纳线应归空: {path}")

    def test_map_output_always_in_adopted_set(self):
        """map_category_l1 的任何非空输出必须 ∈ 平台已采纳 L1 全集（幻影 slug 边界）。"""
        for path in (
            "Nucleotides & Nucleosides|dNTPs",
            "Probes & Epigenetics | Click Chemistry | Nucleosides",
            "X | Y | Molecular Biology Reagents",
            "Proteins | Enzymes",          # 未采纳 → ''
            "Totally Unknown | Foo",        # 无关键词 → ''
        ):
            out = map_category_l1(path)
            self.assertTrue(out == "" or out in _ADOPTED_L1,
                            f"输出必须为空或已采纳 L1，得到: {out!r}")

    def test_failsafe_filters_phantom_slug(self):
        """即使 _CATEGORY_L1_MAP 被误加一条指向未采纳枚举的映射，
        fail-safe 边界也会把它拦成 ''（防 SC8001 幻影 slug 回归）。"""
        from unittest.mock import patch
        import apps.commerce.services.jena_index as ji
        phantom = ji._CATEGORY_L1_MAP + [("proteins", "probes_epigenetics")]
        with patch.object(ji, "_CATEGORY_L1_MAP", phantom):
            # 'probes_epigenetics' 不在 _ADOPTED_L1 → 被拦成 ''
            self.assertEqual(ji.map_category_l1("Proteins | Enzymes"), "")
            # 真实 L1 不受影响
            self.assertEqual(ji.map_category_l1("Nucleotides|X"), "nucleotides_nucleosides")


class ClassifyConcentrationTest(TestCase):
    """classify_concentration：P2-2 与清洗程序 concentration_has_unit（canonical）对齐。

    合法性判据 = 含单位的数值 or 稀释比（1:1000）；无单位散文丢弃。
    """

    def test_keeps_value_with_unit(self):
        self.assertEqual(classify_concentration("100 mM"), "100 mM")
        self.assertEqual(classify_concentration("100 mM - 110 mM"), "100 mM - 110 mM")
        self.assertEqual(classify_concentration("5 mg/ml"), "5 mg/ml")

    def test_keeps_dilution_ratio(self):
        """canonical 对齐后：稀释比 1:1000 视为有效浓度表达（旧实现会误丢）。"""
        self.assertEqual(classify_concentration("1:1000"), "1:1000")

    def test_keeps_unit_even_with_photometrically(self):
        """含单位则保留，即使句中提到 photometrically（旧实现会误丢）。"""
        self.assertEqual(
            classify_concentration("5 mg/ml (photometrically)"),
            "5 mg/ml (photometrically)")

    def test_drops_unitless_prose(self):
        self.assertEqual(classify_concentration("determined photometrically"), "")
        self.assertEqual(classify_concentration("high purity"), "")

    def test_empty_and_none(self):
        self.assertEqual(classify_concentration(""), "")
        self.assertEqual(classify_concentration(None), "")


class JenaDataAvailabilityTest(TestCase):
    """回归守卫：JENA_DATA_DIR 必须指向真实可用的数据文件。

    防止『rebuild 镜像后 jena 数据丢失 / 路径错位』这类静默回归——
    文件缺失时本测试直接失败，CI/本地都能立刻发现。
    """

    def test_jena_data_dir_has_index_file(self):
        import os
        from apps.commerce.services.jena_index import JENA_DATA_DIR, JENA_JSONL_FILENAME
        path = os.path.join(JENA_DATA_DIR, JENA_JSONL_FILENAME)
        self.assertTrue(os.path.exists(path), f"jena index missing at {path}")
        idx = JenaIndex(data_dir=JENA_DATA_DIR)
        idx.build()
        self.assertGreater(idx.size(), 0, "jena index built empty — data file broken/missing")
