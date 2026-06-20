from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.knowledge.api.v1.views import (
    ResearchGoalViewSet, ApplicationViewSet, MethodViewSet,
    ProtocolViewSet, ReferenceViewSet, CompatibilityViewSet,
)
from apps.knowledge.api.v1.site_views import site_home, site_navigation, sitemap_xml
from apps.knowledge.api.v1.search_views import search, search_suggest
from apps.knowledge.api.v1.search_grouped_views import search_grouped
from apps.knowledge.api.v1.graph_views import graph_view
from apps.knowledge.api.v1.intake_views import KnowledgeIntakeView
from apps.knowledge.api.v1.dashboard_views import DashboardStatsView

router = DefaultRouter()
router.register('research-goals', ResearchGoalViewSet, basename='research-goal')
router.register('applications', ApplicationViewSet, basename='application')
router.register('methods', MethodViewSet, basename='method')
router.register('protocols', ProtocolViewSet, basename='protocol')
router.register('references', ReferenceViewSet, basename='reference')
router.register('compatibility', CompatibilityViewSet, basename='compatibility')

urlpatterns = [
    path('sitemap.xml', sitemap_xml, name='api-sitemap'),
    path('site/home', site_home, name='api-site-home'),
    path('site/navigation', site_navigation, name='api-site-nav'),
    path('search', search, name='api-search'),
    path('search/suggest', search_suggest, name='api-search-suggest'),
    path('search/grouped', search_grouped, name='api-search-grouped'),
    path('graph', graph_view, name='api-graph'),
    path('knowledge-intake', KnowledgeIntakeView.as_view(), name='api-knowledge-intake'),
    path('admin/dashboard-stats/', DashboardStatsView.as_view(), name='admin-dashboard-stats'),
    path('', include(router.urls)),
]
