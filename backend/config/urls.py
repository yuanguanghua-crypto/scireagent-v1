from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponseRedirect
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from apps.knowledge.api.v1.site_views import (
    robots_txt, sitemap_index, sitemap_part, sitemap_static,
)
from apps.knowledge.admin_views import knowledge_import_view
from apps.knowledge.admin_dashboard import dashboard_view
from core.health import health_check


def admin_redirect(request):
    """Redirect admin index to the researcher dashboard."""
    return HttpResponseRedirect('/admin/dashboard/')


urlpatterns = [
    path('admin/dashboard/', dashboard_view, name='admin-dashboard'),
    path('admin/knowledge-import/', knowledge_import_view, name='knowledge-import'),
    path('admin/', admin_redirect),  # redirect /admin/ to dashboard
    path('admin/', admin.site.urls),
    path('robots.txt', robots_txt, name='robots-txt'),
    # sitemap：index + 按类型分片（协议上限 50,000 URL/文件，实测已到 42,779）
    path('sitemap.xml', sitemap_index, name='sitemap-xml'),
    path('sitemap-static.xml', sitemap_static, name='sitemap-static'),
    path('sitemap-<str:kind>-<int:page>.xml', sitemap_part, name='sitemap-part'),
    path('api/v1/', include('apps.accounts.api.v1.urls')),
    # 健康检查：匿名可轮询，DB 挂时返 503（对应 FAILURE_MODES 7.2/7.3）
    path('api/v1/health/', health_check, name='health'),
    path('api/v1/', include('apps.knowledge.api.v1.urls')),
    path('api/v1/', include('apps.commerce.api.v1.urls')),
    path('api/v1/', include('apps.bridges.api.v1.urls')),
    path('api/v1/', include('apps.transactions.api.v1.urls')),
    path('api/v1/', include('apps.quotes.api.v1.urls')),
    path('api/v1/', include('apps.assets.api.v1.urls')),
    path('api/v1/', include('apps.documents.api.v1.urls')),
    path('api/v1/', include('apps.inventory.api.v1.urls')),
    # 运营台系统状态（邮件通道 / 投递队列 / 调度心跳）
    path('api/v1/', include('apps.notifications.api.v1.urls')),
    # OpenAPI schema
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
