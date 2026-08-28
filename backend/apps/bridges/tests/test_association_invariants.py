"""
Association Invariant 测试（A1~A8，见方案 v0.2 §10 / GPT 评审 MUST-15）。

TDD 入口：随 Phase 1 逐步充实。A1 为首个 RED→GREEN 测试（DRAFT 护栏）。
A2~A6/A8 为 derived 生成防护网（依赖真实 rc_rebuild 服务化，R3 + MUST-15）。
A7（verified 必须有完整 evidence）属 Phase 3 verified 通道，本轮标注 TODO。

运行（单文件，避免触发全量套件）：
  cd backend && DB_ENGINE=sqlite ./venv/Scripts/python.exe -B -m pytest \
      apps/bridges/tests/test_association_invariants.py -p no:cacheprovider -v
"""
import pytest

from apps.commerce.models import Product
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.models import ReagentClass, Method
from apps.knowledge.tests.factories import MethodFactory
from apps.bridges.models import (
    ProductMethodRelation,
    ProductReagentClass,
    MethodReagentClass,
)
from apps.bridges.services.association_service import AssociationService


# ── fixtures helper（factories.py 无 PRC/MRC/RC 工厂，手动构造）──
def _make_rc(slug, status='approved'):
    return ReagentClass.objects.create(
        id_code='rc-' + slug, name='RC ' + slug, slug=slug, status=status,
    )


def _make_method(slug):
    return MethodFactory(slug=slug)


def _make_prc(product, rc, status='auto_accepted'):
    return ProductReagentClass.objects.create(
        product=product, reagent_class=rc, status=status,
    )


def _make_mrc(method, rc, status='curated', dependency_type='essential'):
    return MethodReagentClass.objects.create(
        method=method, reagent_class=rc, status=status, dependency_type=dependency_type,
    )


def _active_product(slug):
    return ProductFactory(slug=slug, status='active')


def _make_verified(product, method):
    """研究员显式确认的 verified 边（PMR-01：source_rc NULL + evidence 三件套）。"""
    return ProductMethodRelation.objects.create(
        product=product, method=method, relation_type='verified_applicability',
        source_reagent_class=None, evidence_type='pubmed',
        evidence_reference=[{'type': 'PMID', 'value': '123'}],
        evidence_strength='high', evidence_note='verified', status='active',
    )


# ── A1：DRAFT 不产生 production derived（MUST-1 + 核心原则 1）──
@pytest.mark.django_db
def test_invariant_a1_draft_product_produces_no_derived():
    product = ProductFactory(slug="a1-draft-invariant", status='draft')
    AssociationService.process_product(product.id)
    assert ProductMethodRelation.objects.filter(
        product=product, relation_type="derived_relevance"
    ).count() == 0


# ── A2：ARCHIVED 不产生新的 derived（核心原则 1 扩展）──
@pytest.mark.django_db
def test_invariant_a2_archived_product_produces_no_derived():
    product = ProductFactory(slug="a2-archived-invariant", status='archived')
    rc = _make_rc("a2-rc")
    _make_prc(product, rc, status='auto_accepted')
    _make_method("a2-m")
    AssociationService.process_product(product.id)
    assert ProductMethodRelation.objects.filter(
        product=product, relation_type="derived_relevance"
    ).count() == 0


# ── A3：PRC ∉ {auto_accepted, human_verified} → 不产生 derived ──
@pytest.mark.django_db
def test_invariant_a3_prc_rejected_produces_no_derived():
    product = _active_product("a3-active")
    rc = _make_rc("a3-rc")
    _make_prc(product, rc, status='rejected')  # 不在 ALLOWED
    method = _make_method("a3-m")
    _make_mrc(method, rc)
    AssociationService.process_product(product.id)
    assert ProductMethodRelation.objects.filter(
        product=product, relation_type="derived_relevance"
    ).count() == 0


# ── A4：ReagentClass.status != approved → 不产生 derived ──
@pytest.mark.django_db
def test_invariant_a4_rc_not_approved_produces_no_derived():
    product = _active_product("a4-active")
    rc = _make_rc("a4-rc", status='pending_review')  # 非 approved
    _make_prc(product, rc, status='auto_accepted')
    method = _make_method("a4-m")
    _make_mrc(method, rc)
    AssociationService.process_product(product.id)
    assert ProductMethodRelation.objects.filter(
        product=product, relation_type="derived_relevance"
    ).count() == 0


# ── A5：MethodReagentClass.status != curated → 不产生 derived ──
@pytest.mark.django_db
def test_invariant_a5_mrc_not_curated_produces_no_derived():
    product = _active_product("a5-active")
    rc = _make_rc("a5-rc")
    _make_prc(product, rc, status='auto_accepted')
    method = _make_method("a5-m")
    _make_mrc(method, rc, status='pending_review')  # 非 curated
    AssociationService.process_product(product.id)
    assert ProductMethodRelation.objects.filter(
        product=product, relation_type="derived_relevance"
    ).count() == 0


# ── A6：rebuild derived 绝不修改 verified_applicability（A6 护栏）──
@pytest.mark.django_db
def test_invariant_a6_derived_rebuild_keeps_verified():
    product = _active_product("a6-active")
    rc = _make_rc("a6-rc")
    _make_prc(product, rc, status='auto_accepted')
    method = _make_method("a6-m")
    _make_mrc(method, rc)
    _make_verified(product, method)  # 预先存在研究员确认的 verified 边
    assert ProductMethodRelation.objects.filter(
        product=product, relation_type='verified_applicability').count() == 1

    AssociationService.process_product(product.id)

    # derived 应生成（合规链路）
    assert ProductMethodRelation.objects.filter(
        product=product, relation_type='derived_relevance').count() == 1
    # verified 必须保持不变
    assert ProductMethodRelation.objects.filter(
        product=product, relation_type='verified_applicability').count() == 1
    v = ProductMethodRelation.objects.get(
        product=product, relation_type='verified_applicability')
    assert v.source_reagent_class is None
    assert v.evidence_type == 'pubmed'


# ── A8：同 product+method+relation_type 最多一条 PMR（优先级去重）──
@pytest.mark.django_db
def test_invariant_a8_derived_unique_per_product_method_type():
    product = _active_product("a8-active")
    rc1 = _make_rc("a8-rc1")
    rc2 = _make_rc("a8-rc2")
    method = _make_method("a8-m")
    _make_prc(product, rc1, status='auto_accepted')
    _make_prc(product, rc2, status='auto_accepted')
    _make_mrc(method, rc1)
    _make_mrc(method, rc2)  # 两 RC 都映射到同一 method
    AssociationService.process_product(product.id)
    assert ProductMethodRelation.objects.filter(
        product=product, method=method, relation_type='derived_relevance'
    ).count() == 1


# ── A7（verified 必须有完整 evidence）：属 Phase 3 verified 通道，本轮 TODO ──
# 说明：verified 边的 evidence 完整性由 PMR-01 CheckConstraint + verified API 写入校验
# 共同保证，不在 derived 管线的 Phase 1 范围内。Phase 3 实现 verified API 时补专项测试。
@pytest.mark.django_db
def test_invariant_a7_verified_requires_evidence_todo():
    pytest.skip("A7 属 Phase 3 verified 通道，待 verified API 落地后补专项测试")
