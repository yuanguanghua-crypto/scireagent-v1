from django.test import TestCase
from decimal import Decimal
from apps.transactions.api.v1.serializers import (
    OrderListSerializer, OrderDetailSerializer, OrderItemSerializer,
    QuoteListSerializer, QuoteDetailSerializer, QuoteItemSerializer,
    BasketSerializer, WishlistSerializer
)
from apps.transactions.tests.factories import (
    OrderFactory, OrderItemFactory, QuoteFactory, QuoteItemFactory,
    BasketFactory, WishlistFactory
)


class OrderListSerializerTest(TestCase):
    def test_fields(self):
        order = OrderFactory(order_no='ORD-001')
        serializer = OrderListSerializer(order)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('order_no', data)
        self.assertIn('status', data)
        self.assertIn('grand_total', data)
        self.assertIn('currency', data)
        self.assertIn('created_at', data)


class OrderDetailSerializerTest(TestCase):
    def test_items_field(self):
        order = OrderFactory()
        OrderItemFactory(order=order, quantity=2)
        OrderItemFactory(order=order, quantity=3)
        serializer = OrderDetailSerializer(order)
        self.assertEqual(len(serializer.data['items']), 2)

    def test_extra_fields(self):
        order = OrderFactory()
        serializer = OrderDetailSerializer(order)
        data = serializer.data
        self.assertIn('tax_total', data)
        self.assertIn('comment', data)
        self.assertIn('user_id', data)


class OrderItemSerializerTest(TestCase):
    def test_fields(self):
        item = OrderItemFactory(quantity=5, unit_price=Decimal('19.99'))
        serializer = OrderItemSerializer(item)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('product_id', data)
        self.assertIn('sku_id', data)
        self.assertIn('quantity', data)
        self.assertIn('unit_price', data)
        # ★ 2026-10-21 D6：`is_ruo` 必须出现在明细里（缺它 ⇒ 前端 `!== false` 恒真）
        self.assertIn('is_ruo', data)


class OrderItemIsRuoTest(TestCase):
    """D6 回归：明细的 `is_ruo` 必须真实反映产品 `research_use_only`。

    缺陷现场（2026-10-21 全站测试发现，P1·合规误标）：
      `PoOrderDetail.vue:105` 用
        `v-if="order.items?.some(it => it.is_ruo !== false)"`
      决定是否显示 "For Research Use Only. Not for use in diagnostic or therapeutic procedures."，
      但 `OrderItemSerializer.fields` 里**没有 `is_ruo`**
      ⇒ `undefined !== false` 恒为真 ⇒ **每张订单都显示该声明**，哪怕产品明确不是 RUO。
      实测：明细 items 的键里查不到 `is_ruo`（`serializers.py:31-35`）。

    字段来源：`Product.research_use_only`（`apps/commerce/models.py:157`，default=True）。
    `OrderItem.product` 是 `null=True` + `on_delete=SET_NULL` ⇒ 产品被删后无法判定，
    此时返回 `None`，前端 `!== false` 会**保守显示**声明（合规优先：宁可多声明，不可漏声明）。
    """

    def test_true_when_product_is_ruo(self):
        item = OrderItemFactory(product__research_use_only=True)
        self.assertIs(OrderItemSerializer(item).data['is_ruo'], True)

    def test_false_when_product_is_not_ruo(self):
        """★ 关键反向断言：非 RUO 产品必须返回 False，前端才会**不显示**声明。"""
        item = OrderItemFactory(product__research_use_only=False)
        self.assertIs(OrderItemSerializer(item).data['is_ruo'], False)

    def test_none_when_product_deleted(self):
        """产品被删（SET_NULL）⇒ None（无法判定），前端保守显示。"""
        item = OrderItemFactory(product=None)
        self.assertIsNone(OrderItemSerializer(item).data['is_ruo'])


class QuoteListSerializerTest(TestCase):
    def test_fields(self):
        quote = QuoteFactory(quote_no='QT-001')
        serializer = QuoteListSerializer(quote)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('quote_no', data)
        self.assertIn('company_name', data)
        self.assertIn('contact_name', data)
        self.assertIn('status', data)
        self.assertIn('grand_total', data)


class QuoteDetailSerializerTest(TestCase):
    def test_items_field(self):
        quote = QuoteFactory()
        QuoteItemFactory(quote=quote)
        serializer = QuoteDetailSerializer(quote)
        self.assertEqual(len(serializer.data['items']), 1)

    def test_extra_fields(self):
        quote = QuoteFactory()
        serializer = QuoteDetailSerializer(quote)
        data = serializer.data
        self.assertIn('contact_email', data)
        self.assertIn('contact_phone', data)
        self.assertIn('country', data)
        self.assertIn('valid_until', data)
        self.assertIn('remark', data)


class QuoteItemSerializerTest(TestCase):
    def test_fields(self):
        item = QuoteItemFactory()
        serializer = QuoteItemSerializer(item)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('product_id', data)
        self.assertIn('sku_id', data)
        self.assertIn('quantity', data)
        self.assertIn('unit_price', data)
        self.assertIn('note', data)


class BasketSerializerTest(TestCase):
    def test_fields(self):
        basket = BasketFactory()
        serializer = BasketSerializer(basket)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('product_id', data)
        self.assertIn('sku_id', data)
        self.assertIn('quantity', data)
        self.assertIn('product_name', data)
        self.assertIn('sku_code', data)

    def test_product_name_source(self):
        basket = BasketFactory()
        serializer = BasketSerializer(basket)
        self.assertEqual(serializer.data['product_name'], basket.product.name)

    def test_sku_code_source(self):
        basket = BasketFactory()
        serializer = BasketSerializer(basket)
        self.assertEqual(serializer.data['sku_code'], basket.sku.sku_code)


class WishlistSerializerTest(TestCase):
    def test_fields(self):
        wishlist = WishlistFactory(name='My List')
        serializer = WishlistSerializer(wishlist)
        data = serializer.data
        self.assertIn('id', data)
        self.assertIn('name', data)
        self.assertIn('product_count', data)

    def test_product_count(self):
        from apps.commerce.tests.factories import ProductFactory
        wishlist = WishlistFactory()
        p1 = ProductFactory()
        p2 = ProductFactory()
        wishlist.products.add(p1, p2)
        serializer = WishlistSerializer(wishlist)
        self.assertEqual(serializer.data['product_count'], 2)

    def test_product_count_empty(self):
        wishlist = WishlistFactory()
        serializer = WishlistSerializer(wishlist)
        self.assertEqual(serializer.data['product_count'], 0)
