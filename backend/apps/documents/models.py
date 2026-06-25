import json
from django.db import models


class Batch(models.Model):
    """批次 — 挂在 SKU 下，一个 SKU 可有多个批次"""
    sku = models.ForeignKey(
        'commerce.SKU', on_delete=models.CASCADE,
        related_name='batches', verbose_name='SKU'
    )
    lot_number = models.CharField(max_length=50, unique=True, verbose_name='批次号',
        help_text='例如：SC8001-L2026001')
    produced_at = models.DateField(verbose_name='生产日期')
    retest_at = models.DateField(null=True, blank=True, verbose_name='复检日期')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'batch'
        verbose_name = '批次'
        verbose_name_plural = verbose_name
        ordering = ['-produced_at']

    def __str__(self):
        return self.lot_number


class Coa(models.Model):
    """COA — 一对一绑定批次，存产品信息快照"""

    class Status(models.TextChoices):
        DRAFT = 'draft', '草稿'
        APPROVED = 'approved', '已审批'
        PUBLISHED = 'published', '已发布'

    batch = models.OneToOneField(
        Batch, on_delete=models.CASCADE,
        related_name='coa', verbose_name='批次'
    )
    doc_id = models.CharField(max_length=50, unique=True, verbose_name='文档编号',
        help_text='例如：COA-SC8001-2026-001')
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.DRAFT, verbose_name='状态'
    )

    # ── 产品快照（冗余，保证历史 COA 不变脸）──────────
    product_name = models.CharField(max_length=255, verbose_name='产品名称')
    catalog_number = models.CharField(max_length=64, verbose_name='目录号')
    cas_number = models.CharField(max_length=20, blank=True, default='', verbose_name='CAS号')
    molecular_formula = models.CharField(max_length=100, blank=True, default='', verbose_name='分子式')
    molecular_weight = models.CharField(max_length=30, blank=True, default='', verbose_name='分子量')
    storage_condition = models.CharField(max_length=200, blank=True, default='', verbose_name='储存条件')

    # ── QC 检测结果（spec 产品级，result 人工录入）─────
    appearance_spec = models.CharField(max_length=200, blank=True, default='', verbose_name='外观标准')
    appearance_result = models.CharField(max_length=200, blank=True, default='', verbose_name='外观实测')

    purity_spec = models.CharField(max_length=50, blank=True, default='', verbose_name='纯度标准')
    purity_result = models.CharField(max_length=50, blank=True, default='', verbose_name='纯度实测')
    purity_method = models.CharField(max_length=100, blank=True, default='', verbose_name='纯度方法')

    water_content_spec = models.CharField(max_length=50, blank=True, default='', verbose_name='水分标准')
    water_content_result = models.CharField(max_length=50, blank=True, default='', verbose_name='水分实测')

    melting_point = models.CharField(max_length=100, blank=True, default='', verbose_name='熔点')
    specific_rotation = models.CharField(max_length=100, blank=True, default='', verbose_name='比旋光度')
    residual_solvents = models.CharField(max_length=200, blank=True, default='', verbose_name='残留溶剂')
    heavy_metals = models.CharField(max_length=100, blank=True, default='', verbose_name='重金属')

    nmr_result = models.TextField(blank=True, default='', verbose_name='NMR 结果')
    lcms_result = models.CharField(max_length=200, blank=True, default='', verbose_name='LC-MS 结果')

    # ── 色谱条件 ────────────────────────────────────
    hplc_conditions = models.TextField(blank=True, default='', verbose_name='HPLC 条件')
    lcms_conditions = models.TextField(blank=True, default='', verbose_name='LC-MS 条件')

    # ── 签署 ────────────────────────────────────────
    qc_analyst = models.CharField(max_length=100, blank=True, default='', verbose_name='QC 分析师')
    qa_approval = models.CharField(max_length=100, blank=True, default='', verbose_name='QA 审批')
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name='审批时间')

    # ── PDF ──────────────────────────────────────────
    pdf_path = models.CharField(max_length=500, blank=True, default='', verbose_name='PDF 路径')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'coa'
        verbose_name = 'COA'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'COA {self.doc_id}'


class SdsRevision(models.Model):
    """SDS 修订版 — Product 1:N，通过 Product.current_sds 指定当前版本"""
    product = models.ForeignKey(
        'commerce.Product', on_delete=models.CASCADE,
        related_name='sds_revisions', verbose_name='产品'
    )
    revision_no = models.IntegerField(verbose_name='修订版本号')
    revised_at = models.DateField(verbose_name='修订日期')
    change_note = models.TextField(blank=True, default='', verbose_name='修订说明')

    # ── Section 2 — GHS 分类 ────────────────────────
    signal_word = models.CharField(max_length=20, blank=True, default='', verbose_name='信号词',
        help_text='Warning 或 Danger')
    pictograms = models.TextField(blank=True, default='', verbose_name='GHS 象征',
        help_text='JSON 数组，如 ["GHS07","GHS08"]')
    hazard_codes = models.TextField(blank=True, default='', verbose_name='危险代码',
        help_text='JSON 数组，如 ["H302","H315"]')
    precaution_codes = models.TextField(blank=True, default='', verbose_name='防范代码',
        help_text='JSON 数组，如 ["P261","P280"]')

    # ── 完整 16 节数据 ──────────────────────────────
    section_data = models.TextField(blank=True, default='', verbose_name='16 节数据',
        help_text='JSON 字符串，包含完整的 16 节 SDS 数据')

    # ── PDF ──────────────────────────────────────────
    pdf_path = models.CharField(max_length=500, blank=True, default='', verbose_name='PDF 路径')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sds_revision'
        verbose_name = 'SDS 修订版'
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'revision_no'],
                name='unique_product_sds_revision'
            )
        ]
        ordering = ['-revision_no']

    def __str__(self):
        return f'SDS {self.product.catalog_no or self.product.name} v{self.revision_no}'

    def get_pictograms(self):
        return json.loads(self.pictograms) if self.pictograms else []

    def set_pictograms(self, value):
        self.pictograms = json.dumps(value)

    def get_hazard_codes(self):
        return json.loads(self.hazard_codes) if self.hazard_codes else []

    def set_hazard_codes(self, value):
        self.hazard_codes = json.dumps(value)

    def get_precaution_codes(self):
        return json.loads(self.precaution_codes) if self.precaution_codes else []

    def set_precaution_codes(self, value):
        self.precaution_codes = json.dumps(value)

    def get_section_data(self):
        return json.loads(self.section_data) if self.section_data else {}

    def set_section_data(self, value):
        self.section_data = json.dumps(value, ensure_ascii=False)


class PubChemCache(models.Model):
    """PubChem 数据缓存 — 避免重复调用，便于审计"""
    cas_number = models.CharField(max_length=20, db_index=True, verbose_name='CAS号')
    cid = models.IntegerField(null=True, blank=True, verbose_name='PubChem CID')
    data_json = models.TextField(verbose_name='PubChem 数据',
        help_text='完整的 PubChem 返回数据 JSON')
    fetched_at = models.DateTimeField(auto_now=True, verbose_name='获取时间')

    class Meta:
        db_table = 'pubchem_cache'
        verbose_name = 'PubChem 缓存'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'PubChem CAS:{self.cas_number} (CID:{self.cid})'

    def get_data(self):
        return json.loads(self.data_json) if self.data_json else {}
