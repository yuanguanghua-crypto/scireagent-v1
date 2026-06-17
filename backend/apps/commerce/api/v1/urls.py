from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.commerce.api.v1.views import (
    ProductViewSet, SKUViewSet, ProductClassViewSet, CatalogGroupViewSet,
    ProductDocumentViewSet, ProductDetailAPIView,
)
from apps.commerce.api.v1.faq_views import ProductFAQView
from apps.commerce.api.v1.related_views import RelatedProductsView
from apps.commerce.api.v1.categories import CategoryTreeView

router = DefaultRouter()
router.register('products', ProductViewSet, basename='product')
router.register('skus', SKUViewSet, basename='sku')
router.register('product-classes', ProductClassViewSet, basename='product-class')
router.register('catalog-groups', CatalogGroupViewSet, basename='catalog-group')
router.register('documents', ProductDocumentViewSet, basename='document')

urlpatterns = [
    path('categories', CategoryTreeView.as_view(), name='categories'),
    path('products/<int:pk>/detail/', ProductDetailAPIView.as_view(), name='product-detail-v2'),
    path('products/<int:pk>/faq/', ProductFAQView.as_view(), name='product-faq'),
    path('products/<int:pk>/related/', RelatedProductsView.as_view(), name='product-related'),
    path('', include(router.urls)),
]
