#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""核对第 12 章内部台表里「采购（非 staff）」一列，是否与 PAGE_ROLE_MATRIX 的实测判定一致。

手写表格最容易在这里出错：某页实测是 READONLY，表里写成"✅ 可用"，读者就会被误导。
"""
import io
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, 'docs', 'e2e', 'SITE_ROLE_OPERATION_MANUAL.md')
RM = os.path.join(ROOT, 'docs', 'e2e', 'PAGE_ROLE_MATRIX.json')

# 路由 → 组件 basename
ROUTE2COMP = {
    '/workspace': 'DashboardPage',
    '/workspace/products': 'ProductsPage',
    '/workspace/products/new': 'ProductEditPage',
    '/workspace/products/:id/edit': 'ProductEditPage',
    '/workspace/goals': 'GoalsPage',
    '/workspace/applications': 'AppsPage',
    '/workspace/methods': 'MethodsPage',
    '/workspace/protocols': 'ProtocolsPage',
    '/workspace/references': 'ReferencesPage',
    '/workspace/verified': 'VerifiedPage',
    '/workspace/knowledge-intake': 'KnowledgeIntake',
    '/ops/orders': 'AdminOrdersPage',
    '/ops/orders/:id': 'AdminOrderDetail',
    '/ops/po/review': 'PoReviewDesk',
    '/ops/po/shipments': 'PoShipmentDesk',
    '/ops/po/invoicing': 'PoInvoicingDesk',
    '/ops/po/ar': 'PoArReport',
    '/ops/po/organizations': 'PoOrgManagement',
    '/ops/inventory': 'InventoryDesk',
}

EXPECT = {'DEAD': '❌', 'READONLY': '⚠️', 'OK': '✅'}


def main():
    s = io.open(DOC, encoding='utf-8').read()
    m = re.search(r'## 12\.3 内部台.*?(?=## 12\.4)', s, re.S)
    body = m.group(0)
    rm = json.load(io.open(RM, encoding='utf-8'))
    verdict = {}
    for p in rm['pages']:
        comp = os.path.basename(p['file']).replace('.vue', '')
        verdict[comp] = p['roles'].get('procurement', {}).get('verdict')

    rows = re.findall(r'^\|\s*([^|]+)\|\s*`([^`]+)`\s*\|\s*([^|]+)\|', body, re.M)
    print('=== 第 12.3 采购列 vs 实测判定 ===')
    bad = 0
    for nice, route, cell in rows:
        comp = ROUTE2COMP.get(route)
        v = verdict.get(comp) if comp else None
        cell = cell.strip()
        if v is None:
            print('  ?  %-22s %-28s 表内「%s」 实测=未收录' % (nice.strip(), route, cell))
            continue
        want = EXPECT[v]
        ok = cell.startswith(want)
        print('  %s %-22s %-28s 表内「%s」 实测=%s（应 %s）' % (
            '✓' if ok else '✗', nice.strip(), route, cell, v, want))
        if not ok:
            bad += 1
    print('\n不一致 %d 行' % bad)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
