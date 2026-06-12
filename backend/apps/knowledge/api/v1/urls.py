from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.knowledge.api.v1.views import (
    ResearchGoalViewSet, ApplicationViewSet, MethodViewSet,
    ProtocolViewSet, ReferenceViewSet, CompatibilityViewSet,
)
from apps.knowledge.api.v1.site_views import site_home, site_navigation, sitemap_xml
from apps.knowledge.api.v1.search_views import search, search_suggest

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
    path('', include(router.urls)),
]
