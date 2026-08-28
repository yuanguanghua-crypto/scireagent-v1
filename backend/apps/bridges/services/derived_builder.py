"""derived_relevance 边服务化重建（R3 重构 + MUST-15）。

源资格（v0.2 MUST-15 四道 AND）：
  PRC.status      ∈ {auto_accepted, human_verified}
  AND RC.status    = approved
  AND MRC.status   = curated
  AND Method.slug  ∈ allow-list   (rule_registry.method_allowed)
  AND Product.archived = False

设计纪律（来自 GPT 评审 + 项目铁律）：
  - 本模块可被 Django app 内安全 import（无顶层 django.setup，避免 R3 阻断）
  - 单产品重建：DELETE 仅 derived_relevance（绝不碰 verified_applicability，A6 护栏）
  - 事务内 select_for_update(Product) 串行化同产品 rebuild（MUST-2 低成本一致性保险）
  - 复用现有 rc_rebuild 的优先级逻辑（primary=0 < secondary=1 < conditional=2）
  - 向后兼容：rebuild_all_derived() 供 rc_rebuild.py CLI 委托（8-24 生产 backfill 语义）
"""
from django.db import transaction

from apps.bridges.models import (
    ProductMethodRelation,
    ProductReagentClass,
    MethodReagentClass,
)
from apps.bridges.services.rule_registry import method_allowed

ALLOWED_PRC = ['auto_accepted', 'human_verified']
PRIO = {'primary': 0, 'secondary': 1, 'conditional': 2}


def _build_edges_for_product(product) -> list:
    """返回该产品 eligible derived 边 [(product_id, method_id, source_rc_id, prio)]，含 MUST-15。"""
    edges = {}
    prcs = (
        ProductReagentClass.objects
        .filter(product=product, status__in=ALLOWED_PRC,
                reagent_class__status='approved', product__archived=False)
        .select_related('reagent_class')
        .values('id', 'product_id', 'reagent_class_id', 'assignment_type')
    )
    if not prcs:
        return []
    rc_ids = {p['reagent_class_id'] for p in prcs}
    mrcs = (
        MethodReagentClass.objects
        .filter(status='curated', reagent_class__status='approved',
                reagent_class_id__in=rc_ids)
        .select_related('method', 'reagent_class')
        .values('method_id', 'reagent_class_id', 'method__slug')
    )
    # MUST-15 第 4 道 AND：Method allow-list 过滤
    eligible_method_ids = {m['method_id'] for m in mrcs if method_allowed(m['method__slug'])}
    mrc_by_rc = {}
    for m in mrcs:
        if m['method_id'] in eligible_method_ids:
            mrc_by_rc.setdefault(m['reagent_class_id'], []).append(m['method_id'])
    for p in prcs:
        for mid in mrc_by_rc.get(p['reagent_class_id'], []):
            key = (p['product_id'], mid)
            if key not in edges or PRIO[p['assignment_type']] < edges[key][2]:
                edges[key] = (p['product_id'], mid, p['reagent_class_id'], PRIO[p['assignment_type']])
    return list(edges.values())


def rebuild_derived_for_product(product_id) -> list:
    """单产品 derived 重建（幂等）。仅删 derived_relevance，绝不碰 verified。"""
    from apps.commerce.models import Product

    with transaction.atomic():
        product = Product.objects.select_for_update().get(pk=product_id)
        expected = _build_edges_for_product(product)
        # A6 护栏：仅删 derived_relevance，保留 verified_applicability 不变
        ProductMethodRelation.objects.filter(
            product_id=product_id, relation_type='derived_relevance'
        ).delete()
        objs = [
            ProductMethodRelation(
                product_id=pid,
                method_id=mid,
                relation_type='derived_relevance',
                source_reagent_class_id=src_rc,
                status='active',
            )
            for pid, mid, src_rc, _ in expected
        ]
        ProductMethodRelation.objects.bulk_create(objs)
    return expected


def rebuild_all_derived() -> int:
    """全量 backfill（向后兼容 rc_rebuild.py CLI 与 8-24 生产语义）。"""
    from apps.commerce.models import Product

    count = 0
    for pid in Product.objects.values_list('id', flat=True):
        rebuild_derived_for_product(pid)
        count += 1
    return count
