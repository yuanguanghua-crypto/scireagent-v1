from rest_framework import serializers

from core.serializers import BaseModelSerializer
from apps.inventory.models import Inventory, InventoryMovement, StockShortageAlert
from apps.inventory.serializers import AllocationSerializer  # 复用既有占用展示

# ★ P2：`available`/`allocated` 在 Postgres 是 int4，上限 2147483647。
# `IntegerField` 只在 Python 层校验，越界值通过后会一路带到 DB 才炸（实测 500 OverflowError）
# ⇒ 这里给单字段设上界，作为廉价的第一道防线。
# ⚠️ 这**只是第一道**：单字段合法 ≠ 累加后合法（见 services.InventoryService 的累加上界检查），
#    因为本 serializer 的字段是**增量**语义（available += quantity/delta）。
INT4_MAX = 2_147_483_647


class InventoryListSerializer(BaseModelSerializer):
    sku_code = serializers.CharField(source='sku.sku_code', read_only=True)
    product_name = serializers.CharField(source='sku.product.name', read_only=True)
    lot_number = serializers.CharField(source='batch.lot_number', read_only=True)
    on_hand = serializers.IntegerField(read_only=True)
    # ★ A-260（2026-11-18 / S4）：库存台必须能看出「这一行的 SKU 还在不在纳管状态」。
    #
    # 为什么需要：`Stop tracking` 只翻 `SKU.is_stock_tracked`，**不动 Inventory 行**
    # ⇒ 脱管成功后那一行仍然在表里，且长得和普通库存行一模一样（available=0 而已）。
    # 运营会以为「还有一行 0 库存的货」，看不出它其实已经退出缺货校验（≡ 不限量）。
    # 前端据此渲染 `Tracked: Yes/No` 并对未纳管行置灰。
    #
    # 这是**纯追加字段**：不动任何既有键，列表/入库/调整/详情四个消费方逐字节兼容。
    is_stock_tracked = serializers.BooleanField(source='sku.is_stock_tracked', read_only=True)

    class Meta:
        model = Inventory
        fields = [
            'id', 'sku_id', 'sku_code', 'product_name', 'batch_id', 'lot_number',
            'location', 'available', 'allocated', 'on_hand', 'is_stock_tracked',
            'updated_at',
        ]


class InventoryMovementSerializer(BaseModelSerializer):
    class Meta:
        model = InventoryMovement
        fields = [
            'id', 'inventory_id', 'kind', 'delta_available', 'delta_allocated',
            'quantity', 'reason', 'order_id', 'created_by_id', 'created_at',
        ]


class InventoryDetailSerializer(InventoryListSerializer):
    """详情：含最近变动流水（view 层 Prefetch 截取 50 条）与当前 RESERVED 占用。"""
    movements = InventoryMovementSerializer(many=True, read_only=True)
    active_allocations = serializers.SerializerMethodField()

    class Meta(InventoryListSerializer.Meta):
        fields = InventoryListSerializer.Meta.fields + ['movements', 'active_allocations']

    def get_active_allocations(self, obj):
        rows = obj.allocations.filter(status='reserved').select_related('order_item__order')
        return AllocationSerializer(rows, many=True).data


class ReceiptSerializer(serializers.Serializer):
    """入库入参：(sku, batch, location) 累加可分配量。

    ★ 2026-11-28（A-011）：新增 `lot_number` / `produced_at` —— 因为**界面根本
      录不了批次号**：`InventoryDesk` 的入库对话框只有 SKU/库位/数量/备注，
      而 `receipt.batchId` 在 script 里存在、提交时也传了 `batch_id`，**却没有输入控件**
      ⇒ 永远是 null ⇒ `Inventory.batch_id` 全空 ⇒ 库存台的 LOT 列必然全 "—"。
      `lot_number` 与 `batch_id` 互斥（都给会打架）；给了批次号就必须给生产日期
      （`documents.Batch.produced_at` 是必填）。
    """
    sku_id = serializers.IntegerField()
    location = serializers.ChoiceField(choices=Inventory.Location.choices)
    quantity = serializers.IntegerField(min_value=1, max_value=INT4_MAX)
    batch_id = serializers.IntegerField(required=False, allow_null=True)
    lot_number = serializers.CharField(
        max_length=50, required=False, allow_blank=True, allow_null=True)
    produced_at = serializers.DateField(required=False, allow_null=True)
    reason = serializers.CharField(max_length=200)

    def validate_reason(self, v):
        if not v.strip():
            raise serializers.ValidationError('入库必须填写原因')
        return v

    def validate(self, attrs):
        lot = (attrs.get('lot_number') or '').strip()
        if attrs.get('batch_id') and lot:
            raise serializers.ValidationError(
                'batch_id 与 lot_number 只能给一个（前者=已有批次，后者=按批次号新建/复用）')
        if lot and not attrs.get('produced_at'):
            raise serializers.ValidationError('按批次号入库时必须填生产日期 produced_at')
        attrs['lot_number'] = lot or None
        return attrs


class TrackSerializer(serializers.Serializer):
    """纳管开关入参（4a）。

    `tracked=False` 的硬校验在 view 层：要求该 SKU 无库存、无占用才能脱管。
    """
    sku_id = serializers.IntegerField()
    tracked = serializers.BooleanField()


class AdjustSerializer(serializers.Serializer):
    """盘点调整入参：available += delta（结果不可为负）。"""
    delta = serializers.IntegerField(min_value=-INT4_MAX, max_value=INT4_MAX)
    reason = serializers.CharField(max_length=200)

    def validate_delta(self, v):
        if v == 0:
            raise serializers.ValidationError('delta 不能为 0')
        return v

    def validate_reason(self, v):
        if not v.strip():
            raise serializers.ValidationError('调整必须填写原因')
        return v


class StockShortageAlertSerializer(BaseModelSerializer):
    """缺货拦截记录（运营告警台列表）。"""

    reason_label = serializers.CharField(source='get_reason_display', read_only=True)
    source_label = serializers.CharField(source='get_source_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    user_display = serializers.SerializerMethodField()
    handled_by_name = serializers.CharField(source='handled_by.username', read_only=True, default='')

    class Meta:
        model = StockShortageAlert
        fields = [
            'id', 'user_id', 'user_name', 'user_email', 'user_display',
            'sku_id', 'sku_code', 'product_name',
            'requested_quantity', 'available_quantity', 'occurrences',
            'reason', 'reason_label', 'source', 'source_label',
            'status', 'status_label',
            'handled_by_id', 'handled_by_name', 'handled_at', 'note',
            'created_at', 'updated_at',
        ]

    def get_user_display(self, obj):
        """优先显示快照（用户可能已被删除/改名），退化到 FK。"""
        return obj.user_name or getattr(obj.user, 'username', '') or f'user#{obj.user_id}'


class StockShortageResolveSerializer(serializers.Serializer):
    """标记处理：已补货 / 已联系客户 / 已忽略。"""
    status = serializers.ChoiceField(choices=[
        StockShortageAlert.Status.RESTOCKED,
        StockShortageAlert.Status.CONTACTED,
        StockShortageAlert.Status.DISMISSED,
        StockShortageAlert.Status.NEW,      # 允许撤回（误点）
    ])
    note = serializers.CharField(required=False, allow_blank=True, default='', max_length=2000)
