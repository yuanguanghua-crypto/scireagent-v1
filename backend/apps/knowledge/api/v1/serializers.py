from rest_framework import serializers
from django.db import models
from core.serializers import BaseModelSerializer
from apps.knowledge.models import (
    ResearchGoal, Application, Method, Protocol, ProtocolStep, Reference, Compatibility
)


class ResearchGoalListSerializer(BaseModelSerializer):
    slug = serializers.SlugField(required=False, allow_blank=True, allow_null=True)
    # #495-D：列表契约修复——真实关联 Application 计数（原前端用死字段 application_count）。
    # #P0-1：计数改走 M2M application_collection（T4 顶部链真实关联路径），不再数 FK research_goal 反向。
    application_count = serializers.SerializerMethodField()

    class Meta:
        model = ResearchGoal
        fields = ['id', 'name', 'slug', 'summary', 'priority', 'status', 'application_count', 'created_at']

    def get_application_count(self, obj):
        return obj.application_collection.count()


class ResearchGoalProtocolsField(serializers.PrimaryKeyRelatedField):
    """#495 轻量版：策展协议集读=对象 / 写=ID 列表。

    ResearchGoal.protocols 是普通 M2M（无 through），DRF 原生 .set() 即持久化，
    无需 Service 层。字段名与模型属性同名(protocols)，create/update 自动处理 M2M。
    读取时每个 Protocol 返回 {id, name, slug} 供前端直接渲染与跳转。
    """

    def to_representation(self, value):
        return {'id': value.id, 'name': value.name, 'slug': value.slug}


class ResearchGoalDetailSerializer(BaseModelSerializer):
    protocols = ResearchGoalProtocolsField(
        many=True, queryset=Protocol.objects.all(), required=False,
    )
    # #P0-1：RG 详情暴露 M2M 技术族集合（T4 顶部链真实关联，多值语义）。
    application_collection = serializers.SerializerMethodField()

    class Meta:
        model = ResearchGoal
        fields = [
            'id', 'name', 'slug', 'summary', 'priority', 'status',
            'created_at', 'updated_at', 'protocols', 'application_collection',
        ]

    def get_application_collection(self, obj):
        return list(obj.application_collection.all().values('id', 'name', 'slug'))


# 哨兵：区分「字段未提交」与「提交为 None」
_NOT_PROVIDED = object()


class ResearchGoalThroughM2MField(serializers.Field):
    """#P0-1：RG↔AP 关联读 M2M、写 FK+同步 M2M 的自定义字段。

    读：取 Application.research_goal_collections（M2M 反向）中 id 最小的 ResearchGoal；
    写：接收 research_goal_id 整数，落 FK research_goal，并在 serializer 的
    create/update 中同步 M2M application_collection（决策 B1：仅显式变更才动 M2M）。
    """

    default_error_messages = {
        'invalid_id': 'research_goal_id 必须是整数。',
    }

    def get_attribute(self, instance):
        # DRF 默认按 source 取 instance.research_goal_id（int），会把 int 传给
        # to_representation。此处返回 Application 实例本身，让读路径从 M2M 反向
        # research_goal_collections 取 id 最小的 ResearchGoal（id 升序稳定）。
        return instance

    def to_representation(self, value):
        # 读路径：value 为 Application 实例，取 M2M 首个 RG（依赖 prefetch 已按 id 排序）
        first = value.research_goal_collections.all().first()
        return first.id if first else None

    def to_internal_value(self, data):
        if data in (None, ''):
            return None
        try:
            return int(data)
        except (TypeError, ValueError):
            self.fail('invalid_id')
        return data

    def validate_empty_values(self, data):
        if data is None:
            return (True, None)
        return super().validate_empty_values(data)


class ApplicationGoalSyncMixin:
    """#P0-1 决策 B1：RG↔AP 写路径（FK research_goal + 同步 M2M application_collection）公共逻辑。

    List 与 Detail 两个 serializer 共用，避免重复：
    - research_goal_id 读 = M2M 首个 RG id（id 升序稳定）；写 = FK research_goal + 同步 M2M。
    - create：显式提供 research_goal_id → FK 写入 + M2M add（新实体无历史多值）。
    - update：仅当该字段被显式提交且值**变化**时才同步 M2M——
      新值非空 → application_collection.set([rg])（用户显式改归属=覆盖合理）；
      新值为 None → FK 置空 + 从 M2M remove(旧 rg)（保留其它 T4 关联）。
      未提交或值未变 → 不动 M2M（编辑其他字段绝不破坏 T4 多值关联）。
    """

    def get_fields(self):
        """DRF 元类只从各 serializer 类体收集 declared field，mixin 中的字段
        research_goal_id 不会进入 _declared_fields；这里显式注入，
        避免 ModelSerializer 按 FK research_goal 自动构建只读 ReadOnlyField。"""
        fields = super().get_fields()
        fields['research_goal_id'] = ResearchGoalThroughM2MField(
            required=False, allow_null=True,
        )
        return fields

    def get_research_goal_name(self, obj):
        first = obj.research_goal_collections.all().first()
        return first.name if first else None

    def get_research_goals(self, obj):
        return [
            {'id': rg.id, 'name': rg.name}
            for rg in obj.research_goal_collections.all()
        ]

    def create(self, validated_data):
        rg_id = validated_data.pop('research_goal_id', None)
        instance = Application.objects.create(**validated_data)
        if rg_id is not None:
            rg = self._resolve_rg(rg_id)
            instance.research_goal = rg
            instance.research_goal_collections.add(rg)  # M2M 反向同步（正向在 ResearchGoal 侧）
            instance.save(update_fields=['research_goal'])
        return instance

    def update(self, instance, validated_data):
        rg_id = validated_data.pop('research_goal_id', _NOT_PROVIDED)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if rg_id is not _NOT_PROVIDED:
            old_fk_id = instance.research_goal_id
            if rg_id is None:
                # 用户显式清空：FK 置空 + M2M 移除该 RG（保留其它 T4 关联）
                if old_fk_id is not None:
                    old_rg = ResearchGoal.objects.filter(pk=old_fk_id).first()
                    if old_rg is not None:
                        instance.research_goal_collections.remove(old_rg)
                instance.research_goal = None
                instance.save(update_fields=['research_goal'])
            elif rg_id != old_fk_id:
                # 用户显式改归属：FK 更新 + M2M set 为新值（覆盖合理）
                rg = self._resolve_rg(rg_id)
                instance.research_goal = rg
                instance.research_goal_collections.set([rg])
                instance.save(update_fields=['research_goal'])
        return instance

    @staticmethod
    def _resolve_rg(rg_id):
        try:
            return ResearchGoal.objects.get(pk=rg_id)
        except ResearchGoal.DoesNotExist:
            raise serializers.ValidationError({'research_goal_id': '无效 research_goal_id。'})


class ApplicationListSerializer(ApplicationGoalSyncMixin, BaseModelSerializer):
    slug = serializers.SlugField(required=False, allow_blank=True, allow_null=True)
    # #P0-1：RG↔AP 关联改走 M2M（T4 顶部链真实路径）。读 = M2M 首个 RG id（id 升序稳定）；
    # 写 = FK research_goal + 同步 M2M（决策 B1，实现在 ApplicationGoalSyncMixin）。
    research_goal_name = serializers.SerializerMethodField()
    research_goals = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = ['id', 'name', 'slug', 'summary', 'sort_order', 'status',
                  'research_goal_id', 'research_goal_name', 'research_goals', 'created_at']


class ApplicationDetailSerializer(ApplicationGoalSyncMixin, BaseModelSerializer):
    methods = serializers.SerializerMethodField()
    protocols = serializers.SerializerMethodField()
    products = serializers.SerializerMethodField()
    # #P0-1：读 M2M（同 ApplicationListSerializer），写路径 B1 同步实现在 ApplicationGoalSyncMixin。
    research_goal_name = serializers.SerializerMethodField()
    research_goals = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = ['id', 'name', 'slug', 'summary', 'sort_order', 'status',
                  'research_goal_id', 'research_goal_name', 'research_goals',
                  'methods', 'protocols', 'products', 'created_at', 'updated_at']

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
        return list(Product.objects.filter(id__in=product_ids, status=Product.Status.ACTIVE.value).values('id', 'name', 'slug', 'catalog_no'))


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
        return list(Product.objects.filter(id__in=product_ids, status=Product.Status.ACTIVE.value).values('id', 'name', 'slug', 'catalog_no'))

    def get_methods(self, obj):
        """#494 route B：协议关联方法经 MethodProtocol 桥多对多返回（只读）。

        形如 [{id, name, slug, application_id, application_name,
               research_goal_id, research_goal_name, research_goals}]，供前端研究路径
        （RG→AP→Method→Protocol）单一代表分支上溯渲染与跳转。
        #P0-1：research_goal 上溯改走 M2M（research_goal_collections），
        保留 research_goal_id/research_goal_name 单值契约（取 id 最小者），
        新增 research_goals 多值数组。仅含 active 桥；按 display_order 与 method_id 稳定排序。
        """
        from django.db.models import Prefetch
        from apps.bridges.models import MethodProtocol
        from apps.knowledge.models import ResearchGoal
        rows = (
            MethodProtocol.objects.filter(protocol=obj, status='active')
            .select_related('method__application')
            .prefetch_related(
                Prefetch(
                    'method__application__research_goal_collections',
                    queryset=ResearchGoal.objects.order_by('id'),
                )
            )
            .order_by('display_order', 'method_id')
        )
        out = []
        for mp in rows:
            application = mp.method.application
            if application is None:
                out.append({
                    'id': mp.method_id,
                    'name': mp.method.name,
                    'slug': mp.method.slug,
                    'application_id': None,
                    'application_name': None,
                    'research_goal_id': None,
                    'research_goal_name': None,
                    'research_goals': [],
                })
                continue
            rgs = list(application.research_goal_collections.all())
            first = rgs[0] if rgs else None
            out.append({
                'id': mp.method_id,
                'name': mp.method.name,
                'slug': mp.method.slug,
                'application_id': application.id,
                'application_name': application.name,
                'research_goal_id': first.id if first else None,
                'research_goal_name': first.name if first else None,
                'research_goals': [{'id': rg.id, 'name': rg.name} for rg in rgs],
            })
        return out


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
        return list(Product.objects.filter(id__in=product_ids, status=Product.Status.ACTIVE.value).values('id', 'name', 'slug', 'catalog_no'))


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
