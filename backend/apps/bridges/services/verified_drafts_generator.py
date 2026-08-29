"""verified 草稿生成服务层（C2）：Evidence Miner 候选 → PMR(REVIEW) 落库。

纪律：
- 两维度分离（用户 2026-08-29 裁定）：本服务只落 **relevance 级** 证据草稿
  （origin:ai_extracted + relevance:pass + matched_method），evidence_strength
  保持 miner 保守映射，**不因黄金集自动升级**；applicability 由研究员 approve 裁决。
- 幂等：同 product+method 已有 verified 边且 evidence_reference 含该 PMID → 跳过。
- 不自动 approve：落库 status 恒为 REVIEW。
- 每产品候选 ≤3（miner 层护栏 5）；无方法命中 → 进 no_method 统计不落库（宁缺毋滥）。
"""
from apps.bridges.models import ProductMethodRelation
from apps.bridges.services.evidence_miner import (
    ORIGIN_TAG, PubMedClient, match_methods_in_text, match_methods_in_title,
    mine_product,
)
from apps.commerce.models import Product
from apps.knowledge.models import Method


def _existing_pmids(product_id, method_id):
    rows = ProductMethodRelation.objects.filter(
        product_id=product_id, method_id=method_id,
        relation_type=ProductMethodRelation.RelationType.VERIFIED_APPLICABILITY,
    )
    pmids = set()
    for row in rows:
        for ref in (row.evidence_reference or []):
            if isinstance(ref, dict) and ref.get('type') == 'PMID' and ref.get('value'):
                pmids.add(str(ref['value']))
    return pmids


def generate_verified_drafts(product_ids, *, apply=False, client=None, methods=None):
    """miner 候选 → PMR(REVIEW) 草稿。

    返回统计 dict（planned/created/skipped_dup/no_method/zero_candidate/rows）。
    apply=False（默认）→ 只规划不写库（dry-run）。
    """
    client = client or PubMedClient()
    if methods is None:
        methods = [{'id': m.id, 'name': m.name, 'slug': m.slug}
                   for m in Method.objects.all()]

    stats = {'planned': 0, 'created': 0, 'skipped_dup': 0,
             'no_method': 0, 'zero_candidate': 0, 'rows': []}

    products = (Product.objects.filter(id__in=product_ids)
                .order_by('id'))
    for p in products:
        pd = {'id': p.id, 'name': p.name, 'cas': p.cas or '',
              'synonyms': p.synonyms or []}
        res = mine_product(client, pd)
        if not res['candidates']:
            stats['zero_candidate'] += 1
            continue
        for cand in res['candidates']:
            # v0.2：方法匹配用全文（标题+摘要）；标题命中记 source=title，
            # 仅摘要命中记 source=abstract（提升召回，语义仍是 relevance 级）
            record_text = cand.get('record_text') or cand.get('title', '')
            title_hits = match_methods_in_title(cand.get('title', ''), methods)
            full_hits = match_methods_in_text(record_text, methods)
            row = {'product_id': p.id, 'pmid': cand['pmid'],
                   'title': cand.get('title', '')[:80], 'strength': cand['strength']}
            if not full_hits:
                stats['no_method'] += 1
                row['method'] = None
                row['action'] = 'no_method'
                stats['rows'].append(row)
                continue
            m = full_hits[0]
            row['method'] = m['name']
            row['method_source'] = ('title' if (title_hits and title_hits[0]['id'] == m['id'])
                                    else 'abstract')
            if str(cand['pmid']) in _existing_pmids(p.id, m['id']):
                stats['skipped_dup'] += 1
                row['action'] = 'skip_dup'
                stats['rows'].append(row)
                continue
            stats['planned'] += 1
            row['action'] = 'create'
            if apply:
                note = (f"{ORIGIN_TAG}\nrelevance:pass\n"
                        f"matched_method:{m['name']}\nmethod_source:{row['method_source']}")
                ProductMethodRelation.objects.create(
                    product_id=p.id,
                    method_id=m['id'],
                    relation_type=ProductMethodRelation.RelationType.VERIFIED_APPLICABILITY,
                    source_reagent_class=None,   # PMR-01：verified 必须 NULL
                    status=ProductMethodRelation.Status.REVIEW,
                    evidence_type='pubmed',
                    evidence_reference=[{'type': 'PMID', 'value': str(cand['pmid'])}],
                    evidence_strength=cand['strength'],
                    evidence_note=note,
                    curator='system:miner',
                )
                stats['created'] += 1
            stats['rows'].append(row)
    return stats
