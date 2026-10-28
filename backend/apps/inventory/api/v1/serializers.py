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

    class Meta:
        model = Inventory
        fields = [
            'id', 'sku_id', 'sku_code', 'product_name', 'batch_id', 'lot_number',
            'location', 'available', 'allocated', 'on_hand', 'updated_at',
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
    """入库入参：(sku, batch, location) 累加可分配量。"""
    sku_id = serializers.IntegerField()
    location = serializers.ChoiceField(choices=Inventory.Location.choices)
    quantity = serializers.IntegerField(min_value=1, max_value=INT4_MAX)
    batch_id = serializers.IntegerField(required=False, allow_null=True)
    reason = serializers.CharField(max_length=200)

    def validate_reason(self, v):
        if not v.strip():
            raise serializers.ValidationError('入库必须填写原因')
        return v


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
