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

    # ── ★ 2026-09-24 P2 保护：默认**只填空值**，不覆盖已有内容 ──────────────
    def test_default_does_not_overwrite_existing_usage(self):
        """已有 usage（如研究员手填）默认**不得被 docx 覆盖**。

        背景：P2 要给研究员一个录入 `usage` 的入口；而本命令原先**无条件覆盖**
        （只在"同值"时跳过）⇒ 会把手填内容静默冲掉。此用例锁住修正后的语义。
        """
        target = 'SC8001'
        self.assertIsNotNone(_docx_usage(target), 'docx_products.json 缺 SC8001（测试前提）')
        manual = 'MANUAL-USAGE: researcher-entered text that must survive backfill'
        p = ProductFactory(catalog_no=target, usage=manual)
        p.save()

        call_command('backfill_product_usage')

        p.refresh_from_db()
        self.assertEqual(p.usage, manual, '默认必须不覆盖已有值（保护人工录入/既有内容）')

    def test_force_flag_overwrites_existing_usage(self):
        """`--force` 是**显式**的覆盖开关（需要 docx 语料刷新时才用）。"""
        target = 'SC8001'
        expected = _docx_usage(target)
        self.assertIsNotNone(expected, 'docx_products.json 缺 SC8001（测试前提）')
        p = ProductFactory(catalog_no=target, usage='OLD-VALUE-BEFORE-FORCE')
        p.save()

        call_command('backfill_product_usage', force=True)

        p.refresh_from_db()
        self.assertEqual(p.usage, expected, '--force 时应覆盖为 docx 值')

    def test_dry_run_writes_nothing(self):
        """`--dry-run` 只报告不落库（默认模式下也不得写）。"""
        p = ProductFactory(catalog_no='SC8001', usage='')
        p.save()

        call_command('backfill_product_usage', dry_run=True)

        p.refresh_from_db()
        self.assertEqual(p.usage, '', 'dry-run 不得落库')
