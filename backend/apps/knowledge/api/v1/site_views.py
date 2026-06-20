from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import HttpResponse
from django.db.models import Count, Q
from core.svg_sanitizer import sanitize_svg
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

    # Featured products (by display_priority) — prefetch SKUs to avoid N+1
    featured_products = list(
        Product.objects
        .filter(status='active')
        .prefetch_related('skus')
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

    # Stats — aggregate counts from all relevant models
    sku_count = Product.objects.filter(status__in=['active', 'published']).aggregate(
        total=Count('skus__id', distinct=True)
    )['total'] or 0
    area_count = ResearchGoal.objects.count()
    method_count = Method.objects.filter(status='active').count()
    protocol_count = Protocol.objects.filter(status='published').count()
    product_count = Product.objects.filter(status__in=['active', 'published']).count()

    # Stats payload — aligned with frontend StatsBar
    stats_payload = {
        'products': product_count,
        'skus': sku_count,
        'methods': method_count,
        'protocols': protocol_count,
        'areas': area_count,
    }

    # Categories — L1 breakdown with product counts
    category_data = (
        Product.objects
        .filter(status__in=['active', 'published'], category_l1__isnull=False)
        .exclude(category_l1='')
        .values('category_l1')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    categories_payload = []
    CATEGORY_META = {
        'nucleotides_nucleosides': {'name': 'Nucleotides', 'slug': 'nucleotides', 'color': '#7C3AED', 'bg': '#EDE9FE'},
        'click_chemistry': {'name': 'Click Chemistry', 'slug': 'click-chemistry', 'color': '#0F766E', 'bg': '#F0FDFA'},
        'fluorescent_probes': {'name': 'Fluorescent Probes', 'slug': 'fluorescent-probes', 'color': '#0EA5E9', 'bg': '#E0F2FE'},
        'bioconjugation': {'name': 'Bioconjugation', 'slug': 'bioconjugation', 'color': '#CA8A04', 'bg': '#FEF3C7'},
        'modifiers': {'name': 'Modifiers', 'slug': 'modifiers', 'color': '#E11D48', 'bg': '#FCE7F3'},
        'molecular_biology': {'name': 'Molecular Biology', 'slug': 'molecular-biology', 'color': '#64748B', 'bg': '#F1F5F9'},
    }
    for c in category_data:
        key = c['category_l1']
        meta = CATEGORY_META.get(key, {'name': key.replace('_', ' ').title(), 'slug': key, 'color': '#64748B', 'bg': '#F1F5F9'})
        categories_payload.append({**meta, 'count': c['count']})

    # Knowledge section data — aligned with frontend KnowledgeSection
    knowledge_payload = {
        'goals': ResearchGoal.objects.count(),
        'applications': Application.objects.filter(status='active').count(),
        'methods': method_count,
        'protocols': protocol_count,
    }

    # Build featured_products data using prefetched SKUs (no N+1)
    products_data = []
    for p in featured_products:
        skus = list(p.skus.all())
        first_sku = skus[0] if skus else None
        products_data.append({
            'id': p.id,
            'name': p.name,
            'slug': p.slug,
            'catalog_no': p.catalog_no,
            'cas': p.cas,
            'formula': p.formula,
            'category_l1': p.category_l1,
            'purity': p.purity,
            'price': str(first_sku.price) if first_sku else None,
            'currency': first_sku.currency if first_sku else 'USD',
            'structure_svg': sanitize_svg(p.structure_svg) if p.structure_svg else None,
            'display_priority': p.display_priority,
            'status': p.status,
        })

    return Response({
        'success': True,
        'data': {
            'hero': {
                'title': 'SciReagent',
                'subtitle': 'AI-Native Scientific Reagent Platform for Nucleotides & Click Chemistry',
                'suggested_searches': SUGGESTED_SEARCHES,
            },
            'stats': stats_payload,
            'categories': categories_payload,
            'knowledge': knowledge_payload,
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
            'featured_products': products_data,
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
