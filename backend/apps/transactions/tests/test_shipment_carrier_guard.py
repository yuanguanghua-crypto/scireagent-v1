"""A-095：发货单不得「无承运商、无单号」被创建（2026-11-18 / S4）。

## 真实缺口
`ShipmentCreateSerializer` 的 `carrier` 与 `tracking_number` 原先都是
`required=False, allow_blank=True, default=''` ⇒ 后端**主动接受**一次全空发货：
`ShippingRecord` 落一条既无承运商也无单号的记录，订单状态照样推进到 `shipped`，
客户收到的通知里没有任何可追踪信息（出问题既追不了也索赔不了）。
前端 `PoShipmentDesk.vue` 当时是**零校验、零反馈**，点一下按钮就发出去。

## 本文件锁住的契约
1. **两个都空 ⇒ 400**，且**不落库**、订单状态不变（不能"校验失败但状态已推进"）；
2. **只填承运商 / 只填单号 ⇒ 201**（真实履约里这两种都不罕见，不能一刀切要求都填）；
3. 纯空格等同空（`carrier='   '` 不能绕过判断落库成"看起来填了"的脏值）；
4. 文案可操作：说清「至少填一个」，且不吐内部端点路径。
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Organization
from apps.commerce.models import Product, SKU
from apps.transactions.models import Order, OrderItem, ShippingRecord

User = get_user_model()


def _user(username, role='procurement', org=None, is_staff=True):
    return User.objects.create_user(
        username=username, email=f'{username}@example.com', password='x',
        role=role, organization=org, is_staff=is_staff,
    )


class ShipmentCarrierOrTrackingGuardTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='ShipOrg', org_type='academic')
        self.staff = _user('ship_guard_proc', org=self.org)
        self.client = APIClient()
        self.client.force_authenticate(user=self.staff)

        product = Product.objects.create(name='Ship Reagent', slug='ship-reagent')
        self.sku = SKU.objects.create(product=product, sku_code='SKU-SHIP-001', price=10)
        self.order = Order.objects.create(
            user=self.staff, organization=self.org,
            order_no='ORD-SHIP-GUARD-1', po_number='PO-SHIP-GUARD-1',
            status=Order.Status.CONFIRMED,
        )
        self.item = OrderItem.objects.create(
            order=self.order, sku=self.sku, quantity=2, unit_price=Decimal('10.00'),
        )

    def _post(self, payload):
        return self.client.post(
            f'/api/v1/orders/{self.order.id}/shipments/', payload, format='json')

    def _items(self):
        return [{'order_item_id': self.item.id, 'quantity': 1}]

    # ── 1. 主闸门：两个都空 ⇒ 400 且零副作用 ──

    def test_empty_carrier_and_tracking_rejected(self):
        r = self._post({'items': self._items()})

        self.assertEqual(r.status_code, 400, r.content[:400])
        self.assertEqual(
            ShippingRecord.objects.filter(order=self.order).count(), 0,
            '★ 校验失败了却落了发货记录',
        )
        self.order.refresh_from_db()
        self.assertEqual(
            self.order.status, Order.Status.CONFIRMED,
            '★ 发货被拒但订单状态已推进 —— 校验必须发生在状态流转之前',
        )

    def test_explicit_blank_strings_rejected(self):
        """显式传空串（前端表单未填写时的真实形态）同样要拦。"""
        r = self._post({'carrier': '', 'tracking_number': '', 'notes': '', 'items': self._items()})
        self.assertEqual(r.status_code, 400, r.content[:400])
        self.assertEqual(ShippingRecord.objects.filter(order=self.order).count(), 0)

    # ── 2. 不误伤：只要有一个就能发 ──

    def test_carrier_only_accepted(self):
        r = self._post({'carrier': 'DHL', 'items': self._items()})
        self.assertEqual(r.status_code, 201, r.content[:400])
        rec = ShippingRecord.objects.filter(order=self.order).latest('id')
        self.assertEqual(rec.carrier, 'DHL')

    def test_tracking_only_accepted(self):
        r = self._post({'tracking_number': 'TRK-ONLY-1', 'items': self._items()})
        self.assertEqual(r.status_code, 201, r.content[:400])
        rec = ShippingRecord.objects.filter(order=self.order).latest('id')
        self.assertEqual(rec.tracking_number, 'TRK-ONLY-1')

    def test_both_filled_accepted(self):
        r = self._post({'carrier': 'FedEx', 'tracking_number': 'TRK-BOTH-1', 'items': self._items()})
        self.assertEqual(r.status_code, 201, r.content[:400])

    # ── 3. 纯空格不得绕过 ──

    def test_whitespace_only_carrier_rejected_when_no_tracking(self):
        r = self._post({'carrier': '   ', 'tracking_number': '  ', 'items': self._items()})
        self.assertEqual(r.status_code, 400, r.content[:400])
        self.assertEqual(ShippingRecord.objects.filter(order=self.order).count(), 0)

    def test_whitespace_carrier_normalized_when_tracking_given(self):
        """有单号时，纯空格承运商应被归一化成空串而不是原样落库。"""
        r = self._post({'carrier': '   ', 'tracking_number': 'TRK-NORM-1', 'items': self._items()})
        self.assertEqual(r.status_code, 201, r.content[:400])
        rec = ShippingRecord.objects.filter(order=self.order).latest('id')
        self.assertEqual(rec.carrier, '', f'纯空格承运商被原样落库：{rec.carrier!r}')

    # ── 4. 文案可操作 ──

    def test_error_message_is_actionable(self):
        r = self._post({'items': self._items()})
        body = r.content.decode('utf-8', errors='ignore')
        self.assertEqual(r.status_code, 400)
        self.assertIn('carrier', body.lower(), f'文案没提 carrier：{body[:400]}')
        self.assertIn('tracking', body.lower(), f'文案没提 tracking：{body[:400]}')
        self.assertNotIn('/api/', body, '文案里出现了端点路径')
