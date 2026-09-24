"""
Related Products API View
Returns related products for a given product.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from apps.commerce.models import Product
from apps.commerce.services.related_products import get_related_products
from rest_framework.permissions import AllowAny


class RelatedProductsView(APIView):
    """GET /api/v1/products/:id/related/"""

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, status='active')
        related = get_related_products(product, limit=4)

        return Response({
            'success': True,
            'data': [
                {
                    'id': p.id,
                    'name': p.name,
                    'slug': p.slug,
                    'catalog_no': p.catalog_no,
                    'formula': p.formula,
                    'purity': p.purity,
                    'category_l1': p.category_l1,
                }
                for p in related
            ],
            'meta': {
                'product_id': product.id,
                'count': len(related),
            },
        })
    permission_classes = [AllowAny]  # ★ 2026-09-24 显式化：本类**有意公开**（站点公开面），原为「隐式 AllowAny」（DRF 默认）。
