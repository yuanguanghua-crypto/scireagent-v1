"""TDD: bioz_client widget API 集成 + L1 缓存"""
from unittest.mock import patch, MagicMock

from django.test import TestCase

from apps.knowledge.services import bioz_client
from apps.knowledge.services.bioz_client import BiozClient


_SAMPLE_PAYLOAD = {
    "records": [
        {
            "article_title": "Test paper",
            "authors": ["Author A", "Author B"],
            "journal": "Nature Communications",
            "impact_factor": 14.919,
            "pmid": "33542236",
            "pmcid": "7862312",
            "doi": "10.1038/xxx",
            "pub_date": "2021-02-04",
            "techniques": ["PCR"],
            "filter_data": [{"key": "Category", "value": ["mRNA"]}],
            "image_urls": [{"url": "http://x", "caption": "Fig 1"}],
            "long": "used reagent (Jena Biosciences, NU-1138)",
            "medium": ".. (NU-1138) ..",
            "short": "(NU-1138)",
            "catalog_group": ["nu-1138", "nu-1138l"],
            "catalog_number": "nu-1138",
        }
    ],
    "total": 1,
    "unique_articles": 1,
}


class BiozClientTest(TestCase):
    @patch("apps.knowledge.services.bioz_client.request_with_resilience")
    def test_search_by_sku_parses_records(self, mock_req):
        """widget 请求成功 → 解析 records 返回 list[dict]"""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = _SAMPLE_PAYLOAD
        mock_req.return_value = mock_resp

        client = BiozClient()
        records = client.search_by_sku("NU-1138", vendor="Jena Bioscience")

        self.assertEqual(len(records), 1)
        r = records[0]
        self.assertEqual(r["article_title"], "Test paper")
        self.assertEqual(r["journal"], "Nature Communications")
        self.assertEqual(r["impact_factor"], 14.919)
        self.assertEqual(r["pmid"], "33542236")
        self.assertEqual(r["catalog_group"], ["nu-1138", "nu-1138l"])
        # 请求参数
        call_kwargs = mock_req.call_args
        self.assertEqual(call_kwargs[1]["data"]["qx"], "NU-1138")
        self.assertEqual(call_kwargs[1]["data"]["cx"], "Jena Bioscience")
        self.assertEqual(call_kwargs[1]["source"], "bioz")

    @patch("apps.knowledge.services.bioz_client.request_with_resilience")
    def test_vendor_param_passed_to_body(self, mock_req):
        """vendor 参数透传到 body 的 cx（多厂商扩展验证）"""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = {"records": []}
        mock_req.return_value = mock_resp

        BiozClient().search_by_sku("MK-123", vendor="Merck")
        self.assertEqual(mock_req.call_args[1]["data"]["cx"], "Merck")

    @patch("apps.knowledge.services.bioz_client.request_with_resilience")
    def test_l1_cache_hit_skips_request(self, mock_req):
        """L1 缓存命中 → 跳过 widget 请求"""
        from apps.documents.models import DataSourceCache
        from apps.documents.services.datasource_cache import set_cache

        set_cache("bioz", "Jena Bioscience:NU-1138", "sku", [{"article_title": "cached"}])

        records = BiozClient().search_by_sku("NU-1138", vendor="Jena Bioscience")
        mock_req.assert_not_called()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["article_title"], "cached")

    @patch("apps.knowledge.services.bioz_client.request_with_resilience")
    def test_request_failure_returns_empty(self, mock_req):
        """请求异常 → 降级返回 []"""
        mock_req.side_effect = ConnectionError("timeout")
        records = BiozClient().search_by_sku("NU-1138")
        self.assertEqual(records, [])

    @patch("apps.knowledge.services.bioz_client.request_with_resilience")
    def test_non_200_returns_empty(self, mock_req):
        """非 200 → 返回 []"""
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 403
        mock_req.return_value = mock_resp
        records = BiozClient().search_by_sku("NU-1138")
        self.assertEqual(records, [])

    def test_empty_catalog_no_request(self):
        """空 catalog_no → 直接返回 []，不请求"""
        with patch("apps.knowledge.services.bioz_client.request_with_resilience") as m:
            self.assertEqual(BiozClient().search_by_sku("", "Jena Bioscience"), [])
            m.assert_not_called()

    @patch("apps.knowledge.services.bioz_client.request_with_resilience")
    def test_l1_cache_written_after_success(self, mock_req):
        """成功后写 L1 缓存"""
        from apps.documents.models import DataSourceCache

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.json.return_value = _SAMPLE_PAYLOAD
        mock_req.return_value = mock_resp

        BiozClient().search_by_sku("NU-1138", vendor="Jena Bioscience")
        entry = DataSourceCache.objects.filter(
            source="bioz", query_key="Jena Bioscience:NU-1138", query_namespace="sku"
        ).first()
        self.assertIsNotNone(entry)
        self.assertEqual(len(entry.get_data()), 1)
