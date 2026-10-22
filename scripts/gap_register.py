#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""缺口总账 —— 把全局测试方案 V3 与拟人化方案的缺口合并去重，形成唯一 backlog。

## 为什么要合并
两份文档各自列过缺口（V3 §5 的 P0/P1/P2、PERSONA §6 的"需要新增的"），
但那是**两份清单**——如果不同步，就会出现"方案 A 说已补、方案 B 还说缺"。
本脚本以 `flow_coverage_matrix.FLOWS` 为唯一事实源（它记录每条流程的深度），
再把两份文档里提到的、**不属于任何流程**的项（如 F8 Django admin）单独补上。

输出：docs/e2e/GAP_REGISTER.md（人读）+ GAP_REGISTER.json（机读，可作 CI baseline）
"""
from __future__ import annotations

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from flow_coverage_matrix import FLOWS, DEPTH_MARK  # noqa: E402

# 不属于任何"流程编号"、但两份方案里确实需要的条目
# ★ 注意：F8-1 / F8-3 已在 FLOWS 里，不要在 EXTRA 里重复登记（第一版就重了，已删）
EXTRA = [
    # X-3 金额快照 已由 apps/transactions/tests/test_price_snapshot.py 覆盖（3 例，2026-10-22）
    # X-4 邮件：已由 apps/notifications/tests/test_email_outbox_contract.py 锁定契约
    #      （入队 pending / 命令标记 sent / 模板缺失产出空壳），真实投递仍无法测（B 类）
]

# 按深度机械给优先级会误判的两处：C 类不该是 P0；hard-delete 不可逆该提前
OVERRIDE = {
    'F8-3': ('P2', 'C'),   # Django admin 无自动化，用运营手册 + 人工冒烟承担
    'F8-1': ('P1', 'A'),   # 物理删除虽无 UI，但端点级用例必须补（不可逆）
}

# 优先级映射：深度越差、业务越靠近钱/合规 ⇒ 越前
PRIO_BY_DEPTH = {'NONE': 'P0', 'LOAD': 'P1', 'PART': 'P2', 'FULL': '—'}


def main():
    rows = []
    for code, name, depth, specs, gap in FLOWS:
        if depth == 'FULL':
            continue
        prio, owner = OVERRIDE.get(code, (PRIO_BY_DEPTH[depth], 'A'))
        g = gap or '需补主路径断言'
        if code == 'F8-3':
            g = '无自动化（C 类）；另外"改完权限必须重登才看到菜单"这条**从未验证**'
        rows.append({
            'id': code, 'name': name, 'depth': depth, 'mark': DEPTH_MARK[depth],
            'prio': prio, 'owner': owner,
            'existing': specs, 'gap': g,
        })
    for xid, name, prio, owner, ref, gap in EXTRA:
        rows.append({'id': xid, 'name': name, 'depth': 'NONE', 'mark': '🟥',
                     'prio': prio, 'owner': owner, 'existing': ref, 'gap': gap})

    order = {'P0': 0, 'P1': 1, 'P2': 2}
    rows.sort(key=lambda r: (order.get(r['prio'], 9), r['id']))

    cnt = {}
    for r in rows:
        cnt[r['prio']] = cnt.get(r['prio'], 0) + 1

    md = ['# 缺口总账（唯一 backlog）', '',
          '**生成** 2026-10-22 · **事实源** `scripts/flow_coverage_matrix.py` 的 FLOWS 表',
          '**用途** 两份测试方案（V3 / PERSONA）的缺口**只有这一份清单**，不要在别处再列一遍。', '',
          '> 合计 **%d** 条：P0 %d / P1 %d / P2 %d' % (
              len(rows), cnt.get('P0', 0), cnt.get('P1', 0), cnt.get('P2', 0)), '',
          '| 序 | ID | 缺口 | 现深度 | 优先级 | 归属 | 现状 | 缺什么 |',
          '|---|---|---|---|---|---|---|---|']
    for i, r in enumerate(rows, 1):
        md.append('| %d | `%s` | %s | %s %s | **%s** | %s | %s | %s |' % (
            i, r['id'], r['name'], r['mark'], r['depth'], r['prio'], r['owner'],
            r['existing'][:40] or '—', r['gap']))
    md += ['', '## 归属口径（沿用 GLOBAL_TEST_DEFINITION）', '',
           '- **A**：该由自动化承担，且已经能跑（或本轮就该补上）',
           '- **B**：已知未测，但有**可执行的兜底动作**（如"改这些路径时必须手跑某个脚本"）',
           '- **C**：产品面不适用（如 Django admin），用运营手册 + 周期人工冒烟承担', '',
           '> ⚠️ 这份清单**不包含"没人知道没测"的格子**——那是定义里的红线。', '']

    io.open(os.path.join(ROOT, 'docs', 'e2e', 'GAP_REGISTER.md'), 'w',
            encoding='utf-8', newline='').write('\n'.join(md))
    json.dump({'generated': '2026-10-22', 'total': len(rows), 'by_prio': cnt, 'items': rows},
              io.open(os.path.join(ROOT, 'docs', 'e2e', 'GAP_REGISTER.json'), 'w',
                      encoding='utf-8'), ensure_ascii=False, indent=1)

    print('缺口总账：%d 条（P0 %d / P1 %d / P2 %d）' % (
        len(rows), cnt.get('P0', 0), cnt.get('P1', 0), cnt.get('P2', 0)))
    for r in rows:
        print('  %-3s %-8s %-30s %s' % (r['prio'], r['id'], r['name'][:30], r['depth']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
