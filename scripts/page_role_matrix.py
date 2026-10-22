#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""页面 × 角色 判定 —— 把「页面调哪些 API」和「角色能过哪些 API」叉乘（2026-10-22）

## 它回答的问题
"某个角色打开某个页面，页面上哪些请求会被 403" —— 这是"页面能进、按钮没反应"的**可量化定义**。

## 输入
- `docs/e2e/PAGE_API_MAP.json` —— 静态提取的 页面 → METHOD+URL（不含权限判断）
- `docs/e2e/ROLE_CAPABILITY_MATRIX.json` —— `role_capability_probe.py` 产出的 身份 × 端点 判定

## 判定口径（必须理解，否则会误读）
- **首个读请求被拒 = 页面直接白给**（`on_mount` 的 GET 403）⇒ 记 `DEAD`
- **读通过、写被拒 = 页面能看不能改** ⇒ 记 `READONLY`（这才是"按钮点了没反应"）
- 全通过 ⇒ `OK`
- URL 在探针里找不到 ⇒ `UNMATCHED`（**不猜**，如实报，需人工补）

## 用法
  python scripts/page_role_matrix.py
  python scripts/page_role_matrix.py --role procurement
  python scripts/page_role_matrix.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PAGE_MAP = os.path.join(ROOT, 'docs', 'e2e', 'PAGE_API_MAP.json')
ROLE_MATRIX = os.path.join(ROOT, 'docs', 'e2e', 'ROLE_CAPABILITY_MATRIX.json')

WRITE = {'POST', 'PUT', 'PATCH', 'DELETE'}
_PARAM_RE = re.compile(r'(<[^>]+>|\$\{[^}]*\})')
# ViewSet 路由在 resolver 里是正则形态：`^orders/(?P<pk>[^/.]+)/$`
_REGEX_PARAM_RE = re.compile(r'\(\?P<[^>]+>\[[^\]]*\][^)]*\)')


def normalize(url: str) -> str:
    """抹平三种写法：Django `<int:pk>`、resolver 正则 `(?P<pk>[^/.]+)`、JS `${id}`。

    ★ 不做这一步会把同一端点算成两个（`/orders/${id}/` 找不到 `/orders/(?P<pk>[^/.]+)/`），
      进而把 21 个页面里的 10 个误判为 UNMATCHED —— 静默漏判比报错更危险。
    """
    u = url.strip()
    if u.startswith('/api/v1'):
        u = u[len('/api/v1'):]
    u = u.replace('^', '')
    # ★ 顺序有坑：必须**先**替换 `${id}` 再删 `$`。
    #   反过来会把 `${id}` 剪成 `{id}`，于是 `/orders/${id}/` 与 `/orders/(?P<pk>[^/.]+)/`
    #   归一化后不相等 ⇒ 静默 UNMATCHED（本脚本第一版就踩了，10 个页面被误判）。
    u = _REGEX_PARAM_RE.sub('*', u)
    u = _PARAM_RE.sub('*', u)
    u = u.replace('$', '')
    u = u.replace('/?', '/')
    if len(u) > 1 and u.endswith('/'):
        u = u[:-1]
    if not u.startswith('/'):
        u = '/' + u
    return u


def build_index(role_data):
    """{(norm_path, method): row}"""
    idx = {}
    for row in role_data:
        idx[(normalize(row['path']), row['method'])] = row
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--role', default=None)
    ap.add_argument('--json', default=None)
    args = ap.parse_args()

    with open(PAGE_MAP, encoding='utf-8') as f:
        pm = json.load(f)
    with open(ROLE_MATRIX, encoding='utf-8') as f:
        rm = json.load(f)

    identities = list(rm['identities'].keys())
    if args.role:
        identities = [args.role]

    idx_by_role = {name: build_index(rm['detail'][name]) for name in rm['detail']}
    base = pm.get('base_url', '/api/v1')

    out = []
    for page in pm['pages']:
        entry = {'file': page['file'], 'guard': page['guard'], 'roles': {}, 'unmatched': []}
        for name in identities:
            idx = idx_by_role[name]
            mount_total = mount_deny = 0
            write_total = write_deny = 0
            denies = []
            for c in page['calls']:
                key = (normalize(base + c['url']), c['method'])
                row = idx.get(key)
                if row is None:
                    if key not in [(normalize(base + c2['url']), c2['method'])
                                   for c2 in page['calls']]:
                        pass
                    entry['unmatched'].append(f"{c['method']} {c['url']}")
                    continue
                is_write = c['method'] in WRITE
                if is_write:
                    write_total += 1
                    if row['allowed'] is not True:
                        write_deny += 1
                        denies.append(f"{c['method']} {c['url']} <- {row['blocker']}")
                elif c['on_mount']:
                    mount_total += 1
                    if row['allowed'] is not True:
                        mount_deny += 1
                        denies.append(f"{c['method']} {c['url']} [进入即发] <- {row['blocker']}")
            if mount_total and mount_deny == mount_total:
                verdict = 'DEAD'          # 进页面所有首屏读全 403
            elif mount_deny or write_deny:
                verdict = 'READONLY'      # 能进、但有红
            else:
                verdict = 'OK'
            if not mount_total and not write_total:
                verdict = 'N/A'
            entry['roles'][name] = {
                'verdict': verdict,
                'mount': f'{mount_total - mount_deny}/{mount_total}',
                'write': f'{write_total - write_deny}/{write_total}',
                'denies': denies,
            }
        entry['unmatched'] = sorted(set(entry['unmatched']))
        out.append(entry)

    # 打印
    for page in out:
        print(f"\n{page['file']}   [{page['guard']}]")
        for name in identities:
            r = page['roles'][name]
            print(f"   {name:<12} {r['verdict']:<9} 首屏读 {r['mount']:<7} 写 {r['write']}")
        if page['unmatched']:
            print(f"   !! 探针里找不到: {', '.join(page['unmatched'])}")

    # 汇总
    print('\n=== 汇总（每个身份：OK / READONLY / DEAD / N/A 的页面数）===')
    for name in identities:
        tally = {}
        for page in out:
            v = page['roles'][name]['verdict']
            tally[v] = tally.get(v, 0) + 1
        s = '  '.join(f'{k}={v}' for k, v in sorted(tally.items()))
        print(f"  {name:<12} {s}")

    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump({'pages': out}, f, ensure_ascii=False, indent=2)
        print(f'\n已写入 {args.json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
