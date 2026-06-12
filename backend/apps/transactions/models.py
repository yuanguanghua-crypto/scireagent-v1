from django.db import models
from django.conf import settings
from core.models import TimeStampedModel


class Order(TimeStampedModel):
    """订单"""
    class Status(models.TextChoices):
        PENDING = 'pending', '待付款'
        PAID = 'paid', '已付款'
        PROCESSING = 'processing', '处理中'
        SHIPPED = 'shipped', '已发货'
        COMPLETED = 'completed', '已完成'
        CANCELLED = 'cancelled', '已取消'
        REFUNDED = 'refunded', '已退款'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='orders', verbose_name='用户'
    )
    order_no = models.CharField(max_length=50, unique=True, verbose_name='订单号')
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.PENDING, verbose_name='状态'
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='小计')
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='税费')
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='总计')
    currency = models.CharField(max_length=10, default='USD', verbose_name='币种')
    comment = models.TextField(blank=True, default='', verbose_name='备注')

    class Meta:
        db_table = 'order'
        verbose_name = '订单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'Order {self.order_no}'


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

    class Meta:
        db_table = 'order_item'
        verbose_name = '订单明细'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.order} - {self.product}'


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
