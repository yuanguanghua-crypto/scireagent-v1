"""A-080 止损：OrderItem 增加商品标识快照字段。

## 为什么手写（不跑 makemigrations）
本项目模型与 DB 存在历史遗留不一致 —— `makemigrations` 会连带生成
`RemoveField(search_vector)` 与一批 `RemoveIndex`（product_search_gin /
method_search_gin / protocol_name_objective_trgm / reference_search_gin），
提交即连根拔掉全文检索与 trgm 索引（2026-10-28 实际踩到）。所以迁移一律手写。

## 本迁移的实际 DDL
三个 `AddField`，都是 `CharField(blank=True, default='')` ⇒ PG 上是
`ADD COLUMN ... DEFAULT '' NOT NULL`，对 89 行的小表瞬时完成。

## 为什么加这三列
`OrderItem.sku` 与 `.product` 都是 `SET_NULL` —— 主数据一删，历史订单明细就
永久失去商品标识。生产实测（2026-11-26）：89 行里 32 行（36%）的
`sku_id` 与 `product_id` 同时为 NULL，涉及 16 单、合计 7,730,065.00（占全库 GMV 99%）。
本迁移只提供"从今往后不再丢"的能力；**那 32 行无法回填**（源对象已不存在）。
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0011_shippingrecord_cancelled_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='sku_code_snapshot',
            field=models.CharField(
                blank=True, default='', max_length=100, verbose_name='SKU 编码快照'),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='product_name_snapshot',
            field=models.CharField(
                blank=True, default='', max_length=255, verbose_name='产品名快照'),
        ),
        migrations.AddField(
            model_name='orderitem',
            name='sku_spec_snapshot',
            field=models.CharField(
                blank=True, default='', max_length=120, verbose_name='规格快照'),
        ),
    ]
