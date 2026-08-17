import os
from django.db import models
from django.utils.text import slugify
from django.core.validators import MaxValueValidator
from core.models import TimeStampedModel, StatusMixin

_USE_POSTGRES = os.getenv('DB_ENGINE', 'postgres') != 'sqlite'
if _USE_POSTGRES:
    from django.contrib.postgres.indexes import GinIndex
    from django.contrib.postgres.search import SearchVectorField


class TestFixtureQuerySet(models.QuerySet):
    """为顶部知识实体（ResearchGoal/Application/Method）提供测试夹具过滤。

    设计取舍（S1）：**不改默认 manager 语义** —— ``objects.all()`` 仍返回全量，
    以免破坏 e2e 清理脚本、数据修复命令与管理后台等需要看到夹具行的路径。
    对外读取面必须显式调用 ``.public()`` 排除夹具。
    """

    def public(self):
        """排除被标记为测试夹具的行（对外读取面统一入口）。"""
        return self.filter(is_test_fixture=False)

    def test_fixtures(self):
        return self.filter(is_test_fixture=True)


def _test_fixture_field():
    return models.BooleanField(
        default=False, db_index=True, verbose_name='测试夹具',
        help_text='True 表示此行由自动化测试残留产生，不参与任何对外展示与统计；'
                  '仅作标记，数据不会被删除',
    )


class ResearchGoal(StatusMixin, TimeStampedModel):
    """顶层科研意图"""
    name = models.CharField(max_length=255, verbose_name='名称',
        help_text='研究方向名称，例如：RNA Analysis, DNA Sequencing, Click Chemistry')
    slug = models.SlugField(max_length=255, unique=True, verbose_name='Slug',
        help_text='URL 友好的标识符，自动生成')
    summary = models.TextField(blank=True, default='', verbose_name='摘要',
        help_text='一句话描述这个研究方向的核心内容')
    priority = models.IntegerField(default=0, validators=[MaxValueValidator(9999)], verbose_name='优先级',
        help_text='数字越大越靠前，0 为默认排序')
    is_test_fixture = _test_fixture_field()

    # route B 加法：ResearchGoal 作为策展集合（curated collection），手动关联协议，
    # 无路径、无打分。与顶部 RG→AP→ME→Protocol 严格单父 FK 树解耦。
    protocols = models.ManyToManyField(
        'knowledge.Protocol', blank=True, related_name='research_goals',
        verbose_name='策展协议集',
        help_text='研究者人工策展纳入该研究目标的协议集合（无数据驱动，仅策展）',
    )

    objects = TestFixtureQuerySet.as_manager()

    class Meta:
        db_table = 'research_goal'
        verbose_name = '研究目标'
        verbose_name_plural = verbose_name
        ordering = ['priority', 'id']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) if self.name else 'item'
            slug = base
            n = 1
            qs = self.__class__.objects.exclude(pk=self.pk) if self.pk else self.__class__.objects
            while qs.filter(slug=slug).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Application(StatusMixin, TimeStampedModel):
    """应用场景 — 按科研用途分组方法"""
    research_goal = models.ForeignKey(
        ResearchGoal, on_delete=models.CASCADE, related_name='applications', verbose_name='研究目标',
        help_text='这个应用属于哪个研究方向', null=True, blank=True,
    )
    name = models.CharField(max_length=255, verbose_name='名称',
        help_text='具体实验场景，例如：RNA Fluorescent Labeling, Sanger Sequencing')
    slug = models.SlugField(max_length=255, unique=True, verbose_name='Slug')
    summary = models.TextField(blank=True, default='', verbose_name='摘要',
        help_text='描述这个实验场景的原理和用途')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    display_priority = models.PositiveIntegerField(default=0, db_index=True, verbose_name='展示优先级')
    is_test_fixture = _test_fixture_field()
    if _USE_POSTGRES:
        search_vector = SearchVectorField(null=True, blank=True, verbose_name='搜索向量')

    objects = TestFixtureQuerySet.as_manager()

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

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) if self.name else 'item'
            slug = base
            n = 1
            qs = self.__class__.objects.exclude(pk=self.pk) if self.pk else self.__class__.objects
            while qs.filter(slug=slug).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Method(StatusMixin, TimeStampedModel):
    """科研方法 — 工作流家族"""

    class CostBand(models.TextChoices):
        LOW = 'low', '低成本 (<$50/sample)'
        MEDIUM = 'medium', '中等 ($50-200/sample)'
        HIGH = 'high', '高成本 (>$200/sample)'
        UNKNOWN = '', '未确定'

    class Timeline(models.TextChoices):
        MINUTES = 'minutes', '几分钟 (<30 min)'
        HOURS = 'hours', '数小时 (30 min - 4 hours)'
        DAYS = 'days', '数天 (1-7 days)'
        WEEKS = 'weeks', '数周 (>1 week)'
        UNKNOWN = '', '未确定'

    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name='methods', verbose_name='应用场景',
        help_text='这个方法属于哪个实验场景', null=True, blank=True,
    )
    name = models.CharField(max_length=255, verbose_name='名称',
        help_text='技术方法名称，例如：CuAAC Click Chemistry, NHS-Ester Conjugation')
    slug = models.SlugField(max_length=255, unique=True, verbose_name='Slug')
    summary = models.TextField(blank=True, default='', verbose_name='摘要',
        help_text='一句话描述方法原理')
    purpose = models.TextField(blank=True, default='', verbose_name='用途',
        help_text='这个方法具体能做什么')
    advantages = models.TextField(blank=True, default='', verbose_name='优势',
        help_text='每条优势一行，例如：高特异性、快速反应、生物正交')
    limitations = models.TextField(blank=True, default='', verbose_name='局限性',
        help_text='每条局限一行，例如：需要铜催化剂、对活细胞有毒')
    cost_band = models.CharField(max_length=100, blank=True, default='', choices=CostBand.choices, verbose_name='成本区间',
        help_text='每次实验的大致成本范围')
    timeline = models.CharField(max_length=100, blank=True, default='', choices=Timeline.choices, verbose_name='时间线',
        help_text='完成一次实验所需的大致时间')
    display_priority = models.PositiveIntegerField(default=0, db_index=True, verbose_name='展示优先级')
    is_test_fixture = _test_fixture_field()
    if _USE_POSTGRES:
        search_vector = SearchVectorField(null=True, blank=True, verbose_name='搜索向量')

    objects = TestFixtureQuerySet.as_manager()

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

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) if self.name else 'item'
            slug = base
            n = 1
            qs = self.__class__.objects.exclude(pk=self.pk) if self.pk else self.__class__.objects
            while qs.filter(slug=slug).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Protocol(TimeStampedModel):
    """实验协议 — 版本化的实验步骤"""
    class PublicationStatus(models.TextChoices):
        DRAFT = 'draft', '草稿'
        PUBLISHED = 'published', '已发布'
        SUPERSEDED = 'superseded', '已取代'
        ARCHIVED = 'archived', '已归档'

    name = models.CharField(max_length=500, verbose_name='名称',
        help_text='协议全名，例如：CuAAC RNA Fluorescent Labeling Protocol')
    slug = models.SlugField(max_length=255, verbose_name='Slug')
    version = models.CharField(max_length=50, default='1.0', verbose_name='版本号',
        help_text='协议版本，例如：1.0, 2.1')
    objective = models.TextField(blank=True, default='', verbose_name='目标',
        help_text='这个协议要达成什么目的')
    principle = models.TextField(blank=True, default='', verbose_name='原理',
        help_text='实验原理简述')
    materials = models.TextField(blank=True, default='', verbose_name='材料',
        help_text='所需材料列表，每行一个')
    reagents = models.TextField(blank=True, default='', verbose_name='试剂',
        help_text='所需试剂列表，包含浓度和用量')
    equipment = models.TextField(blank=True, default='', verbose_name='设备',
        help_text='所需设备列表')
    troubleshooting = models.TextField(blank=True, default='', verbose_name='故障排除',
        help_text='常见问题和解决方案')
    expected_results = models.TextField(blank=True, default='', verbose_name='预期结果',
        help_text='成功执行后应观察到的结果')
    status = models.CharField(
        max_length=20,
        choices=PublicationStatus.choices,
        default=PublicationStatus.DRAFT,
        verbose_name='状态',
    )
    references = models.TextField(blank=True, default='', verbose_name='参考文献文本',
        help_text='引用的论文，每行一条（PMID 或 DOI）')

    class Source(models.TextChoices):
        CURATED = 'curated', '人工策展库'
        BIOPROCORPUS = 'bioprocorpus', 'BioProCorpus 自动匹配库'

    source = models.CharField(
        max_length=32, choices=Source.choices, default=Source.CURATED,
        blank=True, verbose_name='来源',
        help_text='协议来源：curated=人工策展库；bioprocorpus=BioProCorpus 自动匹配库'
    )
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='发布时间')
    superseded_at = models.DateTimeField(null=True, blank=True, verbose_name='取代时间')
    if _USE_POSTGRES:
        search_vector = SearchVectorField(null=True, blank=True, verbose_name='搜索向量')

    # route B 加法：类型化 facet 标签（无打分）。通过 ProtocolFacet 记录来源（聚类主标签/交叉检测补标）。
    facets = models.ManyToManyField(
        'knowledge.FacetValue', through='knowledge.ProtocolFacet',
        related_name='protocols', blank=True, verbose_name='受控词表标签',
        help_text='协议的类型化 facet 标签（application / method / biological_context / study_type），无打分',
    )

    class Meta:
        db_table = 'protocol'
        verbose_name = '实验协议'
        verbose_name_plural = verbose_name
        ordering = ['-version']
        unique_together = [('slug', 'version')]
        indexes = [
            models.Index(fields=['slug'], name='protocol_slug_idx'),
        ]
        if _USE_POSTGRES:
            indexes.append(GinIndex(fields=['search_vector'], name='protocol_search_gin'))

    def __str__(self):
        return f'{self.name} v{self.version}'

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) if self.name else 'item'
            slug = base
            n = 1
            qs = self.__class__.objects.exclude(pk=self.pk) if self.pk else self.__class__.objects
            while qs.filter(slug=slug).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)


class ProtocolStep(TimeStampedModel):
    """协议步骤 — 有序的原子操作单元"""
    protocol = models.ForeignKey(
        Protocol, on_delete=models.CASCADE, related_name='steps', verbose_name='协议',
        help_text='所属协议'
    )
    step_no = models.PositiveIntegerField(verbose_name='步骤序号',
        help_text='步骤编号，从 1 开始')
    title = models.CharField(max_length=255, verbose_name='步骤标题',
        help_text='简短标题，例如：准备反应液、纯化产物')
    body = models.TextField(blank=True, default='', verbose_name='步骤内容',
        help_text='详细操作描述')
    duration_seconds = models.IntegerField(null=True, blank=True, verbose_name='预计时长(秒)',
        help_text='预计耗时，单位秒（例如 1800 = 30分钟）')
    warnings = models.TextField(blank=True, default='', verbose_name='注意事项',
        help_text='安全提示和注意事项')
    required_materials = models.TextField(blank=True, default='', verbose_name='所需材料',
        help_text='本步骤需要的特定材料')

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

    title = models.CharField(max_length=500, verbose_name='标题',
        help_text='论文/文献完整标题')
    authors = models.TextField(blank=True, default='', verbose_name='作者',
        help_text='作者列表，用逗号分隔')
    journal = models.CharField(max_length=255, blank=True, default='', verbose_name='期刊',
        help_text='期刊名称，例如：Nature Protocols, Chemical Reviews')
    year = models.IntegerField(null=True, blank=True, verbose_name='年份',
        help_text='发表年份，例如：2024')
    doi = models.CharField(max_length=100, blank=True, null=True, unique=True, verbose_name='DOI',
        help_text='数字对象标识符，例如：10.1038/s41586-024-12345-6')
    pmid = models.CharField(max_length=50, blank=True, null=True, unique=True, verbose_name='PMID',
        help_text='PubMed ID，例如：38123456')
    url = models.URLField(max_length=500, blank=True, default='', verbose_name='URL',
        help_text='文献链接')
    citation_text = models.TextField(blank=True, default='', verbose_name='引用文本',
        help_text='标准引用格式文本')
    source_type = models.CharField(
        max_length=20, choices=SourceType.choices, default=SourceType.JOURNAL, verbose_name='来源类型',
        help_text='文献类型'
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

    def save(self, *args, **kwargs):
        # 空字符串视为未填写，转为 NULL 以避免 unique 约束冲突
        # （'' 不等于 NULL，多条空 DOI/PMID 会违反 unique=True 导致 IntegrityError）
        if self.doi == '':
            self.doi = None
        if self.pmid == '':
            self.pmid = None
        super().save(*args, **kwargs)

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

    code = models.CharField(max_length=100, unique=True, verbose_name='规则编码',
        help_text='唯一编码，例如：COMP-PM-001')
    scope = models.CharField(max_length=30, choices=Scope.choices, verbose_name='适用范围',
        help_text='这条规则适用于哪类实体关系')
    rule_type = models.CharField(max_length=20, choices=RuleType.choices, verbose_name='规则类型',
        help_text='兼容/不兼容/条件兼容/警告')
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.INFO, verbose_name='严重程度',
        help_text='违反此规则的严重程度')
    expression_json = models.JSONField(default=dict, blank=True, verbose_name='规则表达式(JSON)',
        help_text='JSON 格式的规则条件，例如：{"min_purity": 95, "temp_range": [-20, 4]}')
    summary = models.TextField(blank=True, default='', verbose_name='规则摘要',
        help_text='用自然语言描述这条规则')

    class Meta:
        db_table = 'compatibility'
        verbose_name = '兼容性规则'
        verbose_name_plural = verbose_name
        ordering = ['code']

    def __str__(self):
        return f'{self.code} ({self.rule_type})'


class FacetValue(TimeStampedModel):
    """受控词表项（route B 加法）。

    类型化 facet 词汇：application / method / biological_context / study_type。
    biological_context 以 kind(species/cell/disease) 区分子类型，单列成一维。
    value 全英文（用户决策：不需要中文名称）。
    """

    class FacetType(models.TextChoices):
        APPLICATION = 'application', '研究域'
        METHOD = 'method', '方法'
        BIOLOGICAL_CONTEXT = 'biological_context', '物种/细胞/疾病'
        STUDY_TYPE = 'study_type', '研究类型'

    class Kind(models.TextChoices):
        SPECIES = 'species', '物种'
        CELL = 'cell', '细胞'
        DISEASE = 'disease', '疾病'

    facet_type = models.CharField(
        max_length=32, choices=FacetType.choices, db_index=True, verbose_name='facet 维度',
    )
    kind = models.CharField(
        max_length=16, choices=Kind.choices, blank=True, default='', db_index=True,
        verbose_name='biological_context 子类型',
        help_text='仅 biological_context 维度使用：species / cell / disease',
    )
    value = models.CharField(max_length=255, verbose_name='facet 值(英文)',
        help_text='受控词表项英文名称，例如：PCR / qPCR、Mus musculus、Cancer / Tumor Model')
    slug = models.SlugField(max_length=255, unique=True, verbose_name='Slug')
    description = models.TextField(blank=True, default='', verbose_name='说明')

    class Meta:
        db_table = 'facet_value'
        verbose_name = '受控词表项'
        verbose_name_plural = verbose_name
        unique_together = [('facet_type', 'kind', 'value')]
        ordering = ['facet_type', 'kind', 'value']

    def __str__(self):
        if self.kind:
            return f'[{self.facet_type}:{self.kind}] {self.value}'
        return f'[{self.facet_type}] {self.value}'

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f'{self.facet_type}-{self.kind}-{self.value}') or 'item'
            slug = base
            n = 1
            qs = self.__class__.objects.exclude(pk=self.pk) if self.pk else self.__class__.objects
            while qs.filter(slug=slug).exists():
                slug = f'{base}-{n}'
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)


class ProtocolFacet(TimeStampedModel):
    """协议 ↔ facet 关联（route B 加法，类型化标签，无打分）。

    通过模型：记录每个 facet 的来源（聚类主标签 / 交叉检测补标），保证 UI 透明。
    """

    class Source(models.TextChoices):
        CLUSTER_MAIN = 'cluster_main', '聚类主标签'
        CROSS_DETECT = 'cross_detect', '交叉检测补标'

    protocol = models.ForeignKey(
        Protocol, on_delete=models.CASCADE, related_name='protocol_facets', verbose_name='协议',
    )
    facet = models.ForeignKey(
        FacetValue, on_delete=models.CASCADE, related_name='protocol_facets', verbose_name='facet',
    )
    source = models.CharField(
        max_length=16, choices=Source.choices, default=Source.CLUSTER_MAIN, verbose_name='来源',
    )

    class Meta:
        db_table = 'protocol_facet'
        verbose_name = '协议-facet 关联'
        verbose_name_plural = verbose_name
        unique_together = [('protocol', 'facet')]
        indexes = [
            models.Index(fields=['protocol', 'source'], name='protocol_facet_src_idx'),
        ]

    def __str__(self):
        return f'{self.protocol} -> {self.facet} ({self.source})'
