from rest_framework import serializers
from core.serializers import BaseModelSerializer
from core.svg_sanitizer import sanitize_svg
from apps.commerce.models import Product, SKU, ProductClass, CatalogGroup, ProductDocument
from apps.knowledge.models import Method, Protocol


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


def _is_product_complete(product):
    """判断产品是否完整（5 条件）。

    1. Name 不为空 + catalog_no 不为空
    2. CAS 不为空
    3. SMILES 不为空
    4. category_l1 不为空
    5. 至少 1 个 SKU 且 is_default=True
    """
    if not (product.name and product.catalog_no):
        return False
    if not product.cas:
        return False
    if not product.smiles:
        return False
    if not product.category_l1:
        return False
    if not product.skus.filter(is_default=True).exists():
        return False
    return True


def _incomplete_items(product):
    """返回不完整条件的名称列表，用于发布弹窗展示。"""
    items = []
    if not (product.name and product.catalog_no):
        items.append('基本信息 (Name + Catalog No)')
    if not product.cas:
        items.append('CAS')
    if not product.smiles:
        items.append('SMILES')
    if not product.category_l1:
        items.append('分类 (category_l1)')
    if not product.skus.filter(is_default=True).exists():
        items.append('默认 SKU')
    return items


class ProductListSerializer(BaseModelSerializer):
    sku_summary = serializers.SerializerMethodField()
    product_class_name = serializers.SerializerMethodField()
    is_complete = serializers.SerializerMethodField()
    incomplete_items = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'catalog_no', 'cas', 'smiles', 'synonyms', 'inchi',
            'formula', 'molecular_weight', 'purity', 'concentration', 'storage',
            'shipping', 'lead_time', 'status', 'research_use_only',
            'product_class_id', 'product_class_name', 'category_l1', 'category_l2',
            'sku_summary', 'created_at', 'updated_at', 'is_complete', 'incomplete_items',
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

    def get_is_complete(self, obj):
        return _is_product_complete(obj)

    def get_incomplete_items(self, obj):
        return _incomplete_items(obj)


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    skus = SKUCreateSerializer(many=True, required=False)
    # Knowledge relationship fields (write-only, optional)
    method_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=None)
    protocol_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=None)
    research_goal_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=None)
    application_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=None)

    class Meta:
        model = Product
        fields = [
            'name', 'slug', 'catalog_no', 'cas', 'smiles', 'synonyms', 'inchi',
            'formula', 'molecular_weight', 'purity', 'concentration', 'storage',
            'shipping', 'lead_time', 'handling_notes', 'shelf_life', 'research_use_only',
            'overview', 'structure_svg', 'seo_title', 'seo_description',
            'category_l1', 'category_l2', 'status', 'product_class_id',
            'skus', 'method_ids', 'protocol_ids', 'research_goal_ids', 'application_ids',
        ]

    def _sync_method_bridges(self, product, method_ids):
        """Sync ProductMethod bridges: remove old, add new."""
        from apps.bridges.models import ProductMethod
        if method_ids is None:
            return  # Not provided, don't touch
        existing = set(ProductMethod.objects.filter(product=product).values_list('method_id', flat=True))
        desired = set(mid for mid in method_ids if Method.objects.filter(id=mid).exists())
        # Remove bridges not in desired
        to_remove = existing - desired
        if to_remove:
            ProductMethod.objects.filter(product=product, method_id__in=to_remove).delete()
        # Add bridges not in existing
        to_add = desired - existing
        for mid in to_add:
            ProductMethod.objects.create(product=product, method_id=mid)

    def _resolve_method_ids_from_goals_or_apps(self, research_goal_ids, application_ids):
        """从 ResearchGoal 或 Application 级联解析出 Method ID 集合。
        用于 research_goal_ids / application_ids 的快捷关联。"""
        from django.db import models as db_models
        q = db_models.Q()
        if research_goal_ids:
            q |= db_models.Q(application__research_goal_id__in=research_goal_ids)
        if application_ids:
            q |= db_models.Q(application_id__in=application_ids)
        if not q:
            return set()
        return set(Method.objects.filter(q).values_list('id', flat=True))

    def _merge_method_ids(self, method_ids, research_goal_ids, application_ids):
        """合并前端传来的 method_ids 和从 goal/app 级联解析出的 method_ids。"""
        direct = set(method_ids) if method_ids else set()
        cascaded = self._resolve_method_ids_from_goals_or_apps(research_goal_ids, application_ids)
        return direct | cascaded

    def _sync_protocol_bridges(self, product, protocol_ids):
        """Sync MethodProtocol bridges via product's methods."""
        from apps.bridges.models import MethodProtocol
        if protocol_ids is None:
            return
        # Get product's method IDs
        method_ids = list(ProductMethod.objects.filter(product=product).values_list('method_id', flat=True))
        if not method_ids:
            return
        # For each protocol, create MethodProtocol bridge if not exists
        for pid in protocol_ids:
            if not Protocol.objects.filter(id=pid).exists():
                continue
            for mid in method_ids:
                MethodProtocol.objects.get_or_create(method_id=mid, protocol_id=pid)

    @staticmethod
    def _auto_seo_on_publish(product):
        """当产品从 draft 变为 active 时，若 SEO 为空则自动生成。"""
        from apps.commerce.services.seo_generator import generate_seo
        changed = False
        if not product.seo_title:
            product.seo_title = f'{product.name} | SciReagent'
            changed = True
        if not product.seo_description:
            desc = f'Buy {product.name}'
            if product.cas:
                desc += f' (CAS: {product.cas})'
            desc += '. High purity research reagent. Order from SciReagent.'
            product.seo_description = desc
            changed = True
        if changed:
            product.save(update_fields=['seo_title', 'seo_description'])

    def create(self, validated_data):
        method_ids = validated_data.pop('method_ids', None)
        protocol_ids = validated_data.pop('protocol_ids', None)
        research_goal_ids = validated_data.pop('research_goal_ids', None)
        application_ids = validated_data.pop('application_ids', None)
        skus_data = validated_data.pop('skus', [])

        product = Product.objects.create(**validated_data)
        for sku_data in skus_data:
            SKU.objects.create(product=product, **sku_data)

        # Sync method bridges only if any method-related field was explicitly provided.
        # Explicit empty list clears all bridges; omitting all fields preserves existing.
        if method_ids is not None or research_goal_ids is not None or application_ids is not None:
            merged = self._merge_method_ids(method_ids, research_goal_ids, application_ids)
            self._sync_method_bridges(product, list(merged))
        self._sync_protocol_bridges(product, protocol_ids)

        # Auto-generate SEO on publish (draft→active)
        self._auto_seo_on_publish(product)
        return product

    def update(self, instance, validated_data):
        method_ids = validated_data.pop('method_ids', None)
        protocol_ids = validated_data.pop('protocol_ids', None)
        research_goal_ids = validated_data.pop('research_goal_ids', None)
        application_ids = validated_data.pop('application_ids', None)
        skus_data = validated_data.pop('skus', None)

        new_status = validated_data.get('status')
        is_becoming_active = (new_status == 'active' and instance.status != 'active')

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if skus_data is not None:
            instance.skus.all().delete()
            for sku_data in skus_data:
                SKU.objects.create(product=instance, **sku_data)

        # Sync method bridges only if any method-related field was explicitly provided.
        # Explicit empty list clears all bridges; omitting all fields preserves existing.
        if method_ids is not None or research_goal_ids is not None or application_ids is not None:
            merged = self._merge_method_ids(method_ids, research_goal_ids, application_ids)
            self._sync_method_bridges(instance, list(merged))
        self._sync_protocol_bridges(instance, protocol_ids)

        # Auto-generate SEO when transitioning from draft to active
        if is_becoming_active:
            self._auto_seo_on_publish(instance)
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
    structure_svg = serializers.SerializerMethodField()
    is_complete = serializers.SerializerMethodField()
    incomplete_items = serializers.SerializerMethodField()

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
            'is_complete', 'incomplete_items',
        ]

    def get_product_class_name(self, obj):
        if obj.product_class:
            return obj.product_class.name
        return None

    def get_structure_svg(self, obj):
        """Sanitize SVG before output to prevent XSS."""
        return sanitize_svg(obj.structure_svg) if obj.structure_svg else None

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

    def get_is_complete(self, obj):
        return _is_product_complete(obj)

    def get_incomplete_items(self, obj):
        return _incomplete_items(obj)
