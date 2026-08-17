from django.db import models
from core.models import TimeStampedModel


class ProductMethod(TimeStampedModel):
    """产品-方法桥接"""
    class Role(models.TextChoices):
        REAGENT = 'reagent', '试剂'
        BUFFER = 'buffer', '缓冲液'
        CONTROL = 'control', '对照'
        ENZYME = 'enzyme', '酶'
        LABEL = 'label', '标记物'
        SOLVENT = 'solvent', '溶剂'
        OTHER = 'other', '其他'

    class EvidenceLevel(models.TextChoices):
        LOW = 'low', '低'
        MEDIUM = 'medium', '中'
        HIGH = 'high', '高'
        CURATED = 'curated', '人工审核'

    product = models.ForeignKey(
        'commerce.Product', on_delete=models.CASCADE,
        related_name='product_methods', verbose_name='产品'
    )
    method = models.ForeignKey(
        'knowledge.Method', on_delete=models.CASCADE,
        related_name='product_methods', verbose_name='方法'
    )
    role = models.CharField(
        max_length=20, choices=Role.choices,
        default=Role.REAGENT, verbose_name='角色'
    )
    evidence_level = models.CharField(
        max_length=20, choices=EvidenceLevel.choices,
        default=EvidenceLevel.MEDIUM, verbose_name='证据等级'
    )
    display_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'product_method'
        verbose_name = '产品-方法关联'
        verbose_name_plural = verbose_name
        unique_together = [('product', 'method', 'role')]
        indexes = [
            models.Index(fields=['method', 'display_order'], name='product_method_order_idx'),
        ]

    def __str__(self):
        return f'{self.product} -> {self.method} ({self.role})'


class MethodProtocol(TimeStampedModel):
    """方法-协议桥接"""
    method = models.ForeignKey(
        'knowledge.Method', on_delete=models.CASCADE,
        related_name='method_protocols', verbose_name='方法'
    )
    protocol = models.ForeignKey(
        'knowledge.Protocol', on_delete=models.CASCADE,
        related_name='method_protocols', verbose_name='协议'
    )
    display_order = models.IntegerField(default=0, verbose_name='排序')
    featured = models.BooleanField(default=False, verbose_name='是否推荐')
    explicit = models.BooleanField(
        default=False, verbose_name='显式关联',
        help_text='研究者显式建立的跨方法合法关联；清理命令不删除 explicit=True 的残留'
    )
    status = models.CharField(max_length=20, default='active', verbose_name='状态')

    class Meta:
        db_table = 'method_protocol'
        verbose_name = '方法-协议关联'
        verbose_name_plural = verbose_name
        unique_together = [('method', 'protocol')]
        indexes = [
            models.Index(fields=['method', 'display_order'], name='method_protocol_order_idx'),
        ]

    def __str__(self):
        return f'{self.method} -> {self.protocol}'


class ProductReference(TimeStampedModel):
    """产品-文献桥接"""
    class CitationRole(models.TextChoices):
        PRIMARY = 'primary', '主要引用'
        SUPPORTING = 'supporting', '支持性引用'
        VALIDATION = 'validation', '验证引用'
        BACKGROUND = 'background', '背景引用'

    product = models.ForeignKey(
        'commerce.Product', on_delete=models.CASCADE,
        related_name='product_references', verbose_name='产品'
    )
    reference = models.ForeignKey(
        'knowledge.Reference', on_delete=models.CASCADE,
        related_name='product_references', verbose_name='文献'
    )
    citation_role = models.CharField(
        max_length=20, choices=CitationRole.choices,
        default=CitationRole.SUPPORTING, verbose_name='引用角色'
    )
    display_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'product_reference'
        verbose_name = '产品-文献关联'
        verbose_name_plural = verbose_name
        unique_together = [('product', 'reference', 'citation_role')]
        indexes = [
            models.Index(fields=['product', 'display_order'], name='product_ref_order_idx'),
        ]


class ProductCompatibility(TimeStampedModel):
    """产品-产品兼容性事实"""
    class Verdict(models.TextChoices):
        COMPATIBLE = 'compatible', '兼容'
        INCOMPATIBLE = 'incompatible', '不兼容'
        CONDITIONAL = 'conditional', '条件兼容'
        WARNING = 'warning', '警告'

    source_product = models.ForeignKey(
        'commerce.Product', on_delete=models.CASCADE,
        related_name='compatibility_as_source', verbose_name='源产品'
    )
    target_product = models.ForeignKey(
        'commerce.Product', on_delete=models.CASCADE,
        related_name='compatibility_as_target', verbose_name='目标产品'
    )
    compatibility = models.ForeignKey(
        'knowledge.Compatibility', on_delete=models.CASCADE,
        related_name='product_facts', verbose_name='兼容性规则'
    )
    verdict = models.CharField(
        max_length=20, choices=Verdict.choices, verbose_name='判定结果'
    )
    notes = models.TextField(blank=True, default='', verbose_name='备注')

    class Meta:
        db_table = 'product_compatibility'
        verbose_name = '产品兼容性事实'
        verbose_name_plural = verbose_name
        unique_together = [('source_product', 'target_product', 'compatibility')]

    def __str__(self):
        return f'{self.source_product} <-> {self.target_product}: {self.verdict}'


class ProductProduct(TimeStampedModel):
    """产品-产品关系"""
    class RelationType(models.TextChoices):
        SUBSTITUTE = 'substitute', '替代品'
        COMPLEMENT = 'complement', '互补品'
        ALTERNATE = 'alternate', '替代方案'
        BUNDLE = 'bundle', '捆绑销售'
        RELATED = 'related', '相关产品'

    class Direction(models.TextChoices):
        ONE_WAY = 'one_way', '单向'
        BIDIRECTIONAL = 'bidirectional', '双向'

    source_product = models.ForeignKey(
        'commerce.Product', on_delete=models.CASCADE,
        related_name='product_relations_as_source', verbose_name='源产品'
    )
    target_product = models.ForeignKey(
        'commerce.Product', on_delete=models.CASCADE,
        related_name='product_relations_as_target', verbose_name='目标产品'
    )
    relation_type = models.CharField(
        max_length=20, choices=RelationType.choices,
        default=RelationType.RELATED, verbose_name='关系类型'
    )
    direction = models.CharField(
        max_length=20, choices=Direction.choices,
        default=Direction.BIDIRECTIONAL, verbose_name='方向'
    )
    strength = models.IntegerField(default=0, verbose_name='关联强度')
    notes = models.TextField(blank=True, default='', verbose_name='备注')

    class Meta:
        db_table = 'product_product'
        verbose_name = '产品-产品关系'
        verbose_name_plural = verbose_name
        unique_together = [('source_product', 'target_product', 'relation_type')]

    def __str__(self):
        return f'{self.source_product} -> {self.target_product} ({self.relation_type})'


class ProductProtocol(TimeStampedModel):
    """产品↔协议直接相关性（三轴融合，§14.3）。

    保持 MethodProtocol 桥不变（铁律①全量保留派生链路）；本表为产品↔协议的
    直接相关性收口，承载三轴融合总分与分量，驱动编辑页/详情页的排序、折叠与
    透明徽标。数据全量保留（折叠≠删除）。
    """

    class LinkSource(models.TextChoices):
        EXPLICIT = 'explicit', '显式关联'
        INHERITED = 'inherited', '派生关联'
        AUTO = 'auto', '自动匹配'

    class Basis(models.TextChoices):
        VENDOR_ONLY = 'vendor_only', '厂商声称'
        BIOZ_ALIGNED = 'bioz_aligned', '文献对齐'
        EMBEDDING_BREAK = 'embedding_break', '语义打散'
        COMBINED = 'combined', '综合'

    class Tier(models.TextChoices):
        DOCUMENT = 'document', '文档相关'
        LITERATURE = 'literature', '文献支持'
        FEATURED = 'featured', '编辑精选'  # 历史值：S4 起不再自动派生/默认；仅存量回退兼容
        WEAK = 'weak', '弱相关'  # S4 新增：广播/仅语义相似桶（S_A=0 且 S_B=0），恒沉底

    product = models.ForeignKey(
        'commerce.Product', on_delete=models.CASCADE,
        related_name='protocol_links', verbose_name='产品'
    )
    protocol = models.ForeignKey(
        'knowledge.Protocol', on_delete=models.CASCADE,
        related_name='product_protocols', verbose_name='协议'
    )
    relevance_score = models.FloatField(
        db_index=True, default=0.0, verbose_name='相关性总分'
    )
    score_a = models.FloatField(null=True, blank=True, verbose_name='轴A 厂商声称')
    score_b = models.FloatField(null=True, blank=True, verbose_name='轴B 文献实证')
    score_c = models.FloatField(null=True, blank=True, verbose_name='轴C 语义')
    literature_count = models.IntegerField(default=0, verbose_name='对齐文献数')
    relevance_basis = models.CharField(
        max_length=32, default='', blank=True, verbose_name='相关性依据'
    )
    link_source = models.CharField(
        max_length=16, choices=LinkSource.choices,
        default=LinkSource.INHERITED, verbose_name='来源'
    )
    tier = models.CharField(
        max_length=16, choices=Tier.choices,
        default=Tier.WEAK, verbose_name='档位'
    )
    computed_at = models.DateTimeField(auto_now=True, verbose_name='计算时间')

    class Meta:
        db_table = 'product_protocol'
        verbose_name = '产品-协议相关性'
        verbose_name_plural = verbose_name
        unique_together = [('product', 'protocol')]
        indexes = [
            models.Index(fields=['product', 'relevance_score'],
                         name='product_proto_score_idx'),
            models.Index(fields=['product', 'tier'],
                         name='product_proto_tier_idx'),
        ]

    def __str__(self):
        return f'{self.product} ~ {self.protocol} (score={self.relevance_score})'
