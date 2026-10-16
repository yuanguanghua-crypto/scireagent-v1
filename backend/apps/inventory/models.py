from django.conf import settings
from django.db import models
from core.models import TimeStampedModel


class Inventory(TimeStampedModel):
    """库存 — 按 SKU + 批次 + 库位承载可用/占用量（不污染 commerce.Batch）。"""

    class Location(models.TextChoices):
        MAIN = 'MAIN', 'Main Warehouse'
        EU = 'EU', 'EU Warehouse'
        US = 'US', 'US Warehouse'

    sku = models.ForeignKey(
        'commerce.SKU', on_delete=models.CASCADE, related_name='inventory', verbose_name='SKU'
    )
    batch = models.ForeignKey(
        'documents.Batch', on_delete=models.CASCADE,
        null=True, blank=True, related_name='inventory', verbose_name='批次'
    )
    location = models.CharField(
        max_length=20, choices=Location.choices, default=Location.MAIN, verbose_name='库位'
    )
    available = models.IntegerField(default=0, verbose_name='可分配量')
    allocated = models.IntegerField(default=0, verbose_name='已占用量')

    class Meta:
        db_table = 'inventory'
        verbose_name = '库存'
        verbose_name_plural = verbose_name
        unique_together = [('sku', 'batch', 'location')]
        ordering = ['sku_id', 'location']

    def __str__(self):
        return f'{self.sku_id} @ {self.location} (avail={self.available}, alloc={self.allocated})'

    @property
    def on_hand(self):
        """在库总量 ≈ available + allocated。"""
        return self.available + self.allocated

    def allocate(self, qty: int):
        """扣减可分配量、增加占用量（调用方须已持行锁）。"""
        if qty < 0:
            raise ValueError('qty must be non-negative')
        if self.available < qty:
            raise InsufficientInventoryError(
                f'Insufficient available stock: requested {qty}, available {self.available}'
            )
        self.available -= qty
        self.allocated += qty

    def release(self, qty: int):
        """释放占用量（调用方须已持行锁）。"""
        if qty < 0:
            raise ValueError('qty must be non-negative')
        if self.allocated < qty:
            raise InsufficientInventoryError(
                f'Cannot release {qty}, only {self.allocated} allocated'
            )
        self.allocated -= qty


class Allocation(TimeStampedModel):
    """库存占用 — 订单行对具体库存记录的锁定。

    ★ 2026-10-16 修 P0（部分发货占用被整额释放）：`quantity` 是**原始占用量**（不可变，
    审计口径），新增 `released_quantity` 记录**累计已出库量**。
    分批发货时每次只释放实发量，`remaining = quantity - released_quantity`；
    仅当 `released_quantity == quantity` 时 status 才转 SHIPPED。
    选此方案而非「拆分 Allocation 行」：后者会让 `filter(status=RESERVED)`
    （inventory/api/v1/serializers.py:40、tests/test_allocate.py:56）与
    `Allocation.objects.count()` 类断言语义破碎，且占用行数量随发货次数膨胀。
    """

    class Status(models.TextChoices):
        RESERVED = 'reserved', 'Reserved'
        SHIPPED = 'shipped', 'Shipped'
        RELEASED = 'released', 'Released'

    order_item = models.ForeignKey(
        'transactions.OrderItem', on_delete=models.CASCADE,
        related_name='allocations', verbose_name='订单明细'
    )
    inventory = models.ForeignKey(
        Inventory, on_delete=models.CASCADE, related_name='allocations', verbose_name='库存'
    )
    quantity = models.IntegerField(default=1, verbose_name='占用数量')
    released_quantity = models.IntegerField(default=0, verbose_name='累计已出库数量')
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.RESERVED
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'allocation'
        verbose_name = '库存占用'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'Alloc {self.order_item_id} → {self.inventory_id} x{self.quantity} ({self.status})'

    @property
    def remaining_quantity(self) -> int:
        """尚未出库的占用量。"""
        return max(0, self.quantity - self.released_quantity)


class InsufficientInventoryError(Exception):
    """Raised when an allocation/release would over-commit inventory."""
    pass


class InventoryMovement(TimeStampedModel):
    """库存变动流水 — available/allocated 的每次变化一条审计记录（v4.1 DEV-1）。

    入库/盘点调整/订单占用/释放/发货出库均在此留痕；由 InventoryService 统一写入，
    禁止绕过服务层直接改 Inventory.available/allocated。
    """

    class Kind(models.TextChoices):
        RECEIPT = 'receipt', '入库'
        ADJUST = 'adjust', '盘点调整'
        ALLOCATE = 'allocate', '订单占用'
        RELEASE = 'release', '占用释放'
        SHIP = 'ship', '发货出库'

    inventory = models.ForeignKey(
        Inventory, on_delete=models.CASCADE, related_name='movements', verbose_name='库存'
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, verbose_name='变动类型')
    delta_available = models.IntegerField(default=0, verbose_name='可分配量变化')
    delta_allocated = models.IntegerField(default=0, verbose_name='占用量变化')
    quantity = models.IntegerField(default=0, verbose_name='操作数量')
    reason = models.CharField(max_length=200, blank=True, default='', verbose_name='原因/备注')
    order = models.ForeignKey(
        'transactions.Order', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='inventory_movements', verbose_name='关联订单'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='操作人'
    )

    class Meta:
        db_table = 'inventory_movement'
        verbose_name = '库存变动流水'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return (f'{self.kind} inv={self.inventory_id} '
                f'dA={self.delta_available} dAl={self.delta_allocated}')
