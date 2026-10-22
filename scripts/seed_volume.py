#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""造大量测试数据 —— 用于**数据量级压力测试**（对应 FAILURE_MODES 10.2）

## 为什么需要
清单里 10.2「数据量 10 倍后崩」原本是 B 类，兜底是"数据增长后重跑 perf_gate 看趋势"——
但那句话**没有任何人真的执行过**，因为我们手上只有当前规模的数据。
本脚本把"10 倍"变成一个可以真的跑出来的场景。

## ★ 安全约束（写死在代码里）
`DB_NAME` **必须包含 "vol"**（例如 `scireagent_vol`），否则直接拒绝执行。
这是为了让"造几十万垃圾数据的脚本"永远不可能误跑在 dev / 生产库上。
配合约定：造数库用完即 `DROP DATABASE`，不留在机器上。

## 用法
```bash
# 1) 建库 + 迁移（只做一次）
createdb scireagent_vol   # 或用 psql -c "CREATE DATABASE scireagent_vol"
DB_ENGINE=... DB_NAME=scireagent_vol ... python manage.py migrate --noinput

# 2) 造 1 倍（基准）
DB_NAME=scireagent_vol ... python ../scripts/seed_volume.py --apps 28600 --products 127

# 3) 测一次，再补到 10 倍
DB_NAME=scireagent_vol ... python ../scripts/seed_volume.py --apps 286000 --products 1270

# 4) 测完 DROP DATABASE scireagent_vol
```
脚本是**幂等增量**的：`--apps N` 表示"目标总数 N"，已存在多少就补多少。
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(os.path.dirname(HERE), 'backend')
sys.path.insert(0, BACKEND)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402

from apps.commerce.models import Product, SKU  # noqa: E402
from apps.knowledge.models import Application  # noqa: E402

BATCH = 5000
#: 汇总文本长度 —— 刻意做得接近真实（搜索要扫这些列）
SUMMARY = ('Volume test fixture for load characterization. '
           'Covers nucleotide labelling, click chemistry and molecular biology workflows. ')


def _guard():
    """库名不含 'vol' 就拒绝 —— 防止误跑在 dev / 生产库。"""
    name = connection.settings_dict.get('NAME') or ''
    if 'vol' not in str(name).lower():
        print(f'❌ 拒接执行：DB_NAME={name!r} 不含 "vol"。')
        print('   本脚本会写入几十万行垃圾数据，只允许在一次性造数库上运行。')
        sys.exit(2)
    print(f'✅ 目标库：{name}（含 "vol"，允许造数）')


def _bulk(model, make_objs, target_total, label):
    existing = model.objects.count()
    need = max(0, target_total - existing)
    if need == 0:
        print(f'  {label}: 已有 {existing} 条 ≥ 目标 {target_total}，跳过')
        return existing
    print(f'  {label}: {existing} → {target_total}（补 {need} 条）…', end='', flush=True)
    done = 0
    while done < need:
        size = min(BATCH, need - done)
        start = existing + done
        model.objects.bulk_create(make_objs(start, start + size), batch_size=BATCH)
        done += size
    total = model.objects.count()
    print(f' 完成，现有 {total} 条')
    return total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--apps', type=int, default=28600, help='application 目标总数')
    ap.add_argument('--products', type=int, default=127, help='product 目标总数')
    args = ap.parse_args()

    _guard()
    print('=' * 70)
    print('造数（数据量级压测用）')
    print('=' * 70)

    _bulk(
        Application,
        lambda a, b: [
            Application(name=f'Volume Application {i}', slug=f'volapp-{i}',
                        status='active', summary=SUMMARY)
            for i in range(a, b)
        ],
        args.apps, 'application',
    )

    _bulk(
        Product,
        lambda a, b: [
            Product(name=f'Volume Product {i}', slug=f'volprod-{i}',
                    status='active', catalog_no=f'VOL-{i:06d}')
            for i in range(a, b)
        ],
        args.products, 'product',
    )

    # 每个 product 至少一个 SKU（products 端点会 prefetch skus；没有 SKU 会让价格字段为空）
    existing_skus = SKU.objects.count()
    need = max(0, args.products - existing_skus)
    if need:
        from decimal import Decimal
        prods = list(Product.objects.filter(slug__startswith='volprod-')
                     .order_by('id')[:args.products])
        start = existing_skus
        made = 0
        while made < need:
            chunk = prods[made:made + BATCH]
            SKU.objects.bulk_create([
                SKU(product=p, sku_code=f'VOL-SKU-{start + made + idx:06d}',
                    price=Decimal('99.00'))
                for idx, p in enumerate(chunk)
            ], batch_size=BATCH)
            made += len(chunk)
        print(f'  sku: → {SKU.objects.count()} 条')

    print('\n完成。当前规模：')
    for m in (Application, Product, SKU):
        print(f'  {m.__name__:12} {m.objects.count():>8}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
