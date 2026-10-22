#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""在**独立的 PG 测试库**上造并发夹具（产品 / SKU / 库存行 / 探测账号）。

安全闸门：只允许 `DB_ENGINE` 为 postgresql 且 `DB_NAME` 以 `_l4` 结尾（即项目的 L4 测试库），
否则拒绝执行 —— 防止误连生产/开发库。

用法（env 必须与 backend 的 PG 配置一致）：
  cd src_claude
  DB_ENGINE=django.db.backends.postgresql DB_NAME=scireagent_l4 DB_USER=scireagent \
  DB_HOST=127.0.0.1 DB_PORT=5433 \
  backend/venv/Scripts/python.exe scripts/probe_seed_pg_concurrency.py
"""
import os
import sys

eng = os.getenv('DB_ENGINE', '')
db = os.getenv('DB_NAME', '')
if 'postgresql' not in eng or not db.endswith('_l4'):
    print('!! 拒绝执行：需要 DB_ENGINE=postgresql 且 DB_NAME 以 _l4 结尾。当前 engine=%r db=%r'
          % (eng, db))
    sys.exit(2)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

import django  # noqa: E402
django.setup()

from decimal import Decimal  # noqa: E402

from apps.accounts.models import Organization, User  # noqa: E402
from apps.commerce.models import Product, SKU  # noqa: E402
from apps.inventory.models import Inventory  # noqa: E402

PW = 'Probe#2026!'

org, _ = Organization.objects.get_or_create(
    name='PG Probe Lab', defaults={'org_type': 'academic'})

# 采购账号（入库端点要 IsProcurementOrAdmin）
proc = User.objects.filter(username='probe_procure').first()
if proc is None:
    proc = User(username='probe_procure', email='probe_procure@probe.local')
proc.role = 'procurement'
proc.is_staff = False
proc.is_org_admin = False
proc.email_verified = True
proc.is_active = True
proc.organization = org
proc.set_password(PW)
proc.save()

prod, _ = Product.objects.get_or_create(
    name='PG Concurrency Probe Product',
    defaults={'slug': 'pg-concurrency-probe-product', 'catalog_no': 'PGPROBE0001',
              'status': 'active'})
sku, _ = SKU.objects.get_or_create(
    sku_code='PGPROBE-SKU-1',
    defaults={'product': prod, 'price': Decimal('10.00'), 'pack_size': '10 mg',
              'is_default': True, 'inventory_status': 'in_stock'})
inv, _ = Inventory.objects.get_or_create(
    sku=sku, location='MAIN', defaults={'available': 1000, 'allocated': 0})

print('PG=%s' % db)
print('org=%s  user=%s(%s)  product=%s  sku=%s  inventory=%s(available=%s)'
      % (org.id, proc.username, proc.id, prod.id, sku.id, inv.id, inv.available))
print('密码：%s' % PW)
