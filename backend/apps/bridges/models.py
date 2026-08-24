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

    # ---- 顶部链治理新增字段（migration 0005_methodprotocol_evidence_source）----
    evidence_source = models.CharField(
        max_length=32, blank=True, default='legacy', verbose_name='关联来源',
        help_text='lexicon_auto=词典自动标注；manual_curated=人工策展；llm_reviewed=LLM 判定；legacy=历史遗留映射',
        choices=[
            ('lexicon_auto', '词典自动标注'),
            ('manual_curated', '人工策展'),
            ('llm_reviewed', 'LLM 判定'),
            ('legacy', '历史遗留'),
        ],
    )

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


# ---------------------------------------------------------------------------
# Reagent Class 桥层（Reagent Class Schema V1.1 / Migration V2.1.3）
# 三层：ReagentClass(knowledge) ← MethodReagentClass ← ProductReagentClass
#       与 ProductMethodRelation（derived materialized cache / verified canonical）
# 治理规则：RC-01~RC-11（见 Reagent_Class_Migration_Implementation_V212.md + Patch V2.1.3）
# ---------------------------------------------------------------------------

ALLOWED_EVIDENCE_REF_TYPES = {'PMID', 'DOI', 'PROTOCOL', 'MANUFACTURER', 'DOC'}


def validate_evidence_reference(value):
    """evidence_reference JSON 结构校验（Python/seed 层，非 DB 约束）。

    规则：list → 每项 dict → type ∈ 枚举 → value 非空。
    拒绝：{}、[{}]、[{"type":"XXX",...}]、[{"type":"PMID","value":""}]。
    """
    from django.core.exceptions import ValidationError
    if value is None:
        return
    if not isinstance(value, list):
        raise ValidationError('evidence_reference 必须是 list')
    for item in value:
        if not isinstance(item, dict):
            raise ValidationError(f'evidence_reference 元素必须是 dict: {item!r}')
        if 'type' not in item or item.get('type') not in ALLOWED_EVIDENCE_REF_TYPES:
            raise ValidationError(f"非法 evidence type: {item.get('type')!r}（允许 {sorted(ALLOWED_EVIDENCE_REF_TYPES)}）")
        if 'value' not in item or not str(item.get('value') or '').strip():
            raise ValidationError(f'evidence value 非空: {item!r}')


class MethodReagentClass(TimeStampedModel):
    """Method ↔ ReagentClass 依赖桥（RC-01/RC-05/RC-07/RC-11）。

    dependency_type（是什么依赖）× scope（依赖在哪个实现范围成立）独立判定；
    dependency_group="" = ungrouped（不参与 OR 分组）；同组须 same dependency_type（RC-11）。
    """

    class DependencyType(models.TextChoices):
        ESSENTIAL = 'essential', 'essential'
        ENABLING = 'enabling', 'enabling'
        OPTIONAL = 'optional', 'optional'

    class Scope(models.TextChoices):
        CANONICAL = 'canonical', 'canonical'
        COMMON = 'common', 'common'
        CONDITIONAL = 'conditional', 'conditional'

    class EvidenceType(models.TextChoices):
        METHOD_DEFINITION = 'method_definition', 'method_definition'
        PROTOCOL = 'protocol', 'protocol'
        LITERATURE = 'literature', 'literature'
        MANUFACTURER = 'manufacturer', 'manufacturer'
        CURATED_INFERENCE = 'curated_inference', 'curated_inference'

    class EvidenceStrength(models.TextChoices):
        HIGH = 'high', 'high'
        MEDIUM = 'medium', 'medium'
        LOW = 'low', 'low'

    class Status(models.TextChoices):
        CURATED = 'curated', 'curated'
        PENDING_REVIEW = 'pending_review', 'pending_review'
        DEPRECATED = 'deprecated', 'deprecated'

    method = models.ForeignKey(
        'knowledge.Method', on_delete=models.PROTECT, related_name='reagent_classes', verbose_name='方法',
    )
    reagent_class = models.ForeignKey(
        'knowledge.ReagentClass', on_delete=models.PROTECT, related_name='methods', verbose_name='试剂类',
    )
    dependency_type = models.CharField(
        max_length=12, choices=DependencyType.choices, db_index=True, verbose_name='依赖类型',
    )
    scope = models.CharField(
        max_length=12, choices=Scope.choices, default=Scope.COMMON, db_index=True, verbose_name='适用范围',
    )
    dependency_group = models.CharField(
        max_length=60, blank=True, default='', db_index=True, verbose_name='功能依赖组',
        help_text='同 method+group 内多 RC = 可替代实现集合（OR，须 same dependency_type，RC-11）；""=ungrouped',
    )
    evidence_type = models.CharField(
        max_length=24, choices=EvidenceType.choices, default=EvidenceType.CURATED_INFERENCE, verbose_name='证据类型',
    )
    evidence_reference = models.JSONField(
        default=list, blank=True, validators=[validate_evidence_reference], verbose_name='证据引用',
        help_text='[{type: PMID|DOI|PROTOCOL|MANUFACTURER|DOC, value}]',
    )
    evidence_strength = models.CharField(
        max_length=6, choices=EvidenceStrength.choices, default=EvidenceStrength.LOW, verbose_name='证据强度',
    )
    evidence_note = models.TextField(blank=True, default='', verbose_name='证据说明')
    curator = models.CharField(max_length=100, blank=True, default='', verbose_name='策展人')
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.CURATED, verbose_name='状态',
    )

    class Meta:
        db_table = 'method_reagent_class'
        verbose_name = '方法-试剂类依赖'
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(fields=['method', 'reagent_class'], name='uq_mrc_method_rc'),
            models.CheckConstraint(
                # scope=conditional 时禁止 essential（V2.1.1 §1.4 非法组合）
                condition=~models.Q(scope='conditional') | ~models.Q(dependency_type='essential'),
                name='ck_mrc_conditional_not_essential',
            ),
        ]
        indexes = [
            models.Index(fields=['method', 'dependency_group'], name='idx_mrc_method_group'),
        ]

    def __str__(self):
        return f'{self.method} ←{self.dependency_type}→ {self.reagent_class}'


class ProductReagentClass(TimeStampedModel):
    """Product ↔ ReagentClass 分类桥（RC-02/RC-08/RC-10）。

    status 状态机：candidate → pending_review → auto_accepted → human_verified / rejected；
    auto_accepted 仅在 rule registry threshold_passed 后产生（RC-10，Rule Governance Test）。
    """

    class AssignmentType(models.TextChoices):
        PRIMARY = 'primary', 'primary'
        SECONDARY = 'secondary', 'secondary'
        CONDITIONAL = 'conditional', 'conditional'

    class ClassificationMethod(models.TextChoices):
        RULE = 'rule', 'rule'
        AI = 'ai', 'ai'
        MANUAL = 'manual', 'manual'

    class Confidence(models.TextChoices):
        HIGH = 'high', 'high'
        MEDIUM = 'medium', 'medium'
        LOW = 'low', 'low'

    class Status(models.TextChoices):
        CANDIDATE = 'candidate', 'candidate'
        PENDING_REVIEW = 'pending_review', 'pending_review'
        AUTO_ACCEPTED = 'auto_accepted', 'auto_accepted'
        HUMAN_VERIFIED = 'human_verified', 'human_verified'
        REJECTED = 'rejected', 'rejected'
        DEPRECATED = 'deprecated', 'deprecated'

    product = models.ForeignKey(
        'commerce.Product', on_delete=models.PROTECT, related_name='reagent_classes', verbose_name='产品',
    )
    reagent_class = models.ForeignKey(
        'knowledge.ReagentClass', on_delete=models.PROTECT, related_name='products', verbose_name='试剂类',
    )
    assignment_type = models.CharField(
        max_length=12, choices=AssignmentType.choices, default=AssignmentType.PRIMARY, verbose_name='分类角色',
    )
    classification_method = models.CharField(
        max_length=8, choices=ClassificationMethod.choices, default=ClassificationMethod.RULE, verbose_name='分类方法',
    )
    classification_rule = models.CharField(
        max_length=100, blank=True, default='', db_index=True, verbose_name='分类规则 ID',
        help_text='如 nucleotide.cy5_dutp；规则标识符，不唯一（同规则应用于多产品）',
    )
    classification_rule_version = models.CharField(
        max_length=20, blank=True, default='', verbose_name='分类规则版本',
        help_text='auto_accepted 必须引用 registry 中 threshold_passed=true 的版本',
    )
    confidence = models.CharField(
        max_length=6, choices=Confidence.choices, default=Confidence.MEDIUM, verbose_name='置信度',
        help_text='规则/模型置信度，≠科学有效性（RC-04）',
    )
    evidence = models.TextField(blank=True, default='', verbose_name='分类证据',
                                help_text='解释文本；assignment_type=conditional 时必填（RC-08）')
    curator = models.CharField(max_length=100, blank=True, default='', verbose_name='策展人')
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING_REVIEW, db_index=True, verbose_name='状态',
        help_text='RC-10：未过阈值验证前不得 auto_accepted',
    )

    class Meta:
        db_table = 'product_reagent_class'
        verbose_name = '产品-试剂类分类'
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(fields=['product', 'reagent_class'], name='uq_prc_product_rc'),
            models.CheckConstraint(
                # RC-08：conditional 必须有 evidence（非 NULL 非空串）
                condition=~models.Q(assignment_type='conditional')
                          | (models.Q(evidence__isnull=False) & ~models.Q(evidence='')),
                name='ck_prc_conditional_requires_evidence',
            ),
        ]
        indexes = [
            models.Index(fields=['product'], name='idx_prc_product'),
            models.Index(fields=['reagent_class'], name='idx_prc_rc'),
        ]

    def __str__(self):
        return f'{self.product} → {self.reagent_class} ({self.status})'


class ProductMethodRelation(TimeStampedModel):
    """Product ↔ Method 关系（derived / verified 双 edge 分离，RC-09/PMR-01）。

    - derived_relevance：materialized cache（allow-list 源重建，不可人工编辑；evidence 全空，
      source_reagent_class 必填=主路径解释，非 canonical provenance）；
    - verified_applicability：canonical Product-specific 关系（source_reagent_class 必须 NULL，
      evidence 三件套必填）。
    """

    class RelationType(models.TextChoices):
        DERIVED_RELEVANCE = 'derived_relevance', 'derived_relevance'
        VERIFIED_APPLICABILITY = 'verified_applicability', 'verified_applicability'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'active'
        REVIEW = 'review', 'review'
        DEPRECATED = 'deprecated', 'deprecated'

    product = models.ForeignKey(
        'commerce.Product', on_delete=models.PROTECT, related_name='method_relations', verbose_name='产品',
    )
    method = models.ForeignKey(
        'knowledge.Method', on_delete=models.PROTECT, related_name='product_relations', verbose_name='方法',
    )
    relation_type = models.CharField(
        max_length=24, choices=RelationType.choices, db_index=True, verbose_name='关系类型',
    )
    source_reagent_class = models.ForeignKey(
        'knowledge.ReagentClass', null=True, blank=True, on_delete=models.PROTECT,
        related_name='method_relation_explanations', verbose_name='来源试剂类',
        help_text='derived 必填（主路径解释）；verified 必须 NULL（PMR-01）',
    )
    evidence_type = models.CharField(max_length=24, blank=True, default='', verbose_name='证据类型')
    evidence_reference = models.JSONField(
        null=True, blank=True, default=None, validators=[validate_evidence_reference], verbose_name='证据引用',
    )
    evidence_strength = models.CharField(max_length=6, blank=True, default='', verbose_name='证据强度')
    evidence_note = models.TextField(blank=True, default='', verbose_name='证据说明')
    curator = models.CharField(max_length=100, blank=True, default='', verbose_name='策展人')
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE, verbose_name='状态',
    )

    class Meta:
        db_table = 'product_method_relation'
        verbose_name = '产品-方法关系'
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'method', 'relation_type'],
                name='uq_pmr_product_method_relation_type',
            ),
            models.CheckConstraint(
                # PMR-01 discriminator：derived → source_rc 必填 + evidence 全空；verified → source_rc NULL + evidence 三件套非空
                condition=(
                    (
                        models.Q(relation_type='derived_relevance')
                        & models.Q(source_reagent_class__isnull=False)
                        & models.Q(evidence_type='')
                        & models.Q(evidence_reference__isnull=True)
                        & models.Q(evidence_strength='')
                    )
                    |
                    (
                        models.Q(relation_type='verified_applicability')
                        & models.Q(source_reagent_class__isnull=True)
                        & ~models.Q(evidence_type='')
                        & models.Q(evidence_reference__isnull=False)
                        & ~models.Q(evidence_strength='')
                    )
                ),
                name='ck_pmr_relation_discriminator',
            ),
        ]
        indexes = [
            models.Index(fields=['product', 'relation_type'], name='idx_pmr_product_rt'),
            models.Index(fields=['method', 'relation_type'], name='idx_pmr_method_rt'),
        ]

    def __str__(self):
        return f'{self.product} → {self.method} ({self.relation_type})'
