from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('apps.accounts.api.v1.urls')),
    path('api/v1/', include('apps.knowledge.api.v1.urls')),
    path('api/v1/', include('apps.commerce.api.v1.urls')),
    path('api/v1/', include('apps.transactions.api.v1.urls')),
    path('api/v1/', include('apps.assets.api.v1.urls')),
    # OpenAPI schema
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
