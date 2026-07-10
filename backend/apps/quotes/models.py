from django.db import models
from django.conf import settings
from core.models import TimeStampedModel


class QuoteRequest(TimeStampedModel):
    """RFQ — 客户提交的报价请求"""

    class Status(models.TextChoices):
        PENDING = 'pending', '待处理'
        REVIEWING = 'reviewing', '审核中'
        QUOTED = 'quoted', '已报价'
        CLOSED = 'closed', '已关闭'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='quote_requests',
        verbose_name='用户',
    )
    contact_name = models.CharField(max_length=200, verbose_name='联系人')
    contact_email = models.EmailField(verbose_name='联系邮箱')
    contact_phone = models.CharField(max_length=50, blank=True, default='', verbose_name='联系电话')
    company_name = models.CharField(max_length=255, blank=True, default='', verbose_name='公司/机构')
    country = models.CharField(max_length=100, blank=True, default='', verbose_name='国家')
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.PENDING, verbose_name='状态',
    )
    notes = models.TextField(blank=True, default='', verbose_name='备注')

    class Meta:
        db_table = 'quote_request'
        verbose_name = '报价请求'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'RFQ {self.id} - {self.contact_name}'


class QuoteRequestItem(TimeStampedModel):
    """报价请求明细"""
    quote_request = models.ForeignKey(
        QuoteRequest, on_delete=models.CASCADE,
        related_name='items', verbose_name='报价请求',
    )
    product = models.ForeignKey(
        'commerce.Product', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='产品',
    )
    sku = models.ForeignKey(
        'commerce.SKU', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='SKU',
    )
    quantity = models.IntegerField(default=1, verbose_name='数量')
    note = models.TextField(blank=True, default='', verbose_name='备注')

    class Meta:
        db_table = 'quote_request_item'
        verbose_name = '报价请求明细'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'RFQ Item {self.id} - x{self.quantity}'
