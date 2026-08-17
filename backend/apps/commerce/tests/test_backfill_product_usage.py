"""
TDD RED: backfill_product_usage 命令（第一版 §9 步骤2 docx 入库之 usage 灌入）。

运行时应 FAIL：
- 命令模块尚不存在 → ImportError / CommandError
- 即便存在，未实现按 catalog 匹配灌入则断言失败

GREEN 后契约：
- 命令读取 backend/docx_products.json（key=`catalog`=SCxxxx, `usage`=厂商声称用途）
- 按 Product.catalog_no == docx.catalog 匹配，将 usage 灌入对应 Product.usage
- 空值安全：usage 为空/缺失的 docx 条目不覆盖已有值；无匹配的 Product 不动
- 幂等：重复运行结果一致
"""
import json
import os

from django.test import TestCase
from django.conf import settings
from django.core.management import call_command

from apps.commerce.models import Product
from apps.commerce.tests.factories import ProductFactory


def _docx_usage(catalog):
    path = os.path.join(settings.BASE_DIR, 'docx_products.json')
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    for r in data:
        if r.get('catalog') == catalog:
            return r.get('usage') or ''
    return None


class BackfillUsageCommandTest(TestCase):
    def test_command_module_importable(self):
        from apps.commerce.management.commands import backfill_product_usage  # noqa: F401

    def test_backfill_fills_matching_product(self):
        target = 'SC8001'
        expected = _docx_usage(target)
        self.assertIsNotNone(expected, "docx_products.json 缺少 SC8001 条目（测试前提）")

        p = ProductFactory(catalog_no=target, usage='')
        p.save()

        call_command('backfill_product_usage')

        p.refresh_from_db()
        self.assertEqual(
            p.usage, expected,
            "backfill 未将 docx usage 灌入匹配 catalog 的 Product",
        )

    def test_backfill_leaves_unmatched_untouched(self):
        p = ProductFactory(catalog_no='ZZ9999NOTINDOCS', usage='')
        p.save()

        call_command('backfill_product_usage')

        p.refresh_from_db()
        self.assertEqual(p.usage, '', "无匹配 catalog 的 Product 不应被改动")

    def test_backfill_idempotent(self):
        target = 'SC8001'
        expected = _docx_usage(target)
        p = ProductFactory(catalog_no=target, usage='')
        p.save()

        call_command('backfill_product_usage')
        call_command('backfill_product_usage')

        p.refresh_from_db()
        self.assertEqual(p.usage, expected)
