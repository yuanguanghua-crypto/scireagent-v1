"""Dashboard Stats API View

Provides aggregated statistics for the admin dashboard.
"""
from rest_framework.views import APIView
from core.permissions import IsStaffUser

from core.mixins import EnvelopeMixin
from apps.commerce.models import Product
from apps.bridges.models import ProductMethod, ProductMethodRelation, MethodProtocol
from apps.knowledge.models import (
    ResearchGoal, Application, Method, Protocol, ProtocolStep,
)


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

        # ── 知识实体治理指标（P1-4 健康看板）──
        # verified 双 edge 状态分布（策展通道）
        verified_qs = ProductMethodRelation.objects.filter(
            relation_type=ProductMethodRelation.RelationType.VERIFIED_APPLICABILITY)
        verified_review = verified_qs.filter(
            status=ProductMethodRelation.Status.REVIEW).count()
        verified_active = verified_qs.filter(
            status=ProductMethodRelation.Status.ACTIVE).count()
        verified_rejected = verified_qs.filter(
            status=ProductMethodRelation.Status.REJECTED).count()

        # canonical Method 收敛（application=None 且 active）
        canonical_methods = Method.objects.filter(
            application__isnull=True, status='active').count()

        # 协议富化：已发布协议中有步骤的比例
        published_protocols = Protocol.objects.filter(status='published')
        total_published = published_protocols.count()
        protocols_with_steps = published_protocols.filter(
            id__in=ProtocolStep.objects.values('protocol_id')).count()
        protocol_steps_coverage = (
            round(protocols_with_steps / total_published * 100)
            if total_published else 0)

        # 悬空协议：已发布但无 MethodProtocol 关联
        hanging_protocols = published_protocols.exclude(
            id__in=MethodProtocol.objects.values('protocol_id')).count()

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
            # 治理指标
            "verified_review": verified_review,
            "verified_active": verified_active,
            "verified_rejected": verified_rejected,
            "canonical_methods": canonical_methods,
            "protocol_steps_coverage": protocol_steps_coverage,
            "hanging_protocols": hanging_protocols,
        })
