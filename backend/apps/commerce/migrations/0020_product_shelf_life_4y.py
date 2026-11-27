"""Product.ShelfLifeOption 补 4 年（P4Y）。

背景（QA A-199，Batch 16）：产品编辑页的 Shelf Life 下拉只有
1 / 2 / 3 / 5 年 + 自定义，**缺 4 年**。而「4 年保质期」在试剂盒里极常见，
运营遇到这类产品只能二选一：选 3 年（少报，客户到手可能已过期）或
选 5 年（虚报，过期仍在卖）—— 两个方向都是错的，且都没有任何提示。

本迁移**只改 choices，不产生任何 DDL**（PostgreSQL 上 choices 是纯 Python 层
校验，数据库里就是普通 varchar）。因此它是零风险的状态迁移。

手写而非 `makemigrations` 的原因同 0019：`config/settings/base.py` 有守卫，
禁止在 sqlite 环境生成迁移（会臆造「删 search_vector / 删 GIN 索引」的破坏性
操作）。而 CI 有 `makemigrations --check --dry-run` 闸门 ⇒ 必须让迁移状态与
模型一致，所以这里手写一份与模型 `choices` 完全对齐的 AlterField。
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commerce', '0019_product_is_test_fixture'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='shelf_life',
            field=models.CharField(
                blank=True,
                choices=[
                    ('P1Y', '1 年'),
                    ('P2Y', '2 年'),
                    ('P3Y', '3 年'),
                    ('P4Y', '4 年'),
                    ('P5Y', '5 年'),
                    ('', '自定义输入'),
                ],
                default='',
                help_text='选择保质期',
                max_length=20,
                verbose_name='保质期',
            ),
        ),
    ]
