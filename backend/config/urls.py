from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from apps.knowledge.api.v1.site_views import robots_txt, sitemap_xml

urlpatterns = [
    path('admin/', admin.site.urls),
    path('robots.txt', robots_txt, name='robots-txt'),
    path('sitemap.xml', sitemap_xml, name='sitemap-xml'),
    path('api/v1/', include('apps.accounts.api.v1.urls')),
    path('api/v1/', include('apps.knowledge.api.v1.urls')),
    path('api/v1/', include('apps.commerce.api.v1.urls')),
    path('api/v1/', include('apps.transactions.api.v1.urls')),
    path('api/v1/', include('apps.quotes.api.v1.urls')),
    path('api/v1/', include('apps.assets.api.v1.urls')),
    # OpenAPI schema
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
