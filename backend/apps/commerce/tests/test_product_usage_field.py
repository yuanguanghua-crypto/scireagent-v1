"""
TDD RED: Product.usage 字段 + 迁移（第一版 §9 步骤1/2 轴A 地基）。

运行时应 FAIL（commerce Product 模型尚无 `usage` 字段），直至 #376 在模型加
`usage = models.TextField(blank=True, default='')` 并生成迁移后转 GREEN。

契约：
- Product 模型必须拥有名为 `usage` 的持久化文本字段（承载 docx 厂商声称用途）
- 该字段可经 ORM 落库并回读（驱动 axes 轴A compute_axis_a 点火）
- blank=True / default=''：存量产品与未来未填产品不强制用途
"""
from django.test import TestCase

from apps.commerce.models import Product
from apps.commerce.tests.factories import ProductFactory


class ProductUsageFieldTest(TestCase):
    def test_usage_field_exists_on_model(self):
        """模型必须声明 usage 字段（当前缺失 → FieldDoesNotExist → RED）。"""
        field = Product._meta.get_field('usage')
        self.assertIsNotNone(field, "Product 模型缺少 usage 字段")

    def test_usage_persists_roundtrip(self):
        """usage 须可经 ORM 落库并回读（驱动轴A 点火）。"""
        p = ProductFactory()
        p.usage = "This reagent is used for rna sequencing and library prep."
        p.save()

        reloaded = Product.objects.get(pk=p.pk)
        self.assertEqual(
            reloaded.usage,
            "This reagent is used for rna sequencing and library prep.",
            "usage 字段未持久化到数据库",
        )

    def test_usage_default_blank(self):
        """存量/未填产品 usage 默认为空串，不强制用途。"""
        p = ProductFactory()
        p.save()
        reloaded = Product.objects.get(pk=p.pk)
        self.assertEqual(reloaded.usage, "")
