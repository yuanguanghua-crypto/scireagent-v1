from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import HttpResponse
from django.db.models import Count, Q
from core.svg_sanitizer import sanitize_svg
from apps.knowledge.models import Application, Method, Protocol, ResearchGoal, Reference
from apps.commerce.models import Product
from apps.bridges.models import ProductMethod
from apps.knowledge.services.graph_service import build_graph

#: 导航里最多返回多少个 application（见 site_navigation 的 docstring）。
#: 默认 200 足够覆盖"常用应用"；上限 2000 是防有人用 `?limit=999999` 把放大点重新打开。
NAV_APPLICATION_LIMIT = 200
NAV_APPLICATION_LIMIT_MAX = 2000


def _build_homepage_graph():
    """Build a graph preview from the top-priority application."""
    top_app = Application.objects.public().filter(
        status='active', display_priority__gt=0
    ).order_by('-display_priority').first()
    if not top_app:
        # Fallback: pick any active application
        top_app = Application.objects.public().filter(status='active').first()
    if not top_app:
        return None
    graph = build_graph('application', top_app.id, depth=2, max_nodes=20, max_edges=30)
    return graph if graph and graph['nodes'] else None


def get_suggested_searches():
    """Popular search tags derived from real, searchable application names.

    After the content translation (knowledge 0010) application names are
    English, so these tags always resolve to at least one grouped result.
    Falls back to a curated English list when no applications exist.
    """
    names = list(
        Application.objects.public().filter(status='active')
        .order_by('-display_priority', 'id')
        .values_list('name', flat=True)[:8]
    )
    if names:
        return names
    return [
        'Fluorescent Labeling', 'Biotin Labeling', 'Click Chemistry Labeling',
        'PCR/qPCR', 'Sequencing', 'FISH', 'In Vitro Transcription',
        'RNA/Protein Purification',
    ]


@api_view(['GET'])
def site_home(request):
    """Home page composite data."""
    # Featured applications (by display_priority)
    #
    # ★ 2026-10-21 性能（L7）：`annotate(...)` + `order_by + [:6]` 生成的是
    #   `GROUP BY application.*, research_goal.*  ORDER BY display_priority DESC, sort_order LIMIT 6`。
    #   **`GROUP BY` 让 `LIMIT` 无法下推** ⇒ PG 必须先对**全部** active application
    #   （该库 28566 行）做完 `LEFT JOIN method → product_method → product` 的聚合，
    #   再排序取 6 行。实测这条 SQL **195ms**，是 `/api/v1/site/home` 剩下的唯一瓶颈
    #   （查询数已从 51 降到 23，但耗时没降 —— 因为瓶颈在这条的单次开销，不在次数）。
    #
    #   排序键 `display_priority` / `sort_order` 都是 Application **自身字段**、
    #   与两个聚合值无关 ⇒ 先按它们取前 6 个 id，再只对这 6 个聚合，**结果等价**。
    #   已用「优化前后响应逐字节比对」验证。
    _top_app_ids = list(
        Application.objects
        .filter(status='active')
        .order_by('-display_priority', 'sort_order')
        .values_list('id', flat=True)[:6]
    )
    featured_apps = (
        Application.objects
        .filter(id__in=_top_app_ids)
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
        .order_by('-display_priority', 'sort_order')
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
        .filter(status='active', archived=False)
        .select_related('product_class__parent__parent')
        .prefetch_related('skus')
        .order_by('-display_priority', 'name')[:20]
    )

    # Featured solutions (Application-level aggregation)
    #
    # ★ 2026-10-21 性能（L7）：原写法是「对**全部** `status=active AND display_priority>0`
    #   的 Application 做 3 组 `COUNT(DISTINCT)`（其中两次跨到
    #   `methods__method_protocols__protocol` / `methods__product_methods__product`
    #   三层），再 `ORDER BY display_priority DESC LIMIT 6`。
    #   **`GROUP BY` 会让 `LIMIT` 无法下推** ⇒ PG 必须先把几千行（实测该库 28566 个
    #   active application）全部聚合出来再排序，实测这条 SQL **192ms**，
    #   占了 `/api/v1/site/home` 的一半以上耗时。
    #
    #   排序键 `display_priority` 是 Application **自身字段**、与三个聚合值无关
    #   ⇒ 可以先按它取前 6 个 id，再只对这 6 个聚合。**结果完全等价**
    #   （已用「优化前后响应逐字节比对」验证，见 COVERAGE_STATUS §3.17）。
    _top_solution_ids = list(
        Application.objects
        .filter(status='active', display_priority__gt=0)
        .order_by('-display_priority', 'id')      # 加 id 作次序键：原写法次序未定义，这里更确定
        .values_list('id', flat=True)[:6]
    )
    featured_solutions = (
        Application.objects
        .filter(id__in=_top_solution_ids)
        .annotate(
            methods_count=Count(
                'methods',
                filter=Q(methods__status='active'),
                distinct=True
            ),
            protocols_count=Count(
                'methods__method_protocols__protocol',
                filter=Q(methods__method_protocols__protocol__status='published'),
                distinct=True
            ),
            products_count=Count(
                'methods__product_methods__product',
                filter=Q(methods__product_methods__product__status__in=['active', 'published']),
                distinct=True
            ),
        )
        .order_by('-display_priority', 'id')
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
    sku_count = Product.objects.filter(
        status__in=['active', 'published'], archived=False
    ).aggregate(
        total=Count('skus__id', distinct=True)
    )['total'] or 0
    # S1：统计口径必须排除测试夹具残骸，否则首页 areas/goals 会把 e2e 残留计入
    area_count = ResearchGoal.objects.public().count()
    method_count = Method.objects.public().filter(status='active').count()
    protocol_count = Protocol.objects.filter(status='published').count()
    product_count = Product.objects.filter(status__in=['active', 'published'], archived=False).count()

    # Stats payload — aligned with frontend StatsBar
    stats_payload = {
        'products': product_count,
        'skus': sku_count,
        'methods': method_count,
        'protocols': protocol_count,
        'areas': area_count,
    }

    # Categories — L1 breakdown with product counts (DB-driven via ProductClass)
    #
    # ★ 2026-10-21 性能（L7）：这里原本是 **N+1**。每个 L1 分类调一次
    #   `get_descendant_product_class_ids`（内部 1 次查 l1 + 1 次查 children +
    #   每个 child 再 1 次查 grandchildren），再各自 `COUNT` 一次产品
    #   ⇒ 实测 `/api/v1/site/home` 共 **51 次查询 / p95 322ms**，其中
    #   **21 次**是 `SELECT id FROM product_class WHERE parent_id = N`。
    #   改为「一次读全树（内存建索引）+ 一次 group by 聚合产品数」⇒ 2 次查询。
    #
    #   语义严格对齐原来的 `get_descendant_product_class_ids(slug)`：
    #   只认 `parent_id IS NULL` 的 slug（见 selector 的 docstring）。
    from apps.commerce.selectors import build_product_class_tree
    CATEGORY_META = {
        'nucleotides_nucleosides': {'name': 'Nucleotides', 'slug': 'nucleotides', 'color': '#7C3AED', 'bg': '#EDE9FE'},
        'click_chemistry': {'name': 'Click Chemistry', 'slug': 'click-chemistry', 'color': '#0F766E', 'bg': '#F0FDFA'},
        'molecular_biology': {'name': 'Molecular Biology', 'slug': 'molecular-biology', 'color': '#64748B', 'bg': '#F1F5F9'},
    }
    desc_map, l1_slug_to_id = build_product_class_tree()
    # 一次聚合：每个 product_class 的产品数（同一次查询覆盖全部分类）
    per_class_counts = {
        cid: n for cid, n in (
            Product.objects
            .filter(status__in=['active', 'published'], archived=False)
            .values('product_class_id')
            .annotate(n=Count('id'))
            .values_list('product_class_id', 'n')
        )
    }
    categories_payload = []
    for l1_slug, meta in CATEGORY_META.items():
        root_id = l1_slug_to_id.get(l1_slug)
        descendant_ids = desc_map.get(root_id, []) if root_id else []
        count = sum(per_class_counts.get(i, 0) for i in descendant_ids)
        categories_payload.append({**meta, 'count': count})

    # Knowledge section data — aligned with frontend KnowledgeSection
    knowledge_payload = {
        'goals': ResearchGoal.objects.public().count(),
        'applications': Application.objects.public().filter(status='active').count(),
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
                'suggested_searches': get_suggested_searches(),
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
    """Navigation tree for frontend.

    ★ 2026-10-21 性能（L7，实测 p95 267ms / 响应 **2.78MB**）：
      此前把**全部** active application 塞进一次响应（实测 28,566 条
      `{id, name, slug}`）。而这份数据**没有任何消费者**：
      `frontend/src/stores/app.js` 的 `fetchNavigation()` 全仓**零调用**，
      也没有任何组件读 `appStore.navigation`。
      ⇒ 2.78MB 白花，而且是**匿名可触发**的带宽/内存放大点
        （配 `AnonRateThrottle` 即可持续打）。

    ⇒ `applications` 改为只取前 `NAV_APPLICATION_LIMIT` 条；
      `meta` 里给出 `application_total`（被截断时调用方能知道还有多少）。
      需要完整列表请用 `/api/v1/applications/`（有分页）。

    ⚠️ 这是**契约变更**（原来返回全量）。已核实前端零消费方；
      若外部有客户端依赖全量，用 `?limit=`（上限 2000）或改用分页端点。
    """
    try:
        limit = int(request.query_params.get('limit') or NAV_APPLICATION_LIMIT)
    except (TypeError, ValueError):
        limit = NAV_APPLICATION_LIMIT
    limit = max(1, min(limit, NAV_APPLICATION_LIMIT_MAX))

    qs = Application.objects.public().filter(status='active').order_by('sort_order')
    total = qs.count()
    apps = qs[:limit]
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
        'meta': {
            'application_total': total,
            'application_limit': limit,
            'applications_truncated': total > limit,
        },
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
    for app in Application.objects.public().filter(status='active'):
        urls.append(f'{base_url}/applications/{app.id}')

    # Methods
    for method in Method.objects.public().filter(status='active'):
        urls.append(f'{base_url}/methods/{method.id}')

    # Protocols
    for protocol in Protocol.objects.filter(status='published'):
        urls.append(f'{base_url}/protocols/{protocol.id}')

    # Products
    for product in Product.objects.filter(status__in=['active', 'published'], archived=False):
        urls.append(f'{base_url}/products/{product.id}')

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for url in urls:
        xml += f'  <url><loc>{url}</loc></url>\n'
    xml += '</urlset>'

    return HttpResponse(xml, content_type='application/xml')
