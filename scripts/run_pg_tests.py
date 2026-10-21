#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""L4 并发测试执行器 —— 在真实 PostgreSQL 上跑「只有 PG 能验」的那批用例

## 为什么需要这个脚本
那批并发用例在 sqlite 下会**诚实 skip**（`select_for_update` 在 sqlite 是 no-op），
所以常规回归永远看不到它们的结果。要真跑，得同时给出 5 个环境变量：

    DB_ENGINE / DB_NAME / DB_USER / DB_HOST / DB_PORT

手敲容易漏一项，漏了就会**静默落回 sqlite 然后整批 skip** —— 跑完看到
"13 passed, 4 skipped" 还以为验过了，其实并发一条都没验。这是最危险的失败模式：
**不报错，只是什么都没测**。

本脚本强制前置检查：连不上 PG 就直接退出（退出码 2），绝不"退化成 sqlite 然后假装成功"。

## 用法
```bash
cd backend
venv/Scripts/python.exe ../scripts/run_pg_tests.py                 # 跑默认 PG-only 集合
venv/Scripts/python.exe ../scripts/run_pg_tests.py --only inventory # 只跑库存并发
venv/Scripts/python.exe ../scripts/run_pg_tests.py -- -k oversell   # 透传给 pytest
```

## 前置条件（本机）
PG 17 集群在 `2026-07-08-11-22-32\\pgdata-l4`，端口 5433，`trust` 认证。
**它需要手动启动**（沙箱禁止本 agent 启动 postgres.exe 进程）：
```powershell
$data = "E:\\Users\\yuankaifeng\\WorkBuddy\\2026-07-08-11-22-32\\pgdata-l4"
& "C:\\Program Files\\PostgreSQL\\17\\bin\\pg_ctl.exe" -D $data `
  -l "$data\\server.log" -o "-p 5433 -c listen_addresses=127.0.0.1" -W start
```
"""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)
BACKEND = os.path.join(PROJECT, 'backend')

PG_HOST = os.getenv('SCIREAGENT_PG_HOST', '127.0.0.1')
PG_PORT = os.getenv('SCIREAGENT_PG_PORT', '5433')
PG_DB = os.getenv('SCIREAGENT_PG_DB', 'scireagent_l4')
PG_USER = os.getenv('SCIREAGENT_PG_USER', 'scireagent')

#: 默认目标：所有「sqlite 下会 skip、只有 PG 能验」的用例
TARGETS = {
    'inventory': 'apps/inventory/tests/test_pg_concurrency.py',
    'order_no': 'apps/transactions/tests/test_order_sequence.py::TestPostgresOnlyConcurrency',
    'invoice_no': ('apps/transactions/tests/test_order_sequence.py'
                   '::TestInvoiceSequenceConcurrencyOnPostgres'),
}
DEFAULT_ORDER = ['inventory', 'order_no', 'invoice_no']


def _port_open(host: str, port: str, timeout: float = 2.0) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((host, int(port))) == 0
    except (OSError, ValueError):
        return False


def _start_hint() -> str:
    data = os.path.join(os.path.dirname(PROJECT), 'pgdata-l4')
    return (
        f'\nPG 没在 {PG_HOST}:{PG_PORT} 上监听。它是**手动启动**的（沙箱不允许 agent '
        f'启动 postgres 进程），在 PowerShell 里跑：\n\n'
        f'  $data = "{data}"\n'
        f'  & "C:\\Program Files\\PostgreSQL\\17\\bin\\pg_ctl.exe" -D $data `\n'
        f'    -l "$data\\server.log" -o "-p {PG_PORT} -c listen_addresses={PG_HOST}" -W start\n'
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', choices=sorted(TARGETS), default=None,
                    help='只跑某一个目标（默认跑全部）')
    ap.add_argument('pytest_args', nargs='*', help='透传给 pytest（放在 -- 之后）')
    args = ap.parse_args()

    print('=' * 78)
    print('L4 并发测试 —— 真实 PostgreSQL')
    print('=' * 78)

    # ★ 前置检查：连不上就**直接失败**，绝不退化成 sqlite 然后整批 skip
    if not _port_open(PG_HOST, PG_PORT):
        print(f'❌ 连不上 {PG_HOST}:{PG_PORT}' + _start_hint())
        return 2
    print(f'✅ PG 可连：{PG_HOST}:{PG_PORT} / db={PG_DB} / user={PG_USER}')

    env = dict(os.environ)
    env.update({
        'DB_ENGINE': 'django.db.backends.postgresql',
        'DB_NAME': PG_DB,
        'DB_USER': PG_USER,
        'DB_PASSWORD': os.getenv('SCIREAGENT_PG_PASSWORD', ''),
        'DB_HOST': PG_HOST,
        'DB_PORT': PG_PORT,
    })

    keys = [args.only] if args.only else DEFAULT_ORDER
    targets = [TARGETS[k] for k in keys]

    cmd = [os.path.join(BACKEND, 'venv', 'Scripts', 'python.exe'),
           '-m', 'pytest', *targets, '-q', '-p', 'no:cacheprovider', '-rs',
           *args.pytest_args]
    print(f'目标：{", ".join(keys)}')
    print(f'命令：{" ".join(cmd)}')
    print('-' * 78, flush=True)      # ★ 必须 flush：否则本脚本的 print 会被缓冲，
                                     #   和 subprocess 的直接写 fd 交错，输出顺序全乱

    result = subprocess.run(cmd, cwd=BACKEND, env=env,
                            capture_output=True, text=True)
    out = (result.stdout or '') + (result.stderr or '')
    print(out)
    print('-' * 78, flush=True)

    if result.returncode != 0:
        print(f'❌ 失败（退出码 {result.returncode}）—— 上面的输出是**真实结果**，'
              f'不是"环境不可用"')
        return result.returncode

    # ★ 退出码 0 也可能"全都是 skip"。最危险的失败模式是：DB_* 没生效（比如
    #   settings 没读到环境变量）⇒ 回落 sqlite ⇒ 那批用例因"需 Postgres"整批跳过
    #   ⇒ 退出码 0、看起来"通过"，但**并发一条都没验**。
    #   所以这里主动检查 skip 原因，命中就判失败（退出码 3），不让它静默通过。
    if '需 Postgres' in out or '需 PostgreSQL' in out:
        print('❌ 有并发用例因「需 Postgres」被跳过 ⇒ PG 环境没真正生效，'
              '本次并发**一条都没验证**。不要把它当成通过。')
        return 3

    print('✅ 通过（无「需 Postgres」跳过项）。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
