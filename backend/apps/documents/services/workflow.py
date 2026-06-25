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
from .pubchem_fetcher import fetch_sds_data_from_pubchem


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
    """
    coa = Coa.objects.get(id=coa_id)
    coa.status = Coa.Status.APPROVED
    coa.qc_analyst = qc_analyst
    coa.qa_approval = qa_approval
    coa.approved_at = timezone.now()

    # 生成 PDF
    pdf_rel_path = generate_coa_pdf(coa)
    coa.pdf_path = pdf_rel_path
    coa.save()
    return coa


# ═══════════════════════════════════════════════════════════
# SDS 工作流
# ═══════════════════════════════════════════════════════════

def generate_sds(product_id):
    """
    为产品生成新版本 SDS。

    流程: 查 PubChemCache → 未命中则调 PubChem API → 写缓存 → 创建 SdsRevision
    """
    from apps.commerce.models import Product

    product = Product.objects.get(id=product_id)
    cas = product.cas or ''
    if not cas:
        raise ValueError('产品没有 CAS 号，无法生成 SDS')

    # 查询缓存
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

    # 从 PubChem 获取数据
    pubchem_data = fetch_sds_data_from_pubchem(
        cas, from_cache_fn=from_cache, save_cache_fn=save_cache
    )

    if not pubchem_data:
        raise ValueError(f'无法从 PubChem 获取 CAS {cas} 的数据')

    # 计算下一个修订版本号
    last_rev = SdsRevision.objects.filter(product=product).order_by('-revision_no').first()
    next_no = (last_rev.revision_no + 1) if last_rev else 1

    # 组装 section_data
    section_data = pubchem_data.get('section_data', {})

    # 创建 SdsRevision
    sds = SdsRevision.objects.create(
        product=product,
        revision_no=next_no,
        revised_at=datetime.date.today(),
        change_note=f'Auto-generated from PubChem (CID: {pubchem_data.get("cid", "N/A")})',
        signal_word=pubchem_data.get('signal_word', 'Warning'),
        pictograms=json.dumps(pubchem_data.get('pictograms', [])),
        hazard_codes=json.dumps(pubchem_data.get('hazard_codes', [])),
        precaution_codes=json.dumps(pubchem_data.get('precaution_codes', [])),
        section_data=json.dumps(section_data, ensure_ascii=False),
    )
    return sds


def approve_sds(revision_id):
    """
    审批 SDS + 生成 PDF + 设置为当前版本。
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

    return sds
