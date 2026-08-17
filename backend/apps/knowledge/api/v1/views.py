from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from core.mixins import EnvelopeMixin
from core.permissions import IsAdminOrReadOnly
from core.jsonld import build_method_jsonld, build_protocol_jsonld
from apps.knowledge.models import (
    ResearchGoal, Application, Method, Protocol, Reference, Compatibility
)
from apps.knowledge.api.v1.serializers import (
    ResearchGoalListSerializer, ApplicationListSerializer, ApplicationDetailSerializer,
    MethodListSerializer, MethodDetailSerializer, ProtocolListSerializer, ProtocolDetailSerializer,
    ReferenceSerializer, CompatibilitySerializer,
)
from apps.knowledge import selectors
from apps.knowledge.api.v1.fixture_visibility import apply_fixture_filter


class ResearchGoalViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    queryset = selectors.get_research_goals_with_applications()
    serializer_class = ResearchGoalListSerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ['name', 'summary']
    ordering_fields = ['priority', 'name']

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
    queryset = Application.objects.select_related('research_goal').all()
    serializer_class = ApplicationListSerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ['name', 'summary']
    ordering_fields = ['sort_order', 'name']
    filterset_fields = ['research_goal_id', 'status']

    def get_queryset(self):
        """公开端点仅返回已发布(ACTIVE)记录；staff 可访问全量。
        S1：测试夹具行默认对所有身份不可见。"""
        qs = apply_fixture_filter(
            Application.objects.select_related('research_goal').all(), self.request
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
    queryset = Protocol.objects.select_related('method').prefetch_related('steps').all()
    serializer_class = ProtocolListSerializer
    permission_classes = [IsAdminOrReadOnly]
    search_fields = ['name', 'objective', 'materials', 'reagents']
    ordering_fields = ['name', 'version']
    filterset_fields = ['method_id', 'status']

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
