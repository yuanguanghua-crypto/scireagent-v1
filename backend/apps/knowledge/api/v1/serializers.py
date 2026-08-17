from rest_framework import serializers
from django.db import models
from core.serializers import BaseModelSerializer
from apps.knowledge.models import (
    ResearchGoal, Application, Method, Protocol, ProtocolStep, Reference, Compatibility
)


class ResearchGoalListSerializer(BaseModelSerializer):
    slug = serializers.SlugField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = ResearchGoal
        fields = ['id', 'name', 'slug', 'summary', 'priority', 'status', 'created_at']


class ApplicationListSerializer(BaseModelSerializer):
    research_goal_id = serializers.PrimaryKeyRelatedField(
        source='research_goal', queryset=ResearchGoal.objects.all(),
        required=False, allow_null=True,
    )
    slug = serializers.SlugField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Application
        fields = ['id', 'name', 'slug', 'summary', 'sort_order', 'status', 'research_goal_id', 'created_at']


class ApplicationDetailSerializer(BaseModelSerializer):
    methods = serializers.SerializerMethodField()
    protocols = serializers.SerializerMethodField()
    products = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = ['id', 'name', 'slug', 'summary', 'sort_order', 'status', 'research_goal_id', 'methods', 'protocols', 'products', 'created_at', 'updated_at']

    def get_methods(self, obj):
        return list(obj.methods.values('id', 'name', 'slug'))

    def get_protocols(self, obj):
        from apps.bridges.models import MethodProtocol
        method_ids = list(obj.methods.values_list('id', flat=True))
        protocol_ids = MethodProtocol.objects.filter(method_id__in=method_ids).values_list('protocol_id', flat=True).distinct()
        return list(Protocol.objects.filter(id__in=protocol_ids).values('id', 'name', 'slug'))

    def get_products(self, obj):
        from apps.bridges.models import ProductMethod
        from apps.commerce.models import Product
        method_ids = list(obj.methods.values_list('id', flat=True))
        product_ids = ProductMethod.objects.filter(method_id__in=method_ids).values_list('product_id', flat=True).distinct()
        return list(Product.objects.filter(id__in=product_ids).values('id', 'name', 'slug', 'catalog_no'))


class ProtocolStepSerializer(BaseModelSerializer):
    class Meta:
        model = ProtocolStep
        fields = ['id', 'step_no', 'title', 'body', 'duration_seconds', 'warnings', 'required_materials']


class ProtocolListSerializer(BaseModelSerializer):
    method_id = serializers.PrimaryKeyRelatedField(
        source='method', queryset=Method.objects.all(),
        required=False, allow_null=True,
    )
    slug = serializers.SlugField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Protocol
        fields = ['id', 'name', 'slug', 'version', 'method_id', 'status', 'created_at']
        # unique_together(method, slug, version) is still enforced at DB level on save;
        # slug is auto-generated (globally unique) by Protocol.save(), so the auto
        # UniqueTogetherValidator must not require slug/version to be supplied on create.
        validators = []


class ProtocolDetailSerializer(BaseModelSerializer):
    steps = ProtocolStepSerializer(many=True, read_only=True)
    references = serializers.SerializerMethodField()
    products = serializers.SerializerMethodField()
    facets = serializers.SerializerMethodField()

    class Meta:
        model = Protocol
        fields = [
            'id', 'name', 'slug', 'version', 'method_id', 'objective', 'principle',
            'materials', 'reagents', 'equipment', 'troubleshooting', 'expected_results',
            'status', 'steps', 'references', 'products', 'facets', 'created_at', 'updated_at',
        ]

    def get_facets(self, obj):
        """route B 加法（范围 A）：按 facet_type 分组返回该协议的受控词表标签。

        仅返回非空组；每条含 id/facet_type/kind/value（按用户决策不暴露 source）。
        一次查询经 protocol_facets.select_related('facet')，无 N+1。
        """
        grouped = {}
        pf_qs = obj.protocol_facets.select_related('facet').order_by(
            'facet__facet_type', 'facet__kind', 'facet__value'
        )
        for pf in pf_qs:
            fv = pf.facet
            grouped.setdefault(fv.facet_type, []).append({
                'id': fv.id,
                'facet_type': fv.facet_type,
                'kind': fv.kind,
                'value': fv.value,
            })
        return grouped

    def get_references(self, obj):
        """从 Protocol.references 文本字段派生 references"""
        if not obj.references:
            return []
        import re
        from apps.knowledge.models import Reference
        dois = re.findall(r'doi:\s*(10\.\S+)', obj.references, re.IGNORECASE)
        pmids = re.findall(r'PMID:?\s*(\d+)', obj.references, re.IGNORECASE)
        q = models.Q()
        if dois:
            q |= models.Q(doi__in=dois)
        if pmids:
            q |= models.Q(pmid__in=pmids)
        if not q:
            return []
        return list(Reference.objects.filter(q).values('id', 'title', 'journal', 'year', 'doi'))

    def get_products(self, obj):
        from apps.bridges.models import ProductMethod
        from apps.commerce.models import Product
        product_ids = ProductMethod.objects.filter(method=obj.method).values_list('product_id', flat=True).distinct()
        return list(Product.objects.filter(id__in=product_ids).values('id', 'name', 'slug', 'catalog_no'))


class MethodListSerializer(BaseModelSerializer):
    application_id = serializers.PrimaryKeyRelatedField(
        source='application', queryset=Application.objects.all(),
        required=False, allow_null=True,
    )
    slug = serializers.SlugField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = Method
        fields = ['id', 'name', 'slug', 'summary', 'application_id', 'cost_band', 'timeline', 'status', 'created_at']


class MethodDetailSerializer(BaseModelSerializer):
    protocols = serializers.SerializerMethodField()
    products = serializers.SerializerMethodField()

    class Meta:
        model = Method
        fields = [
            'id', 'name', 'slug', 'summary', 'purpose', 'advantages', 'limitations',
            'cost_band', 'timeline', 'status', 'application_id',
            'protocols', 'products', 'created_at', 'updated_at',
        ]

    def get_protocols(self, obj):
        return list(obj.protocols.values('id', 'name', 'slug', 'version'))

    def get_products(self, obj):
        from apps.bridges.models import ProductMethod
        from apps.commerce.models import Product
        product_ids = ProductMethod.objects.filter(method=obj).values_list('product_id', flat=True).distinct()
        return list(Product.objects.filter(id__in=product_ids).values('id', 'name', 'slug', 'catalog_no'))


class ReferenceSerializer(BaseModelSerializer):
    class Meta:
        model = Reference
        fields = [
            'id', 'title', 'authors', 'journal', 'year', 'doi', 'pmid',
            'url', 'citation_text', 'source_type', 'created_at',
        ]


class CompatibilitySerializer(BaseModelSerializer):
    class Meta:
        model = Compatibility
        fields = [
            'id', 'code', 'scope', 'rule_type', 'severity',
            'expression_json', 'summary', 'status', 'created_at',
        ]
