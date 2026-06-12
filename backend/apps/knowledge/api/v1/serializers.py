from rest_framework import serializers
from core.serializers import BaseModelSerializer
from apps.knowledge.models import (
    ResearchGoal, Application, Method, Protocol, ProtocolStep, Reference, Compatibility
)


class ResearchGoalListSerializer(BaseModelSerializer):
    class Meta:
        model = ResearchGoal
        fields = ['id', 'name', 'slug', 'summary', 'priority', 'status', 'created_at']


class ApplicationListSerializer(BaseModelSerializer):
    research_goal_id = serializers.IntegerField(source='research_goal.id', read_only=True)

    class Meta:
        model = Application
        fields = ['id', 'name', 'slug', 'summary', 'sort_order', 'status', 'research_goal_id', 'created_at']


class ApplicationDetailSerializer(BaseModelSerializer):
    method_ids = serializers.SerializerMethodField()
    protocol_ids = serializers.SerializerMethodField()
    product_ids = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = ['id', 'name', 'slug', 'summary', 'sort_order', 'status', 'research_goal_id', 'method_ids', 'protocol_ids', 'product_ids', 'created_at', 'updated_at']

    def get_method_ids(self, obj):
        return list(obj.methods.values_list('id', flat=True))

    def get_protocol_ids(self, obj):
        from apps.bridges.models import MethodProtocol
        method_ids = list(obj.methods.values_list('id', flat=True))
        return list(MethodProtocol.objects.filter(method_id__in=method_ids).values_list('protocol_id', flat=True).distinct())

    def get_product_ids(self, obj):
        from apps.bridges.models import ProductMethod
        method_ids = list(obj.methods.values_list('id', flat=True))
        return list(ProductMethod.objects.filter(method_id__in=method_ids).values_list('product_id', flat=True).distinct())


class ProtocolStepSerializer(BaseModelSerializer):
    class Meta:
        model = ProtocolStep
        fields = ['id', 'step_no', 'title', 'body', 'duration_seconds', 'warnings', 'required_materials']


class ProtocolListSerializer(BaseModelSerializer):
    class Meta:
        model = Protocol
        fields = ['id', 'name', 'slug', 'version', 'method_id', 'status', 'created_at']


class ProtocolDetailSerializer(BaseModelSerializer):
    steps = ProtocolStepSerializer(many=True, read_only=True)
    reference_ids = serializers.SerializerMethodField()
    product_ids = serializers.SerializerMethodField()

    class Meta:
        model = Protocol
        fields = [
            'id', 'name', 'slug', 'version', 'method_id', 'objective', 'principle',
            'materials', 'reagents', 'equipment', 'troubleshooting', 'expected_results',
            'status', 'steps', 'reference_ids', 'product_ids', 'created_at', 'updated_at',
        ]

    def get_reference_ids(self, obj):
        """从 Protocol.references 文本字段派生 reference_ids"""
        if not obj.references:
            return []
        import re
        from apps.knowledge.models import Reference
        # 提取 DOI 和 PMID
        dois = re.findall(r'doi:\s*(10\.\S+)', obj.references, re.IGNORECASE)
        pmids = re.findall(r'PMID:?\s*(\d+)', obj.references, re.IGNORECASE)
        ref_ids = []
        if dois:
            refs = Reference.objects.filter(doi__in=dois).values_list('id', flat=True)
            ref_ids.extend(refs)
        if pmids:
            refs = Reference.objects.filter(pmid__in=pmids).values_list('id', flat=True)
            ref_ids.extend(refs)
        return list(set(ref_ids))

    def get_product_ids(self, obj):
        from apps.bridges.models import ProductMethod
        return list(ProductMethod.objects.filter(method=obj.method).values_list('product_id', flat=True).distinct())


class MethodListSerializer(BaseModelSerializer):
    class Meta:
        model = Method
        fields = ['id', 'name', 'slug', 'summary', 'application_id', 'cost_band', 'timeline', 'status', 'created_at']


class MethodDetailSerializer(BaseModelSerializer):
    protocol_ids = serializers.SerializerMethodField()
    product_ids = serializers.SerializerMethodField()

    class Meta:
        model = Method
        fields = [
            'id', 'name', 'slug', 'summary', 'purpose', 'advantages', 'limitations',
            'cost_band', 'timeline', 'status', 'application_id',
            'protocol_ids', 'product_ids', 'created_at', 'updated_at',
        ]

    def get_protocol_ids(self, obj):
        return list(obj.protocols.values_list('id', flat=True))

    def get_product_ids(self, obj):
        from apps.bridges.models import ProductMethod
        return list(ProductMethod.objects.filter(method=obj).values_list('product_id', flat=True).distinct())


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
