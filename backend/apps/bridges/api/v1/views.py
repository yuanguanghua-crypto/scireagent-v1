"""bridges API 视图（Phase 3 verified 通道 + 双 edge，T3.2）。

铁律：API 只编排 VerifiedService / 查询 PMR，绝不直接 ORM 改 PMR（写）。
权限（Phase 4 决策）：GET 双 edge = AllowAny（公开产品页调用，符「知识实体公开读」铁律）；
创建草稿/PATCH = IsAuthenticated；approve/reject = IsStaffUser。
响应：统一 EnvelopeMixin 信封 {success, data, meta}。
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from core.mixins import EnvelopeMixin
from core.permissions import IsStaffUser
from apps.commerce.models import Product
from apps.knowledge.models import Method
from apps.bridges.models import ProductMethodRelation
from apps.bridges.services.verified_service import VerifiedService
from apps.bridges.api.v1.serializers import (
    ProductMethodRelationSerializer,
    VerifiedCreateSerializer,
    VerifiedPatchSerializer,
)


class ProductMethodsView(EnvelopeMixin, APIView):
    """GET product/{id}/methods → 双 edge 分离（related_methods / verified_methods）。"""
    permission_classes = [AllowAny]  # Phase 4：公开产品页调用，公开读

    def get(self, request, pk):
        get_object_or_404(Product, pk=pk)
        derived = ProductMethodRelation.objects.filter(
            product_id=pk, relation_type=ProductMethodRelation.RelationType.DERIVED_RELEVANCE)
        verified = ProductMethodRelation.objects.filter(
            product_id=pk, relation_type=ProductMethodRelation.RelationType.VERIFIED_APPLICABILITY)
        data = {
            "related_methods": ProductMethodRelationSerializer(derived, many=True).data,
            "verified_methods": ProductMethodRelationSerializer(verified, many=True).data,
        }
        return self.success_response(data)


class MethodProductsView(EnvelopeMixin, APIView):
    """GET method/{id}/products → 反向查询（双 edge 合并输出）。"""
    permission_classes = [AllowAny]  # Phase 4：公开读

    def get(self, request, pk):
        get_object_or_404(Method, pk=pk)
        edges = ProductMethodRelation.objects.filter(method_id=pk)
        data = {
            "products": ProductMethodRelationSerializer(edges, many=True).data,
        }
        return self.success_response(data)


class VerifiedCreateView(EnvelopeMixin, APIView):
    """POST verified → 创建 REVIEW 草稿（登录用户即可）。"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = VerifiedCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            pmr = VerifiedService.create_verified_draft(
                product_id=d["product_id"],
                method_id=d["method_id"],
                evidence_type=d.get("evidence_type", ""),
                evidence_reference=d.get("evidence_reference"),
                evidence_strength=d.get("evidence_strength", ""),
                evidence_note=d.get("evidence_note", ""),
                curator=request.user.username,
            )
        except IntegrityError:
            return self.error_response(
                "该 产品-方法 已存在 verified 关系（唯一约束：product+method+relation_type）",
                code="unique_conflict", status_code=status.HTTP_400_BAD_REQUEST)
        return self.success_response(
            ProductMethodRelationSerializer(pmr).data, status_code=status.HTTP_201_CREATED)


class VerifiedPatchView(EnvelopeMixin, APIView):
    """PATCH verified/{id} → 补全 evidence（登录用户即可；不改状态）。"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        serializer = VerifiedPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            pmr = VerifiedService.patch_verified(pk, **serializer.validated_data)
        except ProductMethodRelation.DoesNotExist:
            return self.error_response("verified 关系不存在", status_code=status.HTTP_404_NOT_FOUND)
        return self.success_response(ProductMethodRelationSerializer(pmr).data)


class VerifiedApproveView(EnvelopeMixin, APIView):
    """POST verified/{id}/approve → 研究员置 ACTIVE(verified)（仅 IsStaffUser）。"""
    permission_classes = [IsStaffUser]

    def post(self, request, pk):
        try:
            pmr = VerifiedService.approve_verified(pk, curator=request.user.username)
        except ProductMethodRelation.DoesNotExist:
            return self.error_response("verified 关系不存在", status_code=status.HTTP_404_NOT_FOUND)
        except DjangoValidationError as exc:
            return self.error_response(
                "approve 失败：" + str(exc), code="validation",
                status_code=status.HTTP_400_BAD_REQUEST)
        return self.success_response(ProductMethodRelationSerializer(pmr).data)


class VerifiedRejectView(EnvelopeMixin, APIView):
    """POST verified/{id}/reject → 置 REJECTED（仅 IsStaffUser）。"""
    permission_classes = [IsStaffUser]

    def post(self, request, pk):
        note = request.data.get("note", "") if isinstance(request.data, dict) else ""
        try:
            pmr = VerifiedService.reject_verified(
                pk, curator=request.user.username, note=note)
        except ProductMethodRelation.DoesNotExist:
            return self.error_response("verified 关系不存在", status_code=status.HTTP_404_NOT_FOUND)
        return self.success_response(ProductMethodRelationSerializer(pmr).data)
