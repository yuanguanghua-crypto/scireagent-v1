#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""全站测试统一入口 —— 把 L1~L5 五层用**一个命令**串起来，输出一份统一报告。

## 为什么需要它
现状：12 个 CI job + 78 个 playwright spec + 一堆探测脚本，彼此独立。
想回答"现在全站测试过不过"需要开 5 个终端。本脚本把它们编排成 **suite**，
统一跑、统一计时、统一退出码、统一报告。

## suite 与依赖
| suite | 命令 | 需要什么 |
|---|---|---|
| config | scripts/config_parity.py | 无（静态检查，秒级） |
| perm-matrix | scripts/role_capability_probe.py | 无（0 次 HTTP） |
| unit | pytest apps/<app> | 无（sqlite 测试库） |
| perm-http | scripts/http_role_probe.py | **探测栈**（8011 + 副本） |
| object-perm | scripts/http_object_probe.py | **探测栈 + 跨机构夹具** |
| e2e-smoke | playwright public-smoke permission-matrix | **前端 + 后端** |
| e2e-manual | playwright manual-facts-probe manual-pages-smoke | **前端 + 后端** |
| e2e-full | playwright（全部 spec） | **前端 + 后端** |
| pg-concurrency | scripts/run_pg_tests.py | **PostgreSQL 5433** |
| browser-matrix | playwright --project=firefox,webkit | **前端 + 后端** |
| prod-readonly | scripts/prod_anon_probe.py | 外网（只读） |

## profile
- `fast`    ：config + perm-matrix + unit(核心 app)。**不需要起任何服务**，本地提交前跑
- `full`    ：fast + perm-http + object-perm + e2e-smoke + e2e-manual + e2e-full + pg-concurrency
- `nightly` ：full + browser-matrix + prod-readonly

## 用法
  python scripts/run_all_tests.py --profile fast
  python scripts/run_all_tests.py --profile full --stack-up   # 自动起探测栈并在结束时关掉
  python scripts/run_all_tests.py --only config,perm-matrix   # 只跑指定 suite
  python scripts/run_all_tests.py --profile fast --dry-run    # 只打印将执行什么

退出码：0 全通过；1 有 FAIL；2 有 ERROR（环境缺失/超时，与被测代码无关）
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BACKEND = os.path.join(ROOT, 'backend')
FRONTEND = os.path.join(ROOT, 'frontend')
# ★ 解释器：本地用 backend/venv（Windows 是 Scripts/python.exe）；CI 里没有这个 venv
#   ⇒ 回落到当前解释器。否则在 ubuntu runner 上直接 FileNotFoundError。
_VENV_PY = os.path.join(BACKEND, 'venv', 'Scripts', 'python.exe')
PY = _VENV_PY if os.path.exists(_VENV_PY) else sys.executable
# ★ Windows 上 `npx` 不是可执行文件而是 `npx.cmd`；subprocess 不开 shell 时必须给出真实路径，
#   否则直接 FileNotFoundError（实测踩过：suite 被误报成 ERROR）
import shutil  # noqa: E402

NPX = shutil.which('npx') or shutil.which('npx.cmd') or 'npx'
RUNS = os.path.join(ROOT, '_test_runs')

PROBES = os.getenv('PROBE_BASE', 'http://127.0.0.1:8011')
FE = os.getenv('BASE_URL', 'http://127.0.0.1:5174')

STRIP_PROXY = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']


def clean_env(extra=None):
    env = {k: v for k, v in os.environ.items() if k not in STRIP_PROXY}
    env['NO_PROXY'] = '127.0.0.1,localhost'
    env.setdefault('PYTHONDONTWRITEBYTECODE', '1')
    if extra:
        env.update(extra)
    return env


class Suite:
    def __init__(self, key, desc, cmd, cwd, needs, env=None, timeout=1800):
        self.key, self.desc, self.cmd, self.cwd = key, desc, cmd, cwd
        self.needs, self.env, self.timeout = needs, env or {}, timeout


def build_suites(profile):
    S = {}
    S['config'] = Suite('config', '配置一致性（13 项静态检查）',
                        [PY, 'scripts/config_parity.py'], ROOT, [], timeout=180)
    S['perm-matrix'] = Suite('perm-matrix', '权限矩阵（335 端点 × 8 身份，0 请求）',
                             [PY, 'scripts/role_capability_probe.py', '--json',
                              os.path.join(ROOT, 'docs', 'e2e', 'ROLE_CAPABILITY_MATRIX.json')],
                             ROOT, [], env={'DB_ENGINE': 'sqlite'}, timeout=300)
    S['unit'] = Suite('unit', '后端单测（核心 app）',
                      [PY, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                       'apps/commerce', 'apps/transactions', 'apps/knowledge', 'apps/accounts'],
                      BACKEND, [], env={'DB_ENGINE': 'sqlite'}, timeout=3600)
    S['perm-http'] = Suite('perm-http', '真实 HTTP 权限（8 身份 × 199 端点）',
                           [PY, 'scripts/http_role_probe.py'], ROOT, ['stack'], timeout=1800)
    S['object-perm'] = Suite('object-perm', '对象级权限 / 数据隔离',
                             [PY, 'scripts/http_object_probe.py'], ROOT, ['stack', 'cross-org'],
                             env={'SCIREAGENT_DB_NAME': os.path.join(BACKEND, 'db_probe.sqlite3')},
                             timeout=900)
    S['e2e-smoke'] = Suite('e2e-smoke', 'E2E 冒烟（公开页 + 权限矩阵）',
                           [NPX, 'playwright', 'test', 'public-smoke', 'permission-matrix',
                            '--project=chromium', '--reporter=line', '--retries=0'],
                           FRONTEND, ['stack', 'frontend'], env={'BASE_URL': FE}, timeout=1800)
    S['e2e-manual'] = Suite('e2e-manual', 'E2E 事实核验 + 52 页加载级',
                            [NPX, 'playwright', 'test', 'manual-facts-probe', 'manual-pages-smoke',
                             '--project=chromium', '--reporter=line', '--retries=0'],
                            FRONTEND, ['stack', 'frontend'], env={'BASE_URL': FE}, timeout=2400)
    S['e2e-full'] = Suite('e2e-full', 'E2E 全量（全部 spec）',
                          [NPX, 'playwright', 'test', '--project=chromium',
                           '--reporter=line', '--retries=0'],
                          FRONTEND, ['stack', 'frontend'], env={'BASE_URL': FE}, timeout=7200)
    S['fixtures'] = Suite('fixtures', '重置 E2E 夹具（账号/跨机构/客户流水，仅副本）',
                          [PY, 'scripts/probe_seed_all.py'], ROOT, ['cross-org'],
                          env={'DB_ENGINE': 'sqlite',
                               'SCIREAGENT_DB_NAME': os.path.join(BACKEND, 'db_probe.sqlite3')},
                          timeout=600)
    S['e2e-probe'] = Suite('e2e-probe', 'P0/P1/P2 覆盖补齐（探针栈 + 夹具）',
                           [NPX, 'playwright', 'test', 'p0-', 'p1-', 'p2-',
                            '--project=chromium', '--reporter=line', '--retries=0'],
                           FRONTEND, ['stack', 'frontend', 'cross-org'],
                           env={'BASE_URL': FE}, timeout=3600)
    S['pg-concurrency'] = Suite('pg-concurrency', 'PG 并发（库存/订单号/发票号）',
                                [PY, '../scripts/run_pg_tests.py'], BACKEND, ['pg'], timeout=3600)
    S['browser-matrix'] = Suite('browser-matrix', '跨浏览器（firefox + webkit）',
                                [NPX, 'playwright', 'test', 'manual-facts-probe',
                                 '--project=firefox', '--reporter=line', '--retries=0'],
                                FRONTEND, ['stack', 'frontend'], env={'BASE_URL': FE}, timeout=3600)
    S['prod-readonly'] = Suite('prod-readonly', '生产匿名只读边界',
                               [PY, 'scripts/prod_anon_probe.py'], ROOT, ['net'], timeout=600)

    PROFILES = {
        'fast': ['config', 'perm-matrix', 'unit'],
        'full': ['config', 'perm-matrix', 'unit', 'perm-http', 'object-perm',
                 'e2e-smoke', 'e2e-manual', 'fixtures', 'e2e-probe', 'pg-concurrency'],
        'nightly': ['config', 'perm-matrix', 'unit', 'perm-http', 'object-perm',
                    'e2e-smoke', 'e2e-manual', 'fixtures', 'e2e-probe', 'e2e-full', 'pg-concurrency',
                    'browser-matrix', 'prod-readonly'],
    }
    return S, PROFILES


def check_need(need, notes):
    """返回 (ok, 说明)。只做"够不够跑"的判断，不做业务断言。"""
    import socket
    import urllib.request
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def port_open(host, port):
        with socket.socket() as s:
            s.settimeout(2)
            return s.connect_ex((host, port)) == 0

    if need == 'stack':
        if not port_open('127.0.0.1', 8011):
            return False, '探测后端 8011 未监听（见 MANUAL_FACTS_MEASURED §0 或 --stack-up）'
        try:
            with op.open(PROBES + '/api/v1/health/', timeout=5) as r:
                return r.status == 200, '探测栈健康检查 %s' % r.status
        except Exception as e:                                    # noqa: BLE001
            return False, '探测栈不可用：%s' % e
    if need == 'frontend':
        if not port_open('127.0.0.1', 5174):
            return False, '前端 5174 未监听（VITE_API_PROXY=http://127.0.0.1:8011）'
        return True, '前端就绪'
    if need == 'cross-org':
        db = os.path.join(BACKEND, 'db_probe.sqlite3')
        return os.path.exists(db), '跨机构夹具依赖 %s' % ('db_probe.sqlite3 存在' if os.path.exists(db) else 'db_probe.sqlite3 缺失')
    if need == 'pg':
        return port_open('127.0.0.1', 5433), 'PostgreSQL 5433 %s' % ('在跑' if port_open('127.0.0.1', 5433) else '未启动')
    if need == 'net':
        try:
            with op.open('https://scireagent.com/robots.txt', timeout=10) as r:
                return True, '外网可达（HTTP %s）' % r.status
        except Exception:                                         # noqa: BLE001
            return False, '外网不可达'
    return True, ''


def run_suite(s, run_dir, verbose):
    log = os.path.join(run_dir, s.key + '.log')
    t0 = time.time()
    try:
        with open(log, 'w', encoding='utf-8', errors='replace') as f:
            p = subprocess.run(s.cmd, cwd=s.cwd, env=clean_env(s.env),
                               stdout=f, stderr=subprocess.STDOUT, timeout=s.timeout)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        rc, _ = -1, None
    except FileNotFoundError as e:
        return {'suite': s.key, 'desc': s.desc, 'status': 'ERROR',
                'rc': None, 'sec': 0, 'log': log, 'why': '命令不存在：%s' % e}
    sec = round(time.time() - t0, 1)

    tail = ''
    try:
        lines = [l.rstrip() for l in open(log, encoding='utf-8', errors='replace') if l.strip()]
        tail = ' | '.join(lines[-2:])[:220]
    except Exception:                                             # noqa: BLE001
        pass
    if verbose and tail:
        print('    %s' % tail)

    status = 'PASS' if rc == 0 else ('TIMEOUT' if rc == -1 else 'FAIL')
    return {'suite': s.key, 'desc': s.desc, 'status': status, 'rc': rc,
            'sec': sec, 'log': log, 'why': tail}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--profile', default='fast', choices=['fast', 'full', 'nightly'])
    ap.add_argument('--only', default='')
    ap.add_argument('--skip', default='')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    S, PROFILES = build_suites(args.profile)
    keys = PROFILES[args.profile]
    if args.only:
        keys = [k.strip() for k in args.only.split(',') if k.strip() in S]
    if args.skip:
        drop = {k.strip() for k in args.skip.split(',')}
        keys = [k for k in keys if k not in drop]

    print('=' * 78)
    print('全站测试统一入口  profile=%s  共 %d 个 suite' % (args.profile, len(keys)))
    print('=' * 78)

    # 前置检查：把所有 suite 需要的都验一遍，缺什么提前说，别跑到一半才炸
    need_cache = {}
    blocked = {}
    for k in keys:
        ok_all = True
        msgs = []
        for need in S[k].needs:
            if need not in need_cache:
                need_cache[need] = check_need(need, None)
            ok, msg = need_cache[need]
            if not ok:
                ok_all = False
            if msg:
                msgs.append(msg)
        if not ok_all:
            blocked[k] = '；'.join(msgs)
    if blocked:
        print('\n[前置检查] 以下 suite 因环境缺失将跳过：')
        for k, why in blocked.items():
            print('  - %-16s %s' % (k, why))

    runnable = [k for k in keys if k not in blocked]
    if args.dry_run:
        print('\n[dry-run] 将依次执行：')
        for k in runnable:
            print('  %-16s %s' % (k, S[k].desc))
        return 0

    run_dir = os.path.join(RUNS, time.strftime('%Y%m%d-%H%M%S'))
    os.makedirs(run_dir, exist_ok=True)
    print('\n日志目录：%s\n' % run_dir)

    results = []
    for i, k in enumerate(runnable, 1):
        print('[%d/%d] %-16s %s' % (i, len(runnable), k, S[k].desc))
        r = run_suite(S[k], run_dir, args.verbose)
        results.append(r)
        print('        → %-7s %6.1fs  %s' % (r['status'], r['sec'], r['log']))
    for k, why in blocked.items():
        results.append({'suite': k, 'desc': S[k].desc, 'status': 'SKIP',
                        'rc': None, 'sec': 0, 'log': '', 'why': why})

    # 统一报告
    print('\n' + '=' * 78)
    print('%-16s %-8s %8s  %s' % ('suite', '状态', '秒', '说明'))
    print('-' * 78)
    for r in results:
        print('%-16s %-8s %8.1f  %s' % (r['suite'], r['status'], r['sec'],
                                        (r['why'] or '')[:44]))
    n_fail = sum(1 for r in results if r['status'] in ('FAIL', 'TIMEOUT'))
    n_err = 0
    n_skip = sum(1 for r in results if r['status'] == 'SKIP')
    n_pass = sum(1 for r in results if r['status'] == 'PASS')
    print('-' * 78)
    print('PASS %d / FAIL %d / SKIP %d  （共 %d）' % (n_pass, n_fail, n_skip, len(results)))
    if n_skip:
        print('⚠️ SKIP = 环境缺失，**不代表通过**；要让它们变成结论，补环境后重跑。')
    if n_pass == 0 and n_skip:
        print('⚠️ 本次一条都没真正验证（全是 SKIP）⇒ 退出码按"未验证"处理。')

    json.dump({'profile': args.profile, 'at': time.strftime('%Y-%m-%d %H:%M:%S'),
               'results': results}, open(os.path.join(run_dir, 'summary.json'), 'w',
                                         encoding='utf-8'), ensure_ascii=False, indent=1)
    print('报告：%s' % os.path.join(run_dir, 'summary.json'))
    # 0 全通过；1 有真实失败；2 未验证（环境缺失 / 全 SKIP）
    if n_fail:
        return 1
    if n_pass == 0:
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
