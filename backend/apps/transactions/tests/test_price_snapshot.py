"""X-3 金额快照 —— 内部改价不得影响已下的订单。

为什么必须有用例（此前一次都没验过）：
  `OrderItem.unit_price` 是**下单那一刻从 SKU 现价拷贝的**（`checkout_views.py:110`），
  `subtotal` 由 `OrderItem.save()` 重算。如果哪天有人改成"读 SKU 现价"，
  历史订单金额会**静默变化**——这是财务对账级的事故，但没有任何测试会报警。

覆盖三条：
  T1 下单后单价=当时 SKU 价
  T2 改 SKU 价后，**历史订单金额不变**
  T3 新订单用新价（证明改动确实生效，不是测试假绿）
"""
from decimal import Decimal
from uuid import uuid4

import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.transactions.models import Basket, Order


def _basket(user, sku, qty):
    Basket.objects.update_or_create(
        user=user, sku=sku, defaults={'product': sku.product, 'quantity': qty})
    return None


@pytest.mark.django_db
class TestPriceSnapshot:
    def _ready(self, price='100.00'):
        user = UserFactory(email_verified=True)
        product = ProductFactory(status='active')
        sku = SKUFactory(product=product, price=Decimal(price), is_default=True)
        _basket(user, sku, 2)
        client = APIClient()
        client.force_authenticate(user=user)
        return user, product, sku, client

    def _checkout(self, client):
        resp = client.post('/api/v1/checkout/', {
            'payment_method': 'purchase_order',
            # ★ PO 号对 purchase_order 是**必填**（400 实测），且非空值全局唯一
            #   （`uniq_order_po_number_nonempty`）⇒ 每个用例用唯一值
            'po_number': 'PROBE-PO-%s' % uuid4().hex[:8],
            'shipping_name': 'Probe',
            'shipping_address': 'Probe Addr',
        }, format='json')
        # 实测：checkout 成功返回 201（不是 200）
        assert resp.status_code in (200, 201), resp.content[:400]
        return resp.json()['data']

    def test_t1_unit_price_is_snapshot_of_sku_price(self):
        user, product, sku, client = self._ready('100.00')
        data = self._checkout(client)

        order = Order.objects.get(pk=data['id'])
        item = order.items.first()
        assert item.unit_price == Decimal('100.00'), '下单单价未按 SKU 现价快照'
        assert item.subtotal == Decimal('200.00'), '小计未按 单价×数量 计算'
        assert order.grand_total == Decimal('200.00'), '订单总额不等于明细合计'

    def test_t2_price_change_does_not_touch_history(self):
        user, product, sku, client = self._ready('100.00')
        data = self._checkout(client)
        order_id = data['id']

        # 内部改价 +50%
        sku.price = Decimal('150.00')
        sku.save(update_fields=['price'])

        order = Order.objects.get(pk=order_id)
        item = order.items.first()
        assert item.unit_price == Decimal('100.00'), (
            '★ 改 SKU 价后历史订单单价变了 —— 金额快照失效（财务事故级）')
        assert order.grand_total == Decimal('200.00'), '★ 改价后历史订单总额变了'

        # 再走一次详情接口，确认**对外返回**的也是旧价（不是只在 ORM 里对）
        detail = client.get(f'/api/v1/orders/{order_id}/').json()['data']
        assert Decimal(str(detail['grand_total'])) == Decimal('200.00'), (
            'API 返回的总额被改价影响了')

    def test_t3_new_order_uses_new_price(self):
        user, product, sku, client = self._ready('100.00')
        self._checkout(client)

        sku.price = Decimal('150.00')
        sku.save(update_fields=['price'])

        _basket(user, sku, 2)          # 重新加购（checkout 会清空购物车）
        data = self._checkout(client)
        order = Order.objects.get(pk=data['id'])
        assert order.items.first().unit_price == Decimal('150.00'), (
            '新订单没按新价 —— 说明"改价"本身没生效，T2 的通过可能是假绿')
        assert order.grand_total == Decimal('300.00')
