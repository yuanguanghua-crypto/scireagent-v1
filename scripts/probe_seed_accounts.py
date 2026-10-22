#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""在**数据库副本**上建立 8 种身份的探测账号（绝不触碰 db.sqlite3）。

安全设计：
  · 必须通过环境变量 SCIREAGENT_DB_NAME 指向含 "probe" 字样的文件，否则直接退出
  · 幂等：已存在则更新密码与标记，不会重复创建

用法：
  cp backend/db.sqlite3 backend/db_probe.sqlite3
  cd backend && DB_ENGINE=sqlite SCIREAGENT_DB_NAME=<abs>/db_probe.sqlite3 \
    venv/Scripts/python.exe ../scripts/probe_seed_accounts.py
"""
import os
import sys

DB = os.getenv('SCIREAGENT_DB_NAME', '')
if 'probe' not in DB:
    print('!! 拒绝执行：SCIREAGENT_DB_NAME 必须指向含 "probe" 的副本文件。当前=%r' % DB)
    sys.exit(2)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

import django  # noqa: E402
django.setup()

from apps.accounts.models import Organization, User  # noqa: E402

PW = 'Probe#2026!'

# (username, role, is_staff, is_superuser, is_org_admin, email_verified)
SPECS = [
    ('probe_researcher', 'researcher', False, False, False, True),
    ('probe_orgadmin',   'researcher', False, False, True,  True),
    ('probe_procure',    'procurement', False, False, False, True),
    ('probe_adminrole',  'admin',      False, False, False, True),
    ('probe_staff',      'researcher', True,  False, False, True),
    ('probe_super',      'admin',      True,  True,  False, True),
    ('probe_unverified', 'researcher', False, False, False, False),
]

org, _ = Organization.objects.get_or_create(
    name='Probe Lab', defaults={'org_type': 'academic'})

for username, role, staff, sup, orgadm, verified in SPECS:
    u = User.objects.filter(username=username).first()
    if u is None:
        u = User(username=username, email='%s@probe.local' % username)
    u.role = role
    u.is_staff = staff
    u.is_superuser = sup
    u.is_org_admin = orgadm
    u.email_verified = verified
    u.is_active = True
    u.organization = org
    u.set_password(PW)
    u.save()
    print('%-18s role=%-12s staff=%-5s super=%-5s orgadm=%-5s verified=%s'
          % (username, u.role, u.is_staff, u.is_superuser, u.is_org_admin, u.email_verified))

print('\n密码统一：%s' % PW)
print('账号数：%d' % len(SPECS))

# ★ 把用户名 → id 落一个 JSON：E2E 里"指派销售"这类需要真实数字 id 的用例直接读它，
#   避免在 spec 里硬编码 id（副本重建后 id 可能变）
import json  # noqa: E402

ids = dict(User.objects.filter(username__in=[s[0] for s in SPECS])
           .values_list('username', 'id'))
out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'backend', '_probe_ids.json')
json.dump(ids, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('id 表已写入 %s：%s' % (out, ids))
