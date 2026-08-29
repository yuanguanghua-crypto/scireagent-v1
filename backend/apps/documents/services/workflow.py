"""
COA/SDS 工作流服务
"""
import json
import datetime
from django.utils import timezone
from django.db import transaction

from ..models import Batch, Coa, SdsRevision, PubChemCache
from .coa_generator import generate_coa_pdf
from .sds_generator import generate_sds_pdf
from .pubchem_fetcher import (
    fetch_sds_data_from_pubchem,
    fetch_sds_data,
    _build_section_data,
    _GHS_FALLBACK,
)
from .category_sds_templates import get_category_sds_template


# ═══════════════════════════════════════════════════════════
# COA 工作流
# ═══════════════════════════════════════════════════════════

def create_coa(sku_id, lot_number, produced_at, retest_at=None):
    """
    创建 Batch + COA 草稿。

    流程: SKU → 创建 Batch → 从 Product 复制快照 → 从 Product 复制 spec → 返回 Coa(draft)
    """
    from apps.commerce.models import SKU

    sku = SKU.objects.select_related('product').get(id=sku_id)
    product = sku.product

    # 创建 Batch
    batch = Batch.objects.create(
        sku=sku,
        lot_number=lot_number,
        produced_at=produced_at,
        retest_at=retest_at,
    )

    # 生成 Doc ID: COA-{catalog_no}-{year}-{seq}
    year = produced_at.year if isinstance(produced_at, datetime.date) else produced_at
    seq = Coa.objects.filter(
        catalog_number=product.catalog_no or '',
        created_at__year=year if isinstance(year, int) else year,
    ).count() + 1
    doc_id = f'COA-{product.catalog_no}-{year}-{seq:03d}'

    # 产品快照（冗余，保证历史不变）
    coa = Coa(
        batch=batch,
        doc_id=doc_id,
        status=Coa.Status.DRAFT,
        product_name=product.name,
        catalog_number=product.catalog_no or '',
        cas_number=product.cas or '',
        molecular_formula=product.formula or '',
        molecular_weight=str(product.molecular_weight) if product.molecular_weight else '',
        storage_condition=product.storage or '',
        # 产品级 spec（从 Product.purity 提取）
        purity_spec=product.purity or '',
        appearance_spec='White to off-white powder',
    )
    coa.save()
    return coa


def update_coa_qc_results(coa_id, qc_data):
    """
    更新 COA 的 QC 实测值。

    参数:
        coa_id: int
        qc_data: dict, 如 {
            'appearance_result': 'White powder',
            'purity_result': '99.52%',
            ...
        }
    """
    coa = Coa.objects.get(id=coa_id)
    for field in [
        'appearance_result', 'purity_result', 'purity_method',
        'water_content_spec', 'water_content_result',
        'melting_point', 'specific_rotation',
        'residual_solvents', 'heavy_metals',
        'nmr_result', 'lcms_result',
        'hplc_conditions', 'lcms_conditions',
    ]:
        if field in qc_data:
            setattr(coa, field, qc_data[field])
    coa.save()
    return coa


def approve_coa(coa_id, qc_analyst='', qa_approval=''):
    """
    审批 COA + 生成 PDF。

    审批即通过即发布 → 写入 PUBLISHED（COA.Status.APPROVED 仅保留兼容历史行，
    不再写入）。
    """
    coa = Coa.objects.get(id=coa_id)
    coa.status = Coa.Status.PUBLISHED
    coa.qc_analyst = qc_analyst
    coa.qa_approval = qa_approval
    coa.approved_at = timezone.now()

    # 生成 PDF
    pdf_rel_path = generate_coa_pdf(coa)
    coa.pdf_path = pdf_rel_path
    coa.save()
    return coa


def withdraw_coa(coa_id):
    """
    撤回 COA → 状态回退到 DRAFT。

    保留历史 pdf_path（旧 PDF 文件不删除），仅状态翻转；重新审批会重新生成 PDF
    并覆盖 pdf_path。
    """
    coa = Coa.objects.get(id=coa_id)
    coa.status = Coa.Status.DRAFT
    coa.save(update_fields=['status', 'updated_at'])
    return coa


# ═══════════════════════════════════════════════════════════
# SDS 工作流
# ═══════════════════════════════════════════════════════════

def _next_revision_no(product):
    """计算下一个 SDS 修订版本号。"""
    last_rev = SdsRevision.objects.filter(product=product).order_by('-revision_no').first()
    return (last_rev.revision_no + 1) if last_rev else 1


def _create_sds_revision(product, *, signal_word, pictograms, hazard_codes,
                         precaution_codes, section_data, confidence, source_detail):
    """统一创建 SdsRevision 草稿，并写入数据可信度与来源说明。"""
    next_no = _next_revision_no(product)
    sds = SdsRevision.objects.create(
        product=product,
        revision_no=next_no,
        revised_at=datetime.date.today(),
        change_note=source_detail,
        signal_word=signal_word,
        pictograms=json.dumps(pictograms),
        hazard_codes=json.dumps(hazard_codes),
        precaution_codes=json.dumps(precaution_codes),
        section_data=json.dumps(section_data, ensure_ascii=False),
        data_confidence=confidence,
        data_source_detail=source_detail,
    )
    return sds


def _category_path_of(product):
    """返回产品分类路径字符串（ProductClass 自引用树；无则回退 category_l1）。"""
    names = []
    pc = product.product_class
    while pc:
        names.insert(0, pc.name)
        pc = pc.parent
    if names:
        return ' > '.join(names)
    return product.category_l1 or ''


def _build_generic_sds_data(product):
    """L4 兜底：基于通用 16 节骨架（GENERIC_SAFETY_NOTES），无真实化合物属性。"""
    section_data = _build_section_data(
        name=product.name or 'Unknown Compound',
        formula=product.formula or '',
        mw=str(product.molecular_weight) if product.molecular_weight else '',
        xlogp='', tpsa='', hbd=0, hba=0, rtb=0,
        complexity=0, exact_mass=0, heavy_atoms=0, cid=None,
    )
    return {
        'signal_word': _GHS_FALLBACK['signal_word'],
        'pictograms': _GHS_FALLBACK['pictograms'],
        'hazard_codes': _GHS_FALLBACK['hazard_codes'],
        'precaution_codes': _GHS_FALLBACK['precaution_codes'],
        'section_data': section_data,
    }


def generate_sds(product_id):
    """
    为产品生成新版本 SDS（四级降级链，不再硬 raise）。

    L1 CAS            → PubChem                         confidence=high
    L2 SMILES/InChI/名称 → PubChem                     confidence=medium
    L3 类别模板        → get_category_sds_template       confidence=low
    L4 GENERIC 兜底    → _build_section_data(cid=None)   confidence=very_low

    任意一级成功即创建 SdsRevision(draft) 并写 data_confidence/data_source_detail；
    四级全失败（理论上仅当无任何标识且类别/通用均异常）才 raise。
    """
    from apps.commerce.models import Product

    product = Product.objects.get(id=product_id)
    cas = (product.cas or '').strip()
    smiles = (product.smiles or '').strip()
    inchi = (product.inchi or '').strip()
    name = (product.name or '').strip()

    def from_cache(cas_number):
        try:
            cache = PubChemCache.objects.get(cas_number=cas_number)
            return cache.get_data()
        except PubChemCache.DoesNotExist:
            return None

    def save_cache(cas_number, cid, data_json_str):
        PubChemCache.objects.update_or_create(
            cas_number=cas_number,
            defaults={'cid': cid, 'data_json': data_json_str}
        )

    # ── L1: CAS → PubChem ──
    if cas:
        pubchem_data = fetch_sds_data_from_pubchem(
            cas, from_cache_fn=from_cache, save_cache_fn=save_cache
        )
        if pubchem_data:
            return _create_sds_revision(
                product,
                signal_word=pubchem_data['signal_word'],
                pictograms=pubchem_data['pictograms'],
                hazard_codes=pubchem_data['hazard_codes'],
                precaution_codes=pubchem_data['precaution_codes'],
                section_data=pubchem_data['section_data'],
                confidence=SdsRevision.DataConfidence.HIGH,
                source_detail=f"PubChem CID {pubchem_data.get('cid')} (CAS {cas})",
            )

    # ── L2: SMILES / InChI / 名称 → PubChem ──
    for identifier, id_type in ((smiles, 'smiles'), (inchi, 'inchi'), (name, 'name')):
        if not identifier:
            continue
        pubchem_data = fetch_sds_data(identifier, id_type=id_type)
        if pubchem_data:
            return _create_sds_revision(
                product,
                signal_word=pubchem_data['signal_word'],
                pictograms=pubchem_data['pictograms'],
                hazard_codes=pubchem_data['hazard_codes'],
                precaution_codes=pubchem_data['precaution_codes'],
                section_data=pubchem_data['section_data'],
                confidence=SdsRevision.DataConfidence.MEDIUM,
                source_detail=f"PubChem CID {pubchem_data.get('cid')} ({id_type}: {identifier})",
            )

    # ── L3: 类别模板 ──
    category_path = _category_path_of(product)
    template = get_category_sds_template(category_path)
    if template:
        return _create_sds_revision(
            product,
            signal_word=template['signal_word'],
            pictograms=template['pictograms'],
            hazard_codes=template['hazard_codes'],
            precaution_codes=template['precaution_codes'],
            section_data=template['section_data'],
            confidence=SdsRevision.DataConfidence.LOW,
            source_detail=f"Category template: {template.get('category_label', category_path)}",
        )

    # ── L4: GENERIC 兜底 ──
    generic = _build_generic_sds_data(product)
    return _create_sds_revision(
        product,
        signal_word=generic['signal_word'],
        pictograms=generic['pictograms'],
        hazard_codes=generic['hazard_codes'],
        precaution_codes=generic['precaution_codes'],
        section_data=generic['section_data'],
        confidence=SdsRevision.DataConfidence.VERY_LOW,
        source_detail='Generic safety notes (no identifier matched)',
    )


def _sds_compliance(product):
    """SDS 合规性检查（B1，TECH-P0-3 上线合规闸门）。

    软闸门（架构铁律 5：研究员是最终权威，发布检查=告知非硬阻断）：
    产品无 CAS 号 → 不阻断发布，但返回合规警告供前端展示。
    """
    if not (product.cas or '').strip():
        return {
            'compliant': False,
            'reason': 'no_cas',
            'note': '产品无 CAS 号，SDS 合规性受限（数据来源已降级）',
        }
    return {'compliant': True}


def approve_sds(revision_id):
    """
    审批 SDS + 生成 PDF + 设置为当前版本。

    B1 起返回 (sds, compliance) 二元组：compliance 为软闸门合规检查结果
    （无 CAS 不阻断，仅告警——铁律 5）。
    """
    sds = SdsRevision.objects.select_related('product').get(id=revision_id)

    # 生成 PDF
    pdf_rel_path = generate_sds_pdf(sds)
    sds.pdf_path = pdf_rel_path
    sds.save()

    # 设置为当前版本
    product = sds.product
    product.current_sds = sds
    product.save(update_fields=['current_sds'])

    compliance = _sds_compliance(product)
    return sds, compliance


def withdraw_sds(revision_id):
    """
    撤回 SDS → 清空 Product.current_sds 指针（PDF 文件保留在 MEDIA）。

    仅当该版本正是当前版本时才清指针；历史草稿版本不受影响。
    """
    sds = SdsRevision.objects.select_related('product').get(id=revision_id)
    product = sds.product
    if product.current_sds_id == sds.id:
        product.current_sds = None
        product.save(update_fields=['current_sds'])
    return sds
