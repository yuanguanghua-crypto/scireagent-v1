"""
Product FAQ API View
Returns dynamically generated FAQ for a product.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from apps.commerce.models import Product
from apps.knowledge.services.faq_generator import generate_faq, generate_faq_json_ld


class ProductFAQView(APIView):
    """GET /api/v1/products/:id/faq/"""

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, status='active')
        faqs = generate_faq(product)

        response_data = {
            'success': True,
            'data': faqs,
            'meta': {
                'product_id': product.id,
                'product_name': product.name,
                'count': len(faqs),
            },
        }

        # Include JSON-LD if requested
        if request.GET.get('json_ld'):
            response_data['json_ld'] = generate_faq_json_ld(product, faqs)

        return Response(response_data)
