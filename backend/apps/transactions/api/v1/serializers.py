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
    # ★ 2026-11-26（A-080 止损）：三个商品标识字段改为**快照优先、实时回退**。
    #
    #   改前是纯实时 join（`source='sku.sku_code'` / `source='product.name'`），
    #   而 `sku` / `product` 都是 `SET_NULL` ⇒ 主数据一删，这些字段就永远返回空，
    #   前端渲染成 "—"。生产实测：89 行明细里 32 行（36%）已经变成空白，
    #   涉及 16 单、合计占全库 GMV 的 99%。
    #
    #   回退顺序：快照（下单那一刻拷贝的）→ 实时 join → 空串。
    #   老数据没有快照但主数据还在时，仍能正常显示（快照字段由 save() 自动补，
    #   存量行用 `backfill_order_item_snapshots` 命令回填）。
    product_name = serializers.SerializerMethodField()
    sku_code = serializers.SerializerMethodField()
    pack_size = serializers.SerializerMethodField()
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

    def get_product_name(self, obj):
        if obj.product_name_snapshot:
            return obj.product_name_snapshot
        return obj.product.name if obj.product_id else ''

    def get_sku_code(self, obj):
        if obj.sku_code_snapshot:
            return obj.sku_code_snapshot
        return obj.sku.sku_code if obj.sku_id else ''

    def get_pack_size(self, obj):
        """规格：快照优先（SKU 被删后仍可读），回退 SKU 实时值。"""
        if obj.sku_spec_snapshot:
            return obj.sku_spec_snapshot
        if not obj.sku_id:
            return ''
        return ' · '.join(x for x in (obj.sku.pack_size, obj.sku.concentration) if x)

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


# ── ★ 2026-11-26（A-077）：客户身份的取值实现（列表与详情共用同一份）──
#
# ⚠️ 为什么是**模块级函数**而不是「mixin 里声明字段」：
#   DRF 的 `SerializerMetaclass` 只在**直接以 Serializer 为基类**的类上构建
#   `_declared_fields`；普通 mixin 类体里写的 `serializers.SerializerMethodField()`
#   收集不到 ⇒ 子类 `Meta.fields` 会直接抛
#       ImproperlyConfigured: Field name `customer_name` is not valid for model `Order`
#   （本轮已实测踩到，整包 30 条测试全红）。
#   所以字段声明必须写在每个序列化器**自己的类体**里 —— 与本文件既有的
#   `knowledge` 侧 `MethodApplicationWriteMixin` 约定一致：mixin 只放方法，不放字段。
#   取值逻辑放这里共享，避免列表与详情两份 getter 日后漂移
#   （A-102「Method 列表 protocol_count 与详情不同源」就是这么来的）。
#
# 安全面：`OrderListSerializer` **同时服务客户端** `/orders/` 列表，但
#   `OrderViewSet.get_queryset` 对非内部人员只返回 `user=request.user` 的单
#   ⇒ 客户看到的只是**他自己的**姓名/邮箱/组织，不构成横向泄露。
#
# 性能：启用这两组字段的 queryset 必须 `select_related('user', 'organization')`，
#   否则每行多 2 次查询（100 行 = 200 次）。已接的三处：
#     · `views.py` `OrderViewSet.get_queryset`
#     · `admin_order_views.py` `AdminOrderListView.get`
#     · `admin_order_views.py` `AdminOrderDetailView.get`

def customer_name_of(obj):
    """客户姓名；无 first/last name 时回落用户名（本项目账号多为 username 型）。"""
    user = obj.user
    if not user:
        return ''
    return (user.get_full_name() or '').strip() or user.username or ''


def customer_email_of(obj):
    # 用户已明确要求列表也带邮箱（运营要在列表上直接联系客户）。
    return (obj.user.email if obj.user else '') or ''


def organization_name_of(obj):
    return obj.organization.name if obj.organization else ''


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

    # ★ 2026-10-22 修「下载中心永远空态」：
    #   `PoDownloadCenter.vue:18-21` 用 `o.invoice || o.attachments.length` 过滤订单，
    #   但本序列化器此前**不返回这两个字段** ⇒ 客户即使有已开票订单 + PO 附件，
    #   页面也永远显示 `No downloadable documents yet`。
    #   这里只暴露前端需要的**最小子集**（不把整张发票/全部附件字段倒出来）：
    #     invoice      → {id, invoice_no}   供显示单号 + 下载 PDF
    #     attachments  → [{id, original_filename}]  供按钮标签 + 下载
    #   查询侧已在 ViewSet 的 get_queryset 加 select_related/prefetch，避免 N+1。
    invoice = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()

    # ★ 2026-11-26（A-077）：客户身份三字段（取值见文件上方 `customer_name_of` 等）。
    #   此前列表的 CUSTOMER 列渲染的是 `order.user_id`（`AdminOrdersPage.vue:117`）——
    #   一个**裸数字 id**，而 `user` 为 NULL 时整列空白（QA Batch 8 实测 21 行全空）；
    #   详情页（`AdminOrderDetail.vue:258-259`）也只有 "User ID 12 / Org ID 16"。
    #   ⚠️ 字段必须在类体里声明，不能挪进 mixin（原因见文件上方注释）。
    customer_name = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    organization_name = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_no', 'status', 'payment_method', 'po_number',
            'grand_total', 'currency', 'items_count', 'created_at',
            'invoice', 'attachments',
            # ★ 2026-10-28：补 4 个运营审核必需字段。
            #   此前缺失导致 PoReviewDesk 的 Grant Code / Shipping Method / Ship-to
            #   三格恒为 undefined ⇒ 模板 `|| '—'` 恒显示破折号，把一个**有地址的订单**
            #   显示成没有地址（实测 ORD-A382B455 真实 Ship-to 是 "test001 — test"）。
            #   安全面：`OrderViewSet` 自 2026-10-21 F4 起 `http_method_names` 只读
            #   （views.py:23），本序列化器**没有**任何写入口 ⇒ 加字段只是加读取，
            #   不引入新的可写字段。
            'grant_code', 'shipping_method', 'shipping_name', 'shipping_address',
            # ★ 2026-11-26（A-077）：客户身份（只读派生，见上）
            'customer_name', 'customer_email', 'organization_name',
        ]

    def get_customer_name(self, obj):
        return customer_name_of(obj)

    def get_customer_email(self, obj):
        return customer_email_of(obj)

    def get_organization_name(self, obj):
        return organization_name_of(obj)

    def get_items_count(self, obj):
        # 用索引访问已 prefetch 的缓存；未 prefetch 时退化为一次 COUNT（与原行为一致）
        return len(obj.items.all())

    def get_invoice(self, obj):
        # reverse OneToOne：不存在时抛 RelatedObjectDoesNotExist（是 AttributeError 子类）
        inv = getattr(obj, 'invoice', None)
        if inv is None:
            return None
        return {'id': inv.id, 'invoice_no': inv.invoice_no}

    def get_attachments(self, obj):
        return [
            {'id': a.id, 'original_filename': a.original_filename}
            for a in obj.attachments.all()
        ]


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
    # ★ 2026-11-26（A-077）：详情页 Customer 区此前只有 "User ID 12 / Org ID 16"，
    #   运营联系不上客户。取值与列表同源（文件上方 `customer_name_of` 等）。
    customer_name = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    organization_name = serializers.SerializerMethodField()

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
            # ★ 2026-11-26（A-077）：详情页 Customer 区此前只有 "User ID 12 / Org ID 16"，
            #   运营联系不上客户。三字段由 `CustomerFieldsMixin` 提供（与列表同源）。
            'customer_name', 'customer_email', 'organization_name',
            'created_at', 'updated_at',
        ]

    def get_internal_notes(self, obj):
        request = self.context.get('request')
        if request and request.user and request.user.is_staff:
            return obj.internal_notes
        return None

    def get_customer_name(self, obj):
        return customer_name_of(obj)

    def get_customer_email(self, obj):
        return customer_email_of(obj)

    def get_organization_name(self, obj):
        return organization_name_of(obj)

    def get_invoice(self, obj):
        if hasattr(obj, 'invoice') and obj.invoice:
            # ★ 必须传 context：PaymentRecordSerializer 靠 request.user 判定是否暴露凭证 URL，
            #   不传就会永远当成「外部用户」⇒ 运营在订单详情里也下不到凭证。
            return InvoiceSerializer(obj.invoice, context=self.context).data
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

class PaymentRecordSerializer(BaseModelSerializer):
    """付款记录。**`proof_file` 按角色区分**（2026-10-29）。

    付款凭证是银行回单/转账截图，含账号、户名、流水号 —— 属于敏感财务信息。
    而 `MEDIA_URL` 在生产由 nginx 静态直出、不带鉴权 ⇒ 只要拿到 URL 谁都能下。
    所以：**只有内部人员拿得到 URL，客户只拿到 `has_proof` 布尔**。
    客户本来也不需要点开自己的回单（他手上就有原件）。
    """
    proof_file = serializers.SerializerMethodField()
    has_proof = serializers.SerializerMethodField()

    class Meta:
        model = PaymentRecord
        fields = [
            'id', 'invoice_id', 'method', 'amount', 'currency',
            'reference', 'proof_file', 'has_proof', 'status',
            'verified_by', 'verified_at', 'notes', 'created_at',
        ]
        read_only_fields = ['id', 'status', 'verified_by', 'verified_at', 'created_at']

    def _is_internal(self) -> bool:
        req = self.context.get('request')
        u = getattr(req, 'user', None)
        return bool(u and u.is_authenticated
                    and (u.is_staff or getattr(u, 'role', '') in ('procurement', 'admin')))

    def get_proof_file(self, obj):
        if not obj.proof_file:
            return None
        return obj.proof_file.url if self._is_internal() else None

    def get_has_proof(self, obj):
        return bool(obj.proof_file)


class InvoiceSerializer(BaseModelSerializer):
    amount_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    balance_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    # ★ 2026-10-29：暴露付款记录。客户靠它看到「我传的凭证在审」，
    #   运营靠它看到「有人上传了凭证待核验」。没有这个字段，
    #   两边都不知道对方做了什么。
    payments = PaymentRecordSerializer(many=True, read_only=True)

    class Meta:
        model = Invoice
        fields = [
            'id', 'invoice_no', 'order_id', 'status',
            'issued_at', 'due_date', 'paid_at',
            'subtotal', 'tax_total', 'grand_total', 'currency',
            'payment_ref', 'notes', 'created_at',
            'amount_paid', 'balance_due', 'payments',
        ]


# ── Payment ──

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

    def validate(self, attrs):
        """★ 2026-11-18（A-095）：`carrier` 与 `tracking_number` **至少填一个** → 否则 400。

        背景：两个字段原先都是 `required=False, allow_blank=True, default=''`
        ⇒ 后端**主动接受**一次「无承运商、无单号、无备注」的发货：`ShippingRecord`
        落一条全空记录、订单状态照样推进到 shipped，客户收到的邮件里没有任何可追踪信息。

        为什么是"至少一个"而不是"两个都必填"：
          · 真实履约里有「承运商已知、单号稍后补」（先用 DHL 揽收，晚些拿到运单号）；
          · 也有「客户自提/本地配送」：只有承运商名字（或反之）。
          强行两个都必填只会逼运营填 `N/A` 这种假数据，反而让记录更难用。
          但**两个都空**在任何场景下都没有意义 —— 那条记录既追踪不了也索赔不了。

        错误挂在 `non_field_errors`（跨字段规则），由 `core/exceptions.py` 的格式化器
        直接作为 message 呈现，不加字段前缀。
        """
        attrs = super().validate(attrs)
        carrier = (attrs.get('carrier') or '').strip()
        tracking = (attrs.get('tracking_number') or '').strip()
        if not carrier and not tracking:
            raise serializers.ValidationError(
                'A shipment needs at least a carrier or a tracking number — '
                'otherwise the parcel can\'t be traced or claimed. Please fill in one of them.'
            )
        # 顺手把纯空格归一化成空串：`'   '` 能绕过上面的判断落库成"看起来填了"的脏值
        attrs['carrier'] = carrier
        attrs['tracking_number'] = tracking
        return attrs


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
