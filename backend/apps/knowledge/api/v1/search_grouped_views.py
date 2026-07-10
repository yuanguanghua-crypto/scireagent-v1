"""Grouped search endpoint — /api/v1/search/grouped/

Uses PostgreSQL FTS when available, falls back to icontains for SQLite/dev.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db import connection, models
from django.db.models import Q, Value, FloatField
from apps.commerce.models import Product
from apps.knowledge.models import Application, Method, Protocol, Reference


def _is_postgres():
    return connection.vendor == 'postgresql'


def _search_products_fts(q, limit=10):
    """PostgreSQL FTS with ranking."""
    from django.contrib.postgres.search import SearchQuery, SearchRank
    query = SearchQuery(q)
    return list(
        Product.objects.filter(search_vector=query)
        .annotate(score=SearchRank('search_vector', query))
        .order_by('-score')
        .values('id', 'name', 'slug', 'catalog_no', 'cas', 'formula', 'score')[:limit]
    )


def _search_products_icontains(q, limit=10):
    """SQLite fallback: icontains with simple relevance score."""
    qs = Product.objects.filter(
        Q(name__icontains=q) | Q(cas__icontains=q) | Q(catalog_no__icontains=q) |
        Q(formula__icontains=q) | Q(overview__icontains=q)
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


def _search_model_fts(model, q, fields, limit=5):
    """Generic FTS search for a model."""
    from django.contrib.postgres.search import SearchQuery, SearchRank
    query = SearchQuery(q)
    return list(
        model.objects.filter(search_vector=query)
        .annotate(score=SearchRank('search_vector', query))
        .order_by('-score')
        .values(*fields)[:limit]
    )


def _search_model_icontains(model, q, fields, limit=5):
    """SQLite fallback: icontains search."""
    q_objects = Q()
    search_fields = [f for f in fields if f not in ('id', 'slug', 'score')]
    for f in search_fields:
        q_objects |= Q(**{f'{f}__icontains': q})
    if not q_objects:
        return []
    qs = model.objects.filter(q_objects)
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
            _search_products_fts(q, 10) if use_fts
            else _search_products_icontains(q, 10)
        )
    else:
        data['products'] = []

    if not type_filter or type_filter == 'application':
        data['applications'] = (
            _search_model_fts(Application, q, APPLICATION_FIELDS, 5) if use_fts
            else _search_model_icontains(Application, q, APPLICATION_FIELDS, 5)
        )
    else:
        data['applications'] = []

    if not type_filter or type_filter == 'method':
        data['methods'] = (
            _search_model_fts(Method, q, METHOD_FIELDS, 5) if use_fts
            else _search_model_icontains(Method, q, METHOD_FIELDS, 5)
        )
    else:
        data['methods'] = []

    if not type_filter or type_filter == 'protocol':
        data['protocols'] = (
            _search_model_fts(Protocol, q, PROTOCOL_FIELDS, 5) if use_fts
            else _search_model_icontains(Protocol, q, PROTOCOL_FIELDS, 5)
        )
    else:
        data['protocols'] = []

    if not type_filter or type_filter == 'reference':
        data['references'] = (
            _search_model_fts(Reference, q, REFERENCE_FIELDS, 5) if use_fts
            else _search_model_icontains(Reference, q, REFERENCE_FIELDS, 5)
        )
    else:
        data['references'] = []

    total = sum(len(v) for v in data.values())

    return Response({
        'success': True,
        'data': data,
        'meta': {'query': q, 'count': total},
    })
