from rest_framework import serializers
from core.serializers import BaseModelSerializer
from apps.inventory.models import Inventory, Allocation


class InventorySerializer(BaseModelSerializer):
    sku_code = serializers.CharField(source='sku.sku_code', read_only=True)
    lot_number = serializers.CharField(source='batch.lot_number', read_only=True)
    on_hand = serializers.IntegerField(read_only=True)

    class Meta:
        model = Inventory
        fields = [
            'id', 'sku_id', 'sku_code', 'batch_id', 'lot_number',
            'location', 'available', 'allocated', 'on_hand',
        ]


class AllocationSerializer(BaseModelSerializer):
    class Meta:
        model = Allocation
        fields = [
            'id', 'order_item_id', 'inventory_id', 'quantity', 'status', 'created_at',
        ]


class AllocationLineSerializer(serializers.Serializer):
    """单条占用入参（节点 B 备货台）。"""
    order_item_id = serializers.IntegerField()
    inventory_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class AllocateRequestSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    lines = AllocationLineSerializer(many=True)
