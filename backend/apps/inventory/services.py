from django.db import transaction
from apps.inventory.models import Inventory, Allocation, InsufficientInventoryError


class InventoryService:
    """库存原子操作 — 所有扣减/释放均经 select_for_update，禁止直接改 available。"""

    @staticmethod
    def _lock(inventory_id: int) -> Inventory:
        return Inventory.objects.select_for_update().get(pk=inventory_id)

    @staticmethod
    @transaction.atomic
    def allocate(order_item, inventory_id: int, quantity: int) -> Allocation:
        """锁定指定库存并记录占用（RESERVED）。"""
        inv = InventoryService._lock(inventory_id)
        inv.allocate(quantity)  # raises InsufficientInventoryError if over-commit
        inv.save(update_fields=['available', 'allocated', 'updated_at'])
        return Allocation.objects.create(
            order_item=order_item,
            inventory=inv,
            quantity=quantity,
            status=Allocation.Status.RESERVED,
        )

    @staticmethod
    @transaction.atomic
    def allocate_for_order(order, lines: list) -> list:
        """节点 B 批量锁定：lines=[{order_item_id, inventory_id, quantity}]。"""
        from apps.transactions.models import OrderItem
        allocations = []
        for line in lines:
            oi = OrderItem.objects.get(pk=line['order_item_id'], order=order)
            allocations.append(
                InventoryService.allocate(oi, line['inventory_id'], int(line['quantity']))
            )
        return allocations

    @staticmethod
    @transaction.atomic
    def release(allocation: Allocation):
        """发货：实物已出，释放占用量（allocated-=q，available 不变），标记 SHIPPED。"""
        inv = InventoryService._lock(allocation.inventory_id)
        inv.release(allocation.quantity)
        inv.save(update_fields=['allocated', 'updated_at'])
        allocation.status = Allocation.Status.SHIPPED
        allocation.save(update_fields=['status', 'updated_at'])

    @staticmethod
    @transaction.atomic
    def release_quantity(inventory_id: int, quantity: int):
        inv = InventoryService._lock(inventory_id)
        inv.release(quantity)
        inv.save(update_fields=['allocated', 'updated_at'])

    @staticmethod
    def available_for_sku(sku_id: int):
        rows = Inventory.objects.filter(sku_id=sku_id)
        return {
            'available': sum(r.available for r in rows),
            'allocated': sum(r.allocated for r in rows),
            'on_hand': sum(r.on_hand for r in rows),
        }
