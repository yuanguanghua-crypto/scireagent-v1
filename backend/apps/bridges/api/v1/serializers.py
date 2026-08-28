"""bridges API 序列化器（Phase 3，T3.2）。

铁律：字段显式声明，禁 __all__；API 只编排 VerifiedService，不直接 ORM 改 PMR。
"""
from django.core.exceptions import ValidationError as DjangoValidationError

from rest_framework import serializers

from apps.commerce.models import Product
from apps.knowledge.models import Method
from apps.bridges.models import ProductMethodRelation, validate_evidence_reference


class ProductMethodRelationSerializer(serializers.Serializer):
    """PMR（双 edge）只读输出。显式字段，禁用 ModelSerializer.__all__。

    method_name/method_slug（Phase 4）：前端卡片直接渲染方法名，避免 N+1 取 Method。
    """
    id = serializers.IntegerField(read_only=True)
    product_id = serializers.IntegerField(read_only=True)
    method_id = serializers.IntegerField(read_only=True)
    method_name = serializers.CharField(source='method.name', read_only=True)
    method_slug = serializers.CharField(source='method.slug', read_only=True)
    relation_type = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    source_reagent_class = serializers.PrimaryKeyRelatedField(read_only=True)
    evidence_type = serializers.CharField(read_only=True)
    evidence_reference = serializers.JSONField(read_only=True)
    evidence_strength = serializers.CharField(read_only=True)
    evidence_note = serializers.CharField(read_only=True)
    curator = serializers.CharField(read_only=True)


class VerifiedCreateSerializer(serializers.Serializer):
    """创建 verified REVIEW 草稿。"""
    product_id = serializers.IntegerField(required=True)
    method_id = serializers.IntegerField(required=True)
    evidence_type = serializers.CharField(required=False, default="", allow_blank=True)
    evidence_reference = serializers.JSONField(required=False, default=None)
    evidence_strength = serializers.CharField(required=False, default="", allow_blank=True)
    evidence_note = serializers.CharField(required=False, default="", allow_blank=True)

    def validate(self, attrs):
        # 存在性校验（FK PROTECT，提前给清晰报错而非 500）
        if not Product.objects.filter(id=attrs["product_id"]).exists():
            raise serializers.ValidationError({"product_id": "产品不存在"})
        if not Method.objects.filter(id=attrs["method_id"]).exists():
            raise serializers.ValidationError({"method_id": "方法不存在"})
        # evidence_reference 结构校验（仅当提供了非空内容时）
        ref = attrs.get("evidence_reference")
        if ref:
            try:
                validate_evidence_reference(ref)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"evidence_reference": str(exc)})
        return attrs


class VerifiedPatchSerializer(serializers.Serializer):
    """PATCH 补全 evidence（全部可选；仅更新提供的字段，含显式置空）。"""
    evidence_type = serializers.CharField(required=False, allow_blank=True)
    evidence_reference = serializers.JSONField(required=False)
    evidence_strength = serializers.CharField(required=False, allow_blank=True)
    evidence_note = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        ref = attrs.get("evidence_reference")
        if ref is not None and ref:  # 显式提供了非空 list 才校验结构
            try:
                validate_evidence_reference(ref)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"evidence_reference": str(exc)})
        return attrs
