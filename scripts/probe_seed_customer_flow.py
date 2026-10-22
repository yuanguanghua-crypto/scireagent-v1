#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Batch 2 客户侧夹具：给 probe_ouser_a 造
  ① 一张 completed 订单（供 F3-12 再次订购）
  ② 一张 invoiced 订单 + 发票 + 一条 PO 附件（供 F3-11 下载中心）

只在 DB 副本上跑（硬校验 SCIREAGENT_DB_NAME 含 "probe"）。
id 追加写入 backend/_probe_ids.json，供 E2E 读取。
"""
import io
import json
import os
import sys

DB = os.getenv('SCIREAGENT_DB_NAME', '')
if 'probe' not in DB:
    print('!! 拒绝：SCIREAGENT_DB_NAME 必须含 "probe"')
    sys.exit(2)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

import django  # noqa: E402
django.setup()

from datetime import date, timedelta  # noqa: E402
from decimal import Decimal  # noqa: E402

from apps.accounts.models import User  # noqa: E402
from apps.commerce.models import Product, SKU  # noqa: E402
from apps.transactions.models import (  # noqa: E402
    Invoice, Order, OrderItem, PoAttachment, PaymentRecord,
)

u = User.objects.get(username='probe_ouser_a')
# ★ 必须用 status=active 的产品：非 active 的产品详情页会 404，收藏按钮根本不存在（实测踩过）
prod, _ = Product.objects.get_or_create(
    catalog_no='PROBE-ACTIVE-1',
    defaults=dict(name='Probe Active Product', slug='probe-active-product',
                  cas='9999-99-9', status='active'))
# sku_code 全局唯一 ⇒ 带上产品 id，避免与既有夹具的 SKU 撞（实测踩过）
sku = SKU.objects.filter(product=prod).first() or SKU.objects.create(
    product=prod, sku_code='PROBE-DL-SKU-%d' % prod.id,
    price=Decimal('50.00'), is_default=True)


def mk(no, status, total='100.00'):
    o, _ = Order.objects.get_or_create(
        order_no=no,
        defaults=dict(user=u, organization=u.organization, status=status,
                      payment_method='purchase_order', subtotal=Decimal(total),
                      grand_total=Decimal(total), currency='USD',
                      shipping_name='Probe', shipping_address='Probe Addr'))
    if not o.items.exists():
        OrderItem.objects.create(order=o, product=prod, sku=sku, quantity=2,
                                 unit_price=Decimal('50.00'))
    # ★ 强制回到目标状态：重复跑时上一轮的用例可能已把状态推进（实测踩过：quoted 被 accept 成 confirmed）
    if o.status != status:
        o.status = status
        o.save(update_fields=['status', 'updated_at'])
    return o


# ① 已完成订单（再次订购页的数据源）
o_done = mk('PROBE-CUST-DONE-1', Order.Status.COMPLETED)

# ② 已开票订单 + 发票 + 收款（下载中心的数据源）
o_inv = mk('PROBE-CUST-INV-1', Order.Status.INVOICED, '120.00')
inv, _ = Invoice.objects.get_or_create(
    order=o_inv,
    defaults=dict(invoice_no='PROBE-INV-1', status=Invoice.Status.ISSUED,
                  grand_total=Decimal('120.00'), currency='USD',
                  # due_date 是 NOT NULL（实测：不加会 IntegrityError）
                  due_date=date.today() + timedelta(days=30)))
PaymentRecord.objects.get_or_create(invoice=inv, amount=Decimal('60.00'),
                                    defaults=dict(method='wire'))

# ③ PO 附件（下载中心另一类按钮）
att, _ = PoAttachment.objects.get_or_create(
    order=o_inv, original_filename='probe-po.pdf',
    defaults=dict(mime_type='application/pdf', file_size=1024, uploaded_by=u,
                  file='po_attachments/probe-po.pdf'))

ids_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'backend', '_probe_ids.json')
ids = json.load(io.open(ids_file, encoding='utf-8')) if os.path.exists(ids_file) else {}
# ④ 已报价订单（供 F3-6 接受/拒绝报价）
o_quoted = mk('PROBE-CUST-QUOTED-1', Order.Status.QUOTED, '90.00')

ids.update({
    'order_quoted': o_quoted.id,
    'order_completed': o_done.id,
    'order_invoiced': o_inv.id,
    'invoice_id': inv.id,
    'po_attachment_id': att.id,
    'customer_product_id': prod.id,
})
json.dump(ids, io.open(ids_file, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

print('quoted=%s completed=%s invoiced=%s invoice=%s attachment=%s product=%s'
      % (o_quoted.id, o_done.id, o_inv.id, inv.id, att.id, prod.id))
print('已写入 %s' % ids_file)
