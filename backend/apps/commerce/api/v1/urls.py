from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.commerce.api.v1.views import (
    ProductViewSet, SKUViewSet, ProductClassViewSet, CatalogGroupViewSet,
    ProductDocumentViewSet, ProductDetailAPIView,
)
from apps.commerce.api.v1.faq_views import ProductFAQView
from apps.commerce.api.v1.related_views import RelatedProductsView
from apps.commerce.api.v1.categories import CategoryTreeView
from apps.commerce.api.v1.ai_views import (
    ProductValidateView, ProductRecommendProtocolsView,
    ProductRecommendLiteratureView, BatchValidateView,
    BatchRecommendLiteratureView,
)
from apps.commerce.api.v1.word_views import WordParseView

router = DefaultRouter()
router.register('products', ProductViewSet, basename='product')
router.register('skus', SKUViewSet, basename='sku')
router.register('product-classes', ProductClassViewSet, basename='product-class')
router.register('catalog-groups', CatalogGroupViewSet, basename='catalog-group')
router.register('documents', ProductDocumentViewSet, basename='document')

urlpatterns = [
    path('categories', CategoryTreeView.as_view(), name='categories'),
    # AI tool endpoints — must precede router include to avoid pk matching
    path('products/batch-validate/', BatchValidateView.as_view(), name='batch-validate'),
    path('products/batch-recommend-literature/', BatchRecommendLiteratureView.as_view(), name='batch-recommend-literature'),
    path('products/<int:pk>/validate/', ProductValidateView.as_view(), name='product-validate'),
    path('products/<int:pk>/recommend-protocols/', ProductRecommendProtocolsView.as_view(), name='product-recommend-protocols'),
    path('products/<int:pk>/recommend-literature/', ProductRecommendLiteratureView.as_view(), name='product-recommend-literature'),
    # Existing product routes
    path('products/<int:pk>/detail/', ProductDetailAPIView.as_view(), name='product-detail-v2'),
    path('products/<int:pk>/faq/', ProductFAQView.as_view(), name='product-faq'),
    path('products/<int:pk>/related/', RelatedProductsView.as_view(), name='product-related'),
    # Word import / AI tool endpoints
    path('products/parse-word/', WordParseView.as_view(), name='product-parse-word'),
    path('', include(router.urls)),
]
