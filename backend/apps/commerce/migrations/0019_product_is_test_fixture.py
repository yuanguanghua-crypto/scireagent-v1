"""Product 增加 is_test_fixture 标记字段。

背景（2026-10-30 首页走查）：前台 /products 报 69 个结果，其中
`E2E PO Test Product`(id=5460) 与 `Product 0`(id=2432) 是 e2e 残留，
真实产品只有 67 个。ResearchGoal / Application / Method / Protocol
四张表早已有 `is_test_fixture`（见 `core.models.test_fixture_field`），
只有 Product 缺，导致公开读路径无法统一排除。

本迁移只做 schema 变更（加列 + 索引），**不回填数据** —— 回填走
`manage.py mark_test_fixture_products --apply`，因为「哪些产品算夹具」
需要按环境（本地 / 生产）显式指定，写死在迁移里会在生产误标真实产品。

手写而非 makemigrations 的原因：`config/settings/base.py` 有守卫，
禁止在 sqlite 环境生成迁移（会臆造「删列/删索引」）。本次变更只加一个
BooleanField，不触碰任何 PG 专属字段，手写等价且安全。
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commerce', '0018_sku_price_tier'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='is_test_fixture',
            field=models.BooleanField(
                db_index=True, default=False,
                help_text='True 表示此行由自动化测试残留产生，不参与任何对外展示与统计；'
                          '仅作标记，数据不会被删除',
                verbose_name='测试夹具',
            ),
        ),
    ]
