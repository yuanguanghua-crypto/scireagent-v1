"""C2 生成器单测 — generate_verified_drafts 落库行为（FakeClient 零网络）。

覆盖：草稿字段（review/source_rc NULL/curator=system:miner/note 溯源）/
幂等/不自动 approve/无方法不落库/dry-run 不写库/零候选/已有 ACTIVE 同 PMID 跳过。
"""
import pytest

from apps.bridges.models import ProductMethodRelation
from apps.bridges.services.evidence_miner import ORIGIN_TAG
from apps.bridges.services.verified_drafts_generator import generate_verified_drafts
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.tests.factories import MethodFactory

pytestmark = pytest.mark.django_db


class FakeClient:
    def __init__(self, by_term=None, docs=None):
        self.by_term = by_term or {}
        self.docs = docs or {}

    def esearch(self, term, retmax=5):
        hit = self.by_term.get(term)
        if hit is None:
            return {'count': '0', 'idlist': []}
        return {'count': str(hit.get('count', len(hit['idlist']))),
                'idlist': hit['idlist']}

    def esummary(self, ids):
        return {'uids': ids, **{str(i): self.docs.get(int(i)) for i in ids}}


def _setup_product_method(method_name='DNA Polymerase', title_extra='assay'):
    """构造 5-Iodo-dUTP 产品 + 命中标题的 method + FakeClient。
    显式传 methods 表，隔离真实 DB 的 91 个 Method（避免单 token 方法抢位）。
    """
    product = ProductFactory(name='5-Iodo-dUTP', cas='', synonyms=[])
    method = MethodFactory(name=method_name)
    title = f'5-Iodo-dUTP in {method_name} {title_extra}'
    client = FakeClient(
        by_term={'"5-iodo-dutp"': {'idlist': ['123'], 'count': 1}},
        docs={123: {'title': title, 'source': 'JBC', 'pubdate': '1968'}})
    methods = [{'id': method.id, 'name': method.name, 'slug': method.slug}]
    return product, method, client, methods


def _draft_count(product, method):
    return ProductMethodRelation.objects.filter(
        product=product, method=method,
        relation_type='verified_applicability').count()


def test_create_draft_has_correct_fields():
    product, method, client, methods = _setup_product_method()
    stats = generate_verified_drafts([product.id], apply=True, client=client, methods=methods)
    assert stats['created'] == 1
    pmr = ProductMethodRelation.objects.get(product=product, method=method,
                                            relation_type='verified_applicability')
    assert pmr.status == 'review'                    # 不自动 approve
    assert pmr.source_reagent_class is None          # PMR-01
    assert pmr.curator == 'system:miner'
    assert pmr.evidence_type == 'pubmed'
    assert pmr.evidence_reference == [{'type': 'PMID', 'value': '123'}]
    assert ORIGIN_TAG in pmr.evidence_note           # 溯源护栏①
    assert 'relevance:pass' in pmr.evidence_note
    assert f'matched_method:{method.name}' in pmr.evidence_note
    assert pmr.evidence_strength == 'medium'         # 保守，不自动升级 high


def test_idempotent_second_run_skips_duplicate():
    product, method, client, methods = _setup_product_method()
    first = generate_verified_drafts([product.id], apply=True, client=client, methods=methods)
    second = generate_verified_drafts([product.id], apply=True, client=client, methods=methods)
    assert first['created'] == 1
    assert second['skipped_dup'] == 1
    assert second['created'] == 0
    assert _draft_count(product, method) == 1


def test_no_auto_approve_status_stays_review():
    product, method, client, methods = _setup_product_method()
    generate_verified_drafts([product.id], apply=True, client=client, methods=methods)
    pmr = ProductMethodRelation.objects.get(product=product, method=method)
    assert pmr.status == 'review'


def test_no_method_match_not_persisted():
    product = ProductFactory(name='5-Iodo-dUTP', cas='', synonyms=[])
    client = FakeClient(
        by_term={'"5-iodo-dutp"': {'idlist': ['456'], 'count': 1}},
        # 标题含产品信号（5-Iodo-dUTP）但不含任何方法 → 走 no_method 分支
        docs={456: {'title': '5-Iodo-dUTP synthesis of thiouridine triphosphate',
                    'source': 'Chem Ber', 'pubdate': '1968'}})
    # 显式隔离方法表：标题不含 DNA Polymerase，必落 no_method
    methods = [{'id': 1, 'name': 'DNA Polymerase', 'slug': 'dna-polymerase'}]
    stats = generate_verified_drafts([product.id], apply=True, client=client,
                                     methods=methods)
    assert stats['no_method'] == 1
    assert stats['created'] == 0
    assert ProductMethodRelation.objects.filter(product=product).count() == 0


def test_dry_run_does_not_write():
    product, method, client, methods = _setup_product_method()
    stats = generate_verified_drafts([product.id], apply=False, client=client, methods=methods)
    assert stats['planned'] == 1
    assert stats['created'] == 0
    assert _draft_count(product, method) == 0


def test_zero_candidate_counts():
    product = ProductFactory(name='Rare-Compound-X', cas='', synonyms=[])
    client = FakeClient()  # 所有检索 0 命中（不涉及方法匹配，无需传 methods）
    stats = generate_verified_drafts([product.id], apply=True, client=client)
    assert stats['zero_candidate'] == 1
    assert stats['created'] == 0


def test_existing_active_same_pmid_skipped():
    product, method, client, methods = _setup_product_method()
    # 预置一条 ACTIVE verified（同 PMID）→ 生成器应跳过不重复建
    ProductMethodRelation.objects.create(
        product=product, method=method,
        relation_type='verified_applicability', source_reagent_class=None,
        status='active', evidence_type='pubmed',
        evidence_reference=[{'type': 'PMID', 'value': '123'}],
        evidence_strength='high', evidence_note='', curator='staff1')
    stats = generate_verified_drafts([product.id], apply=True, client=client, methods=methods)
    assert stats['skipped_dup'] == 1
    assert stats['created'] == 0
    assert _draft_count(product, method) == 1  # 未被覆盖
    pmr = ProductMethodRelation.objects.get(product=product, method=method)
    assert pmr.status == 'active'  # 原 ACTIVE 不被降级
