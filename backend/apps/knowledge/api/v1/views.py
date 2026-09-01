from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Prefetch
from core.mixins import EnvelopeMixin
from core.permissions import IsAdminOrReadOnly
from core.jsonld import build_method_jsonld, build_protocol_jsonld
from apps.knowledge.models import (
    ResearchGoal, Application, Method, Protocol, Reference, Compatibility
)
from apps.knowledge.api.v1.serializers import (
    ResearchGoalListSerializer, ResearchGoalDetailSerializer, ApplicationListSerializer, ApplicationDetailSerializer,
    MethodListSerializer, MethodDetailSerializer, ProtocolListSerializer, ProtocolDetailSerializer,
    ReferenceSerializer, CompatibilitySerializer,
)
from apps.knowledge import selectors
from apps.knowledge.api.v1.fixture_visibility import apply_fixture_filter
from apps.knowledge.api.v1.filters import ApplicationFilter


class ResearchGoalViewSet(EnvelopeMixin, viewsets.ModelViewSet):
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
        status 侥幸；staff 可用 ?include_test_fixtures=1 显式查看以便清理。"""
        qs = apply_fixture_filter(
            selectors.get_research_goals_with_applications(), self.request
        )
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return qs
        return qs.filter(status=ResearchGoal.Status.ACTIVE)


class ApplicationViewSet(EnvelopeMixin, viewsets.ModelViewSet):
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
        S1：测试夹具行默认对所有身份不可见。"""
        qs = apply_fixture_filter(
            Application.objects.prefetch_related(self._rg_prefetch).all(), self.request
        )
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return qs
        return qs.filter(status=Application.Status.ACTIVE)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ApplicationDetailSerializer
        return ApplicationListSerializer


class MethodViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    queryset = Method.objects.select_related('application').all()
    serializer_class = MethodListSerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ['name', 'purpose', 'advantages', 'limitations']
    ordering_fields = ['name', 'cost_band']
    filterset_fields = ['application_id', 'status']

    def get_queryset(self):
        """公开端点仅返回已发布(ACTIVE)记录；staff 可访问全量。
        S1：测试夹具行默认对所有身份不可见。"""
        qs = apply_fixture_filter(
            Method.objects.select_related('application').all(), self.request
        )
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return qs
        return qs.filter(status=Method.Status.ACTIVE)

    def get_serializer_class(self):
        if self.action == 'retrieve':
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
    search_fields = ['name', 'objective', 'materials', 'reagents']
    ordering_fields = ['name', 'version']
    filterset_fields = ['status']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProtocolDetailSerializer
        return ProtocolListSerializer

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


class CompatibilityViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    queryset = Compatibility.objects.all()
    serializer_class = CompatibilitySerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ['code', 'summary']
    ordering_fields = ['code']
    filterset_fields = ['scope', 'rule_type', 'severity', 'status']
