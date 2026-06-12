from rest_framework import serializers
from core.serializers import BaseModelSerializer
from apps.commerce.models import Product, SKU, ProductClass, CatalogGroup


class ProductClassSerializer(BaseModelSerializer):
    class Meta:
        model = ProductClass
        fields = ['id', 'name', 'slug', 'parent_id', 'sort_order', 'created_at']


class CatalogGroupSerializer(BaseModelSerializer):
    class Meta:
        model = CatalogGroup
        fields = ['id', 'name', 'slug', 'locale', 'active', 'created_at']


class SKUSerializer(BaseModelSerializer):
    class Meta:
        model = SKU
        fields = ['id', 'product_id', 'sku_code', 'pack_size', 'price', 'currency', 'inventory_status', 'created_at']


class ProductListSerializer(BaseModelSerializer):
    sku_summary = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'cas', 'smiles', 'synonyms', 'inchi',
            'purity', 'storage', 'shipping', 'lead_time', 'status',
            'research_use_only', 'product_class_id', 'sku_summary', 'created_at',
        ]

    def get_sku_summary(self, obj):
        skus = obj.skus.all()
        return {
            'count': skus.count(),
            'price_range': {
                'min': str(min((s.price for s in skus), default=0)),
                'max': str(max((s.price for s in skus), default=0)),
            } if skus else None,
            'statuses': list(skus.values_list('inventory_status', flat=True).distinct()),
        }


class ProductDetailSerializer(BaseModelSerializer):
    skus = SKUSerializer(many=True, read_only=True)
    application_ids = serializers.SerializerMethodField()
    method_ids = serializers.SerializerMethodField()
    protocol_ids = serializers.SerializerMethodField()
    reference_ids = serializers.SerializerMethodField()
    compatibility_summary = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'cas', 'smiles', 'synonyms', 'inchi',
            'purity', 'storage', 'shipping', 'lead_time', 'handling_notes',
            'shelf_life', 'research_use_only', 'status', 'product_class_id',
            'skus', 'application_ids', 'method_ids', 'protocol_ids',
            'reference_ids', 'compatibility_summary', 'created_at', 'updated_at',
        ]

    def get_application_ids(self, obj):
        from apps.bridges.models import ProductMethod
        from apps.knowledge.models import Method
        method_ids = ProductMethod.objects.filter(product=obj).values_list('method_id', flat=True)
        return list(Method.objects.filter(id__in=method_ids).values_list('application_id', flat=True).distinct())

    def get_method_ids(self, obj):
        from apps.bridges.models import ProductMethod
        return list(ProductMethod.objects.filter(product=obj).values_list('method_id', flat=True))

    def get_protocol_ids(self, obj):
        from apps.bridges.models import ProductMethod, MethodProtocol
        method_ids = ProductMethod.objects.filter(product=obj).values_list('method_id', flat=True)
        return list(MethodProtocol.objects.filter(method_id__in=method_ids).values_list('protocol_id', flat=True).distinct())

    def get_reference_ids(self, obj):
        from apps.bridges.models import ProductReference
        return list(ProductReference.objects.filter(product=obj).values_list('reference_id', flat=True))

    def get_compatibility_summary(self, obj):
        from apps.bridges.models import ProductCompatibility
        facts = ProductCompatibility.objects.filter(source_product=obj)
        return {'count': facts.count()}
