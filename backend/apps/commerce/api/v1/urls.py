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
    BatchValidateView,
    BatchRecommendLiteratureView, PubChemEnrichView,
    ProductEnrichView, ProductRenderStructureView, ProductImportProtocolView,
    ProductAdoptBiozRefsView,
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
    # Existing product routes
    path('products/<int:pk>/detail/', ProductDetailAPIView.as_view(), name='product-detail-v2'),
    path('products/<int:pk>/faq/', ProductFAQView.as_view(), name='product-faq'),
    path('products/<int:pk>/related/', RelatedProductsView.as_view(), name='product-related'),
    # Word import / AI tool endpoints
    path('products/parse-word/', WordParseView.as_view(), name='product-parse-word'),
    path('products/enrich-from-pubchem/', PubChemEnrichView.as_view(), name='product-enrich-pubchem'),
    path('products/enrich/', ProductEnrichView.as_view(), name='product-enrich'),
    path('products/render-structure/', ProductRenderStructureView.as_view(), name='product-render-structure'),
    path('products/import-protocol/', ProductImportProtocolView.as_view(), name='product-import-protocol'),
    path('products/<int:pk>/adopt-bioz-refs/', ProductAdoptBiozRefsView.as_view(), name='product-adopt-bioz-refs'),
    path('', include(router.urls)),
]
