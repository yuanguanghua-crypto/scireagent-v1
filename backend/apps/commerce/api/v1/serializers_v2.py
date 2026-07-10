"""
V1.2 Serializers — Phase 1, Week 3.
All serializers per-model, no cross-model reuse.
"""
from rest_framework import serializers
from core.svg_sanitizer import sanitize_svg
from apps.knowledge.models import Application, Method, Protocol, Reference
from apps.commerce.models import Product, SKU, ProductDocument
from math import ceil


class ApplicationBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ['id', 'name', 'slug', 'summary']


class MethodBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Method
        fields = ['id', 'name', 'slug', 'purpose']


class ProtocolBriefSerializer(serializers.ModelSerializer):
    estimated_time_minutes = serializers.SerializerMethodField()

    class Meta:
        model = Protocol
        fields = ['id', 'name', 'slug', 'objective', 'estimated_time_minutes']

    def get_estimated_time_minutes(self, obj):
        from django.db.models import Sum
        total = obj.steps.aggregate(total=Sum('duration_seconds'))['total'] or 0
        return ceil(total / 60)


class ProductBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'catalog_no', 'cas']


class ReferenceBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reference
        fields = ['id', 'title', 'journal', 'year', 'doi']


class RelatedProductSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    catalog_no = serializers.CharField(allow_null=True)
    cas = serializers.CharField(allow_null=True)
    match_reason = serializers.CharField()


class FAQSerializer(serializers.Serializer):
    question = serializers.CharField()
    answer = serializers.CharField()


class GraphNodeSerializer(serializers.Serializer):
    id = serializers.CharField()
    type = serializers.CharField()
    label = serializers.CharField()
    slug = serializers.CharField(required=False, allow_blank=True)


class GraphEdgeSerializer(serializers.Serializer):
    id = serializers.CharField()
    source = serializers.CharField()
    target = serializers.CharField()
    relationship = serializers.CharField()


class SKUSerializerV2(serializers.ModelSerializer):
    class Meta:
        model = SKU
        fields = [
            'id', 'sku_code', 'pack_size', 'concentration', 'price',
            'currency', 'inventory_status', 'lead_time', 'is_default',
        ]


class ProductDocumentSerializerV2(serializers.ModelSerializer):
    class Meta:
        model = ProductDocument
        fields = ['id', 'document_type', 'original_filename', 'file', 'language', 'version']


class ProductFullSerializer(serializers.ModelSerializer):
    skus = SKUSerializerV2(many=True, read_only=True)
    documents = ProductDocumentSerializerV2(many=True, read_only=True)
    product_class_name = serializers.SerializerMethodField()
    product_class_path = serializers.SerializerMethodField()
    structure_svg = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'catalog_no', 'cas', 'smiles', 'synonyms', 'inchi',
            'formula', 'molecular_weight', 'purity', 'concentration', 'storage',
            'shipping', 'lead_time', 'handling_notes', 'shelf_life', 'research_use_only',
            'overview', 'structure_svg', 'seo_title', 'seo_description',
            'category_l1', 'category_l2', 'status', 'product_class_id',
            'product_class_name', 'product_class_path',
            'skus', 'documents', 'created_at', 'updated_at',
        ]

    def get_product_class_name(self, obj):
        return obj.product_class.name if obj.product_class else None

    def get_structure_svg(self, obj):
        """Sanitize SVG before output to prevent XSS."""
        return sanitize_svg(obj.structure_svg) if obj.structure_svg else None

    def get_product_class_path(self, obj):
        if not obj.product_class:
            return []
        path = []
        pc = obj.product_class
        while pc:
            path.insert(0, pc.name)
            pc = pc.parent
        return path


class CompatibilitySerializer(serializers.Serializer):
    methods = MethodBriefSerializer(many=True)
    protocols = ProtocolBriefSerializer(many=True)
    products = ProductBriefSerializer(many=True)
