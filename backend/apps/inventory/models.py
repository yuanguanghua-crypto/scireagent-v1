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
    """库存占用 — 订单行对具体库存记录的锁定。"""

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


class InsufficientInventoryError(Exception):
    """Raised when an allocation/release would over-commit inventory."""
    pass
