"""core/datasource_client.py 单测 — 容错三件套（令牌桶限速 / tenacity 重试 / Retry-After）。

纯逻辑测试，不依赖 Django DB。详见 docs/DATASOURCE_RELIABILITY.md §4。
"""
import threading
import time
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import MagicMock, patch

import requests
from django.test import SimpleTestCase

from core.datasource_client import (
    RetryableHttpError,
    TokenBucket,
    _parse_retry_after,
    _reset_buckets,
    _wait_strategy,
    get_bucket,
    request_with_resilience,
)


class TokenBucketTest(SimpleTestCase):
    def test_initial_capacity(self):
        b = TokenBucket(5, 5)
        self.assertAlmostEqual(b.tokens, 5, places=1)

    def test_acquire_decrements(self):
        b = TokenBucket(3, 0)
        b.acquire(1)
        self.assertAlmostEqual(b.tokens, 2, places=1)

    def test_refill_over_time(self):
        b = TokenBucket(10, 100)  # 100 tokens/s
        b.acquire(10)  # → 0
        self.assertAlmostEqual(b.tokens, 0, places=1)
        time.sleep(0.05)  # +5 tokens
        self.assertGreater(b.tokens, 1)

    def test_timeout_when_empty(self):
        b = TokenBucket(1, 0)  # no refill
        b.acquire(1)  # → 0
        with self.assertRaises(TimeoutError):
            b.acquire(1, timeout=0.3)

    def test_concurrent_acquires_respect_capacity(self):
        """capacity=2 / refill=0：5 个并发 acquire，只有 2 个立即成功。"""
        b = TokenBucket(2, 0)
        results = []

        def worker():
            try:
                b.acquire(1, timeout=0.2)
                results.append("ok")
            except TimeoutError:
                results.append("timeout")

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(results.count("ok"), 2)
        self.assertEqual(results.count("timeout"), 3)


class GetBucketTest(SimpleTestCase):
    def setUp(self):
        _reset_buckets()

    def test_same_source_same_instance(self):
        a = get_bucket("pubchem")
        b = get_bucket("pubchem")
        self.assertIs(a, b)

    def test_different_sources_different_instances(self):
        a = get_bucket("pubchem")
        b = get_bucket("pubmed")
        self.assertIsNot(a, b)

    def test_unknown_source_uses_default(self):
        b = get_bucket("mars_dataset")
        self.assertEqual((b.capacity, b.refill_rate), (1, 1))

    def test_known_rates(self):
        self.assertEqual((get_bucket("pubchem").capacity, get_bucket("pubchem").refill_rate), (5, 5))
        self.assertEqual((get_bucket("pubmed").capacity, get_bucket("pubmed").refill_rate), (3, 3))
        self.assertEqual((get_bucket("chembl").capacity, get_bucket("chembl").refill_rate), (1, 1))


class ParseRetryAfterTest(SimpleTestCase):
    def test_none_when_missing(self):
        self.assertIsNone(_parse_retry_after(MagicMock(headers={})))

    def test_seconds(self):
        self.assertEqual(_parse_retry_after(MagicMock(headers={"Retry-After": "120"})), 120.0)

    def test_http_date(self):
        future = datetime.now(timezone.utc) + timedelta(seconds=2)
        resp = MagicMock(headers={"Retry-After": format_datetime(future)})
        ra = _parse_retry_after(resp)
        self.assertIsNotNone(ra)
        self.assertGreater(ra, 0)
        self.assertLess(ra, 5)

    def test_invalid_returns_none(self):
        self.assertIsNone(_parse_retry_after(MagicMock(headers={"Retry-After": "not-a-date"})))


class WaitStrategyTest(SimpleTestCase):
    def _state(self, exc, attempt=1):
        m = MagicMock()
        m.outcome.exception.return_value = exc
        m.attempt_number = attempt
        return m

    def test_uses_retry_after_when_present(self):
        exc = RetryableHttpError(429, retry_after=5.0)
        self.assertEqual(_wait_strategy(self._state(exc)), 5.0)

    def test_caps_retry_after_at_30(self):
        exc = RetryableHttpError(429, retry_after=100.0)
        self.assertEqual(_wait_strategy(self._state(exc)), 30.0)

    def test_exponential_without_retry_after(self):
        exc = requests.Timeout("slow")
        self.assertEqual(_wait_strategy(self._state(exc, attempt=1)), 1.0)
        self.assertEqual(_wait_strategy(self._state(exc, attempt=2)), 2.0)
        self.assertEqual(_wait_strategy(self._state(exc, attempt=3)), 4.0)


@patch("core.datasource_client._sleep")  # 跳过 tenacity 真实等待，加速测试
class RequestWithResilienceTest(SimpleTestCase):
    def setUp(self):
        _reset_buckets()

    @patch("core.datasource_client.requests.request")
    def test_success_returns_response(self, mock_req, _sleep):
        mock_req.return_value = MagicMock(status_code=200)
        resp = request_with_resilience("GET", "http://x", source="pubchem")
        self.assertEqual(resp.status_code, 200)
        mock_req.assert_called_once()

    @patch("core.datasource_client.requests.request")
    def test_429_retries_then_succeeds(self, mock_req, _sleep):
        mock_req.side_effect = [MagicMock(status_code=429), MagicMock(status_code=200)]
        resp = request_with_resilience("GET", "http://x")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_req.call_count, 2)

    @patch("core.datasource_client.requests.request")
    def test_503_retries_then_succeeds(self, mock_req, _sleep):
        mock_req.side_effect = [MagicMock(status_code=503), MagicMock(status_code=200)]
        resp = request_with_resilience("GET", "http://x")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_req.call_count, 2)

    @patch("core.datasource_client.requests.request")
    def test_504_retries_then_succeeds(self, mock_req, _sleep):
        mock_req.side_effect = [MagicMock(status_code=504), MagicMock(status_code=200)]
        resp = request_with_resilience("GET", "http://x")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_req.call_count, 2)

    @patch("core.datasource_client.requests.request")
    def test_retries_exhausted_raises_retryable(self, mock_req, _sleep):
        mock_req.return_value = MagicMock(status_code=503)
        with self.assertRaises(RetryableHttpError):
            request_with_resilience("GET", "http://x")
        self.assertEqual(mock_req.call_count, 3)

    @patch("core.datasource_client.requests.request")
    def test_4xx_not_retried(self, mock_req, _sleep):
        """404 等非限速 4xx 不重试，直接返回。"""
        mock_req.return_value = MagicMock(status_code=404)
        resp = request_with_resilience("GET", "http://x")
        self.assertEqual(resp.status_code, 404)
        mock_req.assert_called_once()

    @patch("core.datasource_client.requests.request")
    def test_timeout_retries(self, mock_req, _sleep):
        mock_req.side_effect = requests.Timeout("slow")
        with self.assertRaises(requests.Timeout):
            request_with_resilience("GET", "http://x")
        self.assertEqual(mock_req.call_count, 3)

    @patch("core.datasource_client.requests.request")
    def test_connection_error_retries(self, mock_req, _sleep):
        mock_req.side_effect = requests.ConnectionError("down")
        with self.assertRaises(requests.ConnectionError):
            request_with_resilience("GET", "http://x")
        self.assertEqual(mock_req.call_count, 3)

    @patch("core.datasource_client.requests.request")
    def test_500_not_retried(self, mock_req, _sleep):
        """500 不在可重试集合（非 503），不重试直接返回。"""
        mock_req.return_value = MagicMock(status_code=500)
        resp = request_with_resilience("GET", "http://x")
        self.assertEqual(resp.status_code, 500)
        mock_req.assert_called_once()

    @patch("core.datasource_client.requests.request")
    def test_passes_through_kwargs(self, mock_req, _sleep):
        """params/headers 透传 requests.request。"""
        mock_req.return_value = MagicMock(status_code=200)
        request_with_resilience(
            "POST", "http://x", source="pubmed",
            params={"q": "aspirin"}, headers={"Accept": "application/json"},
            json={"a": 1},
        )
        _, kwargs = mock_req.call_args
        self.assertEqual(kwargs["params"], {"q": "aspirin"})
        self.assertEqual(kwargs["headers"], {"Accept": "application/json"})
        self.assertEqual(kwargs["json"], {"a": 1})
        self.assertEqual(kwargs["timeout"], 15.0)

    @patch("core.datasource_client.get_bucket")
    @patch("core.datasource_client.requests.request")
    def test_acquires_token_from_correct_bucket(self, mock_req, mock_get_bucket, _sleep):
        """调用前向对应 source 桶 acquire 令牌。"""
        mock_req.return_value = MagicMock(status_code=200)
        request_with_resilience("GET", "http://x", source="pubmed")
        mock_get_bucket.assert_called_with("pubmed")
        mock_get_bucket.return_value.acquire.assert_called_once()
