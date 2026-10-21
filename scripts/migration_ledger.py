#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""迁移演练**台账**生成器（2026-10-21 新增）

## 为什么要这个
`migration_drill.py` 能演练，但**跑完就散了** —— 没人知道"74 个迁移里哪些真的演练过"。
方案 §9.2 S6 要求"74 个补记录 → 台账"。本脚本把演练结果自动落成一份可复现的台账。

## 粒度（必须写清楚，别误读）
**一个 app 一行**：drill 会把该 app 的**全部迁移**在独立 sqlite 上跑完整链路
（正向 → 造存量数据 → 应用 → 幂等重放 → 反向回滚）。
⇒ 台账"覆盖迁移数"= 该 app 的迁移文件数；**74 个迁移都在这 10 条链路里**。
⚠️ 但它不是"逐个迁移单独回滚"—— 那需要 74×4 次实例创建，成本极高且收益低
（Django 按依赖图执行，app 级链路已能暴露跨 app 依赖与不可逆问题）。

## 诚实的边界（会自动写进台账）
- **造数覆盖面**：`migration_drill.py` 的 seed 只对 documents / commerce / transactions
  造了"贴近生产形态"的数据；其余 app 的造数脚本是空的 ⇒ 那些 app 的演练实际是"空库迁移"。
  台账会标出每行的"造数"状态，不假装都一样。
- 演练环境是**独立临时 sqlite**，与生产 PostgreSQL 有差异（例如 `select_for_update` 行为）。
  它拦的是"迁移图/依赖/可逆性"问题，不替代生产演练。

## 用法
  python scripts/migration_ledger.py             # 跑全部 app 并重写台账
  python scripts/migration_ledger.py --only commerce,documents
  python scripts/migration_ledger.py --audit-only  # 只做静态依赖审计（秒级，不跑迁移）
"""
from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO, 'backend')
DRILL = os.path.join(REPO, 'scripts', 'migration_drill.py')
OUT = os.path.join(REPO, 'docs', 'e2e', 'MIGRATION_DRILL_LEDGER.md')

# 有 seed 脚本的 app（README 里 seed_sds / seed_orders 覆盖的范围）
APPS_WITH_SEED = {'documents', 'commerce', 'transactions'}
# 造数脚本会碰到的 app（跨 app 依赖：documents 的 seed 会用到 commerce 的模型）
SEED_TOUCHES = {'documents': 'documents + commerce（跨 app）',
                'commerce': 'commerce',
                'transactions': 'transactions（双形态单据）'}


def list_migrations() -> dict[str, list[str]]:
    """扫 backend/**/migrations/0*.py，返回 {app: [文件名...]}（按文件名排序）。"""
    out: dict[str, list[str]] = {}
    for root, dirs, files in os.walk(BACKEND):
        if os.path.basename(root) != 'migrations':
            continue
        if 'venv' in root or 'site-packages' in root:
            continue
        app = os.path.basename(os.path.dirname(root))
        names = sorted(f for f in files if re.match(r'^0\d+.*\.py$', f))
        if names:
            out[app] = names
    return dict(sorted(out.items()))


def run_drill(app: str, audit_only: bool) -> tuple[int, str, float]:
    cmd = [sys.executable, DRILL, '--app', app]
    if audit_only:
        cmd.append('--audit-only')
    t0 = time.time()
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    return p.returncode, (p.stdout or '') + (p.stderr or ''), time.time() - t0


def seed_status(app: str, seed_text: str, audit_only: bool) -> tuple[str, bool]:
    """返回 (展示文案, 是否真的造出了存量数据)。

    ★ 为什么要分开：drill 的 ② 有三种结果，含义完全不同 ——
      · 真造出了数据  ⇒ 演练覆盖了"有存量数据时迁移"（证明力强）
      · 跳过（"此刻迁移图里没有 xxx"）⇒ 该 app 的演练实际是**空库迁移**（证明力弱，但链路仍有效）
      · seed 报错      ⇒ 这才是需要人看的问题
    台账若把三者混成一个"通过"，就是把"空库能迁"当成了"有数据也能迁"。
    """
    if audit_only:
        return '不适用（audit-only）', False
    t = (seed_text or '').strip()
    if '失败' in t:
        return '❌ seed 报错：' + t[:70], False

    # ★ 2026-10-21 修：**先判"有没有真的造出数据"，再判"有没有跳过"**。
    #   初版顺序反了 —— seed 文本常是「Product 4 / SdsRevision 8 | 跳过订单造数：…」
    #   这种"部分成功 + 部分跳过"的混合形态，先匹配"跳过"会把 commerce/documents/bridges
    #   三个**明明造了数据**的 app 误标成"空库"（台账出现错信息）。
    # ★ 必须按 ` | ` 切分后再拼装：
    #   ① seed 文本里带 `|`，直接塞进 markdown 表格会把**列切乱**（已实测错位）；
    #   ② 文本常是"部分成功 + 部分跳过"混合，整段照抄会出现
    #      「✅ 有存量数据：跳过 sds 造数：…」这种自相矛盾的显示。
    raw = t.replace('[seed]', '').strip()
    parts = [x.strip() for x in raw.split('|') if x.strip()]
    ok_parts = [x for x in parts if re.search(r'(Product\s+\d+|SdsRevision\s+\d+|Order\s+序号版)', x)]
    skip_parts = [x for x in parts if '跳过' in x]
    def cell(x):
        """清洗成能安全放进 markdown 表格单元格的短文本。

        ⚠️ 三件事：① `|` 会把表格列切乱；② `LookupError: No installed app with label 'commerce'`
        这种异常尾巴对读台账的人是噪声；③ 截断后常留下悬空的 `（`，看着像 bug。
        """
        x = x.replace('|', '/')
        x = re.sub(r"[（(]No installed app with label[^）)]*[）)]", '', x)
        x = re.sub(r"[（(]No installed app[^）)]*[）)]", '', x)
        x = x.replace('No installed app with label', '').strip()
        x = x[:70]
        return x.rstrip('（( 、/ ')

    if ok_parts:
        extra = ''
        if skip_parts:
            short = skip_parts[0].replace('跳过 sds 造数：', '').replace('跳过订单造数：', '')
            extra = '（另有跳过：' + cell(short)[:28] + '）'
        return '✅ 有存量数据：' + cell(' / '.join(ok_parts)) + extra, True
    if skip_parts:
        short = skip_parts[0].replace('跳过 sds 造数：', '').replace('跳过订单造数：', '')
        return '⚠️ 空库（' + cell(short)[:50] + '）', False
    if app not in APPS_WITH_SEED:
        return '⚠️ 空库（该 app 无 seed 脚本）', False
    return '⚠️ 无造数输出（可疑）', False


def parse(out: str) -> dict:
    """从 drill 输出里抽出：结论、各步状态、造数详情、失败项。"""
    verdict = ''
    m = re.search(r'\[结论\]\s*(.+)', out)
    if m:
        verdict = m.group(1).strip()
    steps = []
    for line in out.splitlines():
        mm = re.match(r'^([✅🛑❌⚠️])\s*([①②③④⑤⑥].*)$', line.strip())
        if mm:
            steps.append((mm.group(1), mm.group(2)))
    # 造数状态
    seed = ''
    for i, (icon, text) in enumerate(steps):
        if text.startswith('②'):
            # 下一行是 detail
            idx = out.find(text)
            tail = out[idx + len(text):].splitlines()
            seed = (tail[1].strip() if len(tail) > 1 else '')[:120]
            break
    bad = [f'{i} {t}' for i, t in steps if i in ('🛑', '❌', '⚠️')]
    return {'verdict': verdict, 'steps': steps, 'seed': seed, 'bad': bad}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='', help='只跑这些 app（逗号分隔）')
    ap.add_argument('--audit-only', action='store_true', help='只做静态依赖审计')
    args = ap.parse_args()

    migs = list_migrations()
    apps = list(migs.keys())
    if args.only:
        want = {a.strip() for a in args.only.split(',') if a.strip()}
        apps = [a for a in apps if a in want]

    total_migs = sum(len(migs[a]) for a in apps)
    print(f'演练 {len(apps)} 个 app / {total_migs} 个迁移'
          f'{"（audit-only）" if args.audit_only else ""}…\n')

    rows = []
    t_all = time.time()
    for app in apps:
        rc, out, secs = run_drill(app, args.audit_only)
        info = parse(out)
        ok = rc == 0 and '通过' in info['verdict']
        if args.audit_only and ok:
            # ⚠️ drill 在 audit-only 下也打印「全链路通过」，但**根本没跑迁移**。
            #    台账若照抄这句，就是在宣称"演练过"——那种假绿正是要防的。
            info['verdict'] = '静态依赖审计通过（**未跑迁移**）'
            info['seed'] = '不适用（audit-only）'
        seed_text, has_data = seed_status(app, info['seed'], args.audit_only)
        rows.append({
            'app': app,
            'count': len(migs[app]),
            'latest': migs[app][-1].replace('.py', ''),
            'ok': ok,
            'seed_text': seed_text,
            'has_data': has_data,
            'verdict': info['verdict'] or f'(rc={rc})',
            'seed': info['seed'],
            'bad': info['bad'],
            'secs': secs,
            'rc': rc,
        })
        flag = '✅' if ok else '❌'
        print(f'{flag} {app:14s} {len(migs[app]):2d} 个迁移  {secs:5.1f}s  {info["verdict"]}')
        for b in info['bad']:
            print(f'       └ {b}')
    wall = time.time() - t_all

    passed = sum(1 for r in rows if r['ok'])
    # ── 写台账 ──
    L = []
    L.append('# 迁移演练台账（migration drill ledger）')
    L.append('')
    L.append('> **由 `scripts/migration_ledger.py` 自动生成，勿手改。** 重跑即重写。')
    L.append('> 演练器：`scripts/migration_drill.py`（在**独立临时 sqlite** 上跑，绝不碰项目 DB）。')
    L.append('')
    L.append('## 0. 本次模式')
    L.append('')
    if args.audit_only:
        L.append('> ⚠️ **本次是 `--audit-only`（只做静态跨 app 依赖审计，未执行任何迁移）。**')
        L.append('> 下方"通过"仅表示**依赖图无缺失**，不代表迁移可正向执行/可回滚。')
        L.append('> 要真演练请跑 `python scripts/migration_ledger.py`（不带该参数）。')
    else:
        L.append('> ✅ 本次是**完整演练**：每个 app 都在独立临时 sqlite 上跑了'
                 '正向 → 造数 → 应用 → 幂等重放 → 反向回滚。')
    L.append('')
    L.append('## 1. 结论')
    L.append('')
    L.append(f'- 覆盖：**{len(rows)} 个 app / {total_migs} 个迁移**')
    L.append(f'- 迁移链路：**{passed}/{len(rows)} 个 app 通过**（正向 → 应用 → 幂等重放 → 反向回滚）')
    n_data = sum(1 for r in rows if r['has_data'])
    L.append(f'- 存量数据覆盖：**{n_data}/{len(rows)} 个 app** 真的造出了存量数据；'
             f'其余是**空库迁移**（链路有效，但不证明"有数据时也能迁"）')
    L.append(f'- 总耗时：{wall:.1f}s（含每个 app 的实例创建/迁移/回滚）')
    L.append(f'- 生成时间：{time.strftime("%Y-%m-%d %H:%M:%S")}')
    L.append('')
    L.append('## 2. 粒度与边界（读这张表前必看）')
    L.append('')
    L.append('| 项 | 说明 |')
    L.append('|---|---|')
    L.append('| 粒度 | **一个 app 一行**：drill 会把该 app 的**全部迁移**跑完整链路'
             '（正向 → 造存量数据 → 应用 → 幂等重放 → 反向回滚）⇒ 74 个迁移都在这 10 条链路里 |')
    L.append('| **不是**什么 | **不是**"逐个迁移单独回滚"（那要 74×4 次实例创建，成本极高、收益低） |')
    L.append('| 造数覆盖 | **只有 documents / commerce / transactions** 造了"贴近生产形态"的存量数据；'
             '其余 app 的 seed 是空的 ⇒ 那些 app 的演练实际是**空库迁移**（表里"造数"列会标明） |')
    L.append('| 环境差异 | 独立**临时 sqlite**，与生产 PostgreSQL 有差异（如 `select_for_update` 在 sqlite 上是 no-op）'
             '⇒ 拦的是"迁移图/跨 app 依赖/可逆性"，**不替代生产演练** |')
    L.append('')
    L.append('## 3. 逐 app 结果')
    L.append('')
    L.append('| # | app | 迁移数 | 最新节点 | 迁移链路 | 存量数据 | 耗时 |')
    L.append('|---|---|---|---|---|---|---|')
    for i, r in enumerate(rows, 1):
        link = '✅ 正向/幂等/反向 均通过' if r['ok'] else f'❌ {r["verdict"]}'
        L.append(f'| {i} | `{r["app"]}` | {r["count"]} | `{r["latest"]}` | {link} | {r["seed_text"]} | {r["secs"]:.1f}s |')
    L.append('')
    if any(not r['ok'] for r in rows):
        L.append('## 4. 失败明细')
        L.append('')
        for r in rows:
            if r['ok']:
                continue
            L.append(f'### `{r["app"]}`')
            L.append('')
            for b in r['bad']:
                L.append(f'- {b}')
            L.append(f'- 退出码：{r["rc"]}')
            L.append('')
    L.append('## %d. 怎么复现 / 加新 app' % (5 if any(not r['ok'] for r in rows) else 4))
    L.append('')
    L.append('```bash')
    L.append('python scripts/migration_ledger.py                # 全量重跑并重写本台账')
    L.append('python scripts/migration_ledger.py --audit-only   # 只做静态依赖审计（秒级）')
    L.append('python scripts/migration_drill.py --app documents --target 0006   # 单点复现')
    L.append('```')
    L.append('')
    L.append('新增 app 不需要改本脚本（它扫 `backend/**/migrations/0*.py` 自动发现）；')
    L.append('但**建议同时给它的迁移补 seed**（在 `migration_drill.py` 的 SEED_SCRIPT 里），')
    L.append('否则该 app 的演练只是"空库能迁"，证明力有限。')
    L.append('')

    io.open(OUT, 'w', encoding='utf-8', newline='').write('\n'.join(L))
    print(f'\n台账已写入：{os.path.relpath(OUT, REPO)}')
    print(f'结论：{passed}/{len(rows)} 个 app 通过；覆盖 {total_migs} 个迁移')
    return 0 if passed == len(rows) else 1


if __name__ == '__main__':
    sys.exit(main())
