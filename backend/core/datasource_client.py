"""L3 统一外部数据源客户端 — 容错三件套：超时 + 重试 + 限速。

集中 PubChem/PubMed/ChEMBL 等外部 API 的 HTTP 调用容错，消除三套客户端各自为政：
- 超时：requests 调用强制传 timeout（兜底另有 settings 的 socket.setdefaulttimeout）
- 重试：tenacity 指数退避，针对瞬时故障（网络异常 / 429 / 503 / 504），尊重 Retry-After
- 限速：按数据源配置的令牌桶（PubChem 5 req/s，三套客户端共享同一桶）

本模块不依赖任何 Django app，可独立单测。详见 docs/DATASOURCE_RELIABILITY.md §4。
"""
import logging
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import requests
from tenacity import (
    Retrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
)

logger = logging.getLogger(__name__)

# 测试可 patch 的 sleep（tenacity 等待用），生产为 time.sleep
_sleep = time.sleep


# ── 各数据源令牌桶配置 ──────────────────────────────────────────
# (capacity, refill_rate_per_sec)。capacity 允许短时突发，refill_rate 是持续 QPS 上限。
# PubChem 官方限 5 req/s；PubMed 无 key 3 req/s；ChEMBL 响应慢保守 1 req/s；
# Bioz widget 无公开限速文档，保守 2 req/s。
# Europe PMC（EBI）未公布硬性 QPS 上限，官方只要求「合理使用」；实测单请求
# 约 1.9s，天然远低于限速，故保守配 2 req/s（显式声明，避免落 _DEFAULT_RATE）。
# 详见 docs/DATASOURCE_RELIABILITY.md §4.3
SOURCE_RATES = {
    "pubchem": (5, 5),
    "pubmed": (3, 3),
    "chembl": (1, 1),
    "bioz": (2, 2),
    "europepmc": (2, 2),
}
_DEFAULT_RATE = (1, 1)

# 可重试的 HTTP 状态码（限速 / 服务端临时不可用 / 网关超时）
RETRYABLE_STATUS = (429, 503, 504)


class TokenBucket:
    """线程安全令牌桶限速器。

    capacity: 桶容量（允许突发）
    refill_rate: 每秒补充令牌数（持续 QPS 上限）
    """

    def __init__(self, capacity: float, refill_rate: float):
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self._tokens = float(capacity)
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def _refill_locked(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate)
            self._last = now

    def acquire(self, tokens: float = 1.0, timeout: float = 30.0) -> None:
        """获取令牌；不足则阻塞等待，超时抛 TimeoutError。"""
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                self._refill_locked()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                deficit = tokens - self._tokens
                wait_for = deficit / self.refill_rate if self.refill_rate > 0 else 1.0
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"TokenBucket acquire timeout (need {tokens}, have ~{self._tokens:.2f})"
                )
            _sleep(min(wait_for, remaining))

    @property
    def tokens(self) -> float:
        """当前可用令牌数（近似，用于观测/测试）。"""
        with self._lock:
            self._refill_locked()
            return self._tokens


# ── 按数据源共享的令牌桶单例 ────────────────────────────────────
# 三套 PubChem 客户端（pubchem_enhancer / product_validator / pubchem_fetcher）
# 必须共享同一 'pubchem' 桶，否则各自限速仍会突破 PubChem 5 req/s 上限。
_buckets: dict = {}
_buckets_lock = threading.Lock()


def get_bucket(source: str) -> TokenBucket:
    """获取指定数据源的共享令牌桶（进程级单例，线程安全）。"""
    if source not in _buckets:
        with _buckets_lock:
            if source not in _buckets:
                cap, rate = SOURCE_RATES.get(source, _DEFAULT_RATE)
                _buckets[source] = TokenBucket(cap, rate)
    return _buckets[source]


def _reset_buckets() -> None:
    """清空所有共享令牌桶（测试隔离用，生产不调用）。"""
    with _buckets_lock:
        _buckets.clear()


# ── 可重试的 HTTP 异常 ──────────────────────────────────────────
class RetryableHttpError(Exception):
    """429/503/504 等可重试 HTTP 状态码。携带 retry_after（秒）供退避策略读取。"""

    def __init__(self, status_code: int, retry_after: Optional[float] = None, url: str = ""):
        self.status_code = status_code
        self.retry_after = retry_after
        self.url = url
        super().__init__(f"HTTP {status_code} (retry_after={retry_after}) {url}")


def _parse_retry_after(resp) -> Optional[float]:
    """解析 Retry-After 头：秒数或 HTTP 日期。返回秒数或 None。"""
    headers = getattr(resp, "headers", None) or {}
    val = headers.get("Retry-After")
    if not val:
        return None
    # 秒数形式（"120"）
    try:
        return max(0.0, float(val))
    except (TypeError, ValueError):
        pass
    # HTTP 日期形式（"Wed, 21 Oct 2025 07:28:00 GMT"）
    try:
        dt = parsedate_to_datetime(val)
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = (dt - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, delta)
    except (TypeError, ValueError, OverflowError):
        return None


def _wait_strategy(retry_state) -> float:
    """tenacity wait 回调：RetryableHttpError 携带 retry_after 时优先用，否则指数退避。

    退避序列（按 attempt_number）：1s → 2s → 4s，封顶 8s。
    """
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if isinstance(exc, RetryableHttpError) and exc.retry_after:
        return min(exc.retry_after, 30.0)  # 上限 30s，避免过长阻塞
    attempt = retry_state.attempt_number
    return float(min(2 ** (attempt - 1), 8))


def _do_request(method: str, url: str, source: str, timeout: float, **kwargs):
    """单次 HTTP 调用：限速 → 请求 → 状态码判定。供 tenacity 重试包装。"""
    get_bucket(source).acquire(timeout=timeout)
    resp = requests.request(method, url, timeout=timeout, **kwargs)
    if resp.status_code in RETRYABLE_STATUS:
        raise RetryableHttpError(resp.status_code, _parse_retry_after(resp), url)
    return resp


# 可重试的异常类型：网络异常 + 超时 + 可重试 HTTP 状态
_RETRYABLE_EXC = (
    requests.ConnectionError,
    requests.Timeout,
    RetryableHttpError,
)


def request_with_resilience(
    method: str,
    url: str,
    source: str = "pubchem",
    timeout: float = 15.0,
    retries: int = 3,
    **kwargs,
):
    """带容错三件套的 HTTP 请求入口。

    组合：令牌桶限速（按 source）+ tenacity 重试（瞬时故障）+ 强制超时。
    成功返回 requests.Response；重试耗尽后抛出最后一次异常（reraise）。

    Args:
        method: HTTP 方法（GET/POST/...）
        url: 请求 URL
        source: 数据源标识（pubchem/pubmed/chembl/bioz），决定限速桶
        timeout: 单次请求超时秒数（同时作为令牌桶 acquire 的最长等待）
        retries: 最大尝试次数（含首次）
        **kwargs: 透传 requests.request（params/data/headers 等）
    """
    retrying = Retrying(
        stop=stop_after_attempt(retries),
        wait=_wait_strategy,
        retry=retry_if_exception_type(_RETRYABLE_EXC),
        reraise=True,
        sleep=_sleep,
        before_sleep=before_sleep_log(logger, logging.INFO),
    )
    for attempt in retrying:
        with attempt:
            return _do_request(method, url, source, timeout, **kwargs)
