# -*- coding: utf-8 -*-
"""
SKU.is_stock_tracked —— 显式「纳入库存管理」开关（库存数据维护 4a）。

只有 AddField，**不含数据回填**：回填要读 `inventory.Inventory` 表，把它放在
`inventory/0007_backfill_stock_tracked.py` 里，让"结构变更"和"数据变更"分属各自 app，
迁移图也更好读（commerce 不需要为了读一张别人的表而反向依赖 inventory）。

为什么需要这个字段（而不是继续用「有没有 Inventory 行」判断纳管）：
    `StockShortageService._is_tracked()` 原来查 `Inventory.objects.filter(sku_id=...).exists()`。
    这让「纳管」变成一个**副作用**：加一行就纳管、删一行就脱管，误点一次系统行为就变，
    而且界面上看不见这个状态。更要命的是它无法区分两件业务含义相反的事：
      · 这个 SKU 按需生产、本来就不设库存（应永远不拦）
      · 忘了给这个 SKU 建库存行（应视为 0、必须拦）
    两者在数据上完全一样 ⇒ 只能靠一个显式字段表达。
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commerce', '0016_fts_state_align'),
    ]

    operations = [
        migrations.AddField(
            model_name='sku',
            name='is_stock_tracked',
            field=models.BooleanField(
                db_index=True, default=False, verbose_name='纳入库存管理'),
        ),
    ]
