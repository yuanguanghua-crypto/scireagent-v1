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
