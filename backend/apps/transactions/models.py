from django.conf import settings
from django.db import models

# ★ 业务日历日助手已下沉到 core.business_time（多个 app 共用，避免跨 app 依赖）。
#   本模块继续转发 business_today / business_day_bounds / business_timezone，
#   已有引用（含 tests/test_business_timezone.py、services.py）无需改动。
from core.business_time import business_day_bounds, business_timezone, business_today  # noqa: F401
from core.models import TimeStampedModel


class InvalidTransitionError(Exception):
    """Raised when an order status transition is not allowed."""
    pass


class Order(TimeStampedModel):
    """订单 — B2B life science order with PO/invoice/payment terms"""

    class Status(models.TextChoices):
        # ── New P0 procurement flow ──
        PO_RECEIVED = 'po_received', 'PO Received'
        CONFIRMED = 'confirmed', 'Confirmed'
        IN_PRODUCTION = 'in_production', 'In Production'
        SHIPPED = 'shipped', 'Shipped'
        DELIVERED = 'delivered', 'Delivered'
        INVOICED = 'invoiced', 'Invoiced'
        PAID = 'paid', 'Paid'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
        # ── Deprecated (legacy data only, new flow does not write) ──
        DRAFT = 'draft', 'Draft'
        PROCESSING = 'processing', 'Processing'
        QUOTE_PENDING = 'quote_pending', 'Quote Pending'
        QUOTED = 'quoted', 'Quoted'
        QUOTE_ACCEPTED = 'quote_accepted', 'Quote Accepted'
        QUOTE_REJECTED = 'quote_rejected', 'Quote Rejected'

    class PaymentMethod(models.TextChoices):
        PO = 'purchase_order', 'Purchase Order'
        CREDIT_CARD = 'credit_card', 'Credit Card'
        WIRE_TRANSFER = 'wire_transfer', 'Wire Transfer'
        QUOTE = 'quote', 'Quote'

    class PaymentTerms(models.TextChoices):
        NET30 = 'NET30', 'Net 30'
        NET45 = 'NET45', 'Net 45'
        NET60 = 'NET60', 'Net 60'

    class ShippingMethod(models.TextChoices):
        AMBIENT = 'ambient', 'Ambient'
        COLD_PACK = 'cold_pack', 'Cold Pack'
        DRY_ICE = 'dry_ice', 'Dry Ice'
        BLUE_ICE = 'blue_ice', 'Blue Ice'

    # Canonical state machine (single source of truth). Deprecated entries kept
    # only for backward-compatible replay of legacy data.
    VALID_TRANSITIONS = {
        'po_received':    ['confirmed', 'cancelled'],
        'confirmed':      ['in_production', 'shipped', 'cancelled'],
        'in_production':  ['shipped', 'cancelled'],
        'shipped':        ['delivered', 'cancelled'],
        'delivered':      ['invoiced', 'cancelled'],
        'invoiced':       ['paid', 'cancelled'],
        'paid':           ['completed'],
        'completed':      [],
        'cancelled':      [],
        # deprecated
        'draft':          ['confirmed', 'quote_pending', 'cancelled'],
        'quote_pending':  ['quoted', 'cancelled'],
        'quoted':         ['quote_accepted', 'quote_rejected'],
        'quote_accepted': ['confirmed'],
        'quote_rejected': [],
        'processing':     ['shipped'],
    }

    # Core fields
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='orders', verbose_name='用户'
    )
    organization = models.ForeignKey(
        'accounts.Organization', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='orders', verbose_name='组织'
    )
    order_no = models.CharField(max_length=50, unique=True, verbose_name='订单号')
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.DRAFT, verbose_name='状态'
    )

    # Payment
    payment_method = models.CharField(
        max_length=20, choices=PaymentMethod.choices,
        default=PaymentMethod.PO, verbose_name='付款方式'
    )
    # ★ 2026-10-16 修 P0：`unique=True` 对空串 '' 同样生效 ⇒ 任何走
    #   `Order.objects.create()` 不显式传po_number 的路径落空串后，**第二个这样的订单
    #   必然 IntegrityError（HTTP 500）**。实测：OrderViewSet.create 写权限是
    #   IsAuthenticated ⇒ 任意登录用户连建两单，第二单就 500。
    #   改为 Meta 上的**条件唯一约束**：非空 PO 号仍全局唯一；
    #   NULL / 空串不进唯一索引（PostgreSQL、SQLite 的部分唯一索引对 NULL 不去重）⇒ 可共存。
    po_number = models.CharField(max_length=100, blank=True, null=True, default='', verbose_name='PO 号')
    po_contact = models.CharField(max_length=200, blank=True, default='', verbose_name='PO 联系人')
    payment_terms = models.CharField(
        max_length=20, choices=PaymentTerms.choices,
        default=PaymentTerms.NET30, verbose_name='账期'
    )
    payment_due_date = models.DateField(null=True, blank=True, verbose_name='付款到期日')

    # ── PO Portal extensions (P0) ──
    assigned_rep = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assigned_orders',
        limit_choices_to={'role__in': ['procurement', 'admin']},
        verbose_name='负责销售'
    )
    grant_code = models.CharField(max_length=100, blank=True, default='', verbose_name='基金/赞助号')
    shipping_method = models.CharField(
        max_length=20, choices=ShippingMethod.choices,
        blank=True, default='', verbose_name='运输方式'
    )
    requested_delivery_date = models.DateField(null=True, blank=True, verbose_name='期望到货日')
    etd = models.DateField(null=True, blank=True, verbose_name='预计发货')
    quote = models.ForeignKey(
        'Quote', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orders', verbose_name='关联询价单'
    )
    shipping_address_ref = models.ForeignKey(
        'accounts.Address', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='shipping_orders', verbose_name='收货地址溯源'
    )
    billing_address_ref = models.ForeignKey(
        'accounts.Address', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='billing_orders', verbose_name='账单地址溯源'
    )

    # Totals
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='小计')
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='税费')
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='总计')
    currency = models.CharField(max_length=10, default='USD', verbose_name='币种')

    # Shipping address (snapshot at order time)
    shipping_name = models.CharField(max_length=200, blank=True, default='', verbose_name='收件人')
    shipping_address = models.TextField(blank=True, default='', verbose_name='收货地址')
    shipping_phone = models.CharField(max_length=30, blank=True, default='', verbose_name='收件电话')
    shipping_email = models.EmailField(blank=True, default='', verbose_name='收件邮箱')

    # Billing
    billing_name = models.CharField(max_length=200, blank=True, default='', verbose_name='账单名称')
    billing_address = models.TextField(blank=True, default='', verbose_name='账单地址')

    # Notes
    notes = models.TextField(blank=True, default='', verbose_name='客户备注')
    internal_notes = models.TextField(blank=True, default='', verbose_name='内部备注')
    comment = models.TextField(blank=True, default='', verbose_name='备注')  # legacy compat

    class Meta:
        db_table = 'order'
        verbose_name = '订单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        constraints = [
            #非空 PO 号全局唯一；空串/NUL 行不进入唯一索引（允许"无 PO 号"的多张订单共存）
            models.UniqueConstraint(
                fields=['po_number'],
                condition=~models.Q(po_number=''),
                name='uniq_order_po_number_nonempty',
            ),
        ]

    def __str__(self):
        return f'Order {self.order_no}'

    @property
    def tax_exempt_id(self) -> str:
        """机构免税号（空 = 非免税）。供结账/开票置税为零与发票 PDF 标注使用。"""
        return (self.organization.tax_exempt_id or '') if self.organization else ''

    def can_transition_to(self, new_status: str) -> bool:
        """Check if transition to new_status is valid."""
        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        return new_status in allowed

    def transition_to(self, new_status: str, save: bool = True):
        """Transition to new_status. Raises InvalidTransitionError if not allowed."""
        if not self.can_transition_to(new_status):
            raise InvalidTransitionError(
                f'Cannot transition from {self.status} to {new_status}'
            )
        self.status = new_status
        if save:
            self.save(update_fields=['status', 'updated_at'])


class OrderItem(TimeStampedModel):
    """订单明细"""
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='items', verbose_name='订单'
    )
    product = models.ForeignKey(
        'commerce.Product', on_delete=models.SET_NULL, null=True, verbose_name='产品'
    )
    sku = models.ForeignKey(
        'commerce.SKU', on_delete=models.SET_NULL, null=True, verbose_name='SKU'
    )
    quantity = models.IntegerField(default=1, verbose_name='数量')
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='单价')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='小计')

    class Meta:
        db_table = 'order_item'
        verbose_name = '订单明细'
        verbose_name_plural = verbose_name

    def save(self, *args, **kwargs):
        self.subtotal = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.order} - {self.product} x{self.quantity}'


class Invoice(TimeStampedModel):
    """发票"""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        ISSUED = 'issued', 'Issued'
        PAID = 'paid', 'Paid'
        OVERDUE = 'overdue', 'Overdue'
        VOID = 'void', 'Void'

    order = models.OneToOneField(
        Order, on_delete=models.CASCADE, related_name='invoice', verbose_name='订单'
    )
    invoice_no = models.CharField(max_length=50, unique=True, verbose_name='发票号')
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.DRAFT, verbose_name='状态'
    )
    payment_terms = models.CharField(
        max_length=20, choices=Order.PaymentTerms.choices,
        default=Order.PaymentTerms.NET30, verbose_name='账期'
    )
    issued_at = models.DateTimeField(null=True, blank=True, verbose_name='开具时间')
    due_date = models.DateField(verbose_name='到期日')
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='付款时间')

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='小计')
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='税费')
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='总计')
    currency = models.CharField(max_length=10, default='USD', verbose_name='币种')

    payment_ref = models.CharField(max_length=200, blank=True, default='', verbose_name='付款参考')
    notes = models.TextField(blank=True, default='', verbose_name='备注')

    class Meta:
        db_table = 'invoice'
        verbose_name = '发票'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'Invoice {self.invoice_no}'

    @property
    def is_overdue(self):
        if self.status in ('paid', 'void'):
            return False
        return self.due_date < business_today()

    @property
    def amount_paid(self):
        """已核销金额（VERIFIED 付款之和）。"""
        from decimal import Decimal
        from django.db.models import Sum
        total = self.payments.filter(
            status=PaymentRecord.Status.VERIFIED
        ).aggregate(s=Sum('amount'))['s']
        return total if total is not None else Decimal('0')

    @property
    def balance_due(self):
        """待付余额（派生属性 = grand_total - 已核销额，下限 0）。★ D2 部分付款"""
        from decimal import Decimal
        return max(self.grand_total - self.amount_paid, Decimal('0'))

    def void_invoice(self):
        if self.status == 'paid':
            raise InvalidTransitionError('Cannot void a paid invoice')
        self.status = 'void'
        self.save(update_fields=['status', 'updated_at'])


class PaymentRecord(TimeStampedModel):
    """付款记录"""

    class Method(models.TextChoices):
        ONLINE = 'online', 'Online Payment'
        WIRE = 'wire', 'Wire Transfer'
        CHECK = 'check', 'Check'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Verification'
        VERIFIED = 'verified', 'Verified'
        REJECTED = 'rejected', 'Rejected'

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name='payments', verbose_name='发票'
    )
    method = models.CharField(max_length=20, choices=Method.choices, verbose_name='付款方式')
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='金额')
    currency = models.CharField(max_length=10, default='USD', verbose_name='币种')
    reference = models.CharField(max_length=200, blank=True, default='', verbose_name='交易参考号')
    proof_file = models.FileField(upload_to='payment_proofs/%Y/%m/', blank=True, default='', verbose_name='付款凭证')
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.PENDING, verbose_name='状态'
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='verified_payments', verbose_name='审核人'
    )
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name='审核时间')
    notes = models.TextField(blank=True, default='', verbose_name='备注')

    class Meta:
        db_table = 'payment_record'
        verbose_name = '付款记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'Payment {self.id} for {self.invoice.invoice_no}'


class ShippingRecord(TimeStampedModel):
    """发货记录 — OneToMany per Order (supports partial/batch shipping)."""

    class Status(models.TextChoices):
        PREPARING = 'preparing', 'Preparing'
        SHIPPED = 'shipped', 'Shipped'
        IN_TRANSIT = 'in_transit', 'In Transit'
        DELIVERED = 'delivered', 'Delivered'

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='shipments', verbose_name='订单'
    )
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.PREPARING, verbose_name='状态'
    )
    carrier = models.CharField(max_length=100, blank=True, default='', verbose_name='物流公司')
    tracking_number = models.CharField(max_length=200, blank=True, default='', verbose_name='运单号')
    tracking_url = models.URLField(blank=True, default='', verbose_name='物流链接')
    shipped_at = models.DateTimeField(null=True, blank=True, verbose_name='发货时间')
    estimated_delivery = models.DateField(null=True, blank=True, verbose_name='预计送达')
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name='送达时间')
    received_by = models.CharField(max_length=200, blank=True, default='', verbose_name='签收人')
    notes = models.TextField(blank=True, default='', verbose_name='备注')

    class Meta:
        db_table = 'shipping_record'
        verbose_name = '发货记录'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'Shipping #{self.id} for {self.order.order_no}'


class ShippingRecordItem(TimeStampedModel):
    """发货明细 — how many of which OrderItem were shipped in a ShippingRecord."""

    shipping_record = models.ForeignKey(
        ShippingRecord, on_delete=models.CASCADE, related_name='items', verbose_name='发货记录'
    )
    order_item = models.ForeignKey(
        OrderItem, on_delete=models.CASCADE, related_name='shipment_items', verbose_name='订单明细'
    )
    quantity = models.IntegerField(default=1, verbose_name='数量')

    class Meta:
        db_table = 'shipping_record_item'
        verbose_name = '发货明细'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.shipping_record_id} → {self.order_item_id} x{self.quantity}'


class PoAttachment(TimeStampedModel):
    """PO 附件 — self-contained FileField store (not reusing assets.PdfFile)."""

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='attachments', verbose_name='订单'
    )
    file = models.FileField(upload_to='po_attachments/%Y%m/', verbose_name='文件')
    original_filename = models.CharField(max_length=255, blank=True, default='', verbose_name='原始文件名')
    mime_type = models.CharField(max_length=100, blank=True, default='', verbose_name='MIME 类型')
    file_size = models.IntegerField(default=0, verbose_name='文件大小')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, verbose_name='上传人'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='上传时间')

    class Meta:
        db_table = 'po_attachment'
        verbose_name = 'PO 附件'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.original_filename} ({self.order.order_no})'


class StatusLog(TimeStampedModel):
    """统一状态/操作时间线 — 状态变更与内部操作共用此表（按 action_type 区分）。"""

    class ActionType(models.TextChoices):
        STATUS_CHANGE = 'status_change', 'Status Change'
        REP_ASSIGNED = 'rep_assigned', 'Rep Assigned'
        REJECTED = 'rejected', 'Rejected'
        CANCELLED = 'cancelled', 'Cancelled'
        NOTED = 'noted', 'Noted'
        SHIPMENT = 'shipment', 'Shipment'
        INVOICE = 'invoice', 'Invoice'

    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='status_logs', verbose_name='订单'
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='status_logs', verbose_name='操作人'
    )
    action_type = models.CharField(
        max_length=20, choices=ActionType.choices, default=ActionType.STATUS_CHANGE
    )
    from_status = models.CharField(max_length=20, blank=True, default='')
    to_status = models.CharField(max_length=20, blank=True, default='')
    note = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='时间')

    class Meta:
        db_table = 'status_log'
        verbose_name = '状态日志'
        verbose_name_plural = verbose_name
        ordering = ['created_at']

    def __str__(self):
        return f'[{self.action_type}] {self.order.order_no}: {self.from_status}→{self.to_status}'


class InvoiceSequence(models.Model):
    """独立发票计数器表 — 并发安全取号（year, last_number）。"""

    year = models.IntegerField(unique=True)
    last_number = models.IntegerField(default=0)

    class Meta:
        db_table = 'invoice_sequence'
        verbose_name = '发票序号'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.year}: {self.last_number}'


class OrderSequence(models.Model):
    """独立订单日计数器表 — 并发安全取号（biz_date, last_number）。

    ★ 为什么必须有这张表（2026-10-17，生产已实际发生跳号）：
      checkout 曾用 `Order.objects.filter(created_at__gte=day_start,
      created_at__lt=day_end).count() + 1` 取序号，两个缺陷叠加：
        ① 口径错：PO 单（uuid 版单号 `ORD-{hex8}`）也落在当日窗口内被计入
           ⇒ 生产 2026-07-17 出现 004-007 跳号（Order.id 连续无删除）；
        ② 会回退：删单后 count() 变小 ⇒ 生成与已存在单号冲突的编号。
      改成独立计数器后，计数器**只数 checkout 单**，PO 单天然不污染。

    ★ 用 biz_date（日粒度）而非 year：订单号前缀是 YYYYMMDD，按业务日分桶。
      发票号是年粒度，用 InvoiceSequence，两者互不复用。
    """

    # ★ 唯一性用 Meta.constraints 显式命名，而不是字段上的 unique=True：
    #   后者让 Django 自动生成 `order_sequence_biz_date_<hash>_uniq`（约 39 字符），
    #   超出本项目 30 字符的索引名上限。本项目曾因索引名超长导致生产容器反复重启。
    biz_date = models.DateField()
    last_number = models.IntegerField(default=0)

    class Meta:
        db_table = 'order_sequence'
        constraints = [
            models.UniqueConstraint(fields=['biz_date'], name='uniq_order_seq_biz_date'),
        ]
        verbose_name = '订单日序号'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.biz_date}: {self.last_number}'


class Quote(TimeStampedModel):
    """询价单"""
    class Status(models.TextChoices):
        DRAFT = 'draft', '草稿'
        SUBMITTED = 'submitted', '已提交'
        RESPONDED = 'responded', '已回复'
        NEGOTIATING = 'negotiating', '议价中'
        CLOSED = 'closed', '已成交'
        CANCELLED = 'cancelled', '已取消'

    quote_no = models.CharField(max_length=50, unique=True, null=True, blank=True, verbose_name='询价单号')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='quotes', verbose_name='用户'
    )
    company_name = models.CharField(max_length=255, blank=True, default='', verbose_name='公司/机构')
    contact_name = models.CharField(max_length=255, blank=True, default='', verbose_name='联系人')
    contact_email = models.EmailField(blank=True, default='', verbose_name='联系邮箱')
    contact_phone = models.CharField(max_length=50, blank=True, default='', verbose_name='联系电话')
    country = models.CharField(max_length=100, blank=True, default='', verbose_name='国家')
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.DRAFT, verbose_name='状态'
    )
    valid_until = models.DateField(null=True, blank=True, verbose_name='有效期至')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='小计')
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='总计')
    remark = models.TextField(blank=True, default='', verbose_name='备注')

    class Meta:
        db_table = 'quote'
        verbose_name = '询价单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'Quote {self.quote_no or self.id}'


class QuoteItem(TimeStampedModel):
    """询价明细"""
    quote = models.ForeignKey(
        Quote, on_delete=models.CASCADE, related_name='items', verbose_name='询价单'
    )
    product = models.ForeignKey(
        'commerce.Product', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='产品'
    )
    sku = models.ForeignKey(
        'commerce.SKU', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='SKU'
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=3, default=1, verbose_name='数量')
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='单价'
    )
    note = models.TextField(blank=True, default='', verbose_name='备注')

    class Meta:
        db_table = 'quote_item'
        verbose_name = '询价明细'
        verbose_name_plural = verbose_name


class Basket(TimeStampedModel):
    """购物车 — 已登录用户按 user+sku 去重，匿名用户按 session_key+sku 去重"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='basket_items', verbose_name='用户'
    )
    product = models.ForeignKey(
        'commerce.Product', on_delete=models.CASCADE, verbose_name='产品'
    )
    sku = models.ForeignKey(
        'commerce.SKU', on_delete=models.CASCADE, verbose_name='SKU'
    )
    quantity = models.IntegerField(default=1, verbose_name='数量')
    session_key = models.CharField(max_length=100, blank=True, default='', verbose_name='会话标识')

    class Meta:
        db_table = 'basket'
        verbose_name = '购物车'
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'sku'],
                condition=models.Q(user__isnull=False),
                name='basket_user_sku_unique',
            ),
            models.UniqueConstraint(
                fields=['session_key', 'sku'],
                condition=models.Q(user__isnull=True, session_key__gt=''),
                name='basket_session_sku_unique',
            ),
        ]

    def __str__(self):
        if self.user:
            return f'{self.user} - {self.product} x{self.quantity}'
        return f'session:{self.session_key} - {self.product} x{self.quantity}'


class Wishlist(TimeStampedModel):
    """收藏夹"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='wishlists', verbose_name='用户'
    )
    name = models.CharField(max_length=255, default='My Wishlist', verbose_name='名称')
    products = models.ManyToManyField(
        'commerce.Product', blank=True, related_name='wishlists', verbose_name='产品'
    )

    class Meta:
        db_table = 'wishlist'
        verbose_name = '收藏夹'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.name} ({self.user})'
