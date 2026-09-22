from django.db import IntegrityError, transaction
from rest_framework import serializers, status
from rest_framework.exceptions import APIException, ValidationError
from core.serializers import BaseModelSerializer
from core.svg_sanitizer import sanitize_svg
from apps.commerce.models import Product, SKU, ProductClass, CatalogGroup, ProductDocument
from apps.knowledge.models import Method, Protocol
from apps.commerce.services.commerce_service import CommerceService


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
        fields = ['id', 'sku_code', 'pack_size', 'price', 'currency', 'inventory_status',
                  'concentration', 'lead_time', 'is_default']
        # 移除 sku_code 自动生成的 UniqueValidator：
        # 嵌套写入时 is_valid() 在 update() 之前运行 UniqueValidator，旧 SKU 仍在库中，
        # 草稿保存→发布（sku_code 不变）会被判为 unique 冲突。唯一性由业务保证。
        extra_kwargs = {
            # id 可写但非必填：保存时带上既有 SKU 的 id 即可原地更新，
            # 避免 update() 删光重建（否则 SKU id 变化会级联删 Batch/Coa）。
            'id': {'required': False, 'read_only': False},
            'sku_code': {'validators': []},
        }


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
    4. product_class_id 不为空（分类权威）
    5. 至少 1 个 SKU 且 is_default=True
    """
    if not (product.name and product.catalog_no):
        return False
    if not product.cas:
        return False
    if not product.smiles:
        return False
    if not product.product_class_id:
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
    if not product.product_class_id:
        items.append('分类 (product_class)')
    if not product.skus.filter(is_default=True).exists():
        items.append('默认 SKU')
    return items


class ProductListSerializer(BaseModelSerializer):
    sku_summary = serializers.SerializerMethodField()
    product_class_name = serializers.SerializerMethodField()
    is_complete = serializers.SerializerMethodField()
    incomplete_items = serializers.SerializerMethodField()
    sds_published = serializers.SerializerMethodField()
    coa_published_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'catalog_no', 'cas', 'smiles', 'synonyms', 'inchi',
            'formula', 'molecular_weight', 'purity', 'concentration', 'storage',
            'shipping', 'lead_time', 'status', 'archived', 'research_use_only',
            'product_class_id', 'product_class_name', 'category_l1', 'category_l2',
            'sku_summary', 'created_at', 'updated_at', 'is_complete', 'incomplete_items',
            'sds_published', 'coa_published_count', 'aggregate_relevance_score',
            'substructure_tags',
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

    def get_sds_published(self, obj):
        """SDS 是否已发布 — 通过 Product.current_sds 外键指针判断。"""
        return obj.current_sds_id is not None

    def get_coa_published_count(self, obj):
        """已发布 COA 的批次数（status='published'）。"""
        from apps.documents.models import Coa
        return Coa.objects.filter(
            batch__sku__product=obj, status=Coa.Status.PUBLISHED
        ).count()


class ProductNumberConflict(APIException):
    """货号 / slug 与已存在记录（**含回收站行**）冲突 → 409。

    语义：**货号是产品的永久身份**（印在瓶签 / COA / SDS / 订单 / 文献引用上），
    归档（archived=True）**不释放编号**。命中回收站行时**不再静默复活**
    （旧行为会覆盖旧数据且不产生 CREATE 审计），而是明确告知三条出路：
    恢复（restore）/ 改用新编号 / 先 hard-delete 再重来。
    """
    status_code = status.HTTP_409_CONFLICT
    default_detail = '产品编号冲突'
    default_code = 'product_number_conflict'


class ProductHasDependents(APIException):
    """被 `PROTECT` 关联挡住、无法物理删除 → **409**（附带可操作出路）。

    ★ 2026-09-22 修 B1：`hard_delete` 此前**未捕获 `ProtectedError`** ⇒ 被
    `ProductReagentClass.product`（`apps/bridges/models.py:420`，`on_delete=PROTECT`）挡住时
    返回 **500**（DEBUG 下还吐 38KB 堆栈页）。更糟的是 B′ 的 409 文案恰好让用户
    "先对旧记录 hard-delete" ⇒ **走进死路**。本异常把该情形变成**可操作的 409**。
    """
    status_code = status.HTTP_409_CONFLICT
    default_detail = '产品存在受保护的关联数据'
    default_code = 'product_has_dependents'

    def __init__(self, blocked):
        types = '、'.join(blocked) if blocked else '未知关联'
        super().__init__(
            f'该产品被关联数据保护，不能物理删除（{types}）。'
            '① 只想下架 → 用软归档（DELETE /products/{id}/）；'
            '② 确实要物理删除 → 先解除上述关联；'
            '③ 编号本就永久保留，无需为了释放编号而硬删。'
        )


class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    skus = SKUCreateSerializer(many=True, required=False)
    # 显式声明 product_class_id 为可写：ModelSerializer 会把 FK 的 _id 字段默认设为只读，
    # 导致前端传入的 product_class_id 被丢弃（validated_data 中缺失），分类永远落不进库。
    product_class_id = serializers.IntegerField(required=False, allow_null=True)
    # Knowledge relationship fields (write-only, optional)
    method_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=None)
    protocol_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=None)
    research_goal_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=None)
    application_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=None)

    # ── 编号唯一性口径：货号 / slug 均为「全表永久唯一」（回收站行照常占位）────────
    # 语义：**货号是产品的永久身份**（印在瓶签 / COA / SDS / 订单 / 文献引用上），
    # 归档（archived=True）**不释放编号** —— 否则同一货号会指向另一个分子，
    # 客户手里的 SC8001 与它的 COA 对不上。真实网站绝不允许。
    #
    # 旧实现把 catalog_no 放宽成 filter(archived=False)，使 app 层口径 ≠ DB 层列级
    # UNIQUE，只能靠 create() 的「静默复活分支」掩盖 —— 代价是无 CREATE 审计 +
    # 旧数据被静默覆盖。现改为与 DB 同口径，并统一由 validate() 给出可操作的 409。
    #
    # 两字段都显式声明且 validators=[]：唯一性判定收归 validate() 一处，
    # 避免 DRF 自动 UniqueValidator 先抛出不可操作的 400；DB 列级 UNIQUE 仍作最后兜底。
    slug = serializers.SlugField(max_length=255, validators=[])
    catalog_no = serializers.CharField(
        max_length=64, required=False, allow_null=True, allow_blank=True, validators=[],
    )

    class Meta:
        model = Product
        fields = [
            'id',
            'name', 'slug', 'catalog_no', 'cas', 'smiles', 'synonyms', 'inchi',
            'formula', 'molecular_weight', 'purity', 'concentration', 'storage',
            'shipping', 'lead_time', 'handling_notes', 'shelf_life', 'research_use_only',
            'overview', 'structure_svg', 'structure_image', 'seo_title', 'seo_description',
            'status', 'product_class_id',
            'skus', 'method_ids', 'protocol_ids', 'research_goal_ids', 'application_ids',
        ]
        read_only_fields = ['id']

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
        """Sync MethodProtocol bridges via product's methods.

        修正「派生冗余 bug」：原实现为 method_ids × protocol_ids 笛卡尔积，
        会把「本仅属某方法的协议」额外挂到产品的所有方法上，向共享的
        MethodProtocol 表注入虚假交叉链路，污染其他产品的派生协议集
        （这正是编辑页协议铺满 19~26 条泛化协议的放大器）。

        新语义：仅保证每个给定协议经产品的【至少一个】方法可达；
        已可达则 no-op（绝不向其他方法扇出），不可达才锚定到单一方法，
        避免笛卡尔交叉污染。
        """
        from apps.bridges.models import MethodProtocol, ProductMethod
        if protocol_ids is None:
            return
        # Get product's method IDs
        method_ids = list(ProductMethod.objects.filter(product=product).values_list('method_id', flat=True))
        if not method_ids:
            return
        # 已存在的 (method, protocol) 链接，限定在产品自身的 methods 范围内
        existing = set(
            MethodProtocol.objects.filter(
                method_id__in=method_ids, protocol_id__in=protocol_ids
            ).values_list('method_id', 'protocol_id')
        )
        for pid in protocol_ids:
            if not Protocol.objects.filter(id=pid).exists():
                continue
            # 已通过产品的某个方法可达 → 不扇出、不重复创建
            if any((mid, pid) in existing for mid in method_ids):
                continue
            # 不可达：锚定到单一方法使其可达，避免笛卡尔交叉污染
            MethodProtocol.objects.get_or_create(method_id=method_ids[0], protocol_id=pid)

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

    # 编号字段的中文标签（错误消息用）
    _NUMBER_FIELD_LABELS = {'catalog_no': '货号', 'slug': 'slug'}

    def validate(self, attrs):
        """唯一性口径 = **全表**（含回收站行），与 DB 列级 UNIQUE 一致。

        - 命中**回收站行** → 409 + 可操作出路（restore / 换编号 / hard-delete 重来）
        - 命中**未被软删的行** → 400（真重复）
        - 更新时自身编号未改动 → 不误报
        """
        attrs = super().validate(attrs)
        instance = self.instance
        for field in ('catalog_no', 'slug'):
            if field not in attrs:
                continue                      # 本次未提交该字段 → 不校验
            value = attrs.get(field)
            if value in (None, ''):
                continue                      # 空值不参与唯一性判定
            if instance is not None and getattr(instance, field) == value:
                continue                      # 与自身相同 → 不是冲突
            qs = Product.objects.filter(**{field: value})
            if instance is not None:
                qs = qs.exclude(pk=instance.pk)
            hit = qs.first()
            if hit is None:
                continue
            label = self._NUMBER_FIELD_LABELS[field]
            if hit.archived:
                raise ProductNumberConflict(
                    f'{label}「{value}」已存在（在回收站中，product id={hit.id}）。'
                    f'货号是产品的永久身份，归档不会释放编号：'
                    f'① 要重新上架它 → POST /api/v1/products/{hit.id}/restore/；'
                    f'② 这是另一个产品 → 请改用新的{label}；'
                    f'③ 只想重来一次 → 先对旧记录 hard-delete（仅超管）。'
                )
            raise ValidationError(
                {field: f'{label}「{value}」已被现有产品占用（product id={hit.id}）。'})
        return attrs

    def create(self, validated_data):
        method_ids = validated_data.pop('method_ids', None)
        protocol_ids = validated_data.pop('protocol_ids', None)
        research_goal_ids = validated_data.pop('research_goal_ids', None)
        application_ids = validated_data.pop('application_ids', None)
        skus_data = validated_data.pop('skus', [])

        # 编号冲突已在 validate() 阶段以 409 / 400 返回（全表口径，含回收站行），
        # 故此处**不再**做"命中归档行就静默复活并覆盖"—— 那会绕过 CREATE 审计、
        # 静默改写旧行数据。保留 DB 列级 UNIQUE 的竞态兜底：并发写入不该以 500 收场。
        # ★ 2026-09-22 修 **B6**：原先 `SKU.objects.create` 落在 `try` **之外**、且整段**无事务**
        #   ⇒ 重复 `sku_code` 抛 `IntegrityError` 变成 **500**，而刚建的**产品行已落库**
        #   却没有任何 SKU（**非原子**，实测留下"0-SKU 产品行"）。
        #   现在两步同处一个 `transaction.atomic()`，并把 IntegrityError **按字段归属**分流：
        #     · 命中 `sku_code` ⇒ **400**（嵌套字段值非法。`SKUCreateSerializer` 刻意移除了
        #       UniqueValidator 以兼容"草稿→发布 sku_code 不变"，故冲突只可能在**写入时**暴露）
        #     · 其它（货号 / slug 并发竞态）⇒ 沿用 **409** `ProductNumberConflict`
        try:
            with transaction.atomic():
                product = Product.objects.create(**validated_data)
                for sku_data in skus_data:
                    SKU.objects.create(
                        product=product, **{k: v for k, v in sku_data.items() if k != 'id'})
        except IntegrityError as exc:
            if 'sku_code' in str(exc):
                raise ValidationError(
                    {'skus': ['SKU 编号已存在，请改用新的 sku_code。']}
                ) from exc
            raise ProductNumberConflict(
                '编号冲突（并发写入）：货号或 slug 已被占用。请重试，或改用新的编号。'
            ) from exc

        # Sync method bridges only if any method-related field was explicitly provided.
        # Explicit empty list clears all bridges; omitting all fields preserves existing.
        if method_ids is not None or research_goal_ids is not None or application_ids is not None:
            merged = self._merge_method_ids(method_ids, research_goal_ids, application_ids)
            self._sync_method_bridges(product, list(merged))
        self._sync_protocol_bridges(product, protocol_ids)

        # 刷新继承链：清孤儿 INHERITED 行并重算当前方法链派生（#一致性修复）
        self._refresh_inherited_bridges(product)

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
        try:
            instance.save()
        except IntegrityError as exc:
            raise ProductNumberConflict(
                '编号冲突（并发写入）：货号或 slug 已被占用。请重试，或改用新的编号。'
            ) from exc

        if skus_data is not None:
            # 增量同步：保留既有 SKU（避免删光重建导致 SKU id 变化、Batch/Coa 级联丢失，
            # 修复 COA 报 "SKU does not exist"）。
            # 匹配优先级：payload 带 id → 按 id 原地更新（前端保存走此路径，SKU id 稳定）；
            # 否则按 sku_code 兜底匹配（纯 API/测试不带 id 时仍避免 unique 冲突）。
            # 仅当 skus 在 payload 中才处理；缺失 skus 键则保留现有 SKU 不动。
            existing_by_id = {sku.id: sku for sku in instance.skus.all()}
            existing_by_code = {}
            for sku in existing_by_id.values():
                existing_by_code.setdefault(sku.sku_code, sku)
            matched_existing_ids = set()
            incoming_ids = []
            for sku_data in skus_data:
                sid = sku_data.get('id')
                target = None
                if sid and sid in existing_by_id and sid not in matched_existing_ids:
                    target = existing_by_id[sid]
                elif sku_data.get('sku_code') and sku_data['sku_code'] in existing_by_code:
                    cand = existing_by_code[sku_data['sku_code']]
                    if cand.id not in matched_existing_ids:
                        target = cand
                if target is not None:
                    for attr, val in sku_data.items():
                        if attr == 'id':
                            continue
                        setattr(target, attr, val)
                    target.save()
                    matched_existing_ids.add(target.id)
                    incoming_ids.append(target.id)
                else:
                    sku = SKU.objects.create(
                        product=instance,
                        **{k: v for k, v in sku_data.items() if k != 'id'})
                    incoming_ids.append(sku.id)
            # 删除前端未包含的 SKU（用户移除的），级联删其 Batch/Coa
            stale_ids = [sid for sid in existing_by_id if sid not in matched_existing_ids]
            if stale_ids:
                instance.skus.filter(id__in=stale_ids).delete()

        # Sync method bridges only if any method-related field was explicitly provided.
        # Explicit empty list clears all bridges; omitting all fields preserves existing.
        if method_ids is not None or research_goal_ids is not None or application_ids is not None:
            merged = self._merge_method_ids(method_ids, research_goal_ids, application_ids)
            self._sync_method_bridges(instance, list(merged))
        self._sync_protocol_bridges(instance, protocol_ids)

        # 刷新继承链：清孤儿 INHERITED 行并重算当前方法链派生（#一致性修复）
        self._refresh_inherited_bridges(instance)

        # Auto-generate SEO when transitioning from draft to active
        if is_becoming_active:
            self._auto_seo_on_publish(instance)
            # R1: DRAFT→ACTIVE 唯一触发点编排关联管线（MUST-1）
            # 系统级异常仅记录日志、不阻断产品保持 ACTIVE（Q2：管线故障可恢复）
            try:
                CommerceService.activate_product(instance.id)
            except Exception:
                import logging
                logging.getLogger('association_pipeline').exception(
                    'association_pipeline.activate_failed',
                    extra={'product_id': instance.id},
                )
        return instance

    def _refresh_inherited_bridges(self, product):
        """保存/恢复后刷新 ProductProtocol(link_source=INHERITED) 行，使其与当前方法链一致。

        - 删除不属于当前方法链派生的孤儿 INHERITED 行（续33 等批量落地残留）。
        - 用 recompute_product 重写当前方法链派生的 INHERITED 行（带三轴分数；
          embedding 不可用时安全降级 0，不阻断保存）。AUTO 行不受此影响
          （由 `manage.py recompute_auto_links` 离线单独管理）。
        """
        from apps.bridges.models import ProductMethod, MethodProtocol, ProductProtocol
        from apps.bridges.services.relevance import recompute_product

        method_ids = list(
            ProductMethod.objects.filter(product=product).values_list('method_id', flat=True)
        )
        derived_ids = set(
            MethodProtocol.objects.filter(method_id__in=method_ids)
            .values_list('protocol_id', flat=True).distinct()
        )
        qs = ProductProtocol.objects.filter(
            product=product, link_source=ProductProtocol.LinkSource.INHERITED
        )
        if derived_ids:
            qs.exclude(protocol_id__in=derived_ids).delete()
        else:
            qs.delete()
        if method_ids:
            recompute_product(product)


class ProductDetailSerializer(BaseModelSerializer):
    skus = SKUSerializer(many=True, read_only=True)
    documents = ProductDocumentSerializer(many=True, read_only=True)
    product_class_name = serializers.SerializerMethodField()
    product_class_path = serializers.SerializerMethodField()
    application_ids = serializers.SerializerMethodField()
    method_ids = serializers.SerializerMethodField()
    protocol_ids = serializers.SerializerMethodField()
    protocol_links = serializers.SerializerMethodField()
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
            'overview', 'structure_svg', 'structure_image', 'seo_title', 'seo_description',
            'category_l1', 'category_l2', 'status', 'product_class_id',
            'product_class_name', 'product_class_path',
            'skus', 'documents', 'application_ids', 'method_ids', 'protocol_ids',
            'protocol_links',
            'reference_ids', 'compatibility_summary', 'created_at', 'updated_at',
            'is_complete', 'incomplete_items', 'substructure_tags',
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

    def get_protocol_links(self, obj):
        """产品协议链行（#355）。已收敛至 bridges.services.relevance.build_protocol_links 唯一实现
        （P2-2）：PP 主源（INHERITED/EXPLICIT/AUTO 全量行）+ 无 PP 行时 MethodProtocol 桥 fallback，
        与详情 API ProductDetailAPIView.protocols 走同一核心逻辑，消除双实现输出不一致。
        字段契约不变：id/name/slug/relevance_score/score_a/score_b/score_c/relevance_basis/
        link_source/tier/literature_count；排序复用 build_protocol_links 内 protocol_link_sort_key。
        """
        from apps.bridges.services.relevance import build_protocol_links
        return build_protocol_links(obj)

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
