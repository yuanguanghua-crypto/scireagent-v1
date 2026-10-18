from django.db import transaction
from apps.inventory.models import Inventory, Allocation, InsufficientInventoryError, InventoryMovement

# ★ P2：`available`/`allocated` 是裸 IntegerField，Postgres 侧为 int4（上限 2147483647）。
# 本模块的 quantity/delta 都是**增量**语义（available += x）⇒ 单字段合法 ≠ 累加后合法：
#   available=2,000,000,000 + quantity=300,000,000 ⇒ 2,300,000,000 溢出 int4（实测 500）。
# 故除serializer 的单字段上界外，累加前必须再查一次上界。
INT4_MAX = 2_147_483_647


def _guard_accumulation(current: int, delta: int, field: str = 'available') -> int:
    """累加上界守卫：返回累加结果，越界则抛 ValueError。

    ⚠️ 必须抛 `ValueError`：api/v1/views.py:82/101 的
    `except (ValueError, InsufficientInventoryError)` 已捕获它 ⇒ 零新增捕获逻辑即变400。
    ⚠️ 不能只靠 DB 兜底：SQLite 是 int8，会静默接受越界值（本地测试也测不出 500），
    而生产 Postgres 会直接抛 DataError/OverflowError ⇒ 500。
    """
    result = current + delta
    if result > INT4_MAX:
        raise ValueError(
            f'累加后超出上限：当前 {field}={current}，本次变更 {delta:+d}，'
            f'累加后 {result}，超出 int4 上限 {INT4_MAX}。请调小本次数量。'
        )
    return result


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
        # ★ P2：`allocated` 同为裸 IntegerField，且是**累加**语义 ——
        #   models.Inventory.allocate 的 `available >= qty` 兜底只管 available，
        #   allocated 可被反复占用同一行推过 int4 ⇒ 同样要在写库前查上界。
        #   ValueError 已被 transactions/api/v1/po_views.py:210 的 except 捕获 ⇒ 自动 400。
        _guard_accumulation(inv.allocated, quantity, field='allocated')
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
        inv.available = _guard_accumulation(inv.available, quantity)
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
        inv.available = _guard_accumulation(inv.available, delta)
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
