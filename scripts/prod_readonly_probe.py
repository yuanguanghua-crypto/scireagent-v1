#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生产环境 · 登录态只读探测（补掉"生产未测"这一项）。

## 两层认证怎么共存（读码 + 实测确认）
nginx 用 `Authorization: Basic`（`deploy/nginx.conf:84-85`），
应用层 token 走**独立头** `X-Auth-Token`（`frontend/src/utils/http.js:20-26` 注释写明"避免与
nginx Basic 弹窗冲突"；后端 `apps/accounts/authentication.py:20` 读 `HTTP_X_AUTH_TOKEN`，
且它是 `DEFAULT_AUTHENTICATION_CLASSES` 的第一项）。
⇒ 两个头**同时**发即可。

## 严格边界
- 业务请求**只发 GET**
- 唯一写操作：结束时 `POST /auth/logout` 回收自己刚拿到的 token
- 凭据只从环境变量读，不写进仓库、不落盘

用法：
  SC_BASIC_USER=... SC_BASIC_PASS=... SC_APP_USER=... SC_APP_PASS=... \
    python scripts/prod_readonly_probe.py
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
BU, BP = os.getenv('SC_BASIC_USER', ''), os.getenv('SC_BASIC_PASS', '')
AU, AP = os.getenv('SC_APP_USER', ''), os.getenv('SC_APP_PASS', '')
if not (BU and BP and AU and AP):
    print('缺少环境变量 SC_BASIC_USER/SC_BASIC_PASS/SC_APP_USER/SC_APP_PASS')
    sys.exit(2)

BASIC = 'Basic ' + base64.b64encode(('%s:%s' % (BU, BP)).encode()).decode()
UA = 'scireagent-readonly-probe/1.0'
OP = urllib.request.build_opener()


def call(method, path, token=None, body=None):
    h = {'User-Agent': UA, 'Authorization': BASIC}
    if token:
        h['X-Auth-Token'] = token
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h['Content-Type'] = 'application/json'
    rq = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    t = time.time()
    try:
        with OP.open(rq, timeout=35) as resp:
            return resp.status, resp.read(), int((time.time() - t) * 1000)
    except urllib.error.HTTPError as e:
        return e.code, (e.read() if e.fp else b''), int((time.time() - t) * 1000)
    except Exception as e:                                        # noqa: BLE001
        return type(e).__name__, str(e).encode()[:150], int((time.time() - t) * 1000)


def main():
    st, body, ms = call('POST', '/api/v1/auth/login', body={'username': AU, 'password': AP})
    if st != 200:
        print('登录失败 HTTP %s：%s' % (st, body[:250].decode('utf-8', 'replace')))
        return 2
    d = json.loads(body)
    token = d['data']['token']
    u = d['data']['user']
    ident = {k: u.get(k) for k in ('username', 'role', 'is_staff', 'is_superuser',
                                   'is_org_admin', 'email_verified', 'organization')}
    print('登录成功：%s' % json.dumps(ident, ensure_ascii=False))

    paths = [
        '/api/v1/auth/me',
        '/api/v1/products/?page_size=1',
        '/api/v1/site/home',
        '/api/v1/site/navigation',
        '/api/v1/sitemap.xml',
        '/api/v1/search/grouped?q=a',
        '/api/v1/admin/dashboard-stats/',
        '/api/v1/admin/orders/?page_size=1',
        '/api/v1/verified/?status=review',
        '/api/v1/inventory/?page_size=1',
        '/api/v1/coas/?page_size=1',
        '/api/v1/sds-revisions/?page_size=1',
        '/api/v1/products/?archived=1&page_size=1',
    ]

    rows = []
    print('\n%-46s %-4s %10s %7s %s' % ('路径', '状态', '字节', 'ms', '备注'))
    print('-' * 96)
    for p in paths:
        st, body, ms = call('GET', p, token)
        note = ''
        if 'page_size=1' in p:
            try:
                m = (json.loads(body).get('meta') or {})
                pg = m.get('pagination') or m
                note = 'count=%s' % pg.get('count', '?')
            except Exception:                                     # noqa: BLE001
                note = ''
        rows.append({'path': p, 'status': st, 'bytes': len(body), 'ms': ms, 'note': note})
        print('%-46s %-4s %10d %7d %s' % (p, st, len(body), ms, note))

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'docs', 'e2e', 'PROD_READONLY_PROBE.json')
    json.dump({'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'), 'base': BASE,
               'auth': 'Authorization: Basic (nginx) + X-Auth-Token (Django)',
               'note': 'GET only；末尾 logout 回收 token；凭据来自环境变量，未落盘',
               'identity': ident, 'rows': rows},
              open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\n已写入 %s' % out)

    st, body, _ = call('POST', '/api/v1/auth/logout', token, body={})
    print('logout 回收 token → HTTP %s' % st)
    return 0


if __name__ == '__main__':
    sys.exit(main())
