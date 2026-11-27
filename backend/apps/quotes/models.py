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

    # ── 报价结果（运营在 RFQ 工作台填写，填完即通知客户）──────────────
    #
    # 为什么不复用 `apps/transactions.Quote`：那套是遗留半成品（前端只做 GET，
    # 且已登录 POST /quotes/ 会建出 quote_no=null 的空壳单，见 transactions/api/v1/
    # views.py:72-73 的注释）。客户侧真实入口是本模型的 QuoteRequest，
    # 报价就直接挂在这里，避免两套单子并存、状态对不上。
    quoted_total = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='报价总额',
        help_text='留空表示只回执不报价',
    )
    quoted_currency = models.CharField(
        max_length=8, default='USD', verbose_name='币种',
    )
    quoted_valid_until = models.DateField(
        null=True, blank=True, verbose_name='报价有效期至',
    )
    quoted_note = models.TextField(blank=True, default='', verbose_name='报价说明',
        help_text='会原样出现在发给客户的邮件里，例如交期、运费、最小起订量')
    quoted_at = models.DateTimeField(null=True, blank=True, verbose_name='报价时间')

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
    # ★ 2026-11-27（A-026）：客户**只填名字、不挂库内产品**时的落点。
    #   改前这两项只存在于前端内存里，提交时被 `.map()` 丢掉 ⇒ 明细落库后
    #   product/sku 双双为 NULL、note 也空，运营看到的是一行三个 "—"。
    #   历史行留空（那批数据从未保存过名称，无法回填）。
    requested_product_name = models.CharField(
        max_length=300, blank=True, default='', verbose_name='客户填写的产品名',
        help_text='客户只填名字、未挂库内产品时保存到这里',
    )
    requested_catalog_no = models.CharField(
        max_length=100, blank=True, default='', verbose_name='客户填写的货号',
        help_text='客户手填的目录号/SKU 文本（未匹配到库内 SKU 时）',
    )

    class Meta:
        db_table = 'quote_request_item'
        verbose_name = '报价请求明细'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'RFQ Item {self.id} - x{self.quantity}'
