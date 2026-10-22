"""Grouped search endpoint — /api/v1/search/grouped/

Uses PostgreSQL FTS (computed at query time) when available, falls back to
icontains for SQLite/dev.

The FTS vector is built *per query* from the model's searchable text columns
(with ``Coalesce`` so a single NULL column does not nullify the whole vector).
This deliberately does NOT depend on a pre-populated stored ``search_vector``
column — that column is empty in production (the migration only created it +
a GIN index, with no trigger/backfill), which is exactly why the old FTS path
returned zero results for every query.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db import connection, models
from django.db.models import F, Q, Value, TextField
from django.db.models.functions import Coalesce, Cast
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from apps.commerce.models import Product
from apps.knowledge.models import Application, Method, Protocol, Reference
from apps.knowledge.api.v1.fixture_visibility import apply_public_visibility


def _is_postgres():
    return connection.vendor == 'postgresql'


# Searchable text columns per model (used to build the query-time tsvector).
_PRODUCT_SEARCH_COLS = ['name', 'cas', 'catalog_no', 'formula', 'overview']
_APPLICATION_SEARCH_COLS = ['name', 'summary']
_METHOD_SEARCH_COLS = ['name', 'summary', 'purpose']
_PROTOCOL_SEARCH_COLS = ['name', 'objective']
_REFERENCE_SEARCH_COLS = ['title', 'authors', 'doi']



def _search_products_fts(q, limit=10, request=None):
    """PostgreSQL FTS with ranking — computed at query time.

    Supplements with substring (icontains) matches on ``catalog_no``/``cas``/
    ``name`` when the FTS hit count is below ``limit``. FTS matches whole
    tokens only, so a fragment like ``8003`` (inside ``SC8003``) would
    otherwise never match — the substring fallback covers that case.
    """
    query = SearchQuery(q)
    # ★ 2026-10-22：查**预存列** `search_vector`，不再现场算 tsvector。
    #   实测（28,600 行 application）：现场算 205.8ms → 查列 5.96ms（全命中）/ 0.059ms（走 GIN 索引）。
    #   列由 `0024_search_vector_triggers` 的 trigger 维护 + 首次回填。
    fts = list(
        apply_public_visibility(
            Product.objects.exclude(archived=True), Product, request
        )
        .annotate(score=SearchRank(F('search_vector'), query))
        .filter(search_vector=query)
        .order_by('-score')
        .values('id', 'name', 'slug', 'catalog_no', 'cas', 'formula', 'score')[:limit]
    )
    if len(fts) >= limit:
        return fts
    # Supplement with substring matches not already present in the FTS results.
    seen = {r['id'] for r in fts}
    ql = q.lower()
    supp = apply_public_visibility(
        Product.objects.exclude(archived=True).filter(
            Q(catalog_no__icontains=q) | Q(cas__icontains=q) | Q(name__icontains=q)
        ), Product, request,
    ).exclude(id__in=seen).values(
        'id', 'name', 'slug', 'catalog_no', 'cas', 'formula'
    )[: limit - len(fts)]
    for p in supp:
        if ql in (p['catalog_no'] or '').lower():
            score = 0.6
        elif ql in (p['cas'] or '').lower():
            score = 0.55
        else:
            score = 0.5
        fts.append({**p, 'score': score})
    return fts


def _search_products_icontains(q, limit=10, request=None):
    """SQLite fallback: icontains with simple relevance score."""
    qs = apply_public_visibility(
        Product.objects.exclude(archived=True).filter(
            Q(name__icontains=q) | Q(cas__icontains=q) | Q(catalog_no__icontains=q) |
            Q(formula__icontains=q) | Q(overview__icontains=q)
        ), Product, request,
    )
    results = []
    for p in qs[:limit]:
        score = 0.0
        q_lower = q.lower()
        if q_lower in (p.name or '').lower():
            score = 1.0
        elif q_lower in (p.cas or '').lower():
            score = 0.8
        elif q_lower in (p.catalog_no or '').lower():
            score = 0.6
        else:
            score = 0.3
        results.append({
            'id': p.id, 'name': p.name, 'slug': p.slug,
            'catalog_no': p.catalog_no, 'cas': p.cas,
            'formula': p.formula, 'score': score,
        })
    return sorted(results, key=lambda x: -x['score'])


def _base_qs(model, request):
    """S1 夹具过滤 + P0 status 公开态过滤（统一入口）。"""
    return apply_public_visibility(model.objects.all(), model, request)


def _search_model_fts(model, q, fields, search_cols, limit=5, request=None):
    """Generic FTS search for a model — query-time tsvector."""
    query = SearchQuery(q)
    # ★ 同样改为查预存列（见 products 分支的说明）。
    #   `search_cols` 参数保留：它是"哪些列构成向量"的**声明**，
    #   必须与 `0024_search_vector_triggers.TARGETS` 保持一致，否则搜索字段会静默变窄。
    return list(
        _base_qs(model, request)
        .annotate(score=SearchRank(F('search_vector'), query))
        .filter(search_vector=query)
        .order_by('-score')
        .values(*fields)[:limit]
    )


def _search_model_icontains(model, q, fields, limit=5, request=None):
    """SQLite fallback: icontains search."""
    q_objects = Q()
    search_fields = [f for f in fields if f not in ('id', 'slug', 'score')]
    for f in search_fields:
        q_objects |= Q(**{f'{f}__icontains': q})
    if not q_objects:
        return []
    qs = _base_qs(model, request).filter(q_objects)
    results = []
    for obj in qs[:limit]:
        row = {}
        for f in fields:
            if f == 'score':
                row[f] = 1.0
            else:
                row[f] = getattr(obj, f, None)
        results.append(row)
    return results


APPLICATION_FIELDS = ['id', 'name', 'slug', 'summary']
METHOD_FIELDS = ['id', 'name', 'slug', 'purpose']
PROTOCOL_FIELDS = ['id', 'name', 'slug', 'objective']
REFERENCE_FIELDS = ['id', 'title', 'journal', 'year', 'doi']


@api_view(['GET'])
def search_grouped(request):
    """Grouped search: results grouped by entity type.

    Query params:
        q (str): search query (required)
        type (str): filter to single type (optional)
            product | application | method | protocol | reference

    Returns:
        {
            success: true,
            data: {
                products: [...],
                applications: [...],
                methods: [...],
                protocols: [...],
                references: [...],
            },
            meta: { query, count }
        }
    """
    q = request.query_params.get('q', '').strip()
    type_filter = request.query_params.get('type', '').strip()

    if not q:
        return Response({
            'success': True,
            'data': {
                'products': [], 'applications': [], 'methods': [],
                'protocols': [], 'references': [],
            },
            'meta': {'query': q, 'count': 0},
        })

    use_fts = _is_postgres()

    data = {}

    if not type_filter or type_filter == 'product':
        data['products'] = (
            _search_products_fts(q, 10, request) if use_fts
            else _search_products_icontains(q, 10, request)
        )
    else:
        data['products'] = []

    if not type_filter or type_filter == 'application':
        data['applications'] = (
            _search_model_fts(Application, q, APPLICATION_FIELDS, _APPLICATION_SEARCH_COLS, 5, request) if use_fts
            else _search_model_icontains(Application, q, APPLICATION_FIELDS, 5, request)
        )
    else:
        data['applications'] = []

    if not type_filter or type_filter == 'method':
        data['methods'] = (
            _search_model_fts(Method, q, METHOD_FIELDS, _METHOD_SEARCH_COLS, 5, request) if use_fts
            else _search_model_icontains(Method, q, METHOD_FIELDS, 5, request)
        )
    else:
        data['methods'] = []

    if not type_filter or type_filter == 'protocol':
        data['protocols'] = (
            _search_model_fts(Protocol, q, PROTOCOL_FIELDS, _PROTOCOL_SEARCH_COLS, 5, request) if use_fts
            else _search_model_icontains(Protocol, q, PROTOCOL_FIELDS, 5, request)
        )
    else:
        data['protocols'] = []

    if not type_filter or type_filter == 'reference':
        data['references'] = (
            _search_model_fts(Reference, q, REFERENCE_FIELDS, _REFERENCE_SEARCH_COLS, 5, request) if use_fts
            else _search_model_icontains(Reference, q, REFERENCE_FIELDS, 5, request)
        )
    else:
        data['references'] = []

    total = sum(len(v) for v in data.values())

    return Response({
        'success': True,
        'data': data,
        'meta': {'query': q, 'count': total},
    })
