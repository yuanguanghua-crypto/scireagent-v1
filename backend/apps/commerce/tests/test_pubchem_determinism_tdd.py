"""TDD RED → GREEN: #473-A1 / #475 化学段确定性——缓存键须含 formula/mw。

根因（已钉死）：pubchem_enhancer.resolve_to_properties 的缓存键
  cache_key = f'pubchem:resolve:{namespace}:{identifier}:{expected_cas or ""}'
未纳入 expected_formula / expected_mw。两个同名但文档公式不同的产品会命中同一缓存项，
复用错误化合物的 formula_mismatch / mw_mismatch 状态 → 跨文档污染（#474 非确定性的一类）。

修复：缓存键纳入 expected_formula + expected_mw（与命名空间/标识同列），保证不同文档上下
文落到不同缓存槽，杜绝错配复现（铁律①：未验证/文档不符绝不自动套用）。

本测试离线（patch 底层网络 + L1），仅验证缓存键构造随 formula/mw 变化而不同。
"""
from unittest.mock import patch

from django.test import TestCase

from apps.commerce.services.validators import pubchem_enhancer
from apps.commerce.services.validators.pubchem_enhancer import PubChemEnhancer


_CANNED = {
    "source": "pubchem", "found": True, "namespace": "name",
    "resolved_name": "aspirin", "cid": 2244,
    "properties": {"molecular_formula": "C9H8O4", "molecular_weight": 180.16},
    "candidates": [], "identity_verified": True, "requires_review": False,
    "confidence": "verified", "formula_mismatch": False, "mw_mismatch": False,
    "doc_value_mismatch": False,
}


class PubChemCacheKeyDeterminismTest(TestCase):
    def test_cache_key_includes_formula_and_mw(self):
        """同名不同文档 formula/MW → 缓存键必须不同，避免错配缓存复用。"""
        get_keys = []

        def fake_cache_get(key):
            get_keys.append(key)
            return None

        def fake_cache_set(key, val, ttl=None):
            return None

        enhancer = PubChemEnhancer()
        with patch.object(pubchem_enhancer, "PUBCHEMPY_AVAILABLE", True), \
             patch.object(PubChemEnhancer, "_resolve_to_properties_impl",
                          return_value=dict(_CANNED)), \
             patch("apps.documents.services.datasource_cache.get_cache",
                   return_value=None), \
             patch("apps.documents.services.datasource_cache.set_cache",
                   return_value=None), \
             patch("core.datasource_client.get_bucket") as mkb:
            mkb.return_value.acquire.return_value = None
            with patch.object(pubchem_enhancer.cache, "get", fake_cache_get), \
                 patch.object(pubchem_enhancer.cache, "set", fake_cache_set):
                enhancer.resolve_to_properties(
                    "aspirin", namespace="name",
                    expected_formula="C9H8O4", expected_mw=180.16)
                enhancer.resolve_to_properties(
                    "aspirin", namespace="name",
                    expected_formula="C8H8O2", expected_mw=136.15)

        self.assertEqual(len(get_keys), 2)
        self.assertNotEqual(
            get_keys[0], get_keys[1],
            "缓存键未随 expected_formula/expected_mw 变化——会复用错配缓存 (#475)")
        # 键中应显式含 formula 片段，便于审计
        self.assertIn("C9H8O4", get_keys[0])
        self.assertIn("C8H8O2", get_keys[1])
