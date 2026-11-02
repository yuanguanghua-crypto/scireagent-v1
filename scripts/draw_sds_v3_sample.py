#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""draw_sds_v3_sample.py — SDS-PAGE v3 重验的抽样器（SDS-PAGE 专用，非通用）

## 它做什么

按 `work/A方案_SDS-PAGE_v3重验_草案.md` v3（2026-11-02 18:54 三条决定）的口径抽样：
  · 抽样框 = 池 144 − **2D 命中 20**（决定 D：二维本轮回避）
  · 排除集 = 已用 44（κ 批 20 + 暖身 v2 14 + 旧暖身 10）∪ 2D 20 = **56**
  · 可用 = **88**，分层 S1 7 / S2 1 / S3 32 / S4 84
  · 主样本 n=30，按**全池占比**：**S1 2 / S3 8 / S4 20**（S2 配额 0，已批空缺）
  · 边界探针 3 条 = S1 剩余（不进 κ）

## 两条硬纪律

1. **抽样时点 = 发包前那一刻**。默认 `--dry-run`，只自检 + 报数，**不输出任何 id**。
   只有显式 `--draw` 才真抽。提前抽出来放仓库 = 变相温读。
2. **排除集不许手抄**。全部现取：
   · 已用 44 ← 从三个样本文件**实时读取**
   · 2D 20 + 当前 obj_len / n_steps ← 从生产库**实时 SQL**（只读）

## 为什么 2D 命中不能从本地快照算

`work/sds_pool_20261102.json` 里的 `step_text` **被截断在 4000 字符**
（实测：protocol 13287 与 4691 正好 4000），长协议后半段的 "2-D/two-dimensional" 看不到。
本地按同一正则只复现出 **3/20** ⇒ 只能用 DB 查。**本脚本因此带 `--refresh` 直连生产**。

## 用法

```bash
# ① 刷新抽样框状态（只读 SQL，会访问生产库）
python scripts/draw_sds_v3_sample.py --refresh --key "C:/Users/<u>/.ssh/scireagent_deploy_ed25519"

# ② 自检 + 报数（默认 dry-run，不吐 id）
python scripts/draw_sds_v3_sample.py

# ③ 真抽（★ 只在发包前那一刻跑）
python scripts/draw_sds_v3_sample.py --draw --out work/_sds_v3_sample_20261102.json
```

退出码：0 = 正常；1 = 口径漂移（自检不符）；2 = 环境/参数问题
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import random
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, 'work', '_sds_sample_frame_20261102.json')

SEED = 20261102
N_MAIN = 30
N_PROBE = 3                      # S1 剩余全部作探针

# 方案 v3 的期望值 —— 任何一项不符就说明池/口径漂了，拒绝抽样
EXPECT = {
    'pool': 144,
    'two_d': 20,
    'used': 44,
    'overlap_used_two_d': 8,
    'frame': 124,
    'available': 88,
    'strata': {'S1': 7, 'S2': 1, 'S3': 32, 'S4': 84},
    'used_by_stratum': {'S1': 2, 'S2': 1, 'S3': 11, 'S4': 22},
    'quota': {'S1': 2, 'S3': 8, 'S4': 20},
}

USED_FILES = (
    'work/p0_sds_page_kappa_batch.json',
    'work/p0_sds_page_warmup_v2.json',
    'work/p0_sds_page_warmup_for_author.json',
)

DEFAULT_HOST = os.environ.get('SCIREAGENT_HOST', 'admin@47.82.156.48')
DEFAULT_KEY = os.environ.get('SCIREAGENT_SSH_KEY', '')

# 抽样框状态（只读）。谓词与 2026-11-02 定 20 条时**逐字相同**，勿改以免漂移。
SQL_FRAME = r"""
COPY (
  SELECT pr.id AS protocol_id,
         length(coalesce(pr.objective,'')) AS obj_len,
         (SELECT count(*) FROM protocol_step s WHERE s.protocol_id = pr.id) AS n_steps,
         (coalesce(pr.objective,'') ~* '(2-?D-?PAGE|two.?dimensional|isoelectric|IEF|first dimension|second dimension)'
          OR EXISTS (SELECT 1 FROM protocol_step s WHERE s.protocol_id = pr.id
                      AND coalesce(s.body,'') ~* '(2-?D-?PAGE|two.?dimensional|isoelectric|IEF|first dimension|second dimension)')
         ) AS two_d
    FROM method m
    JOIN method_protocol mp ON mp.method_id = m.id
    JOIN protocol pr ON pr.id = mp.protocol_id
   WHERE m.name = 'SDS-PAGE'
   ORDER BY pr.id
) TO STDOUT WITH (FORMAT csv, HEADER true);
""".strip()


def _stratum(obj_len: int, n_steps: int) -> str:
    if obj_len == 0:
        return 'S1'
    if n_steps <= 2:
        return 'S2'
    if obj_len <= 120:
        return 'S3'
    return 'S4'


def _quota(strata: dict) -> dict:
    """按**全池占比**分 S1/S3/S4，余数给 S4。S2 恒 0（已批空缺）。"""
    tot = sum(strata.values())
    q = {}
    for s in ('S1', 'S3', 'S4'):
        q[s] = round(strata[s] / tot * N_MAIN)
    q['S4'] += N_MAIN - sum(q.values())
    return q


def refresh(args) -> int:
    """从生产库只读抓抽样框状态，写缓存。"""
    if not args.key:
        print('❌ --refresh 需要 --key（或用 SCIREAGENT_SSH_KEY）')
        return 2
    argv = ['ssh', '-i', args.key, '-o', 'StrictHostKeyChecking=accept-new',
            '-o', f'ConnectTimeout={args.timeout}', args.host,
            f'docker exec -i {args.container} psql -U {args.db_user} -d {args.db_name} -v ON_ERROR_STOP=1']
    try:
        p = subprocess.run(argv, input=SQL_FRAME, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=args.timeout + 30)
    except Exception as e:
        print(f'❌ 连不上/执行失败：{e}')
        return 2
    out = (p.stdout or '')
    if p.returncode != 0 or 'ERROR' in (p.stderr or '').upper():
        print(f'❌ psql 失败：{(p.stderr or "")[:400]}')
        return 2

    rows = []
    for line in out.splitlines()[1:]:
        parts = [c.strip() for c in line.split(',')]
        if len(parts) != 4 or not parts[0].isdigit():
            continue
        rows.append({'protocol_id': parts[0], 'obj_len': int(parts[1]),
                     'n_steps': int(parts[2]), 'two_d': parts[3] in ('t', 'true')})
    if not rows:
        print('❌ 没解析到任何行')
        return 2

    payload = {'generated_at': args.stamp, 'source': 'production db (read-only)',
               'sql': SQL_FRAME, 'rows': rows}
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with io.open(CACHE, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
        f.write('\n')
    md5 = hashlib.md5(open(CACHE, 'rb').read()).hexdigest()
    print(f'✅ 抽样框状态已刷新 → {os.path.relpath(CACHE, REPO)}（{len(rows)} 行，md5 {md5}）')
    return 0


def load_frame() -> dict:
    with io.open(CACHE, encoding='utf-8') as f:
        return json.load(f)


def load_used() -> set:
    used = set()
    for rel in USED_FILES:
        p = os.path.join(REPO, rel)
        if not os.path.isfile(p):
            raise RuntimeError(f'缺少已用样本文件：{rel}')
        with io.open(p, encoding='utf-8') as f:
            for x in json.load(f):
                used.add(str(x['protocol_id']))
    return used


def build(verbose=True):
    """算抽样框 / 分层 / 配额，并做口径自检。返回 (frame_ids, strata_avail, quota, diag) 或抛异常。"""
    fr = load_frame()
    rows = {r['protocol_id']: r for r in fr['rows']}
    used = load_used()
    two_d = {pid for pid, r in rows.items() if r['two_d']}

    pool = set(rows)
    frame = {pid for pid in pool if pid not in two_d}
    avail = {pid for pid in frame if pid not in used}

    strata = {'S1': 0, 'S2': 0, 'S3': 0, 'S4': 0}
    used_str = {'S1': 0, 'S2': 0, 'S3': 0, 'S4': 0}
    avail_by = {'S1': [], 'S2': [], 'S3': [], 'S4': []}
    for pid in frame:
        s = _stratum(rows[pid]['obj_len'], rows[pid]['n_steps'])
        strata[s] += 1
        if pid in used:
            used_str[s] += 1
        else:
            avail_by[s].append(pid)
    for k in avail_by:
        avail_by[k].sort(key=int)

    quota = _quota(strata)
    diag = {
        'pool': len(pool), 'two_d': len(two_d), 'used_all': len(used),
        'used_in_pool': len(used & pool),
        'overlap_used_two_d': len(used & two_d),
        'frame': len(frame), 'available': len(avail),
        'strata': strata, 'used_by_stratum': used_str,
        'quota': quota,
    }
    if verbose:
        print(f'抽样框状态：{os.path.relpath(CACHE, REPO)}（生成于 {fr.get("generated_at")}）')
        print(f'  池 {diag["pool"]}｜2D 命中 {diag["two_d"]}｜已用（在池内）{diag["used_in_pool"]}'
              f'｜已用∩2D {diag["overlap_used_two_d"]}')
        print(f'  **抽样框 {diag["frame"]}｜可用 {diag["available"]}**')
        print(f'  分层（框内）：S1 {strata["S1"]} / S2 {strata["S2"]} / S3 {strata["S3"]} / S4 {strata["S4"]}')
        print(f'  已用分层：    S1 {used_str["S1"]} / S2 {used_str["S2"]} / S3 {used_str["S3"]} / S4 {used_str["S4"]}')
        print(f'  ★ 主样本 n={N_MAIN} 配额：S1 {quota["S1"]} / S3 {quota["S3"]} / S4 {quota["S4"]}'
              f'（S2 0，已批空缺）')
        print(f'  ★ 边界探针 n={N_PROBE} = S1 剩余 {len(avail_by["S1"]) - quota["S1"]} 条')

    # ── 口径自检：与方案 v3 逐一比对，任何不符 → 拒绝抽样 ──
    bad = []
    for k in ('pool', 'two_d', 'frame', 'available', 'overlap_used_two_d'):
        if diag[k] != EXPECT[k]:
            bad.append(f'{k} 期望 {EXPECT[k]} / 实际 {diag[k]}')
    if diag['used_in_pool'] != EXPECT['used']:
        bad.append(f'已用（池内）期望 {EXPECT["used"]} / 实际 {diag["used_in_pool"]}')
    for s in strata:
        if strata[s] != EXPECT['strata'][s]:
            bad.append(f'分层 {s} 期望 {EXPECT["strata"][s]} / 实际 {strata[s]}')
        if used_str[s] != EXPECT['used_by_stratum'][s]:
            bad.append(f'已用分层 {s} 期望 {EXPECT["used_by_stratum"][s]} / 实际 {used_str[s]}')
    for s in quota:
        if quota[s] != EXPECT['quota'][s]:
            bad.append(f'配额 {s} 期望 {EXPECT["quota"][s]} / 实际 {quota[s]}')
    probe_room = len(avail_by['S1']) - quota['S1']
    if probe_room != N_PROBE:
        bad.append(f'探针可用数 期望 {N_PROBE} / 实际 {probe_room}')

    if bad:
        print('\n❌ 口径漂移，拒绝抽样（池或口径变了，先核对再抽）：')
        for b in bad:
            print(f'    - {b}')
        raise RuntimeError('口径漂移')
    if verbose:
        print('\n✅ 口径自检通过：与方案 v3 逐项一致')
    return avail_by, quota, diag


def draw(avail_by, quota):
    """按 seed 在各层内抽；层内以 protocol_id 升序为基准，保证可复现。"""
    rnd = random.Random(SEED)
    picked = []
    for s in ('S1', 'S3', 'S4'):
        pool = avail_by[s]
        k = quota[s]
        chosen = rnd.sample(pool, k) if k else []
        picked.extend(sorted(chosen, key=int))
    probe_pool = [p for p in avail_by['S1'] if p not in set(picked)]
    probe = sorted(probe_pool[:N_PROBE], key=int)
    return sorted(picked, key=int), probe


def main() -> int:
    ap = argparse.ArgumentParser(description='SDS-PAGE v3 重验抽样器（默认 dry-run，不吐 id）')
    ap.add_argument('--refresh', action='store_true', help='从生产库只读刷新抽样框状态')
    ap.add_argument('--draw', action='store_true', help='★ 真抽（只在发包前那一刻用）')
    ap.add_argument('--out', default=None, help='--draw 时的输出文件')
    ap.add_argument('--host', default=DEFAULT_HOST)
    ap.add_argument('--key', default=DEFAULT_KEY)
    ap.add_argument('--container', default='scireagent-db-1')
    ap.add_argument('--db-name', default='scireagent')
    ap.add_argument('--db-user', default='scireagent')
    ap.add_argument('--timeout', type=int, default=30)
    ap.add_argument('--stamp', default='2026-11-02')
    a = ap.parse_args()

    if a.refresh:
        rc = refresh(a)
        if rc:
            return rc
    if not os.path.isfile(CACHE):
        print(f'❌ 缺抽样框缓存 {os.path.relpath(CACHE, REPO)}；先跑 --refresh')
        return 2

    try:
        avail_by, quota, diag = build()
    except RuntimeError:
        return 1

    if not a.draw:
        print('\n（dry-run：未输出任何 id。真抽请加 --draw，且只在发包前那一刻跑）')
        return 0

    picked, probe = draw(avail_by, quota)
    out = a.out or os.path.join(REPO, 'work', f'_sds_v3_sample_{a.stamp}.json')
    payload = {
        'method': 'SDS-PAGE', 'definition_version': 3, 'seed': SEED,
        'frame': os.path.relpath(CACHE, REPO),
        'frame_md5': hashlib.md5(open(CACHE, 'rb').read()).hexdigest(),
        'diag': diag,
        'main_sample': picked, 'probe': probe,
        'note': '探针 3 条不进 κ；包内不得标注"这是探针"。',
    }
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with io.open(out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(f'\n✅ 已抽：主样本 {len(picked)} 条 + 探针 {len(probe)} 条')
    print(f'   名单 → {os.path.relpath(out, REPO)}（md5 {hashlib.md5(open(out,"rb").read()).hexdigest()}）')
    print(f'   主样本：{picked}')
    print(f'   探针  ：{probe}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
