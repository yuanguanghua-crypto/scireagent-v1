"""Dashboard Stats API View

Provides aggregated statistics for the admin dashboard.
"""
from rest_framework.views import APIView
from core.permissions import IsStaffUser

from core.mixins import EnvelopeMixin
from apps.commerce.models import Product
from apps.bridges.models import ProductMethod
from apps.knowledge.models import ResearchGoal, Application, Method, Protocol


class DashboardStatsView(EnvelopeMixin, APIView):
    """GET /api/v1/admin/dashboard-stats/

    Returns aggregated dashboard statistics.
    """
    permission_classes = [IsStaffUser]

    def get(self, request):
        # Plan B：软删（回收站）产品不计入工作台统计，避免删除后数字虚高。
        live = Product.objects.filter(archived=False)
        # Product counts
        total_products = live.count()
        active_products = live.filter(status="active").count()
        draft_products = live.filter(status="draft").count()
        inactive_products = live.exclude(status__in=["active", "draft"]).count()

        # Incomplete products (exclude active — those are already published)
        incomplete_count = 0
        for p in live.exclude(status="active").select_related('product_class').iterator():
            if not (p.name and p.catalog_no and p.product_class_id and p.skus.filter(is_default=True).exists()):
                incomplete_count += 1

        # Coverage
        products_with_cas = live.exclude(cas="").count()
        products_with_smiles = live.exclude(smiles="").count()
        products_with_knowledge = ProductMethod.objects.values("product_id").distinct().count()

        # Knowledge graph counts
        total_goals = ResearchGoal.objects.count()
        total_apps = Application.objects.count()
        total_methods = Method.objects.count()
        total_protocols = Protocol.objects.count()

        return self.success_response({
            "total_products": total_products,
            "active_products": active_products,
            "draft_products": draft_products,
            "inactive_products": inactive_products,
            "incomplete_products": incomplete_count,
            "products_with_cas": products_with_cas,
            "products_with_smiles": products_with_smiles,
            "products_with_knowledge": products_with_knowledge,
            "total_goals": total_goals,
            "total_applications": total_apps,
            "total_methods": total_methods,
            "total_protocols": total_protocols,
        })
