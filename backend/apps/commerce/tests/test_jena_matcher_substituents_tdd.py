"""TDD: P0 取代基一致性闸门 —— 修"短名包含"错配。

根因（2026-09-15 生产实测，6 例真实错配，均 `matched=True` 且 `signatures_conflict=None`）：
  jena 匹配的 name 路径是部分匹配 `q in pn or pn in q`，候选的**短名**嵌进请求的**长修饰名**；
  而 signatures_conflict 只比「碱基 + 糖型」，对取代基无感：
    3'-Azido-ddATP  ⊃ ddATP          → jena NU-1015   (纯 ddATP)
    3'-Amino-ddCTP  ⊃ ddCTP          → jena NU-1016
    3'-Amino-ddGTP  ⊃ ddGTP          → jena NU-1017
    5-Bromo-ddUTP   ⊃ ddUTP          → jena NU-1021
    Desthiobiotin-11-UTP ⊃ Biotin-11-UTP → biotium Biotin-11-UTP
    2'-Amino-dGTP   ⊂ 2'-amino-2'-deoxyguanosine-5'-triphosphate（synonym 子串）
                                     → trilink N-2503 (纯 dGTP)

修复：新增 jena_index.substituents_conflict —— 请求名里的每个取代基词都必须在候选名出现，
任一缺席即拒收（宁 miss 不错配）。词表最长匹配优先（biotin ⊂ desthiobiotin 等）。

测试直接打 `_match_jena_no_cache`（绕开 L1 缓存，保证断言的是本次逻辑而非缓存）。
"""
import json
import os
import shutil
import tempfile
from unittest.mock import patch

from django.test import TestCase

from apps.commerce.services import jena_matcher
from apps.commerce.services.jena_index import (
    substituents_conflict,
    substituents_of,
)


def _build_index(records, filename="jena_subst_tdd.jsonl"):
    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, filename)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    from apps.commerce.services.jena_index import JenaIndex
    idx = JenaIndex(data_dir=tmpdir, jsonl_filename=filename)
    idx.build()
    return idx, tmpdir


# ── 词表/判定单元测试（精确钉住新函数语义）──────────────────────────────────
class SubstituentsUnitTest(TestCase):
    def test_longest_match_wins_desthiobiotin_not_biotin(self):
        """desthiobiotin 含 biotin 子串 → 只应保留 desthiobiotin（否则被 biotin 蒙混）。"""
        self.assertEqual(substituents_of("Desthiobiotin-11-UTP"), {"desthiobiotin"})
        self.assertEqual(substituents_of("Biotin-11-UTP"), {"biotin"})

    def test_propargylamino_not_reduced_to_amino(self):
        self.assertEqual(substituents_of("5-Propargylamino-CTP"), {"propargylamino"})
        self.assertEqual(substituents_of("7-Deaza-7-Propargylamino-dATP"),
                         {"deaza", "propargylamino"})

    def test_hydroxymethyl_not_reduced_to_hydroxy_methyl(self):
        self.assertEqual(substituents_of("5-Hydroxymethyl-UTP"), {"hydroxymethyl"})

    def test_no_substituent_means_no_constraint(self):
        """纯核苷酸（dATP/ATP）无取代基词 → 不作约束，避免误杀。"""
        self.assertEqual(substituents_of("dATP"), set())
        self.assertEqual(substituents_of("ATP"), set())
        self.assertFalse(substituents_conflict("dATP", "2'-Deoxyadenosine-5'-Triphosphate"))

    def test_six_production_mismatch_pairs_all_conflict(self):
        cases = [
            ("3'-Azido-ddATP", "ddATP"),
            ("3'-Amino-ddCTP", "ddCTP"),
            ("3'-Amino-ddGTP", "ddGTP"),
            ("5-Bromo-ddUTP", "ddUTP"),
            ("Desthiobiotin-11-UTP", "Biotin-11-UTP"),
            ("2'-Amino-dGTP", "2'-Deoxyguanosine-5'-Triphosphate"),
        ]
        for req, cand in cases:
            self.assertTrue(substituents_conflict(req, cand), f"{req} vs {cand}")

    def test_legitimate_pairs_not_conflict(self):
        """现网正确映射不得被新闸门误杀（尤其甲基/甲氧基写法差异）。"""
        cases = [
            ("O6-Methyl-GTP", "O6-Methylguanosine-5'-Triphosphate"),
            ("5-Methyl-3'-dUTP", "3'-Deoxy-5-Methyluridine-5'-Triphosphate"),
            ("N2-Methyl-dGTP", "N2-Methyl-2'-deoxyguanosine-5'-Triphosphate"),
            ("N1-Methylpseudo-UTP", "N1-Methylpseudo-UTP"),
            ("5-Methoxy-UTP", "5-Methoxyuridine-5'-Triphosphate"),
            ("5-Propynyl-dUTP", "5-Propynyl-2'-deoxyuridine-5'-Triphosphate"),
            ("2'-Amino-dUTP", "2'-Amino-2'-deoxyuridine-5'-Triphosphate"),
            ("2'-Azido-dGTP", "2'-Azido-2'-deoxyguanosine-5'-Triphosphate"),
            ("5-Bromo-2'-dCTP", "5-Bromo-2'-deoxycytidine-5'-Triphosphate"),
            ("5-Carboxy-dCTP", "5-Carboxy-dCTP"),
            ("7-Deaza-7-iodo-dGTP", "7-Deaza-7-iodo-dGTP"),
            ("Biotin-11-ATP", "Biotin-11-ATP"),
            ("Desthiobiotin-11-UTP", "Desthiobiotin-11-UTP"),
            ("6-Aza-dUTP", "6-Aza-2'-deoxyuridine-5'-Triphosphate"),
            ("2-thio-dCTP(1)", "2-Thio-2'-deoxycytidine-5'-Triphosphate"),
        ]
        for req, cand in cases:
            self.assertFalse(substituents_conflict(req, cand), f"{req} vs {cand}")

    def test_mapper_version_bumped_to_invalidate_cache(self):
        """匹配行为已变 → 必须 bump 版本，否则 Redis/DB 里的 v5 旧错结果继续命中。"""
        self.assertEqual(jena_matcher.MAPPER_VERSION, "6")


# ── 集成测试：matcher 必须真的拒收 ────────────────────────────────────────────
class MatcherSubstituentsGateTest(TestCase):
    def setUp(self):
        self._patches = []

    def tearDown(self):
        for p in self._patches:
            p.stop()

    def _with_index(self, records):
        idx, tmpdir = _build_index(records)
        self._patches.append(patch.object(jena_matcher, "_get_index", return_value=idx))
        self._patches[-1].start()
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        return idx

    def _match(self, identifier, synonyms=None, request_name=None):
        return jena_matcher._match_jena_no_cache(
            identifier, list(synonyms or []), request_name or identifier)

    # ---- 6 例错配必须全部被拒（name 路径「短名包含」）----
    def test_azido_ddatp_not_matched_to_plain_ddatp(self):
        self._with_index([{"jena_catalog_no": "NU-1015", "product_name": "ddATP"}])
        r = self._match("3'-Azido-ddATP")
        self.assertFalse(r["matched"])
        self.assertTrue(r["sources"][0]["signatures_conflict"])  # 拒因透明暴露

    def test_amino_ddctp_not_matched_to_plain_ddctp(self):
        self._with_index([{"jena_catalog_no": "NU-1016", "product_name": "ddCTP"}])
        self.assertFalse(self._match("3'-Amino-ddCTP")["matched"])

    def test_amino_ddgtp_not_matched_to_plain_ddgtp(self):
        self._with_index([{"jena_catalog_no": "NU-1017", "product_name": "ddGTP"}])
        self.assertFalse(self._match("3'-Amino-ddGTP")["matched"])

    def test_bromo_ddutp_not_matched_to_plain_ddutp(self):
        self._with_index([{"jena_catalog_no": "NU-1021", "product_name": "ddUTP"}])
        self.assertFalse(self._match("5-Bromo-ddUTP")["matched"])

    def test_desthiobiotin_not_matched_to_biotin(self):
        self._with_index([{"jena_catalog_no": "BIOTIUM-X", "product_name": "Biotin-11-UTP"}])
        self.assertFalse(self._match("Desthiobiotin-11-UTP")["matched"])

    def test_amino_dgtp_not_matched_via_synonym_substring(self):
        """2'-Amino-2'-deoxyguanosine-5'-Triphosphate ⊃ 2'-deoxyguanosine-5'-triphosphate。"""
        self._with_index([{
            "jena_catalog_no": "N-2503",
            "product_name": "2'-Deoxyguanosine-5'-Triphosphate",
            "cas_number": None,
        }])
        r = self._match(
            "2'-Amino-dGTP",
            synonyms=["2'-Amino-2'-deoxyguanosine-5'-Triphosphate"],
            request_name="2'-Amino-dGTP",
        )
        self.assertFalse(r["matched"])

    # ---- 回归：正确映射必须保留 ----
    def test_correct_desthiobiotin_still_matched(self):
        self._with_index([{"jena_catalog_no": "NU-821-D",
                           "product_name": "Desthiobiotin-11-UTP"}])
        r = self._match("Desthiobiotin-11-UTP")
        self.assertTrue(r["matched"])
        self.assertFalse(r["sources"][0]["signatures_conflict"])

    def test_correct_methyl_via_synonym_still_matched(self):
        """O6-Methyl-GTP → O6-Methylguanosine-5'-Triphosphate（甲基写法差异不可误杀）。"""
        self._with_index([{"jena_catalog_no": "N-1031",
                           "product_name": "O6-Methylguanosine-5'-Triphosphate"}])
        r = self._match("O6-Methyl-GTP",
                        synonyms=["O6-Methylguanosine-5'-Triphosphate"],
                        request_name="O6-Methyl-GTP")
        self.assertTrue(r["matched"])

    def test_correct_amino_dutp_still_matched(self):
        self._with_index([{"jena_catalog_no": "N-1027",
                           "product_name": "2'-Amino-2'-deoxyuridine-5'-Triphosphate"}])
        r = self._match("2'-Amino-dUTP",
                        synonyms=["2'-Amino-2'-deoxyuridine-5'-Triphosphate"],
                        request_name="2'-Amino-dUTP")
        self.assertTrue(r["matched"])

    def test_correct_propynyl_still_matched(self):
        self._with_index([{"jena_catalog_no": "N-2017",
                           "product_name": "5-Propynyl-2'-deoxyuridine-5'-Triphosphate"}])
        r = self._match("5-Propynyl-dUTP",
                        synonyms=["5-Propynyl-2'-deoxyuridine-5'-Triphosphate"],
                        request_name="5-Propynyl-dUTP")
        self.assertTrue(r["matched"])

    def test_cas_exact_match_unaffected_by_substituent_gate(self):
        """CAS 精确命中 = 同一化合物，命名差异不得触发闸门。"""
        self._with_index([{
            "jena_catalog_no": "NU-1001",
            "product_name": "dATP - Solution",
            "cas_number": "1927-31-7",
        }])
        r = self._match("1927-31-7")
        self.assertTrue(r["matched"])
        src = r["sources"][0]
        self.assertEqual(src["match_key"], "cas")
        self.assertFalse(src["signatures_conflict"])
