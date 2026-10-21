#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""L5 前后端契约检查 —— 基于 **OpenAPI schema** 的字段集快照（2026-10-21）

## 为什么需要它
本轮修的两个真缺陷是**同一类**：前端读了一个后端不返回的字段，判定恒真/恒假，页面上看不出来：
  · D3：`PoInvoicingDesk` 读 `o.invoice`，列表序列化器不含该字段 ⇒ 开票后订单从队列消失
  · D6：`PoOrderDetail` 读 `it.is_ruo`，同样不存在 ⇒ 每单都显示 RUO 声明
这类问题**没有任何现有闸门能拦**：后端单测只测自己的形状，E2E 走真实数据也不会报错。

## 为什么用 schema，而不是"抓真实响应"
第一版是"抓响应存快照"，实测**天然脆弱**：字段集依赖**数据形态**
（购物车空 ⇒ `items` 空数组 ⇒ 元素字段全"消失"；不同产品 ⇒ 可选字段不同）。
在 CI 的最小种子下大面积假 FAIL。改用 DRF schema 后：**不依赖数据、不需要起服务、可在 CI 跑**。

## 判据
对每个受检端点的 200 响应（展开 `$ref` 后），提取**实体字段集**（剥掉分页/信封包装），
与 `docs/e2e/API_CONTRACT_SCHEMA.json` 比对：
- **少了字段** / **类型变了** ⇒ FAIL（前端很可能正在用它）
- **多了字段** ⇒ WARN（正常演进，需 review）

⚠️ 局限（必须知道）
1. 它不知道**前端到底用了哪些字段** ⇒ 后端删了"没人用"的字段也会 FAIL。**故意偏保守**：
   宁可让人确认一次，也不要静默放行（D3/D6 就是静默放行的结果）。
2. 只保证**字段存在与类型**，不保证运行时值正确（`SerializerMethodField` 可能有值语义 bug）。
3. 只覆盖 `ENDPOINTS` 列出的端点；新增端点请手工加进来。

## 用法
  python scripts/check_api_contract.py             # 比对（CI / 提交前）
  python scripts/check_api_contract.py --update    # 确认变更合理后更新快照（记得看 diff）
  python scripts/check_api_contract.py --verbose   # 打印每个端点抽到的字段数
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO, 'backend')
SNAPSHOT = os.path.join(REPO, 'docs', 'e2e', 'API_CONTRACT_SCHEMA.json')

# 受检端点：(OpenAPI path, 展示名)
ENDPOINTS = [
    ('/api/v1/orders/', 'orders.list'),
    ('/api/v1/orders/{id}/', 'orders.detail'),
    ('/api/v1/products/', 'products.list'),
    ('/api/v1/products/{id}/', 'products.detail'),
    ('/api/v1/admin/orders/', 'admin_orders.list'),
    ('/api/v1/basket', 'basket.detail'),
    ('/api/v1/auth/me', 'auth.me'),
]

# 分页/信封包装键：不属于"实体字段"，比对时剥掉（否则会被 DRF 默认形状干扰）
WRAPPER_KEYS = {'results', 'count', 'next', 'previous', 'success', 'data', 'meta'}
MAX_DEPTH = 6


def gen_schema() -> dict:
    """用项目自己的 drf-spectacular 生成 schema（不依赖 DB 数据，只要 migrate 过）。"""
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    py = os.path.join(BACKEND, 'venv', 'Scripts', 'python.exe')
    if not os.path.isfile(py):
        py = sys.executable
    env = dict(os.environ)
    env.setdefault('DB_ENGINE', 'sqlite')
    env.setdefault('PYTHONDONTWRITEBYTECODE', '1')
    r = subprocess.run(
        [py, '-B', 'manage.py', 'spectacular', '--format', 'openapi-json', '--file', path],
        cwd=BACKEND, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace',
    )
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        print('[FAIL] schema 生成失败：')
        print((r.stdout or '')[-800:])
        print((r.stderr or '')[-800:])
        sys.exit(2)
    try:
        return json.loads(io.open(path, encoding='utf-8').read())
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _deref(node, comps, depth=0):
    if not isinstance(node, dict) or depth > MAX_DEPTH:
        return node
    ref = node.get('$ref')
    if ref:
        name = ref.split('/')[-1]
        return _deref(comps.get(name, {}), comps, depth + 1)
    # oneOf / allOf / anyOf：取第一支（我们的响应基本是单一 $ref）
    for k in ('allOf', 'oneOf', 'anyOf'):
        if isinstance(node.get(k), list) and node[k]:
            return _deref(node[k][0], comps, depth + 1)
    return node


def _type_of(node) -> str:
    if not isinstance(node, dict):
        return 'unknown'
    t = node.get('type')
    if not t and ('properties' in node or '$ref' in node):
        t = 'object'
    fmt = node.get('format')
    base = f'{t}{"(" + fmt + ")" if fmt else ""}' if t else 'unknown'
    return base + ('|null' if node.get('nullable') else '')


def _flatten(node, comps, prefix='', depth=0, out=None) -> dict:
    """把 (已 deref 的) schema 压平成 {字段路径: 类型}。"""
    out = {} if out is None else out
    if depth > MAX_DEPTH:
        return out
    node = _deref(node, comps)
    if not isinstance(node, dict):
        return out
    if node.get('type') == 'array' or 'items' in node:
        items = _deref(node.get('items', {}), comps)
        _flatten(items, comps, f'{prefix}[]' if prefix else '[]', depth + 1, out)
        return out
    props = node.get('properties') or {}
    if not props:
        return out
    for k, v in sorted(props.items()):
        vv = _deref(v, comps)
        path = f'{prefix}.{k}' if prefix else k
        if k in WRAPPER_KEYS:
            # 剥掉分页/信封包装：`results` / `data` 当透明容器展开到同一层
            _flatten(vv, comps, prefix, depth + 1, out)
            continue
        if isinstance(vv, dict) and (vv.get('type') == 'array' or 'items' in vv):
            _flatten(vv, comps, path, depth + 1, out)
        elif isinstance(vv, dict) and (vv.get('properties') or '$ref' in vv or 'allOf' in vv):
            _flatten(vv, comps, path, depth + 1, out)
        else:
            out[path] = _type_of(vv)
    return out


def extract(schema: dict) -> dict:
    comps = schema.get('components', {}).get('schemas', {})
    paths = schema.get('paths', {})
    got = {}
    for path, label in ENDPOINTS:
        op = paths.get(path) or {}
        resp = (op.get('get') or {}).get('responses', {}).get('200') or {}
        content = (resp.get('content') or {}).get('application/json') or {}
        node = content.get('schema')
        if not node:
            print(f'[SKIP] {label}: schema 里没有 200 JSON 响应')
            continue
        flat = _flatten(node, comps)
        if flat:
            got[label] = flat
        else:
            print(f'[SKIP] {label}: 展开后为空（自定义 renderer 可能导致 schema 缺字段）')
    return got


def diff(old: dict, new: dict):
    missing = sorted(set(old) - set(new))
    added = sorted(set(new) - set(old))
    changed = sorted(k for k in set(old) & set(new) if old[k] != new[k])
    return missing, added, changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--update', action='store_true', help='更新快照（确认变更合理后再用）')
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    schema = gen_schema()
    current = extract(schema)
    if not current:
        print('[FAIL] 一个端点都没抽到字段 —— 检查 drf-spectacular 是否正常')
        return 2

    if args.verbose:
        for k, v in sorted(current.items()):
            print(f'  {k}: {len(v)} 个字段路径')

    if args.update or not os.path.isfile(SNAPSHOT):
        os.makedirs(os.path.dirname(SNAPSHOT), exist_ok=True)
        payload = {
            '_comment': 'L5 契约快照（来自 OpenAPI schema，已剥掉分页/信封包装）。'
                        '变更后请 review diff 再提交；更新用 scripts/check_api_contract.py --update',
            'endpoints': current,
        }
        io.open(SNAPSHOT, 'w', encoding='utf-8', newline='').write(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        print(f'[OK] 已写入快照：{os.path.relpath(SNAPSHOT, REPO)}（{len(current)} 个端点）')
        return 0

    snap = json.loads(io.open(SNAPSHOT, encoding='utf-8').read())
    baseline = snap.get('endpoints') or {}

    fail = 0
    for label in sorted(baseline):
        if label not in current:
            print(f'[FAIL] {label}: 本次抽不到响应 schema（端点被删？路径改名？）')
            fail += 1
            continue
        missing, added, changed = diff(baseline[label], current[label])
        if not (missing or added or changed):
            print(f'[OK]   {label}（{len(current[label])} 个字段路径一致）')
            continue
        if missing or changed:
            fail += 1
            print(f'[FAIL] {label}')
            for k in missing:
                print(f'         - 少了字段 {k}（★ 前端可能正在用它）')
            for k in changed:
                print(f'         ~ 类型变了 {k}: {baseline[label][k]} → {current[label][k]}')
        else:
            print(f'[WARN] {label}：只有新增字段（正常演进，请确认）')
        for k in added:
            print(f'         + 新增 {k}: {current[label][k]}')

    if fail:
        print(f'\n契约检查失败：{fail} 个端点有不兼容变更。'
              f'确认合理后跑 `python scripts/check_api_contract.py --update` 更新快照（并 review diff）。')
        return 1
    print('\n契约检查通过。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
