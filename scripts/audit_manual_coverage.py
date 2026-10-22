#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""说明书覆盖度审计：页面覆盖 / 端点覆盖 / 内部数字自洽。

只做可机械判定的事：
  A. 路由表里的每个 name 是否在文档中出现
  B. 335 个 path×method 里有多少出现在文档中（附录 B 自称"代表端点"，要量化到底多少）
  C. 文档自己声明的数字（52 页 / 23 公开 / 19 内部 / 10 客户 / 335 端点 / 8 身份）与实际比对
"""
import io
import os
import re
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, 'docs', 'e2e', 'SITE_ROLE_OPERATION_MANUAL.md')
ROUTER = os.path.join(ROOT, 'frontend', 'src', 'router', 'index.js')
MATRIX = os.path.join(ROOT, 'docs', 'e2e', 'ROLE_CAPABILITY_MATRIX.json')


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
    # 页面分组
    adm = len(re.findall(r'requiresAdmin', 'x'))  # 占位
    print('文档声明：52 实际页面 / 23 公开 / 10 客户 / 19 内部（8 ops + /workspace + 10 子页）')
    ws_children = re.findall(r"path:\s*'([^']*)',\s*name:", router[router.index("path: '/workspace'"):])
    print(f'实测 /workspace 子路由块：{len([c for c in ws_children if c != "/workspace"])}（含空 path 的 Dashboard）')

    # 端点总数与矩阵一致性
    n_ep = len(data['detail']['staff'])
    print(f'矩阵中 staff 端点行数：{n_ep}（文档称 335）')
    print(f'矩阵 identities：{list(data["identities"].keys())}')
    for k, v in data['identities'].items():
        print(f'   {k:<12} 读 {v["read_ok"]}/{v["read_total"]}  写 {v["write_ok"]}/{v["write_total"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
