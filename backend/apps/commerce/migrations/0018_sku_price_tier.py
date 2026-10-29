# -*- coding: utf-8 -*-
"""
SKU 阶梯价（`SkuPriceTier`）—— 结构变更，含表与两条约束。

只 AddModel，**不含数据迁移**：新建的价目表默认是空的，取价函数会回落 `SKU.price`，
所以"没配阶梯价"的行为与改造前**逐字节一致**（这一点很重要：上线当天不改任何价格）。

为什么手写而不跑 `makemigrations`：本仓库的 `commerce` app 里 `search_vector` 是
`if _USE_POSTGRES:` 条件声明的，在 sqlite 下跑 `makemigrations` 会顺手生成删 FTS 的
破坏性迁移（`scripts/check_migrations_safe.py` 会拦，但没必要冒险）。
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('commerce', '0017_sku_is_stock_tracked'),
    ]

    operations = [
        migrations.CreateModel(
            name='SkuPriceTier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True,
                                                    verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True,
                                                    verbose_name='更新时间')),
                ('min_qty', models.PositiveIntegerField(
                    help_text='含本数（>=）。第一档通常填 1 或 10。',
                    verbose_name='起始数量')),
                ('unit_price', models.DecimalField(
                    decimal_places=2, max_digits=12, verbose_name='该档单价')),
                ('sku', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='price_tiers', to='commerce.sku', verbose_name='SKU')),
            ],
            options={
                'verbose_name': 'SKU 阶梯价',
                'verbose_name_plural': 'SKU 阶梯价',
                'db_table': 'sku_price_tier',
                'ordering': ['sku_id', 'min_qty'],
                'unique_together': {('sku', 'min_qty')},
            },
        ),
        migrations.AddConstraint(
            model_name='skupricetier',
            constraint=models.CheckConstraint(
                condition=models.Q(('min_qty__gte', 1)),
                name='ck_spt_min_qty_positive'),
        ),
        migrations.AddConstraint(
            model_name='skupricetier',
            constraint=models.CheckConstraint(
                condition=models.Q(('unit_price__gte', 0)),
                name='ck_spt_unit_price_nonneg'),
        ),
    ]
