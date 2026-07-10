"""TDD: bioz_equivalence 化学等同性校验"""
from django.test import TestCase

from apps.knowledge.services.bioz_equivalence import check_equivalence


class CheckEquivalenceTest(TestCase):
    def test_cas_exact_match(self):
        """双方 CAS 等同 → exact, needs_review=False"""
        r = check_equivalence("1927-31-7", "1927-31-7", "cas")
        self.assertEqual(r["equivalence"], "exact")
        self.assertFalse(r["needs_review"])

    def test_cas_normalize_dash_difference(self):
        """CAS dash 差异但等同 → exact（cas_normalize 去 dash）"""
        r = check_equivalence("1927-31-7", "1927-31-7", "name")
        self.assertEqual(r["equivalence"], "exact")
        self.assertFalse(r["needs_review"])

    def test_cas_mismatch(self):
        """双方都有 CAS 但不一致 → mismatch"""
        r = check_equivalence("1927-31-7", "999-99-9", "cas")
        self.assertEqual(r["equivalence"], "mismatch")
        self.assertTrue(r["needs_review"])

    def test_chembl_smiles_cas_resolved_treated_as_no_cas(self):
        """平台 cas_resolved 是 SMILES（ChEMBL 坑）→ 当无 CAS，按 match_key 降级"""
        r = check_equivalence("CC(=O)OC1=CC=CC=C1C(=O)O", None, "name")
        self.assertIn(r["equivalence"], ("weak", "name_match"))
        self.assertTrue(r["needs_review"])

    def test_match_key_name_no_cas(self):
        """双方无 CAS，match_key=name → weak"""
        r = check_equivalence("", "", "name")
        self.assertEqual(r["equivalence"], "weak")
        self.assertTrue(r["needs_review"])

    def test_match_key_synonym(self):
        """match_key=synonym:xxx → name_match"""
        r = check_equivalence("", None, "synonym:dATP")
        self.assertEqual(r["equivalence"], "name_match")
        self.assertTrue(r["needs_review"])

    def test_platform_cas_only_jena_missing(self):
        """平台有 CAS，jena 无 CAS，match_key=name → weak（无法 CAS 证实）"""
        r = check_equivalence("1927-31-7", "", "name")
        self.assertEqual(r["equivalence"], "weak")
        self.assertTrue(r["needs_review"])

    def test_empty_match_key(self):
        """match_key 空 → weak"""
        r = check_equivalence("", "", "")
        self.assertEqual(r["equivalence"], "weak")
        self.assertTrue(r["needs_review"])
