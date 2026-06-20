"""Dashboard Stats API View

Provides aggregated statistics for the admin dashboard.
"""
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser

from core.mixins import EnvelopeMixin
from apps.commerce.models import Product
from apps.bridges.models import ProductMethod


class DashboardStatsView(EnvelopeMixin, APIView):
    """GET /api/v1/admin/dashboard-stats/

    Returns aggregated dashboard statistics including PubChem coverage.
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        total_products = Product.objects.filter(status="active").count()
        products_with_cas = (
            Product.objects.filter(status="active")
            .exclude(cas="")
            .count()
        )
        pubchem_coverage = (
            round(products_with_cas / total_products * 100, 1)
            if total_products
            else 0.0
        )
        products_without_method = (
            Product.objects.filter(status="active")
            .exclude(id__in=ProductMethod.objects.values("product_id"))
            .count()
        )

        return self.success_response({
            "total_products": total_products,
            "products_with_cas": products_with_cas,
            "pubchem_coverage": pubchem_coverage,
            "products_without_method": products_without_method,
        })
