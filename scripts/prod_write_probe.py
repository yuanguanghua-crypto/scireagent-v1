#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""prod_write_probe.py — 生产「匿名写探针」（部署闸门用）

## 判据（按 2026-11-02 组织方定的停线）

| 响应 | 含义 | 处置 |
|---|---|---|
| **401 / 403** | 鉴权在落库前拦下 | ✅ 正常 |
| **404** | 鉴权可能已放行，但对象不存在 ⇒ **未写数据** | ⚠️ 正常但需记（见下方"404 的二义性"） |
| **200 / 201 / 204** | **真的写进去了** | 🛑 **立即停**，人工核对受影响行 |
| 400 / 405 / 415 / 5xx | 意外状态，按旧口径（`docs/CLAIMS.md`）视为**鉴权被放行** | 🛑 停，人工判 |

## ★ 设计取舍：只打"不存在的 id"，**不测 create**

`POST` 创建请求一旦被放行就是**真的造出一行数据**，与"绝不能真改数据"直接冲突 ——
所以本探针**只做 PATCH / DELETE 打到 `id=-1`**：
即使鉴权被完全放行，也只可能命中"对象不存在"，**不可能新增或修改任何行**。
代价：它测不到"create 端点是否匿名可写"。**这是有意的能力缺口**，用 `permission_audit`
的静态核对兜，不用生产写探针兜。

## ★ 404 的二义性（必须知道）

404 可能是"对象不存在"（说明鉴权放行），也可能是"**这条路由根本不存在**"（那这个探针什么都没测到）。
本脚本先对**同类集合端点**发 GET 做路由确认（`/api/v1/protocols/` 匿名应 401）
—— 集合端点 401 只证明前缀存在且被保护，**不能保证 detail 路由一定存在**，
所以出现 404 时仍须人工确认路由表，脚本会明确要求复核。

## 两层认证

nginx 用 `Authorization: Basic`，Django 用独立头 `X-Auth-Token`。
本探针**只带 Basic、不带 token** ⇒ 若能进到 Django，Django 应按未认证拒绝（401）。
这与 `scripts/prod_readonly_probe.py` 的头约定一致。

用法：
  # ① 完全匿名（只可能测到 nginx 这一层）
  python scripts/prod_write_probe.py
  # ② 带 nginx Basic（才能真正测到应用层）
  SC_BASIC_USER=... SC_BASIC_PASS=... python scripts/prod_write_probe.py

退出码：0 = 无写入迹象；1 = 🛑 出现写成功或意外状态；2 = 环境问题
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.getenv('SC_BASE', 'https://scireagent.com')
BU = os.getenv('SC_BASIC_USER', '')
BP = os.getenv('SC_BASIC_PASS', '')
UA = 'scireagent-write-probe/1.0'

# 目标：只打不存在的 id ⇒ 最坏结果 404，不可能改动任何行
TARGETS = [
    ('PATCH', '/api/v1/protocols/-1/', {'objective': 'probe-do-not-apply'}),
    ('DELETE', '/api/v1/protocols/-1/', None),
    ('PATCH', '/api/v1/methods/-1/', {'name': 'probe-do-not-apply'}),
    ('DELETE', '/api/v1/methods/-1/', None),
]

# 路由存在性旁证：集合端点匿名应 401/403（被保护）。404 说明前缀都不对。
ROUTE_CHECKS = ['/api/v1/protocols/', '/api/v1/methods/']

PASS_STATUS = {401, 403}
REVIEW_STATUS = {404}
STOP_STATUS = {200, 201, 204}


def _headers(extra=None):
    h = {'User-Agent': UA, 'Accept': 'application/json'}
    if BU and BP:
        h['Authorization'] = 'Basic ' + base64.b64encode(
            ('%s:%s' % (BU, BP)).encode()).decode()
    if extra:
        h.update(extra)
    return h


def call(method, path, body=None, timeout=20):
    data = None
    hdr = _headers()
    if body is not None:
        data = json.dumps(body).encode()
        hdr['Content-Type'] = 'application/json'
    elif method in ('POST', 'PATCH', 'PUT'):
        data = b'{}'
        hdr['Content-Type'] = 'application/json'
    req = urllib.request.Request(BASE + path, data=data, headers=hdr, method=method)
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, (r.read() or b'')[:200], int((time.time() - t) * 1000)
    except urllib.error.HTTPError as e:
        return e.code, (e.read() or b'')[:200], int((time.time() - t) * 1000)
    except Exception as e:  # 网络层
        return None, str(e).encode()[:200], int((time.time() - t) * 1000)


def main() -> int:
    mode = '带 nginx Basic Auth（可测应用层）' if (BU and BP) else '完全匿名（只测到 nginx）'
    print(f'目标 {BASE}｜模式：{mode}')
    if not (BU and BP):
        print('⚠️  未提供 SC_BASIC_USER/PASS ⇒ 401 只会来自 nginx，**测不到 Django 应用层**。'
              '要测应用层必须带 Basic。')

    print('\n— 路由存在性旁证（集合端点匿名应 401/403）—')
    route_ok = {}
    for p in ROUTE_CHECKS:
        st, _, ms = call('GET', p)
        route_ok[p] = st
        print(f'  GET {p:32s} → {st} ({ms}ms)')

    print('\n— 写探针（全部打 id=-1，不可能改到真实行）—')
    stop, review, passed = [], [], []
    for method, path, body in TARGETS:
        st, snippet, ms = call(method, path, body)
        if st in STOP_STATUS:
            verdict, bucket = '🛑 写成功 —— 立即停', stop
        elif st in PASS_STATUS:
            verdict, bucket = '✅ 拦下', passed
        elif st in REVIEW_STATUS:
            verdict, bucket = '⚠️ 404（鉴权可能放行 / 或路由不存在）', review
        else:
            verdict, bucket = '🛑 意外状态 —— 停', stop
        bucket.append((method, path, st))
        print(f'  {method:6s} {path:28s} → {st} ({ms}ms)  {verdict}')

    print('\n' + '=' * 64)
    if stop:
        print('🛑 停线触发：以下请求出现写成功或意外状态，**立即停止部署**，先人工核对受影响行：')
        for m, p, s in stop:
            print(f'     {m} {p} → {s}')
        return 1
    if review:
        print('⚠️ 有 404 —— 按判据算"未写数据"，但**必须核实该 detail 路由确实存在**，'
              '否则这个探针等于没测：')
        for m, p, s in review:
            print(f'     {m} {p} → {s}')
        print('   （复核方式：确认路由表里有该 detail 路由；若路由不存在，404 无意义）')
    print(f'✅ 无写入迹象：拦下 {len(passed)} 条 / 待复核 {len(review)} 条 / 写成功 0 条')
    return 0


if __name__ == '__main__':
    sys.exit(main())
