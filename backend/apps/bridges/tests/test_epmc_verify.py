"""TDD: epmc_verify —— EPMC 命中「逐字可核验」闸门（宁 miss 不错配）。"""
import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.bridges.services import epmc_verify

FETCH = "apps.bridges.services.epmc_verify.request_with_resilience"


class CanonicalTest(TestCase):
    def test_removes_all_whitespace(self):
        # EPMC 全文把下角标包成标签，剥标签后会切成 'n 1 -methylpseudo-utp'
        self.assertEqual(epmc_verify.canonical("n 1 -Methylpseudo-UTP"),
                         "n1-methylpseudo-utp")

    def test_normalizes_apostrophes_and_dashes(self):
        self.assertEqual(epmc_verify.canonical("2\u2032-Azido\u2011dGTP"),
                         "2'-azido-dgtp")

    def test_strips_xml_tags(self):
        self.assertEqual(epmc_verify.canonical("<i>Biotin</i>-11-ATP"),
                         "biotin-11-atp")

    def test_empty_is_empty(self):
        self.assertEqual(epmc_verify.canonical(""), "")
        self.assertEqual(epmc_verify.canonical(None), "")


class PatternsForTest(TestCase):
    def test_includes_name_and_dye_stripped_base(self):
        pats = epmc_verify.patterns_for("SC-UNKNOWN", "5\u2011Propargylamino\u2011CTP-Cy5")
        self.assertIn("5-propargylamino-ctp-cy5", pats)
        self.assertIn("5-propargylamino-ctp", pats)      # 去染料后缀

    def test_includes_evidenced_aliases(self):
        pats = epmc_verify.patterns_for("SC8012", "N1-Methylpseudo-UTP")
        self.assertIn("n1-methylpseudouridine", pats)
        self.assertIn("m1\u03c8tp", pats)

    def test_no_leading_trailing_space_in_canonical(self):
        pats = epmc_verify.patterns_for("SC8012", "N1-Methylpseudo-UTP")
        self.assertTrue(all(p == p.strip() for p in pats))
        self.assertTrue(all(" " not in p for p in pats))


class VerifyTextTest(TestCase):
    def test_hit_returns_matched_pattern(self):
        text = epmc_verify.canonical("we used 5-Methoxy-UTP for labeling")
        self.assertEqual(epmc_verify.verify_text(text, ["5-methoxy-utp"]), "5-methoxy-utp")

    def test_miss_returns_none(self):
        self.assertIsNone(epmc_verify.verify_text(epmc_verify.canonical("nothing"), ["5mou"]))

    def test_empty_text_returns_none(self):
        self.assertIsNone(epmc_verify.verify_text("", ["5-methoxy-utp"]))


class LoadAliasesTest(TestCase):
    def test_reads_repo_lexicon(self):
        aliases = epmc_verify.load_aliases()
        self.assertIn("SC8012", aliases)
        self.assertTrue(any("methylpseudouridine" in a for a in aliases["SC8012"]))

    def test_missing_file_returns_empty(self):
        self.assertEqual(epmc_verify.load_aliases("/nonexistent/aliases.json"), {})

    def test_malformed_file_returns_empty(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("{ not json")
            self.assertEqual(epmc_verify.load_aliases(path), {})
        finally:
            os.remove(path)


class FetchFulltextTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        os.environ["EPMC_FULLTEXT_CACHE"] = self.tmp

    def tearDown(self):
        os.environ.pop("EPMC_FULLTEXT_CACHE", None)

    def _resp(self, status, text):
        m = MagicMock()
        m.status_code = status
        m.text = text
        return m

    def test_200_returns_canonical_and_caches(self):
        with patch(FETCH, return_value=self._resp(200, "<p>5-Methoxy-UTP</p>")) as m:
            first = epmc_verify.fetch_fulltext("PMC1")
            second = epmc_verify.fetch_fulltext("PMC1")     # 命中磁盘缓存
        self.assertEqual(first, "5-methoxy-utp")
        self.assertEqual(second, "5-methoxy-utp")
        self.assertEqual(m.call_count, 1)

    def test_404_returns_empty(self):
        with patch(FETCH, return_value=self._resp(404, "no")):
            self.assertEqual(epmc_verify.fetch_fulltext("PMCx"), "")

    def test_404_is_cached_negatively(self):
        # 404 = 确定性（不在 OA 子集）→ 缓存负结果，不重复取
        with patch(FETCH, return_value=self._resp(404, "no")) as m:
            epmc_verify.fetch_fulltext("PMCz")
            epmc_verify.fetch_fulltext("PMCz")
        self.assertEqual(m.call_count, 1)

    def test_5xx_is_not_cached(self):
        # 5xx 瞬时 → 不缓存，下次仍重试
        with patch(FETCH, return_value=self._resp(503, "busy")) as m:
            epmc_verify.fetch_fulltext("PMC5z")
            epmc_verify.fetch_fulltext("PMC5z")
        self.assertEqual(m.call_count, 2)

    def test_exception_returns_empty(self):
        with patch(FETCH, side_effect=ConnectionError("boom")):
            self.assertEqual(epmc_verify.fetch_fulltext("PMCy"), "")

    def test_blank_pmcid_returns_empty(self):
        self.assertEqual(epmc_verify.fetch_fulltext(""), "")


class VerifyRecordsTest(TestCase):
    def test_verdicts_by_fulltext(self):
        good = {"pmid": "1", "_pmcid": "PMC1"}
        bad = {"pmid": "2", "_pmcid": "PMC2"}
        none = {"pmid": "3", "_pmcid": ""}

        def fake(pmcid, **kw):
            if pmcid == "PMC1":
                return epmc_verify.canonical("5-Methoxy-UTP was used")
            if pmcid == "PMC2":
                return epmc_verify.canonical("totally unrelated")
            return ""

        with patch("apps.bridges.services.epmc_verify.fetch_fulltext", side_effect=fake):
            out = epmc_verify.verify_records([good, bad, none], "SC-X", "5-Methoxy-UTP")
        self.assertEqual([v for _, v, _ in out], ["verified", "unverified", "unknown"])
        self.assertEqual(out[0][2], "5-methoxy-utp")
