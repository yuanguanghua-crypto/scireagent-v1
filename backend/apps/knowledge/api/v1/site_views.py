from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import HttpResponse
from django.db.models import Count, Q
from apps.knowledge.models import Application, Method, Protocol, ResearchGoal, Reference
from apps.commerce.models import Product
from apps.bridges.models import ProductMethod
from apps.knowledge.services.graph_service import build_graph


def _build_homepage_graph():
    """Build a graph preview from the top-priority application."""
    top_app = Application.objects.filter(status='active', display_priority__gt=0).order_by('-display_priority').first()
    if not top_app:
        # Fallback: pick any active application
        top_app = Application.objects.filter(status='active').first()
    if not top_app:
        return None
    graph = build_graph('application', top_app.id, depth=2, max_nodes=20, max_edges=30)
    return graph if graph and graph['nodes'] else None


SUGGESTED_SEARCHES = [
    'RNA labeling',
    'Click chemistry',
    'NGS library prep',
    'DNA sequencing',
    'FISH',
    'Modified nucleotides',
    'Fluorescent dyes',
    'Bioconjugation',
]


@api_view(['GET'])
def site_home(request):
    """Home page composite data."""
    # Featured applications (by display_priority)
    featured_apps = (
        Application.objects
        .filter(status='active')
        .select_related('research_goal')
        .annotate(
            products_count=Count(
                'methods__product_methods__product',
                filter=Q(methods__product_methods__product__status__in=['active', 'published']),
                distinct=True
            ),
            methods_count=Count(
                'methods',
                filter=Q(methods__status='active'),
                distinct=True
            ),
        )
        .order_by('-display_priority', 'sort_order')[:6]
    )

    # Featured methods (by display_priority if available, else default)
    featured_methods = (
        Method.objects
        .filter(status='active')
        .annotate(
            products_count=Count(
                'product_methods__product',
                filter=Q(product_methods__product__status__in=['active', 'published']),
                distinct=True
            ),
        )
        .order_by('-display_priority', 'id')[:6]
    )

    # Featured products (by display_priority)
    featured_products = (
        Product.objects
        .filter(status='active')
        .order_by('-display_priority', 'name')[:8]
    )

    # Featured solutions (Application-level aggregation)
    featured_solutions = (
        Application.objects
        .filter(status='active', display_priority__gt=0)
        .annotate(
            methods_count=Count(
                'methods',
                filter=Q(methods__status='active'),
                distinct=True
            ),
            protocols_count=Count(
                'methods__protocols',
                filter=Q(methods__protocols__status='published'),
                distinct=True
            ),
            products_count=Count(
                'methods__product_methods__product',
                filter=Q(methods__product_methods__product__status__in=['active', 'published']),
                distinct=True
            ),
        )
        .order_by('-display_priority')[:6]
    )

    # Research goals
    research_goals = (
        ResearchGoal.objects
        .annotate(
            applications_count=Count(
                'applications',
                filter=Q(applications__status='active'),
                distinct=True
            ),
            products_count=Count(
                'applications__methods__product_methods__product',
                filter=Q(applications__methods__product_methods__product__status__in=['active', 'published']),
                distinct=True
            ),
        )
        .order_by('priority', 'id')[:6]
    )

    # References (recent)
    references = Reference.objects.order_by('-year', '-id')[:5]

    return Response({
        'success': True,
        'data': {
            'hero': {
                'title': 'SciReagent',
                'subtitle': 'AI-Native Scientific Reagent Platform for Nucleotides & Click Chemistry',
                'suggested_searches': SUGGESTED_SEARCHES,
            },
            'stats': {
                'applications': Application.objects.filter(status='active').count(),
                'methods': Method.objects.filter(status='active').count(),
                'protocols': Protocol.objects.filter(status='published').count(),
                'products': Product.objects.filter(status__in=['active', 'published']).count(),
            },
            'featured_applications': [
                {
                    'id': a.id,
                    'name': a.name,
                    'slug': a.slug,
                    'summary': a.summary,
                    'display_priority': a.display_priority,
                    'methods_count': a.methods_count,
                    'products_count': a.products_count,
                }
                for a in featured_apps
            ],
            'featured_methods': [
                {
                    'id': m.id,
                    'name': m.name,
                    'slug': m.slug,
                    'purpose': m.purpose,
                    'products_count': m.products_count,
                }
                for m in featured_methods
            ],
            'featured_products': [
                {
                    'id': p.id,
                    'name': p.name,
                    'slug': p.slug,
                    'catalog_no': p.catalog_no,
                    'cas': p.cas,
                    'formula': p.formula,
                    'purity': p.purity,
                    'price': str(p.skus.first().price) if p.skus.exists() else None,
                    'currency': p.skus.first().currency if p.skus.exists() else 'USD',
                    'structure_svg': p.structure_svg or None,
                    'display_priority': p.display_priority,
                    'status': p.status,
                }
                for p in featured_products
            ],
            'featured_solutions': [
                {
                    'application_id': a.id,
                    'name': a.name,
                    'methods_count': a.methods_count,
                    'protocols_count': a.protocols_count,
                    'products_count': a.products_count,
                }
                for a in featured_solutions
            ],
            'research_goals': [
                {
                    'id': g.id,
                    'name': g.name,
                    'slug': g.slug,
                    'applications_count': g.applications_count,
                    'products_count': g.products_count,
                }
                for g in research_goals
            ],
            'references': [
                {
                    'id': r.id,
                    'title': r.title,
                    'journal': r.journal,
                    'year': r.year,
                    'doi': r.doi,
                }
                for r in references
            ],
            'graph_preview': _build_homepage_graph(),
            'seo': {
                'title': 'SciReagent — AI-Native Scientific Reagent Platform',
                'description': 'Discover nucleotides, click chemistry reagents, and related products with AI-powered knowledge graph. Research-driven reagent selection for life science.',
                'og_image': None,
            },
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
def robots_txt(request):
    """robots.txt for SEO."""
    base_url = f'{request.scheme}://{request.get_host()}'
    content = f"""User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/

Sitemap: {base_url}/sitemap.xml
"""
    return HttpResponse(content.strip(), content_type='text/plain')


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
    for protocol in Protocol.objects.filter(status='published'):
        urls.append(f'{base_url}/protocols/{protocol.id}')

    # Products
    for product in Product.objects.filter(status__in=['active', 'published']):
        urls.append(f'{base_url}/products/{product.id}')

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for url in urls:
        xml += f'  <url><loc>{url}</loc></url>\n'
    xml += '</urlset>'

    return HttpResponse(xml, content_type='application/xml')
