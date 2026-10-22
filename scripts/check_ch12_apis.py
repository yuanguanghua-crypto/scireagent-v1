#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""抽查第 12 章「关键接口」列，是否真在 PAGE_API_MAP 记录的该页调用里出现过。

只看内部台 19 页里"写操作多、最容易写错"的那几张表。
判定：文档声称的每个 METHOD /path 片段，只要能在该页的 calls 里找到同 method 且路径互为前缀，即算通过。
"""
import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, 'docs', 'e2e', 'SITE_ROLE_OPERATION_MANUAL.md')
MAP = os.path.join(ROOT, 'docs', 'e2e', 'PAGE_API_MAP.json')

ROUTE2MAP = {
    '/workspace/products': 'views/workspace/ProductsPage.vue',
    '/workspace/products/new': 'views/workspace/ProductEditPage.vue',
    '/workspace/goals': 'views/workspace/GoalsPage.vue',
    '/workspace/verified': 'views/workspace/VerifiedPage.vue',
    '/ops/inventory': 'views/admin/InventoryDesk.vue',
    '/ops/po/review': 'views/admin/PoReviewDesk.vue',
    '/ops/po/shipments': 'views/admin/PoShipmentDesk.vue',
    '/ops/po/invoicing': 'views/admin/PoInvoicingDesk.vue',
    '/ops/po/ar': 'views/admin/PoArReport.vue',
    '/ops/po/organizations': 'views/admin/PoOrgManagement.vue',
    '/ops/orders': 'views/admin/AdminOrdersPage.vue',
}


def norm(p):
    u = p
    if u.startswith('/api/v1'):
        u = u[len('/api/v1'):]
    u = re.sub(r'\$\{[^}]*\}', '*', u)
    u = re.sub(r'<[^>]+>', '*', u)
    u = re.sub(r'\{[^}]*\}', '*', u)
    return u


def main():
    s = io.open(DOC, encoding='utf-8').read()
    m = re.search(r'## 12\.3 内部台.*?(?=## 12\.4)', s, re.S)
    body = m.group(0)
    rows = re.findall(r'^\|\s*([^|]+)\|\s*`([^`]+)`\s*\|[^|]*\|[^|]*\|\s*([^|]+)\|', body, re.M)

    am = json.load(io.open(MAP, encoding='utf-8'))
    by_file = {p['file']: p['calls'] for p in am['pages']}

    print('=== 第 12.3 关键接口 vs PAGE_API_MAP ===')
    bad = 0
    checked = 0
    for nice, route, api_cell in rows:
        key = ROUTE2MAP.get(route)
        if not key:
            continue
        calls = by_file.get(key)
        if calls is None:
            print('  ?  %-20s %-28s 该页未收录于 PAGE_API_MAP' % (nice.strip(), route))
            continue
        have = set((c['method'], norm(c['url'])) for c in calls)
        # 从文档单元格里抽 METHOD 与路径
        for mm in re.finditer(r'`(GET|POST|PUT|PATCH|DELETE)\s+([^`]+)`', api_cell):
            method, path = mm.group(1), norm(mm.group(2).split('、')[0].strip())
            checked += 1
            ok = any(h[0] == method and (h[1].startswith(path) or path.startswith(h[1]))
                     for h in have)
            if not ok:
                print('  ✗ %-20s %-28s 声称 %s %s —— 该页实测调用里没有' % (
                    nice.strip(), route, method, path))
                bad += 1
    print('\n抽查 %d 条接口声明，不匹配 %d 条' % (checked, bad))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
