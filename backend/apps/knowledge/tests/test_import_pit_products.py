"""TDD：import_pit_products 必须写入**合法**的 status。

背景：该命令原写 `status='published'`，而 Product 状态机（core StatusMixin）的合法枚举
只有 `draft / active / deprecated / archived` ⇒ 这是**枚举外的非法中间态**。
既有 `normalize_product_status` 的清洗规则是：

    非法状态 + archived=True  → 'archived'
    非法状态 + archived=False → 'draft'   ← 「不得自动上站，需人工定夺」

故命令直接写 `draft` 是**行为等价的正解**：去掉非法中间态，终态与今天清洗后一致。
（另有一个副作用被顺带消除：`site_views` 的公开面按 `status__in=['active','published']`
 过滤，非法值 'published' 会让这些产品在被清洗前短暂上站、清洗后又消失。）
"""
import json
import tempfile

from django.core.management import call_command
from django.test import TestCase

from apps.commerce.models import Product


class ImportPitProductsStatusTest(TestCase):
    """命令导入的产品必须落在合法枚举内。"""

    def _run(self, data):
        with tempfile.NamedTemporaryFile(
            'w', suffix='.json', delete=False, encoding='utf-8'
        ) as f:
            json.dump(data, f)
            path = f.name
        call_command('import_pit_products', file=path)

    def test_imported_product_uses_legal_status(self):
        self._run([{
            'catalog_no': 'PIT-TEST-1',
            'product_name': 'PIT Test Product',
            'cas_number': '56-65-5',
            'skus': [],
        }])
        p = Product.objects.get(catalog_no='PIT-TEST-1')
        legal = tuple(c[0] for c in Product.Status.choices)
        self.assertIn(p.status, legal,
                      f'命令写入了枚举外状态 {p.status!r}，合法枚举为 {legal}')
        self.assertEqual(p.status, 'draft',
                         '未归档的新导入品不得自动上站（normalize 既有口径 → draft）')

    def test_reimport_same_catalog_no_is_skipped(self):
        """重复导入同一货号 → 跳过（命令已有全表口径的 exists 守卫），不产生第二条。"""
        payload = [{
            'catalog_no': 'PIT-TEST-2',
            'product_name': 'PIT Dup',
            'cas_number': '',
            'skus': [],
        }]
        self._run(payload)
        self._run(payload)
        self.assertEqual(Product.objects.filter(catalog_no='PIT-TEST-2').count(), 1)
