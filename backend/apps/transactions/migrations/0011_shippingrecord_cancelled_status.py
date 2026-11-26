"""A-262：ShippingRecord 增加 cancelled 状态（订单取消时作废未签收的发货记录）。

## 为什么手写这个迁移，不用 `makemigrations`
本项目模型与 DB 存在历史遗留不一致 —— 直接跑 `makemigrations` 会连带生成一批
`RemoveField(search_vector)` 与 `RemoveIndex(product_search_gin / method_search_gin /
protocol_name_objective_trgm / reference_search_gin)`，**提交即连根拔掉全文检索与 trgm 索引**
（2026-10-28 已实际踩到）。所以迁移一律手写。

## 本迁移的实际 DDL
`choices` 只是应用层枚举，PostgreSQL 上**不生成任何 DDL**
（`sqlmigrate` 会显示为空/仅 state 变更）。真正要用 `cancelled` 这个值，
靠的是模型层的 choices 校验，不是数据库约束。
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('transactions', '0010_order_unpaid_reminder_sent_at'),
    ]

    operations = [
        migrations.AlterField(
            model_name='shippingrecord',
            name='status',
            field=models.CharField(
                choices=[
                    ('preparing', 'Preparing'),
                    ('shipped', 'Shipped'),
                    ('in_transit', 'In Transit'),
                    ('delivered', 'Delivered'),
                    ('cancelled', 'Cancelled'),
                ],
                default='preparing',
                max_length=20,
                verbose_name='状态',
            ),
        ),
    ]
