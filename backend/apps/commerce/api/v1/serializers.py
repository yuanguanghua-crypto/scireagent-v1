from rest_framework import serializers
from core.serializers import BaseModelSerializer
from apps.commerce.models import Product, SKU, ProductClass, CatalogGroup, ProductDocument


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
        fields = [
            'id', 'product_id', 'sku_code', 'pack_size', 'price', 'currency',
            'inventory_status', 'concentration', 'lead_time', 'is_default', 'created_at',
        ]


class SKUCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SKU
        fields = ['sku_code', 'pack_size', 'price', 'currency', 'inventory_status',
                  'concentration', 'lead_time', 'is_default']


class ProductDocumentSerializer(BaseModelSerializer):
    class Meta:
        model = ProductDocument
        fields = ['id', 'product_id', 'document_type', 'language', 'version',
                  'file', 'original_filename', 'created_at']
        read_only_fields = ['id', 'created_at']


class ProductListSerializer(BaseModelSerializer):
    sku_summary = serializers.SerializerMethodField()
    product_class_name = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'catalog_no', 'cas', 'smiles', 'synonyms', 'inchi',
            'formula', 'molecular_weight', 'purity', 'concentration', 'storage',
            'shipping', 'lead_time', 'status', 'research_use_only',
            'product_class_id', 'product_class_name', 'category_l1', 'category_l2',
            'sku_summary', 'created_at',
        ]

    def get_product_class_name(self, obj):
        if obj.product_class:
            return obj.product_class.name
        return None

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


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    skus = SKUCreateSerializer(many=True, required=False)

    class Meta:
        model = Product
        fields = [
            'name', 'slug', 'catalog_no', 'cas', 'smiles', 'synonyms', 'inchi',
            'formula', 'molecular_weight', 'purity', 'concentration', 'storage',
            'shipping', 'lead_time', 'handling_notes', 'shelf_life', 'research_use_only',
            'overview', 'structure_svg', 'seo_title', 'seo_description',
            'category_l1', 'category_l2', 'status', 'product_class_id',
        ]

    def create(self, validated_data):
        skus_data = validated_data.pop('skus', [])
        product = Product.objects.create(**validated_data)
        for sku_data in skus_data:
            SKU.objects.create(product=product, **sku_data)
        return product

    def update(self, instance, validated_data):
        skus_data = validated_data.pop('skus', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if skus_data is not None:
            instance.skus.all().delete()
            for sku_data in skus_data:
                SKU.objects.create(product=instance, **sku_data)
        return instance


class ProductDetailSerializer(BaseModelSerializer):
    skus = SKUSerializer(many=True, read_only=True)
    documents = ProductDocumentSerializer(many=True, read_only=True)
    product_class_name = serializers.SerializerMethodField()
    product_class_path = serializers.SerializerMethodField()
    application_ids = serializers.SerializerMethodField()
    method_ids = serializers.SerializerMethodField()
    protocol_ids = serializers.SerializerMethodField()
    reference_ids = serializers.SerializerMethodField()
    compatibility_summary = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'catalog_no', 'cas', 'smiles', 'synonyms', 'inchi',
            'formula', 'molecular_weight', 'purity', 'concentration', 'storage',
            'shipping', 'lead_time', 'handling_notes', 'shelf_life', 'research_use_only',
            'overview', 'structure_svg', 'seo_title', 'seo_description',
            'category_l1', 'category_l2', 'status', 'product_class_id',
            'product_class_name', 'product_class_path',
            'skus', 'documents', 'application_ids', 'method_ids', 'protocol_ids',
            'reference_ids', 'compatibility_summary', 'created_at', 'updated_at',
        ]

    def get_product_class_name(self, obj):
        if obj.product_class:
            return obj.product_class.name
        return None

    def get_product_class_path(self, obj):
        """Return breadcrumb path: [L1_name, L2_name, L3_name]"""
        if not obj.product_class:
            return []
        path = []
        pc = obj.product_class
        while pc:
            path.insert(0, pc.name)
            pc = pc.parent
        return path

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
