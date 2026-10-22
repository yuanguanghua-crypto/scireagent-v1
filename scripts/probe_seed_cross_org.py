#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""跨机构夹具 —— 为「对象级权限 / queryset 收窄」实测造真实对象（只在 DB 副本上）。

为什么必须造真实对象：
  对象级权限（has_object_permission）与 get_queryset 收窄，只有在**对象真实存在**时才会执行。
  用假 id 探测时，`get_object()` 先 404，权限逻辑根本没跑到 —— 这正是上一轮未覆盖的原因。

造什么：
  Org A（probe_org_a）+ 两个成员：probe_ouser_a（主）、probe_ouser_a2（同机构第二人）
  Org B（probe_org_b）+ 成员：probe_ouser_b
  A 的地址 / B 的地址；A 的订单 / B 的订单

安全：写死 SCIREAGENT_DB_NAME 必须含 "probe"，否则拒绝执行。
"""
import os
import sys

DB = os.getenv('SCIREAGENT_DB_NAME', '')
if 'probe' not in DB:
    print('!! 拒绝执行：SCIREAGENT_DB_NAME 必须指向含 "probe" 的副本。当前=%r' % DB)
    sys.exit(2)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

import django  # noqa: E402
django.setup()

from decimal import Decimal  # noqa: E402

from apps.accounts.models import Address, Organization, User  # noqa: E402
from apps.transactions.models import Order  # noqa: E402

PW = 'Probe#2026!'


def org(name, otype='academic'):
    o, _ = Organization.objects.get_or_create(name=name, defaults={'org_type': otype})
    return o


def user(username, organization):
    u = User.objects.filter(username=username).first()
    if u is None:
        u = User(username=username, email='%s@probe.local' % username)
    u.organization = organization
    u.role = 'researcher'
    u.is_staff = False
    u.is_superuser = False
    u.is_org_admin = False
    u.email_verified = True
    u.is_active = True
    u.set_password(PW)
    u.save()
    return u


def address(organization, attention, city):
    a = Address.objects.filter(organization=organization, attention=attention).first()
    if a is None:
        a = Address.objects.create(organization=organization, attention=attention,
                                   city=city, country='US', line1='%s line1' % city)
    return a


def order(u, organization, no, total):
    o = Order.objects.filter(order_no=no).first()
    if o is None:
        o = Order.objects.create(
            user=u, organization=organization, order_no=no,
            status=Order.Status.CONFIRMED, payment_method=Order.PaymentMethod.PO,
            subtotal=Decimal(total), grand_total=Decimal(total), currency='USD')
    return o


A = org('Probe Org A')
B = org('Probe Org B')
ua = user('probe_ouser_a', A)
ua2 = user('probe_ouser_a2', A)
ub = user('probe_ouser_b', B)

addr_a = address(A, 'Attention A', 'City-A')
addr_b = address(B, 'Attention B', 'City-B')
ord_a = order(ua, A, 'PROBE-ORD-A-0001', '100.00')
ord_b = order(ub, B, 'PROBE-ORD-B-0001', '200.00')

print('Org A id=%s  Org B id=%s' % (A.id, B.id))
print('probe_ouser_a  id=%s org=%s' % (ua.id, ua.organization_id))
print('probe_ouser_a2 id=%s org=%s（同机构第二人）' % (ua2.id, ua2.organization_id))
print('probe_ouser_b  id=%s org=%s' % (ub.id, ub.organization_id))
print('Address A id=%s org=%s | Address B id=%s org=%s'
      % (addr_a.id, addr_a.organization_id, addr_b.id, addr_b.organization_id))
print('Order A   id=%s org=%s user=%s | Order B id=%s org=%s user=%s'
      % (ord_a.id, ord_a.organization_id, ord_a.user_id,
         ord_b.id, ord_b.organization_id, ord_b.user_id))
print('\n密码统一：%s' % PW)
