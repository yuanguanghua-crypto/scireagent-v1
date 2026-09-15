"""TDD: crawl_europepmc_evidence —— EPMC 全文检索落 DataSourceCache（复用 pubmed 槽位）。

覆盖：解析（含丢无题/无 ID、authors 拆解、journal→source 映射）、dry-run 不写、
--apply 写入且形状对齐 adopt 的 pubmed 分支、已有非空证据则跳过、--force 覆盖、
非 ASCII 破折号 0 命中时回退 ASCII 名重试、网络异常不中断整批。
"""
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase

from apps.bridges.management.commands import crawl_europepmc_evidence as mod
from apps.commerce.models import Product
from apps.documents.models import DataSourceCache
from apps.documents.services.datasource_cache import get_cache, set_cache

PATCH_TARGET = ("apps.bridges.management.commands."
                "crawl_europepmc_evidence.request_with_resilience")


def _resp(payload, ok=True):
    m = MagicMock()
    m.ok = ok
    m.json.return_value = payload
    return m


def _payload(records):
    return {"resultList": {"result": records}}


def _rec(pmid="100", title="A paper", journal="Nat Commun", year="2021",
         authors="Ann A, Bob B.", doi="10.1/x", source="MED"):
    return {"id": pmid, "pmid": pmid, "title": title, "journalTitle": journal,
            "pubYear": year, "authorString": authors, "doi": doi,
            "source": source}


class ParseEpmcResultsTest(TestCase):
    def test_maps_to_pubmed_slot_shape(self):
        recs = mod.parse_epmc_results(_payload([_rec()]))
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual(r["pmid"], "100")
        self.assertEqual(r["title"], "A paper")
        self.assertEqual(r["source"], "Nat Commun")   # journal 放在 source（pubmed 槽位约定）
        self.assertEqual(r["doi"], "10.1/x")
        self.assertEqual(r["pubdate"], "2021")
        self.assertEqual(r["authors"], ["Ann A", "Bob B"])
        self.assertEqual(r["_index"], "europepmc")    # 真实索引来源，供审计

    def test_drops_record_without_title(self):
        recs = mod.parse_epmc_results(_payload([_rec(title=""), _rec(title="Keep")]))
        self.assertEqual([r["title"] for r in recs], ["Keep"])

    def test_drops_preprint_source(self):
        """PPR（预印本）id 不是 PMID —— 必须丢弃，否则污染 pmid 字段。"""
        recs = mod.parse_epmc_results(_payload([
            _rec(pmid="PPR907590", source="PPR"),
            _rec(pmid="200", source="PMC"),
            _rec(pmid="300", source="MED"),
        ]))
        self.assertEqual([r["pmid"] for r in recs], ["200", "300"])

    def test_drops_non_numeric_pmid(self):
        recs = mod.parse_epmc_results(_payload([_rec(pmid="abc", source="MED")]))
        self.assertEqual(recs, [])

    def test_tolerates_garbage_payload(self):
        for bad in (None, [], "x", {}, {"resultList": None},
                    {"resultList": {"result": "nope"}}, {"resultList": {"result": [1, 2]}}):
            self.assertEqual(mod.parse_epmc_results(bad), [])

    def test_ascii_dashes_normalizes_unicode_hyphen(self):
        self.assertEqual(mod.ascii_dashes("5\u2011Propargylamino\u2011CTP-Cy3"),
                         "5-Propargylamino-CTP-Cy3")
        self.assertEqual(mod.ascii_dashes("ATP"), "ATP")


class CrawlCommandTest(TestCase):
    def setUp(self):
        self.p = Product.objects.create(
            name="5-Methoxy-UTP", catalog_no="SC-T1", slug="sc-t1", status="draft")

    def _run(self, *args, **kwargs):
        call_command("crawl_europepmc_evidence", *args, **kwargs)

    def test_dry_run_writes_nothing(self):
        with patch(PATCH_TARGET, return_value=_resp(_payload([_rec()]))):
            self._run()
        self.assertIsNone(get_cache("pubmed", "SC-T1", "sku"))

    def test_apply_writes_pubmed_slot_row(self):
        with patch(PATCH_TARGET, return_value=_resp(_payload([_rec()]))):
            self._run("--apply")
        row = DataSourceCache.objects.get(source="pubmed", query_key="SC-T1",
                                         query_namespace="sku")
        data = row.get_data()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["source"], "Nat Commun")
        self.assertEqual(data[0]["authors"], ["Ann A", "Bob B"])

    def test_skips_product_with_existing_nonempty_evidence(self):
        set_cache("pubmed", "SC-T1", "sku", [{"article_title": "old", "pmid": "9"}])
        with patch(PATCH_TARGET, return_value=_resp(_payload([_rec()]))) as m:
            self._run("--apply")
        m.assert_not_called()  # 未发起请求
        self.assertEqual(get_cache("pubmed", "SC-T1", "sku").get_data()[0]["pmid"], "9")

    def test_force_overwrites_existing(self):
        set_cache("pubmed", "SC-T1", "sku", [{"article_title": "old", "pmid": "9"}])
        with patch(PATCH_TARGET, return_value=_resp(_payload([_rec()]))):
            self._run("--apply", "--force")
        self.assertEqual(get_cache("pubmed", "SC-T1", "sku").get_data()[0]["pmid"], "100")

    def test_falls_back_to_ascii_name_when_first_query_empty(self):
        Product.objects.create(name="5\u2011Propargylamino\u2011CTP-Cy5",
                               catalog_no="SC-T2", slug="sc-t2", status="draft")
        calls = []

        def fake(method, url, **kw):
            q = kw["params"]["query"]
            calls.append(q)
            if "\u2011" in q:
                return _resp(_payload([]))
            return _resp(_payload([_rec()]))

        with patch(PATCH_TARGET, side_effect=fake):
            self._run("--apply", "--only-products", "SC-T2")
        self.assertEqual(len(calls), 2)
        self.assertIn("\u2011", calls[0])
        self.assertNotIn("\u2011", calls[1])
        row = DataSourceCache.objects.get(source="pubmed", query_key="SC-T2")
        self.assertEqual(len(row.get_data()), 1)

    def test_network_error_does_not_abort_batch(self):
        Product.objects.create(name="Biotin-11-ATP", catalog_no="SC-T3",
                               slug="sc-t3", status="draft")

        def fake(method, url, **kw):
            if "SC-T1" in "" or "Methoxy" in kw["params"]["query"]:
                raise ConnectionError("boom")
            return _resp(_payload([_rec()]))

        with patch(PATCH_TARGET, side_effect=fake):
            self._run("--apply")  # 不应抛异常
        self.assertIsNone(get_cache("pubmed", "SC-T1", "sku"))
        self.assertEqual(len(get_cache("pubmed", "SC-T3", "sku").get_data()), 1)

    def test_empty_result_not_written(self):
        with patch(PATCH_TARGET, return_value=_resp(_payload([]))):
            self._run("--apply")
        self.assertIsNone(get_cache("pubmed", "SC-T1", "sku"))

    def test_non_200_returns_no_records(self):
        with patch(PATCH_TARGET, return_value=_resp(None, ok=False)):
            self._run("--apply")
        self.assertIsNone(get_cache("pubmed", "SC-T1", "sku"))

    def test_only_products_and_limit(self):
        Product.objects.create(name="Biotin-11-GTP", catalog_no="SC-T4",
                               slug="sc-t4", status="draft")
        with patch(PATCH_TARGET, return_value=_resp(_payload([_rec()]))) as m:
            self._run("--apply", "--only-products", "SC-T4", "--limit", "1")
        self.assertEqual(m.call_count, 1)
        self.assertTrue(DataSourceCache.objects.filter(query_key="SC-T4").exists())

    def test_max_per_product_caps_records(self):
        many = [_rec(pmid=str(i)) for i in range(10)]
        with patch(PATCH_TARGET, return_value=_resp(_payload(many))):
            self._run("--apply", "--max-per-product", "3")
        self.assertEqual(len(get_cache("pubmed", "SC-T1", "sku").get_data()), 3)

    def test_out_dumps_full_records_for_injection(self):
        """--out 必须落完整 records（items），供导出注入生产 DataSourceCache。"""
        import json
        import os
        import tempfile

        fd, path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
        try:
            with patch(PATCH_TARGET, return_value=_resp(_payload([_rec(), _rec(pmid="101")]))):
                self._run("--only-products", "SC-T1", "--out", path)
            rows = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["catalog_no"], "SC-T1")
            self.assertEqual(rows[0]["records"], 2)
            self.assertEqual([r["pmid"] for r in rows[0]["items"]], ["100", "101"])
            self.assertEqual(rows[0]["items"][0]["_index"], "europepmc")
        finally:
            os.remove(path)
