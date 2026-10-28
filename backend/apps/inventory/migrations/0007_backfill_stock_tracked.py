# -*- coding: utf-8 -*-
"""
回填 `SKU.is_stock_tracked`：**已有库存行的 SKU 视为已纳管**。

为什么必须回填（2026-10-28 实测）：
    改造前「纳管」的判据是 `Inventory.objects.filter(sku_id=...).exists()`。
    改成显式字段后，字段默认 `False` ⇒ 如果不回填，**所有已建库存行的 SKU
    会在一瞬间全部脱管**，缺货拦截对它们立刻失效（放行一切下单）。
    本地实测：596 个 SKU 里 1 个（id=1675）有 3 行库存；生产 0 行。
    生产 0 行 ⇒ 这条回填在生产上是空操作；但它保证"本地/其它环境"不会因改造而脱管。

为什么反向是 noop：
    回滚到"没有这个字段"时，字段本身会被 AddField 的反向操作删掉，
    数据不需要复原成任何中间态。
"""
from django.db import migrations


def backfill(apps, schema_editor):
    SKU = apps.get_model('commerce', 'SKU')
    Inventory = apps.get_model('inventory', 'Inventory')
    tracked_sku_ids = list(
        Inventory.objects.values_list('sku_id', flat=True).distinct())
    if not tracked_sku_ids:
        return
    SKU.objects.filter(id__in=tracked_sku_ids).update(is_stock_tracked=True)


class Migration(migrations.Migration):

    dependencies = [
        ('commerce', '0017_sku_is_stock_tracked'),
        ('inventory', '0006_stockshortagealert'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
