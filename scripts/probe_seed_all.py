#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一次性把 E2E 需要的全部夹具造齐（在 DB 副本上）。

为什么需要：P0/P1/P2 用例里有些会**推进业务状态**（例：接受报价把 quoted → confirmed），
重跑就不在同一前提下。所以每次跑这批 E2E 之前都要重置夹具 —— 否则会"第一次绿、第二次红"，
这正是 PERSONA 硬规 3「可重复」要防的。

顺序：账号 → 跨机构 → 客户流水（含状态复位）
用法：
  cd src_claude && DB_ENGINE=sqlite \\
    SCIREAGENT_DB_NAME="$(pwd)/backend/db_probe.sqlite3" \\
    backend/venv/Scripts/python.exe scripts/probe_seed_all.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BACKEND = os.path.join(ROOT, 'backend')
PY = sys.executable

DB = os.getenv('SCIREAGENT_DB_NAME', '')
if 'probe' not in DB:
    print('!! 拒绝：SCIREAGENT_DB_NAME 必须含 "probe"')
    sys.exit(2)
if not os.path.exists(DB):
    print('!! DB 副本不存在：%s\n   先 cp backend/db.sqlite3 backend/db_probe.sqlite3' % DB)
    sys.exit(2)

STEPS = ['probe_seed_accounts.py', 'probe_seed_cross_org.py', 'probe_seed_customer_flow.py']

for s in STEPS:
    print('→ %s' % s)
    r = subprocess.run([PY, os.path.join(HERE, s)], cwd=BACKEND,
                       env={**os.environ, 'DB_ENGINE': 'sqlite'},
                       capture_output=True, text=True, encoding='utf-8')
    if r.returncode != 0:
        print('   ✗ 失败：%s' % (r.stderr or r.stdout)[-500:])
        sys.exit(r.returncode)
    for line in (r.stdout or '').strip().split('\n')[-2:]:
        print('   %s' % line)

print('\n夹具就绪（%d 步全部成功）' % len(STEPS))
