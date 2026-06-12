from django.db import models
from core.models import TimeStampedModel, StatusMixin


class ProductClass(TimeStampedModel):
    """产品分类"""
    name = models.CharField(max_length=255, verbose_name='分类名称')
    slug = models.SlugField(max_length=255, unique=True, verbose_name='Slug')
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name='父分类'
    )
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'product_class'
        verbose_name = '产品分类'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name


class CatalogGroup(TimeStampedModel):
    """目录分组"""
    name = models.CharField(max_length=255, verbose_name='名称')
    slug = models.SlugField(max_length=255, unique=True, verbose_name='Slug')
    locale = models.CharField(max_length=20, default='en', verbose_name='语言')
    active = models.BooleanField(default=True, verbose_name='是否激活')

    class Meta:
        db_table = 'catalog_group'
        verbose_name = '目录分组'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class Product(StatusMixin, TimeStampedModel):
    """产品 — 商务和科学锚点"""
    product_class = models.ForeignKey(
        ProductClass, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='products', verbose_name='产品分类'
    )
    catalog_group = models.ForeignKey(
        CatalogGroup, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='products', verbose_name='目录分组'
    )
    name = models.CharField(max_length=255, verbose_name='产品名称')
    slug = models.SlugField(max_length=255, unique=True, verbose_name='Slug')
    cas = models.CharField(max_length=100, blank=True, default='', verbose_name='CAS号')
    smiles = models.TextField(blank=True, default='', verbose_name='SMILES')
    synonyms = models.JSONField(default=list, blank=True, verbose_name='同义词')
    inchi = models.TextField(blank=True, default='', verbose_name='InChI')
    purity = models.CharField(max_length=100, blank=True, default='', verbose_name='纯度')
    storage = models.TextField(blank=True, default='', verbose_name='储存条件')
    shipping = models.TextField(blank=True, default='', verbose_name='运输条件')
    lead_time = models.CharField(max_length=100, blank=True, default='', verbose_name='货期')
    handling_notes = models.TextField(blank=True, default='', verbose_name='操作注意事项')
    shelf_life = models.DurationField(null=True, blank=True, verbose_name='保质期')
    research_use_only = models.BooleanField(default=True, verbose_name='仅限研究用途')

    class Meta:
        db_table = 'product'
        verbose_name = '产品'
        verbose_name_plural = verbose_name
        ordering = ['name']
        indexes = [
            models.Index(fields=['cas'], name='product_cas_idx'),
            models.Index(fields=['name'], name='product_name_idx'),
            models.Index(fields=['slug'], name='product_slug_idx'),
        ]

    def __str__(self):
        return self.name

    @property
    def inventory_status(self):
        """产品级库存状态 — 通过 SKU 聚合派生"""
        statuses = list(self.skus.values_list('inventory_status', flat=True).distinct())
        if 'in_stock' in statuses:
            return 'in_stock'
        if 'limited' in statuses:
            return 'limited'
        if 'preorder' in statuses:
            return 'preorder'
        return 'out_of_stock'


class SKU(TimeStampedModel):
    """SKU — 可购买变体"""
    class InventoryStatus(models.TextChoices):
        IN_STOCK = 'in_stock', '现货'
        LIMITED = 'limited', '少量'
        PREORDER = 'preorder', '预订'
        OUT_OF_STOCK = 'out_of_stock', '缺货'

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='skus', verbose_name='产品'
    )
    sku_code = models.CharField(max_length=100, unique=True, verbose_name='SKU编码')
    pack_size = models.CharField(max_length=100, blank=True, default='', verbose_name='包装规格')
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='价格')
    currency = models.CharField(max_length=10, default='USD', verbose_name='币种')
    inventory_status = models.CharField(
        max_length=20, choices=InventoryStatus.choices,
        default=InventoryStatus.IN_STOCK, verbose_name='库存状态'
    )

    class Meta:
        db_table = 'sku'
        verbose_name = 'SKU'
        verbose_name_plural = verbose_name
        ordering = ['product', 'price']

    def __str__(self):
        return f'{self.sku_code} ({self.pack_size})'
