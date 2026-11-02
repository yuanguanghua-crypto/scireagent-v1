#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""build_sds_v3_batch.py — 把抽中的 id 从生产库灌成盲测批（SDS-PAGE v3 专用）

输入：`work/_sds_v3_sample_20261102.json`（由 draw_sds_v3_sample.py --draw 产出）
输出：
  · `work/_sds_v3_batch_20261102.json`      ← 进包的样本（33 条，探针已混入、**不标记**）
  · `work/_sds_v3_batch_meta_20261102.json` ← **组织方专属**：哪 3 条是探针 + 各文件 md5

## 三条口径（都是为了不与上轮产生额外变量）

1. **步骤文本 = `title + ' ' + body`** —— 与 2026-11-02 上一轮 `p0_sds_page_kappa_batch.json`
   **逐字同口径**（已实测核对 protocol 4790 / step 136561）。`title` 为空（T3 置空过 1,056 条）
   时退化为纯 body，不补空格。
2. **每協議只取前 6 步**（`step_no, id` 升序）—— 同上轮；`n_steps` 记**实际给到的步数**，不是库内总数。
3. **顺序按 `seed=20261102` 打乱** —— 探针 3 条不得集中在末尾，否则标注员能从位置猜出来。

## 纪律

- 只读生产库（SELECT），不写任何库表
- 探针身份**只写 meta 文件**，绝不进批文件、绝不进包
- 长度字段一律脚本算，禁手填
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
SAMPLE = os.path.join(REPO, 'work', '_sds_v3_sample_20261102.json')
BATCH = os.path.join(REPO, 'work', '_sds_v3_batch_20261102.json')
META = os.path.join(REPO, 'work', '_sds_v3_batch_meta_20261102.json')
SEED = 20261102
STEP_LIMIT = 6          # 与上轮一致：前 6 步

SQL_TPL = """
COPY (
WITH want AS (SELECT unnest(ARRAY[{ids}]::bigint[]) AS pid)
SELECT json_build_object(
  'bridge_id', mp.id,
  'protocol_id', p.id,
  'protocol_name', p.name,
  'objective', coalesce(p.objective, ''),
  'steps', coalesce((
    SELECT json_agg(json_build_object('step_id', x.id, 'step_no', x.step_no, 'text', x.txt)
                    ORDER BY x.step_no, x.id)
      FROM (SELECT s.id, s.step_no,
                   CASE WHEN coalesce(btrim(s.title), '') = '' THEN coalesce(s.body, '')
                        ELSE s.title || ' ' || coalesce(s.body, '') END AS txt
              FROM protocol_step s
             WHERE s.protocol_id = p.id
             ORDER BY s.step_no, s.id
             LIMIT {lim}) x
  ), '[]'::json)
)::text
  FROM method m
  JOIN method_protocol mp ON mp.method_id = m.id
  JOIN protocol p ON p.id = mp.protocol_id
  JOIN want w ON w.pid = p.id
 WHERE m.name = 'SDS-PAGE'
 ORDER BY p.id
) TO STDOUT WITH (FORMAT csv, HEADER false);
""".strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default=os.environ.get('SCIREAGENT_HOST', 'admin@47.82.156.48'))
    ap.add_argument('--key', default=os.environ.get('SCIREAGENT_SSH_KEY', ''))
    ap.add_argument('--container', default='scireagent-db-1')
    ap.add_argument('--db-name', default='scireagent')
    ap.add_argument('--db-user', default='scireagent')
    ap.add_argument('--timeout', type=int, default=30)
    a = ap.parse_args()

    if not a.key:
        print('❌ 需要 --key（或用 SCIREAGENT_SSH_KEY）')
        return 2
    if not os.path.isfile(SAMPLE):
        print(f'❌ 缺抽样结果 {os.path.relpath(SAMPLE, REPO)}；先跑 draw --draw')
        return 2

    smp = json.load(io.open(SAMPLE, encoding='utf-8'))
    main_ids = [str(x) for x in smp['main_sample']]
    probe_ids = [str(x) for x in smp['probe']]
    all_ids = main_ids + probe_ids
    if len(main_ids) != 30 or len(probe_ids) != 3:
        print(f'❌ 样本数不对：主 {len(main_ids)} / 探针 {len(probe_ids)}（应 30 / 3）')
        return 2
    if len(set(all_ids)) != len(all_ids):
        print('❌ 主样本与探针有重复')
        return 2

    sql = SQL_TPL.format(ids=','.join(all_ids), lim=STEP_LIMIT)
    argv = ['ssh', '-i', a.key, '-o', 'StrictHostKeyChecking=accept-new',
            '-o', f'ConnectTimeout={a.timeout}', a.host,
            f'docker exec -i {a.container} psql -U {a.db_user} -d {a.db_name} -v ON_ERROR_STOP=1']
    try:
        p = subprocess.run(argv, input=sql, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=a.timeout + 60)
    except Exception as e:
        print(f'❌ 执行失败：{e}')
        return 2
    if p.returncode != 0 or 'ERROR' in (p.stderr or '').upper():
        print(f'❌ psql 失败：{(p.stderr or "")[:400]}')
        return 2

    recs = []
    for line in (p.stdout or '').splitlines():
        line = line.strip().strip('"').rstrip('"')
        if not line.startswith('{'):
            continue
        obj = json.loads(line.replace('""', '"'))
        recs.append(obj)

    got = {str(r['protocol_id']) for r in recs}
    miss = set(all_ids) - got
    if miss:
        print(f'❌ 这些 id 没灌到（可能桥已变/协议已删）：{sorted(miss, key=int)}')
        return 1
    if len(recs) != len(all_ids):
        print(f'❌ 灌到 {len(recs)} 条，期望 {len(all_ids)}（可能有重复桥）')
        return 1

    # 长度字段：脚本算，禁手填
    for r in recs:
        r['objective_len'] = len(r.get('objective') or '')
        r['n_steps'] = len(r.get('steps') or [])
        r['steps_len'] = sum(len(s.get('text') or '') for s in (r.get('steps') or []))

    # 打乱（探针不得集中在末尾）
    rnd = random.Random(SEED)
    order = list(range(len(recs)))
    rnd.shuffle(order)
    recs = [recs[i] for i in order]

    with io.open(BATCH, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(recs, f, ensure_ascii=False, indent=1)
        f.write('\n')

    probe_pos = [i + 1 for i, r in enumerate(recs) if str(r['protocol_id']) in set(probe_ids)]
    meta = {
        'seed': SEED, 'step_limit': STEP_LIMIT,
        'text_convention': "title + ' ' + body（与上轮 p0_sds_page_kappa_batch.json 同口径）",
        'main_sample': main_ids, 'probe': probe_ids,
        'probe_positions_in_batch': probe_pos,
        'probe_bridge_ids': [r['bridge_id'] for r in recs if str(r['protocol_id']) in set(probe_ids)],
        'batch_md5': hashlib.md5(open(BATCH, 'rb').read()).hexdigest(),
        'note': '★ 组织方专属：probe 身份绝不进包、不进批文件。',
    }
    with io.open(META, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
        f.write('\n')

    print(f'✅ 批已生成 {os.path.relpath(BATCH, REPO)}：{len(recs)} 条   md5 {meta["batch_md5"]}')
    print(f'   步骤上限 {STEP_LIMIT}｜objective 长度 {min(r["objective_len"] for r in recs)}–{max(r["objective_len"] for r in recs)}'
          f'｜steps_len {min(r["steps_len"] for r in recs)}–{max(r["steps_len"] for r in recs)}')
    print(f'   探针落在批内第 {probe_pos} 位（不进包、不标记）')
    print(f'✅ meta 已写 {os.path.relpath(META, REPO)}（组织方专属）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
