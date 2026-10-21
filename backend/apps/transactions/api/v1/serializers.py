from decimal import Decimal

from rest_framework import serializers
from core.business_time import business_today
from core.serializers import BaseModelSerializer
# ★ import 方向已核实：commerce 侧（serializers / models / services / knowledge）
#   **不反向依赖** transactions ⇒ 模块级 import 无循环风险。
#   复用既有 ProductListSerializer，避免为收藏夹另造一套精简产品字段。
from apps.commerce.api.v1.serializers import ProductListSerializer
from apps.commerce.models import Product
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
    sku_available = serializers.SerializerMethodField()  # ★ P1-1：审核台库存可分配量
    # ★ 2026-10-21 修 D6（P1·合规误标）：前端 `PoOrderDetail.vue:105` 用
    #   `order.items?.some(it => it.is_ruo !== false)` 决定是否显示
    #   "For Research Use Only. Not for use in diagnostic or therapeutic procedures."，
    #   但本序列化器**从未返回 `is_ruo`** ⇒ `undefined !== false` 恒真
    #   ⇒ **每张订单都显示该声明**，哪怕产品明确不是 RUO。
    #   三态语义：True=确认 RUO / False=确认非 RUO / None=无法判定（产品已被删，SET_NULL）。
    #   前端用 `!== false` 判定 ⇒ None 时**保守显示**（合规优先：宁可多声明，不可漏声明）。
    is_ruo = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            'id', 'product_id', 'product_name', 'sku_id', 'sku_code', 'pack_size',
            'quantity', 'unit_price', 'subtotal', 'sku_available', 'is_ruo',
        ]

    def get_is_ruo(self, obj):
        """产品是否「仅限研究用途」。字段来源 `Product.research_use_only`
        （`apps/commerce/models.py:157`，default=True）。"""
        product = getattr(obj, 'product', None)
        if product is None:
            return None
        return bool(product.research_use_only)

    def get_sku_available(self, obj):
        from apps.inventory.services import InventoryService
        if not obj.sku_id:
            return 0
        return InventoryService.available_for_sku(obj.sku_id)['available']


class OrderListSerializer(BaseModelSerializer):
    items_count = serializers.SerializerMethodField()
    # ★ 2026-09-24 收紧：本序列化器同时用于 `OrderViewSet` 的 **list 与 create**
    #   （`views.py:12` 与 `get_serializer_class`），而 `status` / `grand_total` 此前**可写**
    #   ⇒ 匿名 `POST /orders/` 能造出「`status=completed`、`grand_total=0.01`、`user=null`」的订单
    #   （2026-09-24 以生产实测确认：HTTP **201** 且 DB 落库）。这两个字段本应由**服务端**决定
    #   （授权路径有 `/checkout/`、`POSubmitView` 等）⇒ 改 `read_only`：
    #   读行为不变；创建时回落到模型默认（`status=DRAFT` / `grand_total=0`）。
    #   注意前端**不使用** `POST /orders/`（下单走 `/checkout/`、PO 走 `/orders/po/`）⇒ 无影响。
    status = serializers.CharField(read_only=True)
    grand_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

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
    # ★ 2026-10-16 修 P0：原default='' 与模型 default='' 叠加，空串订单会撞唯一约束。
    #   改为 default=None + allow_null，让"未填 PO 号"落NULL（不进唯一索引），
    #   与 checkout_views.py:69 的 `data.get('po_number') or None` 口径一致。
    po_number = serializers.CharField(
        max_length=100, required=False, allow_blank=True, allow_null=True, default=None)
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
    amount_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    balance_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_no', 'order_id', 'status',
            'issued_at', 'due_date', 'paid_at',
            'subtotal', 'tax_total', 'grand_total', 'currency',
            'payment_ref', 'notes', 'created_at',
            'amount_paid', 'balance_due',
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


class ShipmentItemSerializer(serializers.Serializer):
    """发货明细项 —— 与 `ShippingService.create_shipment` 的取值约定保持一致。

    ★ 2026-10-13 新增：此前 `ShipmentCreateSerializer.items` 用 `ListField(child=DictField())`
    **完全不校验结构**，服务层直接取 `it['order_item_id']` ⇒ 缺字段抛 KeyError（500）。
    前端 `PoShipmentDesk.vue` 恰好发的结构正确，所以 UI 不踩；但任何 API 消费者/集成方都会吃到 500。
    """

    order_item_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=10000)


class ShipmentCreateSerializer(serializers.Serializer):
    """新建发货记录（支持分批发）入参。"""
    carrier = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    tracking_number = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    tracking_url = serializers.URLField(required=False, allow_blank=True, default='')
    estimated_delivery = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    # ★ 结构不对 ⇒ 400 带字段错误（不再 500）
    items = ShipmentItemSerializer(many=True, allow_empty=False)


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
    quantity = serializers.IntegerField(min_value=1, max_value=10000)
    # ★ 2026-10-21 F5（纵深防御）：单价改为 read_only —— **客户端不可提交**。
    #   此前安全性只靠 `PoSubmissionService` 用 `sku.price` 强制覆盖（services.py:132-141），
    #   是**单点防御**：任何人新增复用本序列化器的写端点、或改动服务层，价格篡改立刻敞开。
    #   DRF 语义：read_only 字段**直接忽略入参**，不会因为前端继续发 unit_price 而报 400
    #   ⇒ **前端零改动**（`validated_data` 里不再出现该键）。
    #   ⚠️ 服务层那道 `unit_price = sku.price or 0` 覆盖**必须保留**（第二道防线）。
    #   回归：apps/transactions/tests/test_po_unit_price_readonly.py
    unit_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal('0'), read_only=True)

    def validate_sku_id(self, value):
        """★ v4.1 对抗性自测 Fix：sku_id 必须指向真实存在的 SKU（此前 500）。"""
        from apps.commerce.models import SKU
        if not SKU.objects.filter(pk=value).exists():
            raise serializers.ValidationError(f'SKU {value} does not exist')
        return value


class PoSubmitSerializer(serializers.Serializer):
    """PO 提交入参。"""
    po_number = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
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

    def validate_requested_delivery_date(self, value):
        """交付日期不得早于今天（运行时校验，避免迁移/时区硬编码带来的下限漂移）。
        value 为 None 时跳过（该字段 required=False, allow_null=True）。

        ★ 必须用 business_today()，不能用 date.today()：
          date.today() 取的是**进程操作系统时区**；生产容器 TZ 为 UTC 时它等于
          UTC 日期，而东八区 00:00-07:59 期间 UTC 日期比业务日期晚一天 ⇒
          用户能提交"昨天"的交付日期并通过校验。"""
        if value is not None and value < business_today():
            raise serializers.ValidationError(
                'Requested delivery date cannot be in the past.'
            )
        return value



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
    """收藏夹：读带完整产品，写用 `product_ids` **整体替换**。

    ★ 2026-10：此前只有 `product_count`，`products`（M2M）完全未暴露
      ⇒ 前端无法加/删收藏。现补：
      - `products`（只读嵌套，复用 `ProductListSerializer`）；
      - `product_ids`（只写，`source='products'`）⇒ DRF 的 `.set()` 语义是
        **整体替换**（`[1,2]` ⇒ 恰好这两个；`[]` ⇒ 清空），不是追加；
      - 省略 `product_ids` ⇒ 产品不动（`required=False`）。
      - 只接受 `archived=False` 的产品：归档产品 id 会在**字段校验阶段**失败（400），
        不会部分写入（校验先于 `create`/`update`）。
    """
    product_count = serializers.SerializerMethodField()
    products = ProductListSerializer(many=True, read_only=True)
    product_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        write_only=True,
        required=False,
        source='products',
        queryset=Product.objects.filter(archived=False),
    )

    class Meta:
        model = Wishlist
        fields = ['id', 'name', 'product_count', 'products', 'product_ids', 'created_at']

    def get_product_count(self, obj):
        return obj.products.count()
