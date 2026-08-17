"""
TDD 规格/回归：crawl_bioz_jena 命令可导入且已注册（第一版 §9 步骤3 Bioz 实抓前置）。

注：原始 `apps.knowledge.services.jena_index` 错误导入已由 #346 修复；
本测试作为回归守卫，确保命令模块可导入、Command 类存在、且被 Django 命令系统识别。
若将来有人误改导入路径导致 ModuleNotFoundError，本测试会立刻 RED 报警。
"""
from django.test import TestCase
from django.core.management import get_commands


class CrawlBiozImportTest(TestCase):
    def test_command_registered(self):
        self.assertIn(
            'crawl_bioz_jena', get_commands(),
            "crawl_bioz_jena 命令未被 Django 识别（可能 app 未注册或模块损坏）",
        )

    def test_module_importable_with_command_class(self):
        from apps.bridges.management.commands import crawl_bioz_jena
        self.assertTrue(
            hasattr(crawl_bioz_jena, 'Command'),
            "crawl_bioz_jena 模块缺少 Command 类（导入路径可能已损坏）",
        )

    def test_bioz_client_importable(self):
        # 命令依赖的 Bioz 客户端必须可导入（早期 bug 与此相关）
        from apps.knowledge.services.bioz_client import BiozClient  # noqa: F401
