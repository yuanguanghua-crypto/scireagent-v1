from decimal import Decimal

from rest_framework import serializers
from core.serializers import BaseModelSerializer
from apps.transactions.models import (
    Order, OrderItem, Invoice, PaymentRecord, ShippingRecord,
    ShippingRecordItem, PoAttachment, StatusLog,
    Quote, QuoteItem, Basket, Wishlist,
)

# PO 附件白名单 + 大小上限（Service 层也会复校）
PO_ATTACHMENT_ALLOWED_MIME = {'application/pdf', 'image/png', 'image/jpeg'}
PO_ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024


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


class StatusLogSerializer(BaseModelSerializer):
    """状态/操作时间线（前端统一渲染来源）。"""
    class Meta:
        model = StatusLog
        fields = [
            'id', 'order_id', 'actor_id', 'action_type',
            'from_status', 'to_status', 'note', 'created_at',
        ]


class ShippingRecordItemSerializer(BaseModelSerializer):
    order_item_id = serializers.IntegerField(read_only=True)
    sku_code = serializers.CharField(source='order_item.sku.sku_code', read_only=True)

    class Meta:
        model = ShippingRecordItem
        fields = ['id', 'order_item_id', 'quantity', 'sku_code']


class OrderDetailSerializer(BaseModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    invoice = serializers.SerializerMethodField()
    shipments = serializers.SerializerMethodField()
    status_logs = StatusLogSerializer(many=True, read_only=True)
    internal_notes = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_no', 'user_id', 'organization_id', 'status',
            'payment_method', 'po_number', 'po_contact', 'payment_terms', 'payment_due_date',
            'assigned_rep_id', 'grant_code', 'shipping_method',
            'requested_delivery_date', 'etd', 'quote_id',
            'shipping_address_ref_id', 'billing_address_ref_id',
            'subtotal', 'tax_total', 'grand_total', 'currency',
            'shipping_name', 'shipping_address', 'shipping_phone', 'shipping_email',
            'billing_name', 'billing_address',
            'notes', 'internal_notes', 'comment',
            'items', 'invoice', 'shipments', 'status_logs',
            'created_at', 'updated_at',
        ]

    def get_internal_notes(self, obj):
        request = self.context.get('request')
        if request and request.user and request.user.is_staff:
            return obj.internal_notes
        return None

    def get_invoice(self, obj):
        if hasattr(obj, 'invoice') and obj.invoice:
            return InvoiceSerializer(obj.invoice).data
        return None

    def get_shipments(self, obj):
        if hasattr(obj, 'shipments'):
            return ShippingRecordSerializer(obj.shipments.all(), many=True).data
        return []


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
    items = ShippingRecordItemSerializer(many=True, read_only=True)

    class Meta:
        model = ShippingRecord
        fields = [
            'id', 'order_id', 'status', 'carrier', 'tracking_number',
            'tracking_url', 'shipped_at', 'estimated_delivery',
            'delivered_at', 'received_by', 'notes', 'items',
        ]


class ShipmentCreateSerializer(serializers.Serializer):
    """新建发货记录（支持分批发）入参。"""
    carrier = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    tracking_number = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    tracking_url = serializers.URLField(required=False, allow_blank=True, default='')
    estimated_delivery = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    items = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=False,
    )


class PoAttachmentSerializer(BaseModelSerializer):
    """PO 附件 — 双校验白名单 MIME + ≤10MB（Service 层也会复校）。"""
    class Meta:
        model = PoAttachment
        fields = [
            'id', 'order_id', 'file', 'original_filename',
            'mime_type', 'file_size', 'uploaded_by_id', 'created_at',
        ]
        read_only_fields = ['id', 'original_filename', 'mime_type', 'file_size', 'uploaded_by_id', 'created_at']

    def validate_file(self, value):
        if value.content_type not in PO_ATTACHMENT_ALLOWED_MIME:
            raise serializers.ValidationError(
                f"Unsupported file type '{value.content_type}'. Allowed: pdf, png, jpeg."
            )
        if value.size > PO_ATTACHMENT_MAX_BYTES:
            raise serializers.ValidationError('File too large (max 10MB).')
        return value


class InvoiceIssueSerializer(serializers.Serializer):
    payment_terms = serializers.ChoiceField(
        choices=Order.PaymentTerms.choices, required=False, default=Order.PaymentTerms.NET30
    )


class PaymentCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0'))
    method = serializers.ChoiceField(choices=PaymentRecord.Method.choices)
    paid_at = serializers.DateTimeField(required=False)
    reference = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class PoSubmitItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(required=False, allow_null=True)
    sku_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0'))


class PoSubmitSerializer(serializers.Serializer):
    """PO 提交入参。"""
    po_number = serializers.CharField(max_length=100)
    quote_id = serializers.IntegerField(required=False, allow_null=True)
    grant_code = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    shipping_method = serializers.ChoiceField(
        choices=Order.ShippingMethod.choices, required=False, allow_blank=True, default=''
    )
    requested_delivery_date = serializers.DateField(required=False, allow_null=True)
    shipping_name = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    shipping_address = serializers.CharField(required=False, allow_blank=True, default='')
    shipping_phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default='')
    shipping_email = serializers.EmailField(required=False, allow_blank=True, default='')
    billing_name = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    billing_address = serializers.CharField(required=False, allow_blank=True, default='')
    shipping_address_ref_id = serializers.IntegerField(required=False, allow_null=True)
    billing_address_ref_id = serializers.IntegerField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    items = PoSubmitItemSerializer(many=True)



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
