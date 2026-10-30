from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Case, IntegerField, Q, Value, When
from apps.commerce.models import Product
from apps.knowledge.models import (
    Application, Method, Protocol, ProtocolFacet, Reference,
)
from apps.knowledge.api.v1.fixture_visibility import apply_public_visibility


def facet_protocol_ids(q):
    """facet 受控词表命中的协议 id（子查询）。

    ★ 2026-10-30：搜索此前只查 `name` + `objective`，完全不看 facet 标签，
    导致「搜 DNA extraction 只回 10 条协议，而 facet 里 `DNA Extraction & Purification`
    实际标了 325 条」—— 差 32 倍。facet 是全库唯一收敛干净的分类层（121 个值），
    搜索不用它等于把整理好的数据白放着。

    性能：`facet_value` 只有 121 行，Seq Scan + ILIKE 实测 4.5ms，可直接进搜索主路径。
    """
    return ProtocolFacet.objects.filter(
        Q(facet__value__icontains=q) | Q(facet__slug__icontains=q)
    ).values('protocol_id')


def protocol_search_qs(q, request):
    """协议的搜索 QuerySet：名称/摘要/facet 三路命中，按相关度排序。

    排序口径：名称命中(3) > 目标摘要命中(2) > 仅 facet 标签命中(1)。
    没有这个排序，325 条 facet 命中的协议会把真正名称匹配的挤到后面。
    """
    qs = Protocol.objects.filter(
        Q(name__icontains=q) | Q(objective__icontains=q)
        | Q(id__in=facet_protocol_ids(q))
    ).annotate(
        _rank=Case(
            When(name__icontains=q, then=Value(3)),
            When(objective__icontains=q, then=Value(2)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by('-_rank', 'id')
    return apply_public_visibility(qs, Protocol, request)


@api_view(['GET'])
def search(request):
    """Universal search across all resources."""
    q = request.query_params.get('q', '').strip()
    resource_type = request.query_params.get('type', '')

    if not q:
        return Response({'success': True, 'data': [], 'meta': {'query': q}})

    results = []

    if not resource_type or resource_type == 'product':
        # P0：统一入口（staff 全量）；archived 对所有人隐藏（展示决策）
        products = apply_public_visibility(
            Product.objects.filter(
                Q(name__icontains=q) | Q(cas__icontains=q) | Q(smiles__icontains=q) |
                Q(inchi__icontains=q) | Q(catalog_no__icontains=q) | Q(formula__icontains=q) |
                Q(overview__icontains=q)
            ).exclude(archived=True),
            Product, request,
        )[:20]
        results.extend([
            {'type': 'product', 'id': p.id, 'name': p.name, 'slug': p.slug,
             'cas': p.cas, 'catalog_no': p.catalog_no, 'formula': p.formula}
            for p in products
        ])

    if not resource_type or resource_type == 'application':
        # S1：夹具过滤 + P0：公开读 draft 不可见（统一入口）
        apps = apply_public_visibility(Application.objects.filter(
            Q(name__icontains=q) | Q(summary__icontains=q)
        ), Application, request)[:10]
        results.extend([
            {'type': 'application', 'id': a.id, 'name': a.name, 'slug': a.slug}
            for a in apps
        ])

    if not resource_type or resource_type == 'method':
        methods = apply_public_visibility(Method.objects.filter(
            Q(name__icontains=q) | Q(summary__icontains=q) | Q(purpose__icontains=q)
        ), Method, request)[:10]
        results.extend([
            {'type': 'method', 'id': m.id, 'name': m.name, 'slug': m.slug}
            for m in methods
        ])

    protocol_matched = 0
    if not resource_type or resource_type == 'protocol':
        # P0：协议公开态 = published（原实现完全无过滤，结构性泄漏点）
        # 2026-10-30：三路命中（名称/摘要/facet 标签），并给出匹配总数，
        # 让前端能说「共 N 条，这里显示前 10」而不是假装只有 10 条。
        qs = protocol_search_qs(q, request)
        protocol_matched = qs.count()
        protocols = qs[:10]
        results.extend([
            {'type': 'protocol', 'id': p.id, 'name': p.name, 'slug': p.slug, 'version': p.version}
            for p in protocols
        ])

    if not resource_type or resource_type == 'reference':
        refs = Reference.objects.filter(
            Q(title__icontains=q) | Q(authors__icontains=q) | Q(doi__icontains=q)
        )[:10]
        results.extend([
            {'type': 'reference', 'id': r.id, 'title': r.title, 'doi': r.doi}
            for r in refs
        ])

    return Response({
        'success': True,
        'data': results,
        # `count` 是**返回条数**（保持旧契约）；`matched` 是**真实匹配总数**。
        # 两者必须分开：搜索"DNA extraction"时 matched=325 而 count=10，
        # 前端据此显示"共 325 条，显示前 10"，用户才知道该去列表页翻。
        'meta': {'query': q, 'count': len(results),
                 'matched': {'protocols': protocol_matched}},
    })


@api_view(['GET'])
def search_suggest(request):
    """Search suggestions for autocomplete."""
    q = request.query_params.get('q', '').strip()
    if not q or len(q) < 2:
        return Response({'success': True, 'data': [], 'meta': {}})

    products = apply_public_visibility(
        Product.objects.filter(name__icontains=q).exclude(archived=True),
        Product, request,
    )[:5]
    methods = apply_public_visibility(
        Method.objects.filter(name__icontains=q), Method, request
    )[:3]

    suggestions = []
    for p in products:
        suggestions.append({'type': 'product', 'id': p.id, 'text': p.name})
    for m in methods:
        suggestions.append({'type': 'method', 'id': m.id, 'text': m.name})

    return Response({
        'success': True,
        'data': suggestions,
        'meta': {'query': q},
    })
