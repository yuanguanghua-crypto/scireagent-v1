from django.db import transaction
from apps.inventory.models import Inventory, Allocation, InsufficientInventoryError, InventoryMovement


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
        allocation = Allocation.objects.create(
            order_item=order_item,
            inventory=inv,
            quantity=quantity,
            status=Allocation.Status.RESERVED,
        )
        # ★ v4.1 DEV-1：变动流水（同事务审计）
        InventoryMovement.objects.create(
            inventory=inv, kind=InventoryMovement.Kind.ALLOCATE,
            delta_available=-quantity, delta_allocated=quantity, quantity=quantity,
            reason=f'order:{order_item.order_id}', order_id=order_item.order_id,
        )
        return allocation

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
    def release(allocation: Allocation, quantity: int | None = None) -> int:
        """发货：实物已出，释放占用量（allocated-=q，available 不变）。

        ★ 2026-10-16 修 P0（部分发货占用被整额释放）：原实现无条件释放
          `allocation.quantity` 整额，而调用方（ShippingService.mark_shipped）
          的 `remaining` 只决定何时停止遍历、不决定释放多少 ⇒ 占用 10、发货 5
          会把 allocated 直接归零，账实不符。
          现支持 `quantity` 参数做部分释放：只减实发量，流水按实发量写，
          `allocation.released_quantity` 累计，仅当释放完毕才转 SHIPPED。
          `quantity=None`（默认）时为全量释放，行为与修复前完全一致。

        返回实际释放量。
        """
        # ★ 重取并加行锁：调用方传进来的 allocation 可能是发货前读出的快照，
        #   同一 order_item 的多批发货并发 mark_shipped 时 released_quantity 会是陈值
        #   ⇒ 累计量算错、status 误判。与本类「所有扣减/释放均经 select_for_update」一致。
        allocation = Allocation.objects.select_for_update().get(pk=allocation.pk)
        inv = InventoryService._lock(allocation.inventory_id)
        if quantity is None:
            quantity = allocation.remaining_quantity
        quantity = min(int(quantity), allocation.remaining_quantity)
        if quantity <= 0:
            return 0
        inv.release(quantity)
        inv.save(update_fields=['allocated', 'updated_at'])
        allocation.released_quantity += quantity
        update_fields = ['released_quantity', 'updated_at']
        # ★ 仅在占用被全部释放时才置 SHIPPED；部分释放保持 RESERVED
        if allocation.released_quantity >= allocation.quantity:
            allocation.status = Allocation.Status.SHIPPED
            update_fields.append('status')
        allocation.save(update_fields=update_fields)
        # ★ v4.1 DEV-1：发货出库流水（同事务审计）—— 按**实际释放量**写，
        #   不能按 allocation.quantity 整额写，否则流水与账面不符。
        InventoryMovement.objects.create(
            inventory=inv, kind=InventoryMovement.Kind.SHIP,
            delta_allocated=-quantity, quantity=quantity,
            reason=f'order:{allocation.order_item.order_id}', order_id=allocation.order_item.order_id,
        )
        return quantity

    @staticmethod
    @transaction.atomic
    def release_quantity(inventory_id: int, quantity: int):
        inv = InventoryService._lock(inventory_id)
        inv.release(quantity)
        inv.save(update_fields=['allocated', 'updated_at'])
        # ★ v4.1 DEV-1：占用释放流水（同事务审计）
        InventoryMovement.objects.create(
            inventory=inv, kind=InventoryMovement.Kind.RELEASE,
            delta_allocated=-quantity, quantity=quantity,
        )

    @staticmethod
    @transaction.atomic
    def receipt(sku_id: int, location: str, quantity: int, *,
                batch_id=None, user=None, reason: str = '') -> Inventory:
        """入库：指定 (sku, batch, location) 累加可分配量（无则建行），写 RECEIPT 流水。

        并发说明：行不存在时首建存在唯一约束兜底（unique_together），
        极端并发下第二个事务会 IntegrityError —— 内部低频操作可接受。
        """
        if quantity <= 0:
            raise ValueError('quantity must be positive')
        lookup = {'sku_id': sku_id, 'location': location, 'batch_id': batch_id}
        inv = Inventory.objects.filter(**lookup).select_for_update().first()
        if inv is None:
            inv = Inventory.objects.create(**lookup, available=0, allocated=0)
            inv = InventoryService._lock(inv.pk)
        inv.available += quantity
        inv.save(update_fields=['available', 'updated_at'])
        InventoryMovement.objects.create(
            inventory=inv, kind=InventoryMovement.Kind.RECEIPT,
            delta_available=quantity, quantity=quantity, reason=reason, created_by=user,
        )
        return inv

    @staticmethod
    @transaction.atomic
    def adjust(inventory_id: int, delta: int, *, user=None, reason: str = '') -> Inventory:
        """盘点调整：available += delta（结果不可为负），写 ADJUST 流水。"""
        if delta == 0:
            raise ValueError('delta must be non-zero')
        inv = InventoryService._lock(inventory_id)
        if inv.available + delta < 0:
            raise InsufficientInventoryError(
                f'Adjust would over-draw: available {inv.available}, delta {delta}'
            )
        inv.available += delta
        inv.save(update_fields=['available', 'updated_at'])
        InventoryMovement.objects.create(
            inventory=inv, kind=InventoryMovement.Kind.ADJUST,
            delta_available=delta, quantity=abs(delta), reason=reason, created_by=user,
        )
        return inv

    @staticmethod
    def available_for_sku(sku_id: int):
        rows = Inventory.objects.filter(sku_id=sku_id)
        return {
            'available': sum(r.available for r in rows),
            'allocated': sum(r.allocated for r in rows),
            'on_hand': sum(r.on_hand for r in rows),
        }
