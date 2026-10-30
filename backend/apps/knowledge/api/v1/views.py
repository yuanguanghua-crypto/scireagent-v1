from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Prefetch, Q
from core.mixins import EnvelopeMixin
from core.permissions import IsAdminOrReadOnly
from core.jsonld import build_method_jsonld, build_protocol_jsonld
from apps.knowledge.models import (
    ResearchGoal, Application, Method, Protocol, Reference, Compatibility,
    ProtocolFacet, FacetValue,
)
from apps.knowledge.api.v1.serializers import (
    ResearchGoalListSerializer, ResearchGoalDetailSerializer, ApplicationListSerializer, ApplicationDetailSerializer,
    MethodListSerializer, MethodDetailSerializer, ProtocolListSerializer, ProtocolDetailSerializer,
    ReferenceSerializer, CompatibilitySerializer,
)
from apps.knowledge import selectors
from apps.knowledge.api.v1.fixture_visibility import (
    apply_public_visibility, include_unpublished, public_statuses,
)
from apps.knowledge.api.v1.filters import ApplicationFilter


# 测试夹具命名前缀 —— 与 `manage.py mark_test_fixtures` 的 DEFAULT_PREFIX 保持同一份约定。
# 任何以 `__` 开头的名称都是测试用的临时实体（`__e2e_goals_<ts>__`、`__curl_test_goal__`）。
TEST_FIXTURE_NAME_PREFIX = '__'


class AutoTagTestFixtureMixin:
    """API 创建/更新时，按名称前缀自动把 `is_test_fixture` 置 True。

    ## 为什么需要它

    2026-10-26 线上事故的根因链：E2E 通过**生产 API** 建了 9 条 `__e2e_goals_*`，
    而当时唯一的标记手段是**事后**跑 `mark_test_fixtures` 命令。一旦忘了跑，
    脏数据就以 `is_test_fixture=False` 的身份混进正常数据，只能靠每个查询自己
    记得调 `.public()` 过滤 —— 首页就漏了一处，结果测试垃圾占了首屏。

    改为**写入时就标记**：脏数据从诞生那一刻起就是脏的，不再依赖谁记得跑命令，
    也不再依赖每个查询都写对过滤条件。

    ## 为什么放在 ViewSet 而不是 model.save()

    1. 只覆盖 API 写入路径，不污染导入命令 / 数据修复脚本 / factory。
    2. `apps/knowledge/tests/test_test_fixture_isolation.py` 明确依赖
       「factory 创建时 `is_test_fixture` 仍为 False，须跑 mark 命令才变 True」
       这一前提 —— 改 model 层会让那个契约失效。

    ## 只判 `name`，不看 status

    因为 status 靠不住：现网曾有一批脏实体恰好是 `draft`，靠 status 侥幸挡住了
    列表端点，但 search 系列端点根本没有 status 过滤。名称前缀是唯一稳定信号。
    """

    def perform_create(self, serializer):
        serializer.save(**self._fixture_kwargs(serializer))

    def perform_update(self, serializer):
        serializer.save(**self._fixture_kwargs(serializer))

    @staticmethod
    def _fixture_kwargs(serializer):
        name = serializer.validated_data.get('name')
        if isinstance(name, str) and name.startswith(TEST_FIXTURE_NAME_PREFIX):
            # 只往"真"的方向标：真实实体改名为 `__` 开头也算测试数据；
            # 但把测试实体改名成正常名字时，**不自动取消标记** ——
            # 取消标记是人工判断（可能还有关联数据挂在上面），不该由一次改名决定。
            if not serializer.instance or not serializer.instance.is_test_fixture:
                return {'is_test_fixture': True}
        return {}



class ResearchGoalViewSet(AutoTagTestFixtureMixin, EnvelopeMixin, viewsets.ModelViewSet):
    queryset = selectors.get_research_goals_with_applications()
    serializer_class = ResearchGoalListSerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ['name', 'summary']
    ordering_fields = ['priority', 'name']

    def get_serializer_class(self):
        # #495 轻量版：详情/写入走 Detail（暴露并可写策展 protocols）；
        # 列表/删除走 List（轻量、无 N+1）。写权限沿用 IsAdminOrReadOnly（写=is_staff）。
        if self.action in ('retrieve', 'create', 'update', 'partial_update'):
            return ResearchGoalDetailSerializer
        return ResearchGoalListSerializer

    def get_queryset(self):
        """公开端点（匿名/普通用户）仅返回已发布(ACTIVE)记录，规避草稿/测试数据外泄；
        staff 可访问全量（含草稿/归档），便于后台管理。

        S1：测试夹具行（is_test_fixture=True）对所有身份默认不可见——不依赖
        status 侥幸；staff 可用 ?include_test_fixtures=1 显式查看以便清理。
        P0：统一走 apply_public_visibility。"""
        return apply_public_visibility(
            selectors.get_research_goals_with_applications(),
            ResearchGoal, self.request,
        )


class ApplicationViewSet(AutoTagTestFixtureMixin, EnvelopeMixin, viewsets.ModelViewSet):
    # #P0-1：prefetch M2M 反向（research_goal_collections，按 id 升序）替代 FK
    # select_related，与 API 读取路径（M2M）一致，避免 N+1 且保证读序稳定。
    _rg_prefetch = Prefetch(
        'research_goal_collections',
        queryset=ResearchGoal.objects.order_by('id'),
    )
    queryset = Application.objects.prefetch_related(_rg_prefetch).all()
    serializer_class = ApplicationListSerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ['name', 'summary']
    ordering_fields = ['sort_order', 'name']
    filterset_class = ApplicationFilter

    def get_queryset(self):
        """公开端点仅返回已发布(ACTIVE)记录；staff 可访问全量。
        S1：测试夹具行默认对所有身份不可见。P0：统一走 apply_public_visibility。"""
        return apply_public_visibility(
            Application.objects.prefetch_related(self._rg_prefetch).all(),
            Application, self.request,
        )

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ApplicationDetailSerializer
        return ApplicationListSerializer


class MethodViewSet(AutoTagTestFixtureMixin, EnvelopeMixin, viewsets.ModelViewSet):
    queryset = Method.objects.select_related('application').all()
    serializer_class = MethodListSerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ['name', 'purpose', 'advantages', 'limitations']
    ordering_fields = ['name', 'cost_band']
    # ★ 2026-10-30（B 方案阶段 2）：`application_id` 从自动筛选移除 ——
    #   django-filter 会去查 `Method.application` FK，而该 FK 语义已废弃。
    #   改为在 get_queryset 里手工按 `application_id` 查桥（参数名不变，前端无感）。
    filterset_fields = ['status', 'origin']

    def get_queryset(self):
        """公开端点仅返回已发布(ACTIVE)记录。
        S1：测试夹具行默认对所有身份不可见。P0：统一走 apply_public_visibility。

        ★ 2026-10-26（方案 B）：**仅列表端点**让 staff 也默认只看公开态。
          此前 staff 在 list 上拿到 47,927（含 47,834 个 draft），而首页统计写死
          active 只显示 93 ⇒ 同一个用户点 "Browse 93 →" 进去看到 "Total 47927"。
          详情/写操作**不过滤**：后台要能打开草稿详情，否则管理功能断裂
          （实测在共用函数里统一改会挂掉 40+ 用例）。显式 ?include_unpublished=1 看全量。
        """
        qs = apply_public_visibility(
            Method.objects.select_related('application').all(),
            Method, self.request,
        )
        if self.action == 'list' and not include_unpublished(self.request):
            statuses = public_statuses(Method)
            if statuses:
                qs = qs.filter(status__in=statuses)

        # ★ 2026-10-30：application_id 走桥（见 filterset_fields 说明）
        _app_id = (self.request.query_params.get('application_id') or '').strip()
        if _app_id:
            qs = qs.filter(application_methods__application_id=_app_id)
        return qs

    def get_serializer_class(self):
        # ★ 2026-09-24：**写路径也走 Detail**，对齐 `ResearchGoalViewSet`（`views.py:28-33`）的既有正确模式。
        #   此前只在 `retrieve` 走 Detail、`create/update` 走 List，而 List **未声明 `purpose`**
        #   ⇒ MethodsPage 的 Purpose 输入框「读恒空、写被静默忽略」。列表仍走 List（轻量、公开载荷不变）。
        if self.action in ('retrieve', 'create', 'update', 'partial_update'):
            return MethodDetailSerializer
        return MethodListSerializer

    @action(detail=True, methods=['get'], url_path='json-ld')
    def json_ld(self, request, pk=None):
        """Return JSON-LD structured data for a single method."""
        method = self.get_object()
        data = build_method_jsonld(method, request)
        return Response(data)


class ProtocolViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    queryset = Protocol.objects.prefetch_related('steps').all()
    serializer_class = ProtocolListSerializer
    permission_classes = [IsAdminOrReadOnly]
    # ★ 2026-10-30：`search` 参数改由 get_queryset 自己处理（见下方），
    #   因为要把 facet 标签并进 OR 命中。若同时留 search_fields，
    #   DRF SearchFilter 会与本逻辑 AND 叠加 ⇒ 只剩「既命中字段又命中 facet」
    #   的极少数结果，看起来像搜索坏了。
    search_fields = []
    ordering_fields = ['name', 'version']
    filterset_fields = ['status']

    def _base_queryset(self):
        """基础 queryset + 按 action 决定要不要预取材料清单。

        材料清单在 Bio-protocol 一份协议能有 268 条，全库 16.9 万条 ——
        **只在 retrieve 预取**，列表页绝不带（否则列表接口体积和查询数都会爆）。
        """
        qs = Protocol.objects.prefetch_related('steps')
        if self.action == 'retrieve':
            qs = qs.prefetch_related('materials_items')
        return qs.all()

    def get_queryset(self):
        """P0：公开端点仅返回已发布(PUBLISHED)记录。
        （原实现无任何 get_queryset 过滤，属结构性泄漏点。）

        ★ 2026-10-26（方案 B）：**仅列表端点**让 staff 也默认只看公开态，
          与首页 "Browse 14121" 对齐（此前 staff 看到 14,128，多出 7 条 draft）。
          详情/写操作不过滤，?include_unpublished=1 看全量。
        """
        qs = apply_public_visibility(
            self._base_queryset(),
            Protocol, self.request,
        )
        if self.action == 'list' and not include_unpublished(self.request):
            statuses = public_statuses(Protocol)
            if statuses:
                qs = qs.filter(status__in=statuses)

        # ★ 2026-10-26：facet 筛选。参数不限维度（用 slug 而非 value —— value 是
        #   带空格的英文短语，URL 要编码；slug 干净）。
        #   `facet`        —— 一级（前端用 application）
        #   `facet_method` —— 二级（在选定领域内按方法再筛）
        #   两者链式 filter 会生成两个独立 JOIN ⇒ 要求同一 protocol 同时满足，
        #   这正是"该领域下的该方法"的语义。
        params = self.request.query_params
        facet_slug = (params.get('facet') or '').strip()
        if facet_slug:
            qs = qs.filter(protocol_facets__facet__slug=facet_slug).distinct()

        facet_method = (params.get('facet_method') or '').strip()
        if facet_method:
            qs = qs.filter(protocol_facets__facet__slug=facet_method).distinct()

        # `unclassified=1` —— 未挂 application facet 的协议（当前 1,523 条）。
        # 用 exclude 而非 filter(isnull)，因为 M2M 需要 NOT EXISTS 语义。
        if (params.get('unclassified') or '').lower() in ('1', 'true', 'yes'):
            qs = qs.exclude(protocol_facets__facet__facet_type='application')

        # ★ 2026-10-30：列表页搜索同样要能命中 facet 标签。
        #   原来 `?search=DNA extraction` 只查 name/objective/materials/reagents，
        #   facet 里明明标了 325 条 `DNA Extraction & Purification` 却一条都搜不到 ——
        #   用户从搜索页点"查看全部"跳过来会看到空列表。
        term = (params.get('search') or '').strip()
        if term:
            facet_ids = (ProtocolFacet.objects
                         .filter(Q(facet__value__icontains=term)
                                 | Q(facet__slug__icontains=term))
                         .values('protocol_id'))
            qs = qs.filter(
                Q(name__icontains=term) | Q(objective__icontains=term)
                | Q(materials__icontains=term) | Q(reagents__icontains=term)
                | Q(id__in=facet_ids)
            ).distinct()
        return qs

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProtocolDetailSerializer
        return ProtocolListSerializer

    @action(detail=False, methods=['get'], url_path='facets')
    def facets(self, request):
        """GET /api/v1/protocols/facets/?facet_type=application

        返回该维度下每个受控词表值各挂了**多少条 published protocol**，
        供前端渲染分类导航（chip 上的数字）。

        ⚠️ 数字语义：这是"该分类下的协议数"，而**一个协议可挂多个分类**
            ⇒ 各分类之和 > 去重后的协议总数（当前 18 个 application 覆盖
            12,598 条不重复协议，但计数之和会更大）。这不是 bug，前端要
            明确告知用户，否则会被当成"数字对不上"。
        """
        type_ = (request.query_params.get('facet_type') or 'application').strip()
        if type_ not in dict(FacetValue.FacetType.choices):
            return Response(
                {'detail': f'Unknown facet_type: {type_}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        base = ProtocolFacet.objects.filter(
            facet__facet_type=type_, protocol__status='published',
        )
        # `within=<application-slug>` —— 只统计该领域内的协议，用于二级筛选。
        within = (request.query_params.get('within') or '').strip()
        if within:
            sub = (ProtocolFacet.objects
                   .filter(facet__slug=within, protocol__status='published')
                   .values('protocol'))
            base = base.filter(protocol__in=sub)
        rows = (
            base.values('facet__slug', 'facet__value')
            .annotate(n=Count('protocol', distinct=True))
            .order_by('-n')
        )
        data = [
            {'slug': r['facet__slug'], 'value': r['facet__value'], 'count': r['n']}
            for r in rows
        ]
        # 顺带给出去重后的覆盖总数，让前端能说清"12,598/14,121 已分类"这件事
        covered = base.values('protocol').distinct().count()
        # within 生效时，"总数"应是该领域内的协议数（否则 unclassified 会算成负数）
        if within:
            total_published = (ProtocolFacet.objects
                               .filter(facet__slug=within, protocol__status='published')
                               .values('protocol').distinct().count())
        else:
            total_published = Protocol.objects.filter(status='published').count()
        return self.success_response(data, meta={
            'facet_type': type_,
            'within': within or None,
            'covered_protocols': covered,                      # 已归类的去重协议数
            'unclassified': total_published - covered,         # 未挂该维度 facet 的
            'total_published': total_published,
            # ⚠️ 这句必须对"多对多"和"1:1"两种数据形态都成立 ——
            #    不要断言各分类计数之和与 covered_protocols 的关系（那取决于基数）。
            'note': f'{covered} 条协议已归入该维度分类，另有 {total_published - covered} 条未分类',
        })

    @action(detail=True, methods=['get'], url_path='json-ld')
    def json_ld(self, request, pk=None):
        """Return JSON-LD structured data for a single protocol."""
        protocol = self.get_object()
        steps = protocol.steps.all()
        data = build_protocol_jsonld(protocol, steps, request)
        return Response(data)


class ReferenceViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    queryset = Reference.objects.all()
    serializer_class = ReferenceSerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ['title', 'authors', 'doi', 'pmid']
    ordering_fields = ['year', 'title']
    filterset_fields = ['source_type']

    def get_queryset(self):
        """★ 2026-10-30：Reference 此前**完全没有夹具过滤**（连接口都没覆写）。

        本地 219 条里有 32 条 e2e 残留（31 条 `__e2e_references_*__` + 1 条
        `E2E stub reference`），那条 stub 的 year=2026 会稳定占住首页
        "Recent Publications" 第一位。走统一入口 `apply_public_visibility`：
        Reference 无 status 字段 ⇒ 该函数对它等价于「只做夹具过滤」。
        """
        return apply_public_visibility(super().get_queryset(), Reference, self.request)


class CompatibilityViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    queryset = Compatibility.objects.all()
    serializer_class = CompatibilitySerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ['code', 'summary']
    ordering_fields = ['code']
    filterset_fields = ['scope', 'rule_type', 'severity', 'status']
