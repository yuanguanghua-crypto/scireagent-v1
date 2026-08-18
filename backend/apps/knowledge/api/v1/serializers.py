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
    slug = serializers.SlugField(required=False, allow_blank=True, allow_null=True)
    # #494 route B：协议↔方法改走 MethodProtocol 桥（多对多）。
    # methods 仅作写入字段（创建/编辑时建桥），不进列表响应。
    methods = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Method.objects.all(), required=False, write_only=True,
    )

    class Meta:
        model = Protocol
        fields = ['id', 'name', 'slug', 'version', 'status', 'methods', 'created_at']
        # unique_together(method, slug, version) is still enforced at DB level on save;
        # slug is auto-generated (globally unique) by Protocol.save(), so the auto
        # UniqueTogetherValidator must not require slug/version to be supplied on create.
        validators = []

    def create(self, validated_data):
        methods = validated_data.pop('methods', [])
        protocol = Protocol.objects.create(**validated_data)
        for m in methods:
            MethodProtocol.objects.update_or_create(
                method=m, protocol=protocol,
                defaults={'explicit': True, 'status': 'active'},
            )
        return protocol

    def update(self, instance, validated_data):
        methods = validated_data.pop('methods', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if methods is not None:
            # 仅刷新「显式（explicit）」桥：删除不再勾选的、补建新增的，
            # 不触动非显式桥（如服务层 / AI 派生）。
            existing = set(
                MethodProtocol.objects.filter(protocol=instance, explicit=True)
                .values_list('method_id', flat=True)
            )
            wanted = {m.id for m in methods}
            to_remove = existing - wanted
            if to_remove:
                MethodProtocol.objects.filter(
                    protocol=instance, explicit=True, method_id__in=to_remove
                ).delete()
            for m in methods:
                MethodProtocol.objects.update_or_create(
                    method=m, protocol=instance,
                    defaults={'explicit': True, 'status': 'active'},
                )
        return instance


class ProtocolDetailSerializer(BaseModelSerializer):
    steps = ProtocolStepSerializer(many=True, read_only=True)
    references = serializers.SerializerMethodField()
    products = serializers.SerializerMethodField()
    facets = serializers.SerializerMethodField()
    methods = serializers.SerializerMethodField()

    class Meta:
        model = Protocol
        fields = [
            'id', 'name', 'slug', 'version', 'objective', 'principle',
            'materials', 'reagents', 'equipment', 'troubleshooting', 'expected_results',
            'status', 'steps', 'references', 'products', 'facets', 'methods', 'created_at', 'updated_at',
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
        from apps.bridges.models import ProductMethod, MethodProtocol
        from apps.commerce.models import Product
        method_ids = MethodProtocol.objects.filter(protocol=obj).values_list('method_id', flat=True)
        product_ids = ProductMethod.objects.filter(method_id__in=list(method_ids)).values_list('product_id', flat=True).distinct()
        return list(Product.objects.filter(id__in=product_ids).values('id', 'name', 'slug', 'catalog_no'))

    def get_methods(self, obj):
        """#494 route B：协议关联方法经 MethodProtocol 桥多对多返回（只读）。

        形如 [{id, name, slug}]，供前端上游实体 / 研究路径 / 「关联方法」渲染与跳转。
        仅含 active 桥；按 display_order 与 method_id 稳定排序。
        """
        from apps.bridges.models import MethodProtocol
        rows = (
            MethodProtocol.objects.filter(protocol=obj, status='active')
            .select_related('method')
            .order_by('display_order', 'method_id')
        )
        return [
            {'id': mp.method_id, 'name': mp.method.name, 'slug': mp.method.slug}
            for mp in rows
        ]


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
        return list(Protocol.objects.filter(method_protocols__method=obj).values('id', 'name', 'slug', 'version'))

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
