#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""deploy_table_counts.py — 部署闸门「表行数 Δ0」的可执行判据

## 为什么需要它

历史文档里一直写「部署闸门：**8 表 Δ0**」，但 2026-11-02 全仓核查发现：

  · 没有任何地方列出过这 **8 张表究竟是哪 8 张**
  · 也没有任何脚本可执行这道闸门
  · 历史上全靠人工按文档数几张表

⇒ 这是一处**真盲区**（"没人知道这里没测"）。本脚本把它落成可执行判据。

## 判据

**核心 8 表**（`CORE8`）行数变化必须 **Δ0**。为什么是这 8 张：覆盖
① 知识实体链（重建镜像 / migrate / backfill 最容易静默改动的）：
   `protocol` · `protocol_step` · `method` · `application_method`
   `research_goal` · `method_protocol`
② 商业核心（价格、库存、前台展示依赖）：
   `product` · `sku`

其余业务表**照常计数并打印**，但不参与 Δ0 判定（它们可能因正常业务写入变化）。
**看到非核心表有 Δ 不等于失败**，但必须在报告里解释。

## 只读保证

只发 `SELECT`，不发任何 DDL/DML。计数用 `query_to_xml` 逐表包一层
`SELECT count(*)`，单语句完成，不开事务、不加锁（MVCC 快照读）。

## 用法

```bash
# 1) 部署前抓基线（写文件）
python scripts/deploy_table_counts.py --capture work/_deploy_baseline/tables.json

# 2) 部署后比对（Δ0 才 exit 0）
python scripts/deploy_table_counts.py --compare work/_deploy_baseline/tables.json
```

退出码：
  0 = 核心 8 表 Δ 全为 0（非核心表的变化只打印不判负）
  1 = 核心 8 表有 Δ ≠ 0，或有表在基线里存在而现状缺失
  2 = 环境问题（SSH 连不上 / SQL 报错 / 基线文件损坏）
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_HOST = os.environ.get('SCIREAGENT_HOST', 'admin@47.82.156.48')
DEFAULT_KEY = os.environ.get('SCIREAGENT_SSH_KEY', '')
DEFAULT_CONTAINER = os.environ.get('SCIREAGENT_DB_CONTAINER', 'scireagent-db-1')
DEFAULT_DB = os.environ.get('SCIREAGENT_DB_NAME', 'scireagent')
DEFAULT_USER = os.environ.get('SCIREAGENT_DB_USER', 'scireagent')

# ★ 核心 8 表 —— 部署闸门判 Δ0 的集合（定义见模块 docstring）
CORE8 = (
    'protocol',
    'protocol_step',
    'method',
    'application_method',
    'research_goal',
    'method_protocol',
    'product',
    'sku',
)

# 运行时/框架表：计了也没意义，直接排除（避免 auth/session 的自然增长造成噪声）
SKIP_PREFIX = ('django_', 'auth_', 'authtoken_', 'sessions')

# 逐表精确计数：一条语句数完 public 下所有基表（含 0 行表）
SQL_ALL_TABLES = """
SELECT 'C|' || t.table_name || '|' ||
       (xpath('/row/c/text()',
              query_to_xml(
                format('SELECT count(*) AS c FROM %I.%I', t.table_schema, t.table_name),
                false, true, ''
              )
       ))[1]::text
  FROM information_schema.tables t
 WHERE t.table_schema = 'public'
   AND t.table_type = 'BASE TABLE'
 ORDER BY t.table_name;
""".strip()

# ★ 内容摘要：为什么光有行数不够
#   Δ0 只挡「增 / 删」，**挡不住 UPDATE** —— 行数不变、内容被改，行数闸门完全看不见。
#   D 处置（443 条 objective 置空）正是 UPDATE 型改动，所以必须有摘要。
#   用 sum(hashtext(row::text))：与行序无关（求和可交换），能捕获任意一行的内容变化；
#   不是密码学哈希，但作为"变了没有"的闸门足够，且不必排序整表。
CHECKSUM_SQL = '\nUNION ALL\n'.join(
    "SELECT 'H|{t}|' || count(*) || '|' || "
    "coalesce(sum(hashtext(x::text)::bigint), 0)::text FROM {t} x".format(t=t)
    for t in CORE8
) + '\n;'


def _ssh_argv(args) -> list[str]:
    argv = ['ssh', '-i', args.key, '-o', 'StrictHostKeyChecking=accept-new',
            '-o', f'ConnectTimeout={args.timeout}', args.host]
    # 远端命令写成单个字符串由远端 shell 解析；内部不含引号，避开本项目踩过的转义坑
    argv.append(
        f'docker exec -i {args.container} psql -U {args.db_user} -d {args.db_name} '
        f'-A -t -v ON_ERROR_STOP=1'
    )
    return argv


def capture(args) -> tuple[dict, dict]:
    """连生产库读一遍行数 + 核心 8 表内容摘要（只读）。"""
    if not args.key:
        raise RuntimeError('未提供 SSH key：用 --key 或环境变量 SCIREAGENT_SSH_KEY')
    argv = _ssh_argv(args)
    sql = SQL_ALL_TABLES + '\n\n' + CHECKSUM_SQL
    try:
        p = subprocess.run(argv, input=sql, capture_output=True,
                           text=True, encoding='utf-8', errors='replace',
                           timeout=args.timeout + 30)
    except FileNotFoundError:
        raise RuntimeError('找不到 ssh 可执行文件')
    except subprocess.TimeoutExpired:
        raise RuntimeError(f'SSH 超时（{args.timeout + 30}s）')

    out = (p.stdout or '').strip()
    err = (p.stderr or '').strip()
    if p.returncode != 0 or 'ERROR' in err.upper():
        raise RuntimeError(f'psql 失败（exit={p.returncode}）：{err[:600]}')

    counts, checksums = {}, {}
    for line in out.splitlines():
        line = line.strip()
        if not line or '|' not in line:
            continue
        parts = line.split('|')
        if parts[0] == 'C' and len(parts) == 3:
            if parts[1].startswith(SKIP_PREFIX):
                continue
            counts[parts[1]] = int(parts[2])
        elif parts[0] == 'H' and len(parts) == 4:
            checksums[parts[1]] = {'n': int(parts[2]), 'sum': int(parts[3])}

    if not counts:
        raise RuntimeError(f'没解析到任何表计数，原始输出前 300 字：{out[:300]}')
    if len(checksums) != len(CORE8):
        raise RuntimeError(
            f'内容摘要只拿到 {len(checksums)}/{len(CORE8)} 张核心表'
            f'（拿到 {sorted(checksums)}）；不允许降级为"只比行数"')
    return counts, checksums
    return counts


def _fmt_delta(d):
    if d > 0:
        return f'+{d}'
    return str(d)


def _compare(base_counts: dict, now: dict, base_ck: dict | None = None,
             now_ck: dict | None = None):
    """纯逻辑比对，不碰网络。返回 (fails, missing, others, ck_fails)。

    fails   = [(表, 基线, 现状, Δ)]  核心表行数 Δ≠0
    missing = [表]                   基线里有、现在库里没有（表被删 = 必须红）
    others  = [(表, 基线, 现状, Δ)]  非核心表变化（只提示，不判负）
    ck_fails= [(表, 基线摘要, 现状摘要)]  行数没变但**内容变了**（UPDATE 型）
    """
    fails, missing = [], []
    for t in CORE8:
        if t not in base_counts:
            missing.append(t)
            continue
        if t not in now:
            # 表在现状视图里消失 ⇒ 按「缺失」判红，不能因为取不到数就跳过
            # （自检用例5 抓到的真实缺陷：原实现这里直接 KeyError 抛栈）
            missing.append(t)
            continue
        d = now[t] - base_counts[t]
        if d != 0:
            fails.append((t, base_counts[t], now[t], d))

    # 内容摘要：只有基线里带摘要的才比（老基线无此字段 ⇒ 跳过，不假装通过）
    ck_fails = []
    if base_ck and now_ck:
        for t in CORE8:
            b = base_ck.get(t)
            n = now_ck.get(t)
            if not b or not n:
                continue
            if b.get('sum') != n.get('sum'):
                ck_fails.append((t, b.get('sum'), n.get('sum')))

    others = []
    for t in sorted(set(base_counts) | set(now)):
        if t in CORE8:
            continue
        b = base_counts.get(t)
        n = now.get(t)
        if b is None and n is not None:
            others.append((t, None, n, None))
        elif n is None and b is not None:
            others.append((t, b, None, None))
        elif b != n:
            others.append((t, b, n, n - b))
    return fails, missing, others, ck_fails


def _report(fails, missing, others, ck_fails=(), has_ck=True) -> bool:
    """打印判定结果，返回是否通过（不需要网络）。"""
    if missing:
        print(f'❌ 基线里有、定义里缺：{missing}')
    if others:
        print(f'ℹ️  非核心表变化 {len(others)} 张（不判负，但报告里必须解释）：')
        for t, b, n, d in others:
            print(f'     {t:30s} {b} → {n} ({_fmt_delta(d) if d is not None else "表增删"})')
    if not has_ck:
        print('⚠️  基线里没有内容摘要（老格式）⇒ 本轮**只比了行数，UPDATE 型改动测不到**')

    if fails or missing or ck_fails:
        print('❌ 闸门红：核心 8 表无变化这一条不成立')
        for t, b, n, d in fails:
            print(f'     行数 {t:22s} {b} → {n} ({_fmt_delta(d)})')
        for t, b, n in ck_fails:
            print(f'     内容 {t:22s} 摘要 {b} → {n}（行数可能没变 ⇒ UPDATE 型改动）')
        return False

    print('✅ 闸门绿：核心 8 表行数 Δ 全为 0' + ('，内容摘要也全一致' if has_ck else ''))
    return True


def self_test() -> int:
    """★ 判据自检：喂已知结果，断言闸门**在该红时必须红**。

    不连生产。为了证明这道闸门不是摆设 ——
    一道从没被证明会红的闸门，等于没有闸门。
    """
    base = {t: 100 for t in CORE8}
    base['reference'] = 50
    base_ck = {t: {'n': 100, 'sum': 1000} for t in CORE8}

    ok = True

    # 用例 1：完全一致 ⇒ 必须绿
    now = dict(base)
    fails, missing, others, ck_fails = _compare(base, now, base_ck, dict(base_ck))
    r1 = (not fails and not missing and not others and not ck_fails)
    print(f'  用例1 全一致 → 期望绿 / 实际{"绿" if r1 else "红"}')
    ok &= r1

    # 用例 2：核心表差 1 ⇒ 必须红（差一点点也算变）
    now = dict(base)
    now['protocol'] = 101
    fails, missing, others, ck_fails = _compare(base, now)
    r2 = len(fails) == 1 and fails[0][0] == 'protocol' and fails[0][3] == 1
    print(f'  用例2 核心表 +1 → 期望红 / 实际{"红" if r2 else "绿(失败)"}')
    ok &= r2

    # 用例 3：核心表少 5 ⇒ 必须红
    now = dict(base)
    now['sku'] = 95
    fails, missing, others, ck_fails = _compare(base, now)
    r3 = len(fails) == 1 and fails[0][3] == -5
    print(f'  用例3 核心表 -5 → 期望红 / 实际{"红" if r3 else "绿(失败)"}')
    ok &= r3

    # 用例 4：只有非核心表变化 ⇒ 必须绿（只提示）
    now = dict(base)
    now['reference'] = 57
    fails, missing, others, ck_fails = _compare(base, now)
    r4 = not fails and not missing and len(others) == 1 and not ck_fails
    print(f'  用例4 仅非核心表 +7 → 期望绿+提示1条 / 实际{"绿" if r4 else "红(失败)"}'
          f'（提示 {len(others)} 条）')
    ok &= r4

    # 用例 5：基线里的核心表在现状缺失（表被删）⇒ 必须红
    now = dict(base)
    now.pop('method_protocol')
    fails, missing, others, ck_fails = _compare(base, now)
    r5 = not fails and missing == ['method_protocol']
    print(f'  用例5 核心表消失 → 期望红 / 实际{"红" if r5 else "绿(失败)"}')
    ok &= r5

    # 用例 6：非核心表新增 ⇒ 只提示，不判负
    now = dict(base)
    now['brand_new_table'] = 3
    fails, missing, others, ck_fails = _compare(base, now)
    r6 = not fails and not missing and len(others) == 1
    print(f'  用例6 新增非核心表 → 期望绿+提示1条 / 实际'
          f'{"绿" if r6 else "红(失败)"}（提示 {len(others)} 条）')
    ok &= r6

    # 用例 7：★ 行数没变、内容变了（UPDATE 型，如 D 处置）⇒ 必须红
    #   这是「只看行数」的致命盲区 —— 行数闸门对这种改动完全瞎
    now_ck = {t: {'n': 100, 'sum': 1000} for t in CORE8}
    now_ck['protocol'] = {'n': 100, 'sum': 999}
    fails, missing, others, ck_fails = _compare(base, dict(base), base_ck, now_ck)
    r7 = (not fails and not missing and len(ck_fails) == 1
          and ck_fails[0][0] == 'protocol')
    print(f'  用例7 行数不变但内容变 → 期望红 / 实际'
          f'{"红" if r7 else "绿(失败)"}（内容差异 {len(ck_fails)} 张）')
    ok &= r7

    # 用例 8：老基线没有摘要字段 ⇒ 只比行数，且必须**显式提示**
    fails, missing, others, ck_fails = _compare(base, dict(base), {}, {})
    r8 = (not ck_fails)
    print(f'  用例8 基线缺摘要 → 期望不因此误报红 / 实际'
          f'{"不误报" if r8 else "误报(失败)"}')
    ok &= r8

    print()
    if ok:
        print('✅ 自检通过：8/8 用例符合预期 ⇒ 这道闸门在该红时会红（含 UPDATE 型）')
        return 0
    print('❌ 自检失败：判据本身有问题 ⇒ 闸门不可信，必须修脚本后才能用于部署')
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description='部署闸门：核心 8 表行数 Δ0 的可执行判据（只读）')
    ap.add_argument('--capture', metavar='PATH', help='抓基线并写入 JSON')
    ap.add_argument('--compare', metavar='PATH', help='与基线 JSON 比对，核心 8 表须 Δ0')
    ap.add_argument('--self-test', action='store_true',
                    help='★ 只验判据本身（不连生产）：喂已知结果，断言该红时必红')
    ap.add_argument('--host', default=DEFAULT_HOST)
    ap.add_argument('--key', default=DEFAULT_KEY, help='SSH 私钥路径（Windows 路径用正斜杠）')
    ap.add_argument('--container', default=DEFAULT_CONTAINER)
    ap.add_argument('--db-name', default=DEFAULT_DB)
    ap.add_argument('--db-user', default=DEFAULT_USER)
    ap.add_argument('--timeout', type=int, default=30, help='SSH ConnectTimeout 秒')
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    if not args.capture and not args.compare:
        ap.error('至少给一个：--capture PATH / --compare PATH / --self-test')

    try:
        now, now_ck = capture(args)
    except RuntimeError as e:
        print(f'❌ 环境问题：{e}')
        return 2

    missing_core = [t for t in CORE8 if t not in now]
    if missing_core:
        print(f'❌ 核心表在库里不存在：{missing_core}')
        return 2

    print(f'表计数（排除 {SKIP_PREFIX} 前缀）：共 {len(now)} 张')
    for t in CORE8:
        print(f'  ★ {t:22s} {now[t]:>8d}   内容摘要 {now_ck[t]["sum"]}')

    if args.capture:
        path = args.capture
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        payload = {
            'core8': list(CORE8),
            'counts': dict(sorted(now.items())),
            'checksums': {t: now_ck[t] for t in CORE8},
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write('\n')
        print(f'✅ 基线已写入 {path}（{len(now)} 张表 + {len(CORE8)} 张内容摘要）')

    if not args.compare:
        return 0

    path = args.compare
    if not os.path.isfile(path):
        print(f'❌ 基线文件不存在：{path}')
        return 2
    with open(path, encoding='utf-8') as f:
        base = json.load(f)
    base_counts = base.get('counts') or {}
    base_ck = base.get('checksums') or {}

    print('\n' + '=' * 62)
    fails, missing, others, ck_fails = _compare(base_counts, now, base_ck, now_ck)
    has_ck = bool(base_ck)
    return 0 if _report(fails, missing, others, ck_fails, has_ck) else 1


if __name__ == '__main__':
    sys.exit(main())
