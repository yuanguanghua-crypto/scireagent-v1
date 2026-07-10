"""TDD: cas_normalize 共享工具"""
from django.test import TestCase

from apps.commerce.services.cas_normalize import cas_normalize, is_cas_like


class CasNormalizeTest(TestCase):
    def test_basic_normalize(self):
        """标准 CAS → 去 dash 大写"""
        self.assertEqual(cas_normalize("1927-31-7"), "1927317")

    def test_strip_whitespace(self):
        """首尾空格 strip"""
        self.assertEqual(cas_normalize("  1927-31-7  "), "1927317")

    def test_case_insensitive_upper(self):
        """大写化（CAS 本身全数字，但保持一致性）"""
        self.assertEqual(cas_normalize("1927-31-7"), "1927317")

    def test_dash_difference_equal(self):
        """带 dash 与不带 dash 视为等同（跨源比对场景）"""
        self.assertEqual(cas_normalize("1927-31-7"), "1927317")

    def test_smiles_returns_none(self):
        """SMILES 非 CAS 形态 → None（规避 ChEMBL cas_resolved 坑）"""
        self.assertIsNone(cas_normalize("CC(=O)OC1=CC=CC=C1C(=O)O"))

    def test_product_name_returns_none(self):
        """产品名非 CAS 形态 → None"""
        self.assertIsNone(cas_normalize("N1-Methylpseudo-UTP"))

    def test_empty_returns_none(self):
        """空字符串/None → None"""
        self.assertIsNone(cas_normalize(""))
        self.assertIsNone(cas_normalize(None))

    def test_short_digit_string_returns_none(self):
        """数字但不符合 CAS 形态（如纯数字无 dash）→ None"""
        self.assertIsNone(cas_normalize("1927317"))

    def test_is_cas_like(self):
        """is_cas_like 布尔判断"""
        self.assertTrue(is_cas_like("1927-31-7"))
        self.assertFalse(is_cas_like("CC(=O)O"))
        self.assertFalse(is_cas_like(""))
        self.assertFalse(is_cas_like(None))
