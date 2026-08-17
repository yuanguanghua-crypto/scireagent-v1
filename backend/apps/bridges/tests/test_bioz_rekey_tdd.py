"""TDD RED → GREEN: 收口缺口「bioz 缓存按 SC catalog_no 重键, 接通 S_B(literature 轴)」。

根因(已钉死并实测): load_product_bioz 按 [catalog_no, *sku_codes](SC 内部码)查 bioz 缓存,
而历史 bioz 缓存按厂商货号键入(如 Jena Bioscience:36544), 二者无法对齐 → S_B 全库恒 0
(实测 23431 行 ProductProtocol: score_b>0=0, lit>0=0)。

修复: rekey_bioz_by_sc() 对每个可经 resolve_jena 解析到厂商货号、且已有对应厂商键 bioz
缓存的产品, 写一条 SC 键别名(query_key=product.catalog_no), 使 loader 命中。离线操作
(只读 jena 索引), 仅写 DataSourceCache, 幂等。实测覆盖: 256 产品中 83 个可解析且 100%
已有对应 bioz 缓存 → S_B 将为这 83 个产品接通。

本测试用 mock resolve_jena 隔离对真实 jena 索引的依赖, 断言重键后 SC 键别名存在且
load_product_bioz 命中。
"""
import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.documents.models import DataSourceCache
from apps.bridges.services.relevance import load_product_bioz
from apps.commerce.tests.factories import ProductFactory


def _vendor_bioz_row(vendor_key, payload):
    return DataSourceCache.objects.create(
        source="bioz", query_key=vendor_key, query_namespace="sku",
        data_json=json.dumps(payload),
        expires_at=timezone.now() + timedelta(days=30),
    )


class BiozRekeyTddTest(TestCase):
    """收口缺口红灯: 重键后 SC 键别名须存在且 loader 命中。"""

    @patch("apps.bridges.management.commands.rekey_bioz_by_sc.resolve_jena")
    def test_rekey_writes_sc_alias_and_loader_hits(self, mock_resolve):
        product = ProductFactory(catalog_no="SC8123", name="5PropargylaminoCTP")
        _vendor_bioz_row(
            "Jena Bioscience:ATPNU-1015",
            [{"article_title": "rna labeling study", "techniques": "rna",
              "long": "", "medium": "", "short": ""}],
        )

        def fake_resolve(p):
            if p.get("catalog_no") == "SC8123":
                return ("ATPNU-1015", "Jena Bioscience")
            return None

        mock_resolve.side_effect = fake_resolve

        # 重键前: SC 键不存在, loader 返回 []
        self.assertFalse(
            DataSourceCache.objects.filter(source="bioz", query_key="SC8123").exists())
        self.assertEqual(load_product_bioz(product), [])

        from apps.bridges.management.commands.rekey_bioz_by_sc import rekey_bioz_by_sc
        n = rekey_bioz_by_sc()
        self.assertEqual(n, 1)

        # 重键后: SC 键别名存在且载荷非空
        alias = DataSourceCache.objects.filter(
            source="bioz", query_key="SC8123").first()
        self.assertIsNotNone(alias)
        self.assertEqual(len(alias.get_data()), 1)

        # 重键后: loader 命中 → S_B 计算原料到位
        self.assertEqual(len(load_product_bioz(product)), 1)

    @patch("apps.bridges.management.commands.rekey_bioz_by_sc.resolve_jena")
    def test_rekey_is_idempotent(self, mock_resolve):
        ProductFactory(catalog_no="SC8123")
        _vendor_bioz_row(
            "Jena Bioscience:ATPNU-1015",
            [{"article_title": "x", "techniques": "", "long": "", "medium": "", "short": ""}],
        )

        def fake_resolve(p):
            if p.get("catalog_no") == "SC8123":
                return ("ATPNU-1015", "Jena Bioscience")
            return None

        mock_resolve.side_effect = fake_resolve

        from apps.bridges.management.commands.rekey_bioz_by_sc import rekey_bioz_by_sc
        rekey_bioz_by_sc()
        before = DataSourceCache.objects.filter(source="bioz").count()
        n2 = rekey_bioz_by_sc()
        after = DataSourceCache.objects.filter(source="bioz").count()
        self.assertEqual(after, before)   # 不重复写入
        self.assertEqual(n2, 0)

    @patch("apps.bridges.management.commands.rekey_bioz_by_sc.resolve_jena")
    def test_rekey_skips_unresolved(self, mock_resolve):
        ProductFactory(catalog_no="SC8123")
        mock_resolve.return_value = None

        from apps.bridges.management.commands.rekey_bioz_by_sc import rekey_bioz_by_sc
        n = rekey_bioz_by_sc()
        self.assertEqual(n, 0)
        self.assertFalse(
            DataSourceCache.objects.filter(source="bioz", query_key="SC8123").exists())
