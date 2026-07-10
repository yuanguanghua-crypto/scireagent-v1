"""Pytest 全局配置。

每个测试隔离外部可变状态：
- Django cache（cache-aside 跨测试累积，会污染断言）→ 清空
- datasource_client 令牌桶单例（限速状态跨测试）→ 重置
- tenacity 真实 sleep（重试退避拖慢测试）→ no-op 替代

生产环境正常使用缓存/限速/重试，仅测试需隔离与加速。
"""
import pytest
from django.core.cache import cache

from core.datasource_client import _reset_buckets


@pytest.fixture(autouse=True)
def _clear_cache_between_tests():
    """每个测试隔离：清 cache + 重置令牌桶 + 跳过 tenacity 真实 sleep。"""
    from core import datasource_client as dsc
    orig_sleep = dsc._sleep
    dsc._sleep = lambda *a, **k: None
    _reset_buckets()
    cache.clear()
    try:
        yield
    finally:
        dsc._sleep = orig_sleep
        _reset_buckets()
        cache.clear()
