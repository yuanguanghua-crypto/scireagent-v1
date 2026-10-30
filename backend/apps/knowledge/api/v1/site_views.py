from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import Http404, HttpResponse
from django.db.models import Count, Q
from core.svg_sanitizer import sanitize_svg
from apps.knowledge.models import Application, Method, Protocol, ResearchGoal, Reference
from apps.commerce.models import Product
from apps.commerce.services.pricing import start_price
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
            # ★ 2026-10-30（B 方案阶段 2）：改走 ApplicationMethod 桥。
            #   桥里全是 canonical（active 且无 application），所以不再需要
            #   `methods__status='active'` 过滤。
            products_count=Count(
                'application_methods__method__product_methods__product',
                filter=Q(application_methods__method__product_methods__product__status__in=['active', 'published']),
                distinct=True
            ),
            methods_count=Count('application_methods', distinct=True),
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
    # ★ 2026-10-29 修：下面用 `start_price(first_sku)` 取「起价」，它会读 `sku.price_tiers.all()`。
    #   只 prefetch `skus` 没 prefetch `skus__price_tiers` ⇒ 每个 SKU 一次查询，
    #   20 个产品就是 20 次额外往返。这是加阶梯价时引入的退化，不是原有代码的问题。
    featured_products = list(
        Product.objects
        .filter(status='active', archived=False)
        .select_related('product_class__parent__parent')
        .prefetch_related('skus', 'skus__price_tiers')
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
    #
    # ★ 2026-10-26 修两处缺陷（用户报「首页分类/产品不一致」，实为测试数据上首屏）：
    #   1. 此前是 `ResearchGoal.objects` —— **漏了 .public()**，而本文件其它所有对外
    #      查询（Application/Method/Product）都走 .public()。库里 9 条 E2E 残留
    #      （__e2e_goals_* / __curl_test_goal__，id 34-42）is_test_fixture 已正确标记，
    #      只是这里没调用过滤 ⇒ 直接占了首页 6 个位置中的 5 个。
    #   2. 此前 `order_by('priority', 'id')` 是**升序**，而 priority 字段自己写着
    #      help_text='数字越大越靠前' ⇒ 语义反了。全站 11,045 个 goal 里 11,037 个是
    #      默认值 0，精心设过优先级的 8 个（id 23-30，priority 5/10）全被挤到最后。
    #   修后应取到 id 23-28 那 6 个业务目标。
    research_goals = (
        ResearchGoal.objects.public()
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
        .order_by('-priority', 'id')[:6]
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
            'price': str(start_price(first_sku)) if first_sku else None,
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


#: sitemap 单文件 URL 上限。协议硬上限 50,000，留 10% 余量防边界。
SITEMAP_PAGE_SIZE = 45000

#: 静态页（不来自数据库）
SITEMAP_STATIC_PATHS = ['/', '/products', '/applications', '/methods',
                        '/protocols', '/research-goals']


def _site_base(request) -> str:
    """站点根 URL。

    ⚠️ 依赖 `request.scheme`，反代场景下它来自 `X-Forwarded-Proto`
    （`production.py` 已设 `SECURE_PROXY_SSL_HEADER`，nginx 也设了
    `proxy_set_header X-Forwarded-Proto https`）。
    若哪天漏设该头，sitemap 里的 URL 会退化成 http —— 搜索引擎会去爬 http
    再被重定向，白耗抓取配额。这是一处**脆弱依赖**，改动反代配置时要想到它。
    """
    return f'{request.scheme}://{request.get_host()}'


def _sitemap_sources() -> dict:
    """分片类型 → **只取 id** 的 QuerySet。

    ★ 只 `values_list('id', flat=True)` 而不遍历对象：原实现逐个实例化模型，
    10 倍数据下光 ORM 实例化就占了大半耗时（实测 16.6MB / 7.6s）。
    """
    return {
        'applications': (Application.objects.public().filter(status='active')
                         .values_list('id', flat=True)),
        'methods': (Method.objects.public().filter(status='active')
                    .values_list('id', flat=True)),
        'protocols': (Protocol.objects.filter(status='published')
                      .values_list('id', flat=True)),
        'products': (Product.objects.filter(status__in=['active', 'published'], archived=False)
                     .values_list('id', flat=True)),
    }


def _urlset(urls) -> HttpResponse:
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        xml.append(f'  <url><loc>{u}</loc></url>')
    xml.append('</urlset>')
    return HttpResponse('\n'.join(xml), content_type='application/xml')


@api_view(['GET'])
def sitemap_index(request):
    """`/sitemap.xml` → `<sitemapindex>`，指向各分片。

    ★ 2026-10-22 改（FAILURE_MODES 10.2 的实测结论）：
      原实现把全站 URL 塞进**一个** `urlset`。实测生产 **42,779 个 URL / 2.72MB**，
      而协议上限是**单文件 ≤ 50,000 URL / ≤ 50MB** —— **只剩 17% 余量**，
      数据再涨 17% 搜索引擎就会拒收整个 sitemap。
      10 倍压测时响应到 **16.6MB / 7.6s**（超线性 25.5 倍）。
      ⇒ 改为 sitemap index + 按类型分片（每片 ≤45,000 URL）。
      这是 sitemap 协议的**标准做法**，搜索引擎完全支持。
    """
    base = _site_base(request)
    parts = [f'{base}/sitemap-static.xml']
    for kind, qs in _sitemap_sources().items():
        total = qs.count()
        pages = max(1, -(-total // SITEMAP_PAGE_SIZE))     # 向上取整
        for page in range(1, pages + 1):
            parts.append(f'{base}/sitemap-{kind}-{page}.xml')

    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for part in parts:
        xml.append(f'  <sitemap><loc>{part}</loc></sitemap>')
    xml.append('</sitemapindex>')
    return HttpResponse('\n'.join(xml), content_type='application/xml')


@api_view(['GET'])
def sitemap_static(request):
    """`/sitemap-static.xml` —— 静态页分片（不随数据量增长）。"""
    base = _site_base(request)
    return _urlset(f'{base}{path}' for path in SITEMAP_STATIC_PATHS)


@api_view(['GET'])
def sitemap_part(request, kind: str, page: int):
    """`/sitemap-<kind>-<page>.xml` —— 某一类实体的某一页（每页 ≤45,000 条）。"""
    sources = _sitemap_sources()
    qs = sources.get(kind)
    if qs is None or page < 1:
        raise Http404

    start = (page - 1) * SITEMAP_PAGE_SIZE
    ids = list(qs[start:start + SITEMAP_PAGE_SIZE])
    if not ids and page > 1:
        # 越界页码：404 比"空 urlset"更明确（空 urlset 会被搜索引擎当成"该片没内容"）
        raise Http404

    base = _site_base(request)
    return _urlset(f'{base}/{kind}/{pk}' for pk in ids)


def sitemap_xml(request):
    """兼容别名 —— 旧路由仍指向 `/sitemap.xml`（现为 index）。"""
    return sitemap_index(request)
