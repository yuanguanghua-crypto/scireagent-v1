from rest_framework import serializers
from core.serializers import BaseModelSerializer
from apps.transactions.models import (
    Order, OrderItem, Invoice, PaymentRecord, ShippingRecord,
    Quote, QuoteItem, Basket, Wishlist,
)


# ── Order ──

class OrderItemSerializer(BaseModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    sku_code = serializers.CharField(source='sku.sku_code', read_only=True)
    pack_size = serializers.CharField(source='sku.pack_size', read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'product_id', 'product_name', 'sku_id', 'sku_code', 'pack_size', 'quantity', 'unit_price', 'subtotal']


class OrderListSerializer(BaseModelSerializer):
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_no', 'status', 'payment_method', 'po_number',
            'grand_total', 'currency', 'items_count', 'created_at',
        ]

    def get_items_count(self, obj):
        return obj.items.count()


class OrderDetailSerializer(BaseModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    invoice = serializers.SerializerMethodField()
    shipping = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_no', 'user_id', 'organization_id', 'status',
            'payment_method', 'po_number', 'po_contact', 'payment_terms', 'payment_due_date',
            'subtotal', 'tax_total', 'grand_total', 'currency',
            'shipping_name', 'shipping_address', 'shipping_phone', 'shipping_email',
            'billing_name', 'billing_address',
            'notes', 'internal_notes', 'comment',
            'items', 'invoice', 'shipping',
            'created_at', 'updated_at',
        ]

    def get_invoice(self, obj):
        if hasattr(obj, 'invoice') and obj.invoice:
            return InvoiceSerializer(obj.invoice).data
        return None

    def get_shipping(self, obj):
        if hasattr(obj, 'shipping') and obj.shipping:
            return ShippingRecordSerializer(obj.shipping).data
        return None


# ── Checkout ──

class CheckoutSerializer(serializers.Serializer):
    PAYMENT_METHOD_CHOICES = ['purchase_order', 'credit_card', 'wire_transfer', 'quote']

    payment_method = serializers.ChoiceField(choices=PAYMENT_METHOD_CHOICES)
    po_number = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    po_contact = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    shipping_name = serializers.CharField(max_length=200)
    shipping_address = serializers.CharField()
    shipping_phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default='')
    shipping_email = serializers.EmailField(required=False, allow_blank=True, default='')
    billing_name = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    billing_address = serializers.CharField(required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        if data['payment_method'] == 'purchase_order' and not data.get('po_number'):
            raise serializers.ValidationError({'po_number': 'PO number is required for purchase order payment.'})
        if not data.get('shipping_name') or not data.get('shipping_address'):
            raise serializers.ValidationError('Shipping name and address are required.')
        return data


# ── Invoice ──

class InvoiceSerializer(BaseModelSerializer):
    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_no', 'order_id', 'status',
            'issued_at', 'due_date', 'paid_at',
            'subtotal', 'tax_total', 'grand_total', 'currency',
            'payment_ref', 'notes', 'created_at',
        ]


# ── Payment ──

class PaymentRecordSerializer(BaseModelSerializer):
    class Meta:
        model = PaymentRecord
        fields = [
            'id', 'invoice_id', 'method', 'amount', 'currency',
            'reference', 'proof_file', 'status',
            'verified_by', 'verified_at', 'notes', 'created_at',
        ]
        read_only_fields = ['id', 'status', 'verified_by', 'verified_at', 'created_at']


class PaymentProofSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


# ── Shipping ──

class ShippingRecordSerializer(BaseModelSerializer):
    class Meta:
        model = ShippingRecord
        fields = [
            'id', 'order_id', 'status', 'carrier', 'tracking_number',
            'tracking_url', 'shipped_at', 'estimated_delivery',
            'delivered_at', 'notes',
        ]


class AdminShipSerializer(serializers.Serializer):
    carrier = serializers.CharField(max_length=100)
    tracking_number = serializers.CharField(max_length=200)
    tracking_url = serializers.URLField(required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')


# ── Admin Actions ──

class AdminQuoteSerializer(serializers.Serializer):
    grand_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    valid_until = serializers.DateField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class AdminVerifyPaymentSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField()
    action = serializers.ChoiceField(choices=['verify', 'reject'])
    notes = serializers.CharField(required=False, allow_blank=True, default='')


# ── Quote (legacy) ──

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


# ── Basket / Wishlist ──

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
