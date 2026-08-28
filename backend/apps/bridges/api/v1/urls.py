"""bridges API v1 路由（Phase 3 verified 通道 + 双 edge）。

挂载点：config/urls.py → path('api/v1/', include('apps.bridges.api.v1.urls'))
完整前缀：/api/v1/bridges/...
"""
from django.urls import path

from apps.bridges.api.v1.views import (
    ProductMethodsView,
    MethodProductsView,
    VerifiedCreateView,
    VerifiedPatchView,
    VerifiedApproveView,
    VerifiedRejectView,
)

app_name = "bridges"

urlpatterns = [
    path("products/<int:pk>/methods/", ProductMethodsView.as_view(), name="product-methods"),
    path("methods/<int:pk>/products/", MethodProductsView.as_view(), name="method-products"),
    path("verified/", VerifiedCreateView.as_view(), name="verified-create"),
    path("verified/<int:pk>/approve/", VerifiedApproveView.as_view(), name="verified-approve"),
    path("verified/<int:pk>/reject/", VerifiedRejectView.as_view(), name="verified-reject"),
    path("verified/<int:pk>/", VerifiedPatchView.as_view(), name="verified-patch"),
]
