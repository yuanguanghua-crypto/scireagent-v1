from rest_framework import serializers

from core.serializers import BaseModelSerializer
from apps.inventory.models import Inventory, InventoryMovement
from apps.inventory.serializers import AllocationSerializer  # 复用既有占用展示


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
    quantity = serializers.IntegerField(min_value=1)
    batch_id = serializers.IntegerField(required=False, allow_null=True)
    reason = serializers.CharField(max_length=200)

    def validate_reason(self, v):
        if not v.strip():
            raise serializers.ValidationError('入库必须填写原因')
        return v


class AdjustSerializer(serializers.Serializer):
    """盘点调整入参：available += delta（结果不可为负）。"""
    delta = serializers.IntegerField()
    reason = serializers.CharField(max_length=200)

    def validate_delta(self, v):
        if v == 0:
            raise serializers.ValidationError('delta 不能为 0')
        return v

    def validate_reason(self, v):
        if not v.strip():
            raise serializers.ValidationError('调整必须填写原因')
        return v
