import os
from django.db import models
from django.core.validators import MaxValueValidator
from core.models import TimeStampedModel, StatusMixin

_USE_POSTGRES = os.getenv('DB_ENGINE', 'postgres') != 'sqlite'
if _USE_POSTGRES:
    from django.contrib.postgres.indexes import GinIndex
    from django.contrib.postgres.search import SearchVectorField


class ResearchGoal(StatusMixin, TimeStampedModel):
    """顶层科研意图"""
    name = models.CharField(max_length=255, verbose_name='名称')
    slug = models.SlugField(max_length=255, unique=True, verbose_name='Slug')
    summary = models.TextField(blank=True, default='', verbose_name='摘要')
    priority = models.IntegerField(default=0, validators=[MaxValueValidator(9999)], verbose_name='优先级')

    class Meta:
        db_table = 'research_goal'
        verbose_name = '研究目标'
        verbose_name_plural = verbose_name
        ordering = ['priority', 'id']

    def __str__(self):
        return self.name


class Application(StatusMixin, TimeStampedModel):
    """应用场景 — 按科研用途分组方法"""
    research_goal = models.ForeignKey(
        ResearchGoal, on_delete=models.CASCADE, related_name='applications', verbose_name='研究目标'
    )
    name = models.CharField(max_length=255, verbose_name='名称')
    slug = models.SlugField(max_length=255, unique=True, verbose_name='Slug')
    summary = models.TextField(blank=True, default='', verbose_name='摘要')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    display_priority = models.PositiveIntegerField(default=0, db_index=True, verbose_name='展示优先级')
    if _USE_POSTGRES:
        search_vector = SearchVectorField(null=True, blank=True, verbose_name='搜索向量')

    class Meta:
        db_table = 'application'
        verbose_name = '应用场景'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'id']
        indexes = []
        if _USE_POSTGRES:
            indexes.append(GinIndex(fields=['search_vector'], name='application_search_gin'))

    def __str__(self):
        return self.name


class Method(StatusMixin, TimeStampedModel):
    """科研方法 — 工作流家族"""
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name='methods', verbose_name='应用场景'
    )
    name = models.CharField(max_length=255, verbose_name='名称')
    slug = models.SlugField(max_length=255, unique=True, verbose_name='Slug')
    summary = models.TextField(blank=True, default='', verbose_name='摘要')
    purpose = models.TextField(blank=True, default='', verbose_name='用途')
    advantages = models.TextField(blank=True, default='', verbose_name='优势')
    limitations = models.TextField(blank=True, default='', verbose_name='局限性')
    cost_band = models.CharField(max_length=100, blank=True, default='', verbose_name='成本区间')
    timeline = models.CharField(max_length=100, blank=True, default='', verbose_name='时间线')
    display_priority = models.PositiveIntegerField(default=0, db_index=True, verbose_name='展示优先级')
    if _USE_POSTGRES:
        search_vector = SearchVectorField(null=True, blank=True, verbose_name='搜索向量')

    class Meta:
        db_table = 'method'
        verbose_name = '科研方法'
        verbose_name_plural = verbose_name
        ordering = ['id']
        indexes = [
            models.Index(fields=['slug'], name='method_slug_idx'),
        ]
        if _USE_POSTGRES:
            indexes.append(GinIndex(fields=['search_vector'], name='method_search_gin'))

    def __str__(self):
        return self.name


class Protocol(TimeStampedModel):
    """实验协议 — 版本化的实验步骤"""
    class PublicationStatus(models.TextChoices):
        DRAFT = 'draft', '草稿'
        PUBLISHED = 'published', '已发布'
        SUPERSEDED = 'superseded', '已取代'
        ARCHIVED = 'archived', '已归档'

    method = models.ForeignKey(
        Method, on_delete=models.CASCADE, related_name='protocols', verbose_name='方法'
    )
    name = models.CharField(max_length=255, verbose_name='名称')
    slug = models.SlugField(max_length=255, verbose_name='Slug')
    version = models.CharField(max_length=50, default='1.0', verbose_name='版本号')
    objective = models.TextField(blank=True, default='', verbose_name='目标')
    principle = models.TextField(blank=True, default='', verbose_name='原理')
    materials = models.TextField(blank=True, default='', verbose_name='材料')
    reagents = models.TextField(blank=True, default='', verbose_name='试剂')
    equipment = models.TextField(blank=True, default='', verbose_name='设备')
    troubleshooting = models.TextField(blank=True, default='', verbose_name='故障排除')
    expected_results = models.TextField(blank=True, default='', verbose_name='预期结果')
    status = models.CharField(
        max_length=20,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DRAFT,
        verbose_name='状态',
    )
    references = models.TextField(blank=True, default='', verbose_name='参考文献文本')
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='发布时间')
    superseded_at = models.DateTimeField(null=True, blank=True, verbose_name='取代时间')
    if _USE_POSTGRES:
        search_vector = SearchVectorField(null=True, blank=True, verbose_name='搜索向量')

    class Meta:
        db_table = 'protocol'
        verbose_name = '实验协议'
        verbose_name_plural = verbose_name
        ordering = ['method', '-version']
        unique_together = [('method', 'slug', 'version')]
        indexes = [
            models.Index(fields=['slug'], name='protocol_slug_idx'),
        ]
        if _USE_POSTGRES:
            indexes.append(GinIndex(fields=['search_vector'], name='protocol_search_gin'))

    def __str__(self):
        return f'{self.name} v{self.version}'


class ProtocolStep(TimeStampedModel):
    """协议步骤 — 有序的原子操作单元"""
    protocol = models.ForeignKey(
        Protocol, on_delete=models.CASCADE, related_name='steps', verbose_name='协议'
    )
    step_no = models.PositiveIntegerField(verbose_name='步骤序号')
    title = models.CharField(max_length=255, verbose_name='步骤标题')
    body = models.TextField(blank=True, default='', verbose_name='步骤内容')
    duration_seconds = models.IntegerField(null=True, blank=True, verbose_name='预计时长(秒)')
    warnings = models.TextField(blank=True, default='', verbose_name='注意事项')
    required_materials = models.TextField(blank=True, default='', verbose_name='所需材料')

    class Meta:
        db_table = 'protocol_step'
        verbose_name = '协议步骤'
        verbose_name_plural = verbose_name
        ordering = ['protocol', 'step_no']
        unique_together = [('protocol', 'step_no')]
        indexes = [
            models.Index(fields=['protocol', 'step_no'], name='protocol_step_idx'),
        ]

    def __str__(self):
        return f'Step {self.step_no}: {self.title}'


class Reference(TimeStampedModel):
    """参考文献 — 规范化的引用对象"""
    class SourceType(models.TextChoices):
        JOURNAL = 'journal', '期刊论文'
        BOOK = 'book', '书籍'
        PATENT = 'patent', '专利'
        THESIS = 'thesis', '学位论文'
        WEB = 'web', '网页'
        OTHER = 'other', '其他'

    title = models.CharField(max_length=500, verbose_name='标题')
    authors = models.TextField(blank=True, default='', verbose_name='作者')
    journal = models.CharField(max_length=255, blank=True, default='', verbose_name='期刊')
    year = models.IntegerField(null=True, blank=True, verbose_name='年份')
    doi = models.CharField(max_length=100, blank=True, default='', unique=True, null=True, verbose_name='DOI')
    pmid = models.CharField(max_length=50, blank=True, default='', unique=True, null=True, verbose_name='PMID')
    url = models.URLField(max_length=500, blank=True, default='', verbose_name='URL')
    citation_text = models.TextField(blank=True, default='', verbose_name='引用文本')
    source_type = models.CharField(
        max_length=20, choices=SourceType.choices, default=SourceType.JOURNAL, verbose_name='来源类型'
    )
    if _USE_POSTGRES:
        search_vector = SearchVectorField(null=True, blank=True, verbose_name='搜索向量')

    class Meta:
        db_table = 'reference'
        verbose_name = '参考文献'
        verbose_name_plural = verbose_name
        ordering = ['-year', 'title']
        indexes = []
        if _USE_POSTGRES:
            indexes.append(GinIndex(fields=['search_vector'], name='reference_search_gin'))

    def __str__(self):
        return self.title[:80]


class Compatibility(StatusMixin, TimeStampedModel):
    """兼容性规则 — 定义实体间的兼容语义"""
    class Scope(models.TextChoices):
        PRODUCT_PRODUCT = 'product-product', '产品-产品'
        PRODUCT_METHOD = 'product-method', '产品-方法'
        PRODUCT_PROTOCOL = 'product-protocol', '产品-协议'
        PRODUCT_INSTRUMENT = 'product-instrument', '产品-仪器'

    class RuleType(models.TextChoices):
        COMPATIBLE = 'compatible', '兼容'
        INCOMPATIBLE = 'incompatible', '不兼容'
        CONDITIONAL = 'conditional', '条件兼容'
        WARNING = 'warning', '警告'

    class Severity(models.TextChoices):
        INFO = 'info', '信息'
        WARNING = 'warning', '警告'
        BLOCKING = 'blocking', '阻断'
        CRITICAL = 'critical', '严重'

    code = models.CharField(max_length=100, unique=True, verbose_name='规则编码')
    scope = models.CharField(max_length=30, choices=Scope.choices, verbose_name='适用范围')
    rule_type = models.CharField(max_length=20, choices=RuleType.choices, verbose_name='规则类型')
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.INFO, verbose_name='严重程度')
    expression_json = models.JSONField(default=dict, blank=True, verbose_name='规则表达式(JSON)')
    summary = models.TextField(blank=True, default='', verbose_name='规则摘要')

    class Meta:
        db_table = 'compatibility'
        verbose_name = '兼容性规则'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} ({self.rule_type})'
