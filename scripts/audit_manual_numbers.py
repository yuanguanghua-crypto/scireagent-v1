#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""核对说明书自述的页面数字（52 / 23 公开 / 10 客户 / 19 内部）是否与路由表一致。

判定规则（与 router/index.js 的 beforeEach 同构）：
  - 路由记录自身 meta.requiresAdmin  ⇒ 内部台
  - /workspace 的子路由（自身无 meta）⇒ 随父级算内部台
  - meta.requiresAuth 且非内部        ⇒ 客户门户
  - 其余                              ⇒ 公开
  - 单独统计 404 兜底
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROUTER = os.path.join(ROOT, 'frontend', 'src', 'router', 'index.js')


def main():
    src = io.open(ROUTER, encoding='utf-8').read()
    # 按出现顺序切出每个路由记录：(path, name, meta 文本)
    recs = []
    for m in re.finditer(r"path:\s*'([^']*)'", src):
        tail = src[m.end(): m.end() + 500]
        nm = re.search(r"name:\s*'([^']+)'", tail)
        mt = re.search(r"meta:\s*\{([^{}]*)\}", tail)
        recs.append({
            'path': m.group(1),
            'name': nm.group(1) if nm else None,
            'meta': mt.group(1) if mt else '',
            'pos': m.start(),
        })

    ws_start = src.index("path: '/workspace'")
    ws_end = src.index("path: '/:pathMatch(.*)*'")

    internal, customer, public, notfound = [], [], [], []
    seen_path = set()
    for r in recs:
        if not r['name']:
            continue
        # /workspace 父级记录只是壳，真正渲染的是它 path='' 的子路由 Dashboard
        # ⇒ 壳不计为独立页面，否则会多算 1（19 → 20）
        if r['path'] == '/workspace' and r['name'] == 'Workspace':
            continue
        if 'pathMatch' in r['path']:
            notfound.append(r); continue
        in_ws_block = ws_start <= r['pos'] < ws_end
        if 'requiresAdmin' in r['meta'] or in_ws_block:
            internal.append(r)
        elif 'requiresAuth' in r['meta']:
            customer.append(r)
        else:
            public.append(r)

    print(f"内部台（requiresAdmin + /workspace 子路由）：{len(internal)}")
    for r in internal:
        print(f"   {r['name']:<28} {r['path']}")
    print(f"\n客户门户（仅 requiresAuth）：{len(customer)}")
    for r in customer:
        print(f"   {r['name']:<28} {r['path']}")
    print(f"\n公开：{len(public)}")
    for r in public:
        print(f"   {r['name']:<28} {r['path']}")
    print(f"\n404 兜底：{len(notfound)}")
    pages = len(internal) + len(customer) + len(public)
    print(f"\n页面合计（不含 404）= {pages}；含 404 = {pages + len(notfound)}")
    print(f"说明书自述：52 实际页面（23 公开 / 10 客户 / 19 内部）+ 1 个 404")
    print(f"实测：{len(public)} 公开 / {len(customer)} 客户 / {len(internal)} 内部 = {pages}"
          f"  {'✅ 一致' if pages == 52 else '❌ 与自述不符'}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
