from rest_framework import serializers
from core.serializers import BaseModelSerializer
from apps.transactions.models import Order, OrderItem, Quote, QuoteItem, Basket, Wishlist


class OrderItemSerializer(BaseModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product_id', 'sku_id', 'quantity', 'unit_price']


class OrderListSerializer(BaseModelSerializer):
    class Meta:
        model = Order
        fields = ['id', 'order_no', 'status', 'subtotal', 'grand_total', 'currency', 'created_at']


class OrderDetailSerializer(BaseModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_no', 'user_id', 'status', 'subtotal', 'tax_total',
            'grand_total', 'currency', 'comment', 'items', 'created_at', 'updated_at',
        ]


class QuoteItemSerializer(BaseModelSerializer):
    class Meta:
        model = QuoteItem
        fields = ['id', 'product_id', 'sku_id', 'quantity', 'unit_price', 'note']


class QuoteListSerializer(BaseModelSerializer):
    class Meta:
        model = Quote
        fields = ['id', 'quote_no', 'company_name', 'contact_name', 'status', 'grand_total', 'created_at']


class QuoteDetailSerializer(BaseModelSerializer):
    items = QuoteItemSerializer(many=True, read_only=True)

    class Meta:
        model = Quote
        fields = [
            'id', 'quote_no', 'user_id', 'company_name', 'contact_name',
            'contact_email', 'contact_phone', 'country', 'status',
            'valid_until', 'subtotal', 'grand_total', 'remark',
            'items', 'created_at', 'updated_at',
        ]


class BasketSerializer(BaseModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    sku_code = serializers.CharField(source='sku.sku_code', read_only=True)

    class Meta:
        model = Basket
        fields = ['id', 'product_id', 'sku_id', 'quantity', 'session_key', 'product_name', 'sku_code']


class WishlistSerializer(BaseModelSerializer):
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Wishlist
        fields = ['id', 'name', 'product_count', 'created_at']

    def get_product_count(self, obj):
        return obj.products.count()
