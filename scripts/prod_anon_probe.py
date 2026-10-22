#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生产环境 · 匿名只读探测（绝不登录、绝不写）。

能回答什么：**一个匿名互联网用户在生产上到底能碰到哪些东西**。
不能回答什么：登录后的行为、写操作、内部台 —— 那需要 nginx 第一层 basic-auth 账号
与应用层账号（本地无凭据文件 `deploy/CREDENTIALS.txt`），本轮不猜、不试弱口令。

安全约束（本脚本硬编码）：
  · 只用 GET
  · 不带任何 Authorization
  · 请求数固定、不循环重试
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = 'https://scireagent.com'
PATHS = [
    '/',                          # SPA 根
    '/robots.txt',
    '/sitemap.xml',
    '/api/v1/health/',            # 后端健康检查
    '/api/v1/site/home',          # 公开首页数据
    '/api/v1/products/',          # 公开产品列表
    '/api/v1/search/suggest?q=a',
    '/api/v1/orders/',            # 需登录（匿名应 401/403）
    '/api/v1/admin/orders/',      # staff 专属（匿名应 401/403）
    '/api/v1/verified/',          # staff 专属
]


def probe(path, use_proxy=True):
    op = (urllib.request.build_opener() if use_proxy
          else urllib.request.build_opener(urllib.request.ProxyHandler({})))
    req = urllib.request.Request(BASE + path,
                                 headers={'User-Agent': 'scireagent-readonly-probe/1.0'})
    t = time.time()
    try:
        with op.open(req, timeout=20) as r:
            return {'path': path, 'status': r.status,
                    'bytes': len(r.read()),
                    'ms': int((time.time() - t) * 1000),
                    'ctype': r.headers.get('Content-Type', ''),
                    'www_auth': (r.headers.get('WWW-Authenticate') or '')[:40]}
    except urllib.error.HTTPError as e:
        return {'path': path, 'status': e.code, 'bytes': 0,
                'ms': int((time.time() - t) * 1000),
                'ctype': (e.headers or {}).get('Content-Type', ''),
                'www_auth': ((e.headers or {}).get('WWW-Authenticate') or '')[:40]}
    except Exception as e:                                          # noqa: BLE001
        return {'path': path, 'status': type(e).__name__, 'bytes': 0,
                'ms': int((time.time() - t) * 1000), 'ctype': '', 'www_auth': ''}


def main():
    rows = [probe(p) for p in PATHS]
    print('%-34s %-6s %-8s %-6s %s' % ('路径', '状态', '字节', 'ms', 'WWW-Authenticate'))
    print('-' * 96)
    for r in rows:
        print('%-34s %-6s %-8s %-6s %s' % (r['path'], r['status'], r['bytes'], r['ms'], r['www_auth']))

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'docs', 'e2e', 'PROD_ANON_PROBE.json')
    json.dump({'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
               'base': BASE, 'method': 'GET only, no auth, no writes',
               'rows': rows}, open(out, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('\n已写入 %s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
