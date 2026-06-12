from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from core.mixins import EnvelopeMixin
from core.jsonld import build_product_jsonld
from apps.commerce.models import Product, SKU, ProductClass, CatalogGroup
from apps.commerce.api.v1.serializers import (
    ProductListSerializer, ProductDetailSerializer, SKUSerializer,
    ProductClassSerializer, CatalogGroupSerializer,
)
from apps.commerce import selectors


class ProductViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    queryset = Product.objects.select_related('product_class').prefetch_related('skus').all()
    serializer_class = ProductListSerializer
    search_fields = ['name', 'cas', 'smiles', 'inchi']
    ordering_fields = ['name', 'created_at']
    filterset_fields = ['product_class_id', 'status']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductDetailSerializer
        return ProductListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        query = self.request.query_params.get('search', '')
        if query:
            qs = selectors.filter_products(query)
        return qs

    @action(detail=True, methods=['get'], url_path='json-ld')
    def json_ld(self, request, pk=None):
        """Return JSON-LD structured data for a single product."""
        product = self.get_object()
        data = build_product_jsonld(product, request)
        return Response(data)


class SKUViewSet(EnvelopeMixin, viewsets.ModelViewSet):
    queryset = SKU.objects.select_related('product').all()
    serializer_class = SKUSerializer
    filterset_fields = ['product_id', 'inventory_status']
    search_fields = ['sku_code']


class ProductClassViewSet(EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    queryset = ProductClass.objects.all()
    serializer_class = ProductClassSerializer


class CatalogGroupViewSet(EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    queryset = CatalogGroup.objects.filter(active=True)
    serializer_class = CatalogGroupSerializer
