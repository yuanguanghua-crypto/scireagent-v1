from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import HttpResponse
from apps.knowledge.models import Application, Method, Protocol
from apps.commerce.models import Product


@api_view(['GET'])
def site_home(request):
    """Home page composite data."""
    featured_apps = Application.objects.filter(status='active').select_related('research_goal').order_by('sort_order')[:6]
    featured_methods = Method.objects.filter(status='active')[:6]
    featured_products = Product.objects.filter(status='active')[:6]

    return Response({
        'success': True,
        'data': {
            'hero': {
                'title': 'SciReagent',
                'subtitle': 'AI-Native Scientific Reagent Platform for Nucleotides & Click Chemistry',
            },
            'stats': {
                'applications': Application.objects.filter(status='active').count(),
                'methods': Method.objects.filter(status='active').count(),
                'protocols': Protocol.objects.filter(status='published').count(),
                'products': Product.objects.filter(status='active').count(),
            },
            'featured_applications': [
                {
                    'id': a.id,
                    'name': a.name,
                    'slug': a.slug,
                    'summary': a.summary,
                    'category': a.research_goal.name if a.research_goal else None,
                    'status': a.status,
                    'method_count': a.methods.filter(status='active').count(),
                    'created_at': a.created_at.isoformat(),
                }
                for a in featured_apps
            ],
            'featured_methods': [
                {
                    'id': m.id,
                    'name': m.name,
                    'slug': m.slug,
                    'summary': m.summary,
                    'purpose': m.purpose,
                    'status': m.status,
                    'protocol_count': m.protocols.filter(status='published').count(),
                }
                for m in featured_methods
            ],
            'featured_products': [
                {
                    'id': p.id,
                    'name': p.name,
                    'slug': p.slug,
                    'cas': p.cas,
                    'status': p.status,
                    'inventory_status': p.inventory_status,
                    'purity': p.purity,
                    'storage': p.storage,
                }
                for p in featured_products
            ],
        },
        'meta': {},
    })


@api_view(['GET'])
def site_navigation(request):
    """Navigation tree for frontend."""
    apps = Application.objects.filter(status='active').order_by('sort_order')
    return Response({
        'success': True,
        'data': {
            'primary': [
                {'label': 'Home', 'path': '/'},
                {'label': 'Applications', 'path': '/applications'},
                {'label': 'Methods', 'path': '/methods'},
                {'label': 'Protocols', 'path': '/protocols'},
                {'label': 'Research Goals', 'path': '/research-goals'},
            ],
            'applications': [
                {'id': a.id, 'name': a.name, 'slug': a.slug}
                for a in apps
            ],
        },
        'meta': {},
    })


@api_view(['GET'])
def sitemap_xml(request):
    """Generate basic sitemap XML."""
    base_url = f'{request.scheme}://{request.get_host()}'
    urls = [f'{base_url}/']

    # Applications
    for app in Application.objects.filter(status='active'):
        urls.append(f'{base_url}/applications/{app.id}')

    # Methods
    for method in Method.objects.filter(status='active'):
        urls.append(f'{base_url}/methods/{method.id}')

    # Protocols
    for protocol in Protocol.objects.filter(status='active'):
        urls.append(f'{base_url}/protocols/{protocol.id}')

    # Products
    for product in Product.objects.filter(status='active'):
        urls.append(f'{base_url}/products/{product.id}')

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for url in urls:
        xml += f'  <url><loc>{url}</loc></url>\n'
    xml += '</urlset>'

    return HttpResponse(xml, content_type='application/xml')
