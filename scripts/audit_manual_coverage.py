#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""说明书覆盖度审计：页面覆盖 / 端点覆盖 / 内部数字自洽。

只做可机械判定的事：
  A. 路由表里的每个 name 是否在文档中出现
  B. 每个 path×method 有多少出现在文档中（附录 B 自称"代表端点"，要量化到底多少）
  C. 文档**自己声明**的数字（页数分组、端点总数）与实际比对
     —— 自述值从说明书解析，不硬编码（硬编码守不住文档漂移）
"""
import io
import os
import re
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, 'docs', 'e2e', 'SITE_ROLE_OPERATION_MANUAL.md')
ROUTER = os.path.join(ROOT, 'frontend', 'src', 'router', 'index.js')
MATRIX = os.path.join(ROOT, 'docs', 'e2e', 'ROLE_CAPABILITY_MATRIX.json')

# 页面分组自述：「| **不同 URL 的页面** | **53** | 23 公开 + 10 客户 + 20 内部；… |」
_RE_PAGES = re.compile(
    r'不同 URL 的页面\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|\s*(\d+)\s*公开\s*\+\s*(\d+)\s*客户\s*\+\s*(\d+)\s*内部')
# 端点总数自述：「N 个 path×method」
_RE_EP = re.compile(r'(\d+)\s*个\s*path×method')


def _read_claimed_pages():
    try:
        txt = io.open(DOC, encoding='utf-8').read()
    except OSError:
        return None
    m = _RE_PAGES.search(txt)
    if not m:
        return None
    return {'total': int(m.group(1)), 'public': int(m.group(2)),
            'customer': int(m.group(3)), 'internal': int(m.group(4))}


def _read_claimed_endpoints():
    try:
        txt = io.open(DOC, encoding='utf-8').read()
    except OSError:
        return None
    hits = [int(x) for x in _RE_EP.findall(txt)]
    if not hits:
        return None
    # 多处声明应完全一致；取出现最多的那个（容忍正文里偶发的其他数字）
    return max(set(hits), key=hits.count)


def main():
    doc = io.open(DOC, encoding='utf-8').read()
    router = io.open(ROUTER, encoding='utf-8').read()

    # ---------- A. 页面覆盖 ----------
    names = re.findall(r"name:\s*'([^']+)'", router)
    paths = re.findall(r"path:\s*'([^']*)'", router)
    uniq_names = list(dict.fromkeys(names))
    print('=== A. 路由覆盖 ===')
    print(f'路由 name 声明 {len(names)} 条 / 唯一 {len(uniq_names)} 条；path 声明 {len(paths)} 条')
    miss = [n for n in uniq_names if n not in doc]
    print(f'文档未提及的 name：{len(miss)}')
    for n in miss:
        print('   -', n)

    # 反向：文档里提到但路由表没有的 name（说明写错了）
    docname = set(re.findall(r"\b(Home|ProductIndex|ProductDetail|Search|Cart|Checkout|Settings|Login|Register|Workspace\w*|Po\w+Desk\w*|Admin\w+)\b", doc))
    bogus = sorted(n for n in docname if n not in uniq_names and not n.endswith('Desk') and n not in ('Home', 'Search', 'Cart', 'Checkout', 'Settings', 'Login', 'Register'))
    if bogus:
        print('文档中出现但不在路由表 name 里的标识（需人工确认是否张冠李戴）：', bogus)

    # ---------- B. 端点覆盖 ----------
    print('\n=== B. 端点覆盖（附录 B 自称"代表端点"）===')
    data = json.load(io.open(MATRIX, encoding='utf-8'))
    rows = data['detail']['staff']
    # 归一化路径：去掉 /api/v1 前缀与正则参数
    def norm(p):
        u = p
        if u.startswith('/api/v1'):
            u = u[len('/api/v1'):]
        u = re.sub(r'\(\?P<[^>]+>\[[^\]]*\][^)]*\)', '{id}', u)
        u = re.sub(r'<[^>]+>', '{id}', u)
        u = u.replace('^', '').replace('$', '')
        if len(u) > 1 and u.endswith('/'):
            u = u[:-1]
        return u

    # 只看"真端点"：排除格式后缀变体（含 \. 或 {id}. 的）
    real = {}
    for r in rows:
        p = r['path']
        if '\\.' in p or re.search(r'\{id\}\.', p):
            continue
        real.setdefault(norm(p), set()).add(r['method'])

    total = sum(len(v) for v in real.values())
    hit_paths = [p for p in real if p in doc]
    hit_ep = 0
    for p, ms in real.items():
        if p in doc:
            hit_ep += len(ms)
    print(f'去格式变体后端点：{len(real)} 条路径 / {total} 个 method')
    print(f'文档中出现的路径：{len(hit_paths)} 条 ⇒ 覆盖 method 约 {hit_ep}/{total} = {hit_ep/total*100:.1f}%')
    notin = sorted(set(real) - set(hit_paths))
    print(f'未出现的路径：{len(notin)} 条')
    for p in notin[:40]:
        print('   ', ','.join(sorted(real[p])), p)
    if len(notin) > 40:
        print(f'   …另有 {len(notin)-40} 条')

    # ---------- C. 数字自洽 ----------
    print('\n=== C. 文档自述数字 vs 实际 ===')
    # ★ 自述数字一律**从说明书解析**，不硬编码。
    #   硬编码的期望值（此前写死 52 页 / 335 端点）守不住文档漂移：
    #   文档改了脚本还在比旧数，输出的"不一致"其实是脚本自己在说谎。
    claimed = _read_claimed_pages()
    if claimed:
        print('文档声明：%d 实际页面 / %d 公开 / %d 客户 / %d 内部'
              % (claimed['total'], claimed['public'], claimed['customer'], claimed['internal']))
    else:
        print('!! 说明书里找不到"不同 URL 的页面"行，跳过页面自述核对')
    ws_children = re.findall(r"path:\s*'([^']*)',\s*name:", router[router.index("path: '/workspace'"):])
    print(f'实测 /workspace 子路由块：{len([c for c in ws_children if c != "/workspace"])}（含空 path 的 Dashboard）')

    # 端点总数与矩阵一致性
    n_ep = len(data['detail']['staff'])
    claimed_ep = _read_claimed_endpoints()
    if claimed_ep is None:
        print(f'矩阵中 staff 端点行数：{n_ep}（说明书里找不到端点总数自述）')
    else:
        print(f'矩阵中 staff 端点行数：{n_ep}（文档称 {claimed_ep}）'
              + ('  ✅ 一致' if claimed_ep == n_ep else '  ❌ 不一致'))
    print(f'矩阵 identities：{list(data["identities"].keys())}')
    for k, v in data['identities'].items():
        print(f'   {k:<12} 读 {v["read_ok"]}/{v["read_total"]}  写 {v["write_ok"]}/{v["write_total"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
