#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""对象级权限 · 第二轮 —— 跨用户购物车/收藏夹、发票 PDF、SDS 下载门控。

第一轮（http_object_probe.py）覆盖了订单与地址。这一轮补四类"对象归属于某人"的资源：
  1. 发票 PDF：别人的发票能不能下载
  2. 愿望清单：能不能改别人的收藏夹
  3. 购物车行：能不能改别人的购物车
  4. 合规文档下载门控：draft 的 SDS 能否匿名下载（published 应当可以）

夹具来源：DB 副本里真实的 invoice 266（order 1167 / user 12）、sds 1(published) / 17(draft)、sku 443。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import http_role_probe as P

INVOICE_ID = 266
SDS_PUBLISHED = 1
SDS_DRAFT = 17
SKU_ID, PRODUCT_ID = 443, 61


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
        with P._OPENER.open(req, timeout=15) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers or {})
    except Exception as e:                                            # noqa: BLE001
        return 0, str(e).encode(), {}


def brief(b, n=120):
    return b.decode('utf-8', 'replace').replace('\n', ' ')[:n]


def main():
    rows = []

    def rec(section, who, method, path, expect, note='', body=None, tok=None):
        st, b, hdrs = call(method, path, tok, body)
        rows.append({'section': section, 'who': who, 'method': method, 'path': path,
                     'status': st, 'expect': expect, 'note': note,
                     'ctype': hdrs.get('Content-Type', ''), 'body': brief(b)})
        return st, b

    # ---------- 1. 发票 PDF ----------
    rec('1 匿名下载发票PDF', 'anon', 'GET', '/api/v1/invoices/%d/pdf/' % INVOICE_ID, '401/403')
    for who in ('probe_ouser_a', 'probe_ouser_b'):
        tok, _, _ = P.login(who)
        rec('1 非本人下载发票PDF', who, 'GET', '/api/v1/invoices/%d/pdf/' % INVOICE_ID,
            '403/404', tok=tok)

    # ---------- 2. 合规文档下载门控 ----------
    rec('2 匿名下载已发布SDS', 'anon', 'GET', '/api/v1/sds-revisions/%d/download/' % SDS_PUBLISHED,
        '200 + application/pdf')
    rec('2 匿名下载草稿SDS', 'anon', 'GET', '/api/v1/sds-revisions/%d/download/' % SDS_DRAFT,
        '403/404（门控）')

    # ---------- 3. 购物车行跨用户 ----------
    ta, _, _ = P.login('probe_ouser_a')
    tb, _, _ = P.login('probe_ouser_b')
    st, b, _ = call('POST', '/api/v1/basket/items', ta,
                    {'product_id': PRODUCT_ID, 'sku_id': SKU_ID, 'quantity': 1})
    item_id = None
    try:
        d = json.loads(b)
        item_id = (d.get('data') or {}).get('id')
    except Exception:                                                 # noqa: BLE001
        pass
    rows.append({'section': '3 A 建购物车行', 'who': 'probe_ouser_a', 'method': 'POST',
                 'path': '/api/v1/basket/items', 'status': st, 'expect': '201',
                 'note': 'item_id=%s' % item_id, 'ctype': '', 'body': brief(b)})

    if item_id:
        rec('3 B 改A的购物车行', 'probe_ouser_b', 'PATCH',
            '/api/v1/basket/items/%d' % item_id, '403/404', body={'quantity': 99}, tok=tb)
        rec('3 B 删A的购物车行', 'probe_ouser_b', 'DELETE',
            '/api/v1/basket/items/%d/delete' % item_id, '403/404', tok=tb)

    # ---------- 4. 愿望清单跨用户 ----------
    st, b, _ = call('GET', '/api/v1/wishlist/', ta)
    wid_a = None
    try:
        items = (json.loads(b).get('data') or [])
        wid_a = items[0]['id'] if items else None
    except Exception:                                                 # noqa: BLE001
        pass
    if wid_a is None:
        st, b, _ = call('POST', '/api/v1/wishlist/', ta, {'name': 'Probe A Wishlist', 'product_ids': []})
        try:
            wid_a = (json.loads(b).get('data') or {}).get('id')
        except Exception:                                             # noqa: BLE001
            pass
    rows.append({'section': '4 A 的愿望清单', 'who': 'probe_ouser_a', 'method': 'GET',
                 'path': '/api/v1/wishlist/', 'status': 200, 'expect': '—',
                 'note': 'wishlist_id=%s' % wid_a, 'ctype': '', 'body': ''})
    if wid_a:
        rec('4 B 改A的愿望清单', 'probe_ouser_b', 'PATCH', '/api/v1/wishlist/%d/' % wid_a,
            '403/404', body={'name': 'HIJACKED'}, tok=tb)
        rec('4 A 事后读自己的清单', 'probe_ouser_a', 'GET', '/api/v1/wishlist/', '200',
            note='name 是否被改成 HIJACKED', tok=ta)

    print('%-24s %-16s %-6s %-42s %-4s %s' % ('场景', '身份', '方法', '路径', '状态', '期望'))
    print('-' * 140)
    for r in rows:
        print('%-24s %-16s %-6s %-42s %-4s %s' % (
            r['section'][:24], r['who'], r['method'], r['path'][:42], r['status'], r['expect'][:22]))

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'docs', 'e2e', 'HTTP_OBJECT_PROBE2.json')
    json.dump({'generated_at': P.time.strftime('%Y-%m-%d %H:%M:%S'),
               'fixture': {'invoice': INVOICE_ID, 'sds_published': SDS_PUBLISHED,
                           'sds_draft': SDS_DRAFT, 'sku': SKU_ID},
               'rows': rows}, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\n已写入 %s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
