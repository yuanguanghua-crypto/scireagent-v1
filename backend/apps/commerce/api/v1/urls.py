from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.commerce.api.v1.views import (
    ProductViewSet, SKUViewSet, ProductClassViewSet, CatalogGroupViewSet,
)

router = DefaultRouter()
router.register('products', ProductViewSet, basename='product')
router.register('skus', SKUViewSet, basename='sku')
router.register('product-classes', ProductClassViewSet, basename='product-class')
router.register('catalog-groups', CatalogGroupViewSet, basename='catalog-group')

urlpatterns = [path('', include(router.urls))]
