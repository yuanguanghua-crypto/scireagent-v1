"""TDD: bioz_sanitizer 厂商无关化净化"""
from django.test import TestCase

from apps.knowledge.services.bioz_sanitizer import sanitize_citation, sanitize_record


class SanitizeCitationTest(TestCase):
    def test_removes_vendor_name(self):
        """删厂商名变体"""
        s = sanitize_citation("used Pseudo-UTP (Jena Biosciences) for IVT", "NU-1138")
        self.assertNotIn("Jena Bioscience", s, lower=True) if False else None
        self.assertNotIn("Jena Biosciences", s)
        self.assertNotIn("Jena Bioscience", s)
        self.assertIn("Pseudo-UTP", s)
        self.assertIn("IVT", s)

    def test_removes_vendor_in_c_tag(self):
        """删 <c>厂商</c> 标签整体"""
        s = sanitize_citation(
            "with <cdd>50%</cdd> supplement of <t>5-Methyl-CTP</t> and Pseudo-UTP (<c>Jena Biosciences</c>), following protocol",
            "NU-1138",
        )
        self.assertNotIn("Jena", s)
        self.assertNotIn("<c>", s)
        self.assertNotIn("</c>", s)
        # 化学物质名保留
        self.assertIn("5-Methyl-CTP", s)
        self.assertIn("Pseudo-UTP", s)
        # 浓度保留
        self.assertIn("50%", s)

    def test_removes_sku_variants_from_catalog_group(self):
        """删 catalog_group 全部 SKU 变体（大小写不敏感）"""
        s = sanitize_citation(
            "reagent (NU-1138) and alternative (nu-1138l) or (NU-1138s)",
            "NU-1138",
            catalog_group=["nu-1138l", "nu-1138", "nu-1138s"],
        )
        self.assertNotIn("NU-1138", s)
        self.assertNotIn("nu-1138", s.lower())
        self.assertNotIn("1138", s)

    def test_removes_preprint_tag(self):
        """删 <b>PrePrint:</b> 标签"""
        s = sanitize_citation("<b>PrePrint:</b> mRNA was synthesized", "NU-1138")
        self.assertNotIn("PrePrint", s)
        self.assertNotIn("<b>", s)
        self.assertIn("mRNA was synthesized", s)

    def test_preserves_chemical_name(self):
        """化学物质名不动"""
        s = sanitize_citation("used 5-Ethynyl-dUTP for labeling", "NU-1138")
        self.assertIn("5-Ethynyl-dUTP", s)
        self.assertIn("labeling", s)

    def test_empty_input(self):
        """空输入返回空"""
        self.assertEqual(sanitize_citation("", "NU-1138"), "")
        self.assertEqual(sanitize_citation(None, "NU-1138"), "")

    def test_only_vendor_returns_empty(self):
        """原文只剩厂商名 → 净化后空字符串"""
        s = sanitize_citation("Jena Biosciences", "NU-1138")
        self.assertEqual(s, "")

    def test_trims_residual_punctuation(self):
        """修剪残留空括号/双点/首尾逗号"""
        s = sanitize_citation(".. used reagent (), following protocol,", "NU-1138")
        self.assertNotIn("..", s)
        self.assertNotIn("()", s)
        self.assertFalse(s.startswith(","))
        self.assertFalse(s.endswith(","))

    def test_removes_jenabioscience_url(self):
        """product_url 含 jenabioscience.com 不直接出现在引用里，但若有也删"""
        # URL 不在 long/medium/short 里（在 product_url 字段），此测试验证 catalog_group 变体删除即可
        s = sanitize_citation("see NU-1138 for details", "NU-1138")
        self.assertNotIn("NU-1138", s)


class SanitizeRecordTest(TestCase):
    def test_record_sanitizes_three_levels(self):
        """sanitize_record 对 long/medium/short 三级净化"""
        record = {
            "article_title": "Test paper",
            "authors": ["Author A"],
            "journal": "Nature",
            "impact_factor": 14.9,
            "pmid": "12345",
            "doi": "10.1038/xxx",
            "pub_date": "2021-02-04",
            "techniques": ["PCR"],
            "filter_data": [{"key": "Category", "value": ["mRNA"]}],
            "image_urls": [{"url": "http://x", "caption": "Fig 1"}],
            "long": "used <t>5-Methyl-CTP</t> (<c>Jena Biosciences</c>) for IVT",
            "medium": ".. 5-Methyl-CTP (Jena Bioscience, NU-1138) ..",
            "short": "<b>PrePrint:</b> (NU-1138)",
            "catalog_group": ["nu-1138", "nu-1138l"],
            "catalog_number": "nu-1138",
        }
        s = sanitize_record(record, "NU-1138", "Jena Bioscience")
        # 三级都净化
        for field in ("clean_long", "clean_medium", "clean_short"):
            self.assertNotIn("Jena", s[field])
            self.assertNotIn("NU-1138", s[field])
            self.assertNotIn("nu-1138", s[field].lower())
        # 化学名保留
        self.assertIn("5-Methyl-CTP", s["clean_long"])
        # 不含原始 long/medium/short 和厂商字段
        self.assertNotIn("long", s)
        self.assertNotIn("catalog_group", s)
        self.assertNotIn("catalog_number", s)
        # 元数据保留
        self.assertEqual(s["journal"], "Nature")
        self.assertEqual(s["impact_factor"], 14.9)
        self.assertEqual(s["pmid"], "12345")
