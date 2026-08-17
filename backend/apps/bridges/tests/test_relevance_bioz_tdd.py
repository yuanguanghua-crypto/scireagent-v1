"""TDD RED → GREEN: #473-B2 修复 load_product_bioz 静默死轴。

根因（已钉死）：relevance.load_product_bioz 从 apps.knowledge.models 导入 DataSourceCache
（模型实属 apps.documents.models）→ ImportError 被 try/except 吞 → 永远返回 []；且
filter 用不存在的 resolved_catalog 列、取 r.payload（真实是 get_data()）。三处缺陷叠加
使轴B 文献轴全库恒为 0（literature 档从未触发）。

本测试断言：当存在以产品可解析键（catalog_no / 关联 SKU.sku_code）键入的 bioz 缓存行时，
load_product_bioz 必须返回该文献载荷（不再静默 []）。

注：生产 S_B 仍无法接通属独立数据缺口（bioz 缓存按厂商货号键入，产品不持厂商货号），
不属本 loader 代码缺陷，需另行按 SC catalog_no 重键 bioz 缓存。
"""
import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.documents.models import DataSourceCache
from apps.bridges.services.relevance import load_product_bioz
from apps.commerce.tests.factories import ProductFactory
from apps.commerce.models import SKU


def _bioz_row(query_key, payload):
    return DataSourceCache.objects.create(
        source="bioz", query_key=query_key, query_namespace="sku",
        data_json=json.dumps(payload),
        expires_at=timezone.now() + timedelta(days=30),
    )


class LoadProductBiozTddTest(TestCase):
    """B2 红灯：键对齐时 loader 必须返回 bioz 载荷（当前因 import/字段 bug 返回 []）。"""

    def test_returns_payload_when_cached_by_catalog_no(self):
        product = ProductFactory(catalog_no="SC8123")
        payload = [{
            "article_title": "rna sequencing study",
            "techniques": "rna sequencing",
            "long": "", "medium": "", "short": "",
        }]
        _bioz_row("SC8123", payload)
        out = load_product_bioz(product)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["article_title"], "rna sequencing study")

    def test_returns_payload_when_cached_by_sku_code(self):
        product = ProductFactory(catalog_no="SC8124")
        SKU.objects.create(
            product=product, sku_code="SC8124-100ul", pack_size="100 μL",
            is_default=True,
        )
        payload = [{
            "article_title": "pcr optimization",
            "techniques": "pcr",
            "long": "", "medium": "", "short": "",
        }]
        _bioz_row("SC8124-100ul", payload)
        out = load_product_bioz(product)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["article_title"], "pcr optimization")

    def test_returns_empty_when_no_bioz_cache(self):
        product = ProductFactory(catalog_no="SC8999")
        out = load_product_bioz(product)
        self.assertEqual(out, [])

    def test_does_not_raise_when_datasourcecache_import_broken(self):
        """回归守卫：即便导入路径异常，也应安全降级 [] 而非抛栈。"""
        product = ProductFactory(catalog_no="SC8131")
        with patch("apps.bridges.services.relevance.DataSourceCache",
                   side_effect=ImportError("simulated"), create=True):
            out = load_product_bioz(product)
        self.assertEqual(out, [])
