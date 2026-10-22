#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""对象级权限 / queryset 收窄 —— 真实 HTTP 实测（补充上一轮的最大空白）。

上一轮的局限：探测器用假 id，`get_object()` 先 404，`has_object_permission` 根本没执行。
本脚本用**真实对象**（scripts/probe_seed_cross_org.py 造）逐条打，覆盖：

  A. 客户只能看自己的订单 / 地址（queryset 收窄）
  B. 同机构第二人能改第一人的地址（AddressPermission 文档声称"机构内协作"）
  C. 跨机构读/写/删别人的地址（对象级隔离）
  D. 跨机构读别人的订单（订单无对象级权限，靠 queryset）
  E. 跨用户对别人的订单执行动作（confirm-quote）
  F. staff / procurement 跨机构可见性（两者口径是否一致）

判定：403/404 都算"被挡"，但必须区分 —— 404 说明"查不到"（queryset 收窄），
      403 说明"查得到但不许"（对象级权限）。两者对用户的可观测行为不同。

用法（后端需指到 DB 副本）：
  env -u HTTP_PROXY ... python scripts/http_object_probe.py
"""
from __future__ import annotations

import json
import sys
import os
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import http_role_probe as P  # 复用 login / _OPENER / BASE

ORDER_A, ORDER_B = 1257, 1258
ADDR_A, ADDR_B = 6, 7
PW = P.PASSWORD


def call(method, path, token=None, body=None):
    headers = {'Host': '127.0.0.1:8011'}
    if token:
        headers['Authorization'] = 'Token ' + token
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(P.BASE + path, data=data, method=method, headers=headers)
    try:
        with P._OPENER.open(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:                                          # noqa: BLE001
        return 0, str(e).encode()


def brief(body, n=110):
    t = body.decode('utf-8', 'replace').replace('\n', ' ')
    return t[:n]


def main():
    tokens = {}
    for name in ('probe_ouser_a', 'probe_ouser_a2', 'probe_ouser_b', 'probe_staff', 'probe_procure'):
        tok, st, _ = P.login(name)
        if not tok:
            raise SystemExit('登录失败 %s (HTTP %s)' % (name, st))
        tokens[name] = tok

    rows = []

    def rec(section, who, method, path, expect, note=''):
        st, body = call(method, path, tokens[who])
        rows.append({'section': section, 'who': who, 'method': method, 'path': path,
                     'status': st, 'expect': expect, 'note': note, 'body': brief(body)})
        return st, body

    # ---------- A. 自己的对象 ----------
    rec('A 自己的订单', 'probe_ouser_a', 'GET', '/api/v1/orders/%d/' % ORDER_A, '200')
    rec('A 自己的地址', 'probe_ouser_a', 'GET', '/api/v1/addresses/%d/' % ADDR_A, '200')
    rec('A 订单列表', 'probe_ouser_a', 'GET', '/api/v1/orders/', '200')
    rec('A 地址列表', 'probe_ouser_a', 'GET', '/api/v1/addresses/', '200')

    # ---------- C. 跨机构读别人的地址 ----------
    rec('C 跨机构读地址', 'probe_ouser_a', 'GET', '/api/v1/addresses/%d/' % ADDR_B, '403 或 404')
    # ---------- C2. 跨机构改 / 删别人的地址（对象级写） ----------
    # 带 body 的跨机构写（对象级权限只有在真改时才会触发）
    st, body = call('PUT', '/api/v1/addresses/%d/' % ADDR_B, tokens['probe_ouser_a'],
                    {'attention': 'HIJACKED-BY-A', 'city': 'Hacked'})
    rows.append({'section': 'C 跨机构改地址(带 body)', 'who': 'probe_ouser_a', 'method': 'PUT',
                 'path': '/api/v1/addresses/%d/' % ADDR_B, 'status': st,
                 'expect': '403 或 404', 'note': 'body={attention:HIJACKED-BY-A}',
                 'body': brief(body)})

    # ---------- B. 同机构第二人改第一人的地址 ----------
    st, body = call('PUT', '/api/v1/addresses/%d/' % ADDR_A, tokens['probe_ouser_a2'],
                    {'attention': 'EDITED-BY-A2', 'city': 'City-A'})
    rows.append({'section': 'B 同机构第二人改地址', 'who': 'probe_ouser_a2', 'method': 'PUT',
                 'path': '/api/v1/addresses/%d/' % ADDR_A, 'status': st,
                 'expect': '待测（文档称机构内可互改）', 'note': 'body={attention:EDITED-BY-A2}',
                 'body': brief(body)})

    # ---------- D. 跨机构读订单 ----------
    rec('D 跨机构读订单', 'probe_ouser_a', 'GET', '/api/v1/orders/%d/' % ORDER_B, '403 或 404')

    # ---------- E. 跨用户对别人订单执行动作 ----------
    rec('E 对别人订单 accept 报价', 'probe_ouser_a', 'POST',
        '/api/v1/orders/%d/confirm-quote/' % ORDER_B, '403 或 404', 'body={action:accept}')
    st, body = call('POST', '/api/v1/orders/%d/confirm-quote/' % ORDER_B,
                    tokens['probe_ouser_a'], {'action': 'accept'})
    rows.append({'section': 'E 对别人订单 accept(带 body)', 'who': 'probe_ouser_a', 'method': 'POST',
                 'path': '/api/v1/orders/%d/confirm-quote/' % ORDER_B, 'status': st,
                 'expect': '403 或 404', 'note': 'body={action:accept}', 'body': brief(body)})

    # ---------- F. staff / procurement 跨机构可见 ----------
    rec('F staff 读 B 订单', 'probe_staff', 'GET', '/api/v1/orders/%d/' % ORDER_B, '200（全库可见）')
    rec('F procurement 读 B 订单', 'probe_procure', 'GET', '/api/v1/orders/%d/' % ORDER_B,
        '200（跨机构可见）')
    rec('F staff 读 B 地址', 'probe_staff', 'GET', '/api/v1/addresses/%d/' % ADDR_B,
        '待测（无机构时 .none()）')
    rec('F procurement 读 B 地址', 'probe_procure', 'GET', '/api/v1/addresses/%d/' % ADDR_B,
        '待测')

    # ---------- 最后才删：跨机构删别人地址 ----------
    st, body = call('DELETE', '/api/v1/addresses/%d/' % ADDR_B, tokens['probe_ouser_a'])
    rows.append({'section': 'C 跨机构删地址', 'who': 'probe_ouser_a', 'method': 'DELETE',
                 'path': '/api/v1/addresses/%d/' % ADDR_B, 'status': st,
                 'expect': '403 或 404', 'note': '', 'body': brief(body)})

    # 删除后再确认对象是否还在（真删了才说明隔离失效）
    st2, b2 = call('GET', '/api/v1/addresses/%d/' % ADDR_B, tokens['probe_ouser_b'])
    rows.append({'section': 'C 事后校验 B 自己的地址', 'who': 'probe_ouser_b', 'method': 'GET',
                 'path': '/api/v1/addresses/%d/' % ADDR_B, 'status': st2,
                 'expect': '200 = 未被删掉（隔离生效）', 'note': '若 404 说明被跨机构删除',
                 'body': brief(b2)})

    # ---------- 列表里是否混入他人数据 ----------
    for who, tag in (('probe_ouser_a', 'A'), ('probe_ouser_b', 'B')):
        st, body = call('GET', '/api/v1/orders/?page_size=200', tokens[who])
        txt = body.decode('utf-8', 'replace')
        rows.append({'section': 'G 订单列表是否含他机构单', 'who': who, 'method': 'GET',
                     'path': '/api/v1/orders/?page_size=200', 'status': st,
                     'expect': '只含自己的',
                     'note': 'A 单=%s B 单=%s' % ('PROBE-ORD-A-0001' in txt, 'PROBE-ORD-B-0001' in txt),
                     'body': '含A=%s 含B=%s' % ('PROBE-ORD-A-0001' in txt, 'PROBE-ORD-B-0001' in txt)})
        st, body = call('GET', '/api/v1/addresses/?page_size=200', tokens[who])
        txt = body.decode('utf-8', 'replace')
        rows.append({'section': 'G 地址列表是否含他机构地址', 'who': who, 'method': 'GET',
                     'path': '/api/v1/addresses/?page_size=200', 'status': st,
                     'expect': '只含本机构',
                     'note': 'Attention A=%s Attention B=%s' % ('Attention A' in txt, 'Attention B' in txt),
                     'body': '含A=%s 含B=%s' % ('Attention A' in txt, 'Attention B' in txt)})

    print('%-26s %-18s %-6s %-46s %-4s %s' % ('场景', '身份', '方法', '路径', '状态', '期望'))
    print('-' * 150)
    for r in rows:
        print('%-26s %-18s %-6s %-46s %-4s %s' % (
            r['section'][:26], r['who'], r['method'], r['path'][:46], r['status'], r['expect'][:26]))

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'docs', 'e2e', 'HTTP_OBJECT_PROBE.json')
    json.dump({'generated_at': P.time.strftime('%Y-%m-%d %H:%M:%S'),
               'fixture': {'order_a': ORDER_A, 'order_b': ORDER_B,
                           'addr_a': ADDR_A, 'addr_b': ADDR_B},
               'rows': rows}, open(out, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('\n已写入 %s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
