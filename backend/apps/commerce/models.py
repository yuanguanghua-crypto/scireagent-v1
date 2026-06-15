import os
from django.db import models
from core.models import TimeStampedModel, StatusMixin

# PostgreSQL-only: SearchVectorField + GinIndex
_USE_POSTGRES = os.getenv('DB_ENGINE', 'postgres') != 'sqlite'
if _USE_POSTGRES:
    from django.contrib.postgres.indexes import GinIndex
    from django.contrib.postgres.search import SearchVectorField


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
    name = models.CharField(max_length=255, verbose_name='产品名称',
        help_text='产品全名，例如：2\'-Azido-dATP Sodium Salt')
    slug = models.SlugField(max_length=255, unique=True, verbose_name='Slug',
        help_text='URL 标识符，自动生成')
    catalog_no = models.CharField(max_length=64, unique=True, null=True, blank=True, verbose_name='目录号',
        help_text='唯一产品编号，例如：SC8047')
    cas = models.CharField(max_length=100, blank=True, default='', verbose_name='CAS号',
        help_text='CAS 注册号，例如：73449-06-6')
    smiles = models.TextField(blank=True, default='', verbose_name='SMILES',
        help_text='简化分子输入行系统，例如：C1=NC(=C2C(=N1)N(C=N2)[C@H]3...')
    synonyms = models.JSONField(default=list, blank=True, verbose_name='同义词',
        help_text='JSON 数组格式，例如：["2\'-F-dATP", "2-Fluoro-dATP"]')
    inchi = models.TextField(blank=True, default='', verbose_name='InChI',
        help_text='国际化合物标识，标准 InChI 字符串')
    formula = models.CharField(max_length=256, blank=True, default='', verbose_name='分子式',
        help_text='分子式，例如：C10H15N8O12P3')
    molecular_weight = models.FloatField(null=True, blank=True, verbose_name='分子量',
        help_text='分子量（g/mol），例如：532.2')
    purity = models.CharField(max_length=100, blank=True, default='', verbose_name='纯度',
        help_text='纯度描述，例如：≥95% (HPLC)')
    concentration = models.CharField(max_length=64, blank=True, default='', verbose_name='浓度',
        help_text='浓度信息，例如：10 mM in water')
    storage = models.TextField(blank=True, default='', verbose_name='储存条件',
        help_text='储存温度和条件，例如：-20°C, protect from light')
    shipping = models.TextField(blank=True, default='', verbose_name='运输条件',
        help_text='运输温度和包装要求，例如：Blue ice, ambient')
    lead_time = models.CharField(max_length=100, blank=True, default='', verbose_name='货期',
        help_text='发货周期，例如：1-3 business days')
    handling_notes = models.TextField(blank=True, default='', verbose_name='操作注意事项',
        help_text='安全操作提示')
    shelf_life = models.DurationField(null=True, blank=True, verbose_name='保质期',
        help_text='保质期，例如：P1Y 表示 1 年')
    research_use_only = models.BooleanField(default=True, verbose_name='仅限研究用途',
        help_text='勾选表示此产品仅用于科学研究')
    overview = models.TextField(blank=True, default='', verbose_name='产品概述',
        help_text='产品详细介绍，支持 Markdown')
    structure_svg = models.TextField(blank=True, default='', verbose_name='结构式SVG',
        help_text='分子结构 SVG 代码')
    seo_title = models.CharField(max_length=256, blank=True, default='', verbose_name='SEO标题',
        help_text='搜索引擎标题，建议 50-60 字符')
    seo_description = models.TextField(blank=True, default='', verbose_name='SEO描述',
        help_text='搜索引擎描述，建议 120-160 字符')
    category_l1 = models.CharField(max_length=128, blank=True, default='', verbose_name='一级分类',
        help_text='产品大类，例如：Nucleotides & Nucleosides')
    category_l2 = models.CharField(max_length=128, blank=True, default='', verbose_name='二级分类',
        help_text='产品子类，例如：2\'-Modified dNTPs')
    display_priority = models.PositiveIntegerField(default=0, db_index=True, verbose_name='展示优先级',
        help_text='数字越大越靠前，0 为默认排序')

    # PostgreSQL FTS field — only added when running on PostgreSQL
    if _USE_POSTGRES:
        search_vector = SearchVectorField(null=True, blank=True, verbose_name='搜索向量')

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
        if _USE_POSTGRES:
            indexes.append(GinIndex(fields=['search_vector'], name='product_search_gin'))

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
    concentration = models.CharField(max_length=64, blank=True, default='', verbose_name='浓度')
    lead_time = models.CharField(max_length=64, blank=True, default='', verbose_name='交货时间')
    is_default = models.BooleanField(default=False, verbose_name='默认SKU')

    class Meta:
        db_table = 'sku'
        verbose_name = 'SKU'
        verbose_name_plural = verbose_name
        ordering = ['product', 'price']

    def __str__(self):
        return f'{self.sku_code} ({self.pack_size})'


class ProductDocument(TimeStampedModel):
    """产品文档"""
    class DocumentType(models.TextChoices):
        DATASHEET = 'datasheet', 'Datasheet'
        MSDS = 'msds', 'MSDS'
        COA = 'coa', 'COA'
        APPLICATION_NOTE = 'application_note', 'Application Note'

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='documents', verbose_name='产品'
    )
    document_type = models.CharField(
        max_length=20, choices=DocumentType.choices, verbose_name='文档类型'
    )
    language = models.CharField(max_length=16, default='en', verbose_name='语言')
    version = models.CharField(max_length=16, default='1.0', verbose_name='版本')
    file = models.FileField(upload_to='documents/%Y/%m/', blank=True, default='')
    original_filename = models.CharField(max_length=256, blank=True, default='', verbose_name='原始文件名')

    class Meta:
        db_table = 'product_document'
        verbose_name = '产品文档'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.product.name} - {self.document_type}'
