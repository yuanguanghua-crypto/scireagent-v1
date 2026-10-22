#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""并发实测（SQLite 副本）—— 库存入库的"丢失更新"检测 + 并发下单写争用。

## 先说局限（不夸大）
SQLite 下 `select_for_update()` 是 **no-op**（Django 明确文档），所以本脚本**测不出
行级锁互斥是否有效**。它能测的是：
  · 应用层在 SQLite 下并发调用时的**实际结果**（是否丢失更新、能否全成功）
  · 写争用的失败形态（database is locked / 500 / 正常排队）
⇒ 结论只能写成"SQLite 下实测如何"，**不能**外推到生产 PostgreSQL。

## 两个实验
E1 库存入库并发：同一 (sku, location) 并发 N 次 +1，看最终 available 是否 = 初始 + N
E2 PO 提交并发：同一用户并发 N 次 POST /orders/po/，看成功率与失败形态（单号是否唯一）

用法：
  env -u HTTP_PROXY ... python scripts/http_concurrency_probe.py --n 10
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import http_role_probe as P

# 由 snapshot 动态确定（副本里未必有 sku 443 的库存行）
SKU_ID = None
LOCATION = None


def _django_once():
    '''一次初始化（重复调用安全：apps.ready 后会提前返回）。'''
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
    import django
    django.setup()
    from apps.inventory.models import Inventory
    return Inventory


def pick_row():
    '''选一个已有库存行作为并发目标（同一 (sku, location) 才能构成争用）。'''
    Inventory = _django_once()
    row = Inventory.objects.order_by('id').first()
    if row is None:
        raise SystemExit('副本里没有任何库存行，无法做并发测试')
    return row.sku_id, row.location


def inv_snapshot():
    """直接读副本库拿 (available, allocated)，避免走 API 的权限/分页干扰。"""
    Inventory = _django_once()
    row = Inventory.objects.filter(sku_id=SKU_ID, location=LOCATION).first()
    if row is None:
        return None
    return {'id': row.id, 'available': row.available, 'allocated': row.allocated}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=10)
    ap.add_argument('--out', default='docs/e2e/CONCURRENCY_PROBE.json')
    ap.add_argument('--label', default='sqlite')
    args = ap.parse_args()
    n = args.n

    global SKU_ID, LOCATION
    SKU_ID, LOCATION = pick_row()
    print('并发目标库存行：sku=%s location=%s' % (SKU_ID, LOCATION))

    tok, st, _ = P.login('probe_procure')
    if not tok:
        raise SystemExit('采购登录失败 HTTP %s' % st)

    before = inv_snapshot()
    if before is None:
        raise SystemExit('未找到 sku=%s location=%s 的库存行，无法做入库并发' % (SKU_ID, LOCATION))

    def receipt(_i):
        # 直接打 HTTP，每线程独立连接
        import urllib.error
        import urllib.request
        body = json.dumps({'sku_id': SKU_ID, 'location': LOCATION, 'quantity': 1,
                           'reason': 'conc-probe'}).encode()
        req = urllib.request.Request(
            P.BASE + '/api/v1/inventory/receipt/', data=body, method='POST',
            headers={'Host': '127.0.0.1:8011', 'Content-Type': 'application/json',
                     'Authorization': 'Token ' + tok})
        try:
            with P._OPENER.open(req, timeout=30) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
        except Exception:                                          # noqa: BLE001
            return 0

    with ThreadPoolExecutor(max_workers=n) as ex:
        e1_codes = list(ex.map(receipt, range(n)))

    after = inv_snapshot()

    # ---------- E2 并发 PO 提交 ----------
    def submit_po(i):
        import urllib.error
        import urllib.request
        body = json.dumps({'po_number': '', 'items': [], 'notes': 'conc %d' % i}).encode()
        req = urllib.request.Request(
            P.BASE + '/api/v1/orders/po/', data=body, method='POST',
            headers={'Host': '127.0.0.1:8011', 'Content-Type': 'application/json',
                     'Authorization': 'Token ' + tok})
        try:
            with P._OPENER.open(req, timeout=30) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
        except Exception:                                          # noqa: BLE001
            return 0

    with ThreadPoolExecutor(max_workers=n) as ex:
        e2_codes = list(ex.map(submit_po, range(n)))

    delta = after['available'] - before['available']
    print('=== E1 库存入库并发（N=%d，每次 +1）===' % n)
    print('  初始 available = %d' % before['available'])
    print('  结束 available = %d' % after['available'])
    print('  实际增量 = %d  （期望 %d）%s' % (delta, n, '✅' if delta == n else '❌ 丢失更新'))
    from collections import Counter
    print('  响应码分布 = %s' % dict(Counter(e1_codes)))
    print('\n=== E2 PO 提交并发（N=%d，空 body ⇒ 期望 400）===' % n)
    print('  响应码分布 = %s' % dict(Counter(e2_codes)))
    print('  （400 = 权限通过、校验失败；500 = 服务端异常；0 = 连接失败/超时）')

    out = args.out
    if not os.path.isabs(out):
        out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), out)
    json.dump({'generated_at': P.time.strftime('%Y-%m-%d %H:%M:%S'),
               'engine': args.label,
               'n': n,
               'e1_inventory_receipt': {'before': before, 'after': after, 'delta': delta,
                                        'codes': dict(Counter(e1_codes))},
               'e2_po_submit': {'codes': dict(Counter(e2_codes))}},
              open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('\n已写入 %s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
