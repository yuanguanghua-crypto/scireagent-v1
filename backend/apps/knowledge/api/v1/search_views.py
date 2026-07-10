from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Q
from apps.commerce.models import Product
from apps.knowledge.models import Application, Method, Protocol, Reference


@api_view(['GET'])
def search(request):
    """Universal search across all resources."""
    q = request.query_params.get('q', '').strip()
    resource_type = request.query_params.get('type', '')

    if not q:
        return Response({'success': True, 'data': [], 'meta': {'query': q}})

    results = []

    if not resource_type or resource_type == 'product':
        products = Product.objects.filter(
            Q(name__icontains=q) | Q(cas__icontains=q) | Q(smiles__icontains=q) |
            Q(inchi__icontains=q) | Q(catalog_no__icontains=q) | Q(formula__icontains=q) |
            Q(overview__icontains=q)
        )[:20]
        results.extend([
            {'type': 'product', 'id': p.id, 'name': p.name, 'slug': p.slug,
             'cas': p.cas, 'catalog_no': p.catalog_no, 'formula': p.formula}
            for p in products
        ])

    if not resource_type or resource_type == 'application':
        apps = Application.objects.filter(
            Q(name__icontains=q) | Q(summary__icontains=q)
        )[:10]
        results.extend([
            {'type': 'application', 'id': a.id, 'name': a.name, 'slug': a.slug}
            for a in apps
        ])

    if not resource_type or resource_type == 'method':
        methods = Method.objects.filter(
            Q(name__icontains=q) | Q(summary__icontains=q) | Q(purpose__icontains=q)
        )[:10]
        results.extend([
            {'type': 'method', 'id': m.id, 'name': m.name, 'slug': m.slug}
            for m in methods
        ])

    if not resource_type or resource_type == 'protocol':
        protocols = Protocol.objects.filter(
            Q(name__icontains=q) | Q(objective__icontains=q)
        )[:10]
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
        'meta': {'query': q, 'count': len(results)},
    })


@api_view(['GET'])
def search_suggest(request):
    """Search suggestions for autocomplete."""
    q = request.query_params.get('q', '').strip()
    if not q or len(q) < 2:
        return Response({'success': True, 'data': [], 'meta': {}})

    products = Product.objects.filter(name__icontains=q)[:5]
    methods = Method.objects.filter(name__icontains=q)[:3]

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
