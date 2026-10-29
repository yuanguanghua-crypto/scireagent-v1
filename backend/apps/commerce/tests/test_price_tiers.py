# -*- coding: utf-8 -*-
"""阶梯价（`SkuPriceTier`）与唯一取价入口 `resolve_unit_price` —— 2026-10-29。

这个能力的失效方式全是"不报错但收错钱"，所以每条都要钉：
  · 档位取错（买 5 件按 1 件价收）⇒ 客户多付，投诉；
  · 档位取错（买 1 件按 10 件价收）⇒ 我们少收，且对不上账；
  · 改价波及历史订单 ⇒ 已开发票的金额变了；
  · 前端显示一个价、落库另一个价 ⇒ 客户截图对不上。
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Organization, User
from apps.commerce.models import Product, SKU, SkuPriceTier
from apps.commerce.services.pricing import (
    resolve_unit_price, start_price, tier_segments,
)
from apps.transactions.models import Basket, Order, OrderItem


class TierBase(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Lab', org_type='academic')
        self.admin = User.objects.create_user(
            username='tier_admin', password='x', email='a@lab.edu',
            organization=self.org, role='admin', is_staff=True)
        self.res = User.objects.create_user(
            username='tier_res', password='x', email='r@lab.edu',
            organization=self.org, role='researcher')
        self.product = Product.objects.create(name='Pseudo-UTP', slug='pseudo-utp-tier')
        self.sku = SKU.objects.create(
            product=self.product, sku_code='SC9700-1',
            pack_size='100 mg', price=Decimal('100.00'))
        self.client = APIClient()

    def _tiers(self, *pairs):
        for qty, price in pairs:
            SkuPriceTier.objects.create(
                sku=self.sku, min_qty=qty, unit_price=Decimal(price))


class ResolveUnitPriceTest(TierBase):
    def test_no_tiers_falls_back_to_catalog_price(self):
        """没配档位 = 行为与改造前完全一致（这是上线当天不改价的前提）。"""
        self.assertEqual(resolve_unit_price(self.sku, 1), Decimal('100.00'))
        self.assertEqual(resolve_unit_price(self.sku, 999), Decimal('100.00'))

    def test_tier_boundaries(self):
        self._tiers((1, '100'), (5, '90'), (10, '80'))
        cases = {1: '100', 4: '100', 5: '90', 9: '90', 10: '80', 999: '80'}
        for qty, expect in cases.items():
            self.assertEqual(
                resolve_unit_price(self.sku, qty), Decimal(expect),
                f'数量 {qty} 应按 {expect} 计价')

    def test_missing_lowest_tier_falls_back_for_small_qty(self):
        """只配了 10+ 档 ⇒ 1 件时回落目录价，而不是误用 10 件价。

        这正是「全量替换而不是逐条增删」要避免的中间态：如果 1-4 档缺失，
        买 1 件反而按更贵的价（或更便宜的价）算，都对不上。
        """
        self._tiers((10, '80'))
        self.assertEqual(resolve_unit_price(self.sku, 1), Decimal('100.00'))
        self.assertEqual(resolve_unit_price(self.sku, 10), Decimal('80.00'))

    def test_quote_price_wins(self):
        """报价单价 > 阶梯价（形参已留好，目前无调用方）。"""
        self._tiers((1, '100'), (10, '80'))
        self.assertEqual(
            resolve_unit_price(self.sku, 10, quote_unit_price=Decimal('70.00')),
            Decimal('70.00'))

    def test_zero_quantity_does_not_crash(self):
        self._tiers((1, '100'))
        self.assertEqual(resolve_unit_price(self.sku, 0), Decimal('100.00'))

    def test_start_price_is_lowest_tier(self):
        self._tiers((1, '100'), (5, '90'), (10, '80'))
        self.assertEqual(start_price(self.sku), Decimal('80.00'))

    def test_start_price_without_tiers(self):
        self.assertEqual(start_price(self.sku), Decimal('100.00'))

    def test_tier_segments_max_is_derived(self):
        self._tiers((1, '100'), (5, '90'), (10, '80'))
        segs = tier_segments(self.sku.price_tiers.all())
        self.assertEqual([s['min_qty'] for s in segs], [1, 5, 10])
        self.assertEqual([s['max_qty'] for s in segs], [4, 9, None])
        self.assertEqual(segs[2]['unit_price'], '80.00')


class TierEndpointTest(TierBase):
    URL = None  # 在 setUp 里按 sku id 拼

    def setUp(self):
        super().setUp()
        self.URL = f'/api/v1/skus/{self.sku.pk}/price-tiers/'

    def _put(self, tiers, user=None):
        self.client.force_authenticate(user=user or self.admin)
        return self.client.put(self.URL, {'tiers': tiers}, format='json')

    def test_replace_tiers(self):
        r = self._put([
            {'min_qty': 1, 'unit_price': '100.00'},
            {'min_qty': 5, 'unit_price': '90.00'},
            {'min_qty': 10, 'unit_price': '80.00'},
        ])
        self.assertEqual(r.status_code, 200, r.content[:400])
        self.assertEqual(SkuPriceTier.objects.filter(sku=self.sku).count(), 3)
        self.assertEqual(r.json()['data']['price_tiers'][0]['max_qty'], 4)

    def test_replace_is_full_swap(self):
        self._tiers((1, '100'), (5, '90'))
        r = self._put([{'min_qty': 1, 'unit_price': '95.00'}])
        self.assertEqual(r.status_code, 200)
        rows = list(SkuPriceTier.objects.filter(sku=self.sku))
        self.assertEqual(len(rows), 1, '全量替换必须把旧档位删掉')
        self.assertEqual(rows[0].unit_price, Decimal('95.00'))

    def test_empty_list_clears_tiers(self):
        self._tiers((1, '100'), (10, '80'))
        r = self._put([])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(SkuPriceTier.objects.filter(sku=self.sku).count(), 0)
        self.assertEqual(resolve_unit_price(self.sku, 10), Decimal('100.00'))

    def test_rejects_duplicate_min_qty(self):
        r = self._put([
            {'min_qty': 5, 'unit_price': '90.00'},
            {'min_qty': 5, 'unit_price': '80.00'},
        ])
        self.assertEqual(r.status_code, 400, r.content[:400])
        self.assertEqual(r.json()['meta']['error']['code'], 'DUPLICATE_TIER')

    def test_rejects_price_increasing_with_quantity(self):
        """买得多反而更贵 ⇒ 一定是录错了。这条挡住绝大多数手工失误。"""
        r = self._put([
            {'min_qty': 1, 'unit_price': '80.00'},
            {'min_qty': 10, 'unit_price': '95.00'},
        ])
        self.assertEqual(r.status_code, 400, r.content[:400])
        self.assertEqual(r.json()['meta']['error']['code'],
                         'TIER_PRICE_NOT_DESCENDING')

    def test_rejects_min_qty_below_one(self):
        r = self._put([{'min_qty': 0, 'unit_price': '10.00'}])
        self.assertEqual(r.status_code, 400)

    def test_writes_audit_log(self):
        """价格是敏感数据，改价必须留痕（谁改的、改成什么）。"""
        from apps.commerce.models import AuditLog
        self._put([{'min_qty': 1, 'unit_price': '88.00'}])
        log = AuditLog.objects.filter(action=AuditLog.ACTION_UPDATE).first()
        self.assertIsNotNone(log, '改价必须写 AuditLog')
        self.assertEqual(log.user_id, self.admin.pk)
        self.assertEqual(log.snapshot.get('scope'), 'price_tiers')
        self.assertEqual(log.snapshot['after'][0]['unit_price'], '88.00')

    def test_researcher_forbidden(self):
        r = self._put([{'min_qty': 1, 'unit_price': '1.00'}], user=self.res)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(SkuPriceTier.objects.filter(sku=self.sku).count(), 0)


class OrderSnapshotTest(TierBase):
    def test_changing_tiers_does_not_affect_existing_order(self):
        """改档位不得影响已落库的订单行金额（否则已开发票的金额会变）。"""
        self._tiers((1, '100'), (10, '80'))
        order = Order.objects.create(
            user=self.res, order_no='ORD-TIER-1', status=Order.Status.CONFIRMED)
        price = resolve_unit_price(self.sku, 10)
        oi = OrderItem.objects.create(
            order=order, product=self.product, sku=self.sku,
            quantity=10, unit_price=price)
        self.assertEqual(oi.unit_price, Decimal('80.00'))

        # 运营改价
        SkuPriceTier.objects.filter(sku=self.sku).update(unit_price=Decimal('50.00'))
        oi.refresh_from_db()
        self.assertEqual(oi.unit_price, Decimal('80.00'),
                         '订单行单价是下单时快照，不得随改价变化')
        self.assertEqual(oi.subtotal, Decimal('800.00'))

class CheckoutUsesTierTest(TierBase):
    """端到端：结账真的按阶梯价收费，而不只是算价函数能用。"""

    def test_checkout_charges_tier_price(self):
        self._tiers((1, '100'), (10, '80'))
        Basket.objects.create(user=self.res, product=self.product,
                              sku=self.sku, quantity=10)
        c = APIClient()
        c.force_authenticate(self.res)
        r = c.post('/api/v1/checkout/', {
            'payment_method': 'purchase_order',
            'po_number': 'PO-TIER-1',
            'shipping_name': 'Buyer',
            'shipping_address': '1 Lab Rd',
            'shipping_email': 'r@lab.edu',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content[:400])

        oi = OrderItem.objects.get()
        self.assertEqual(oi.unit_price, Decimal('80.00'),
                         '10 件必须按 10 件档单价落库')
        self.assertEqual(oi.subtotal, Decimal('800.00'))
        order = Order.objects.get()
        self.assertEqual(order.grand_total, Decimal('800.00'))

    def test_cart_line_shows_tier_price_for_current_quantity(self):
        """购物车行的单价随数量变（不是固定 1 件价）。

        直接测序列化器而不经 view：view 的包装结构（分页/信封）与本功能无关，
        而「单价必须跟随数量」才是要钉的点。
        """
        from apps.transactions.api.v1.basket_serializers import BasketItemSerializer

        self._tiers((1, '100'), (5, '90'), (10, '80'))
        row = Basket.objects.create(user=self.res, product=self.product,
                                    sku=self.sku, quantity=5)
        data = BasketItemSerializer(row).data
        self.assertEqual(Decimal(str(data['unit_price'])), Decimal('90.00'))
        self.assertEqual(Decimal(str(data['subtotal'])), Decimal('450.00'))

        row.quantity = 10
        row.save(update_fields=['quantity'])
        data = BasketItemSerializer(row).data
        self.assertEqual(Decimal(str(data['unit_price'])), Decimal('80.00'),
                         '数量改到 10 应自动切到 10 件档')
