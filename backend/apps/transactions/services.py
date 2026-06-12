import uuid
from django.db import transaction
from .models import Order, OrderItem, Basket


class TransactionService:
    """交易层域服务"""

    @staticmethod
    @transaction.atomic
    def create_order(user, items_data: list) -> Order:
        """创建订单及其明细"""
        order = Order.objects.create(
            user=user,
            order_no=f'ORD-{uuid.uuid4().hex[:8].upper()}',
        )
        total = 0
        for item in items_data:
            OrderItem.objects.create(order=order, **item)
            total += item.get('unit_price', 0) * item.get('quantity', 1)
        order.subtotal = total
        order.grand_total = total
        order.save(update_fields=['subtotal', 'grand_total'])
        return order

    @staticmethod
    def add_to_basket(user, product_id, sku_id, quantity=1):
        """添加商品到购物车"""
        basket_item, created = Basket.objects.update_or_create(
            user=user, sku_id=sku_id,
            defaults={'product_id': product_id, 'quantity': quantity}
        )
        return basket_item
