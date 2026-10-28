from django.conf import settings
from django.core.validators import MinValueValidator
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
    # ★ P2：裸 IntegerField 无任何下界约束（实测 ORM 直接写 available=-500 能成功）。
    # 补应用层校验（比 DB 约束更早失败，且不触碰存量数据）。
    # ✅ 2026-10-18 补 DB 层 CheckConstraint：生产 `inventory` 表已实测核实为
    #    0 行（total_rows=0，available/allocated 负数行与超 int4 行均为 0），
    #    ⇒ AddConstraint 不会因存量负数行而失败，兜底已放行。
    #    命名沿用本项目 `ck_` 前缀惯例（如 ck_mrc_conditional_not_essential），
    #    不用 Django 自动生成的带哈希后缀名，便于回滚定位。
    available = models.IntegerField(
        default=0, validators=[MinValueValidator(0)], verbose_name='可分配量')
    allocated = models.IntegerField(
        default=0, validators=[MinValueValidator(0)], verbose_name='已占用量')

    class Meta:
        db_table = 'inventory'
        verbose_name = '库存'
        verbose_name_plural = verbose_name
        unique_together = [('sku', 'batch', 'location')]
        ordering = ['sku_id', 'location']
        constraints = [
            # DB 层兜底：即使绕过应用层（raw SQL / 脚本 / 未来新代码漏校验），
            # 也写不进负库存。MinValueValidator 只在 full_clean() 时跑，
            # ORM save() 不调用它 —— 这才是 DB 约束不可省的原因。
            models.CheckConstraint(
                condition=models.Q(available__gte=0),
                name='ck_inv_available_nonneg'),
            models.CheckConstraint(
                condition=models.Q(allocated__gte=0),
                name='ck_inv_allocated_nonneg'),
        ]

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


class StockShortageAlert(TimeStampedModel):
    """缺货下单拦截记录 — 客户想买但库存不够时留痕，供运营跟进。

    ★ 2026-10-28 新增。为什么需要独立表而不是复用 StatusLog：
      StatusLog 挂在 Order 上，而被拦截的下单**根本没有订单**（订单在库存校验
      之前就被拒），所以必须有一张与订单无关的表来承载"谁想要什么、被拦了几次"。
      运营据此判断：补库存 / 联系客户换货。

    口径（与 `StockShortageService.is_short` 同一份实现）：
      · SKU.inventory_status == out_of_stock ⇒ 拦
      · 该 SKU 已建库存记录（inventory 有行）且 sum(available) < 下单量 ⇒ 拦
      · 没有任何库存记录的 SKU（= 尚未纳入库存管理）不判定，避免把"没建账"
        误当成"没货"。

    字段里同时存 FK 与**快照**（user_email / sku_code / product_name）：
    用户或 SKU 之后被删/改名，运营看到的仍是拦截当时的原始信息。
    """

    class Reason(models.TextChoices):
        OUT_OF_STOCK = 'out_of_stock', 'SKU 标记缺货'
        INSUFFICIENT = 'insufficient', '可用量不足'

    class Source(models.TextChoices):
        PO_SUBMIT = 'po_submit', 'PO 提交'
        CHECKOUT = 'checkout', '购物车结账'

    class Status(models.TextChoices):
        NEW = 'new', '待处理'
        RESTOCKED = 'restocked', '已补库存'
        CONTACTED = 'contacted', '已联系客户'
        DISMISSED = 'dismissed', '已忽略'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='stock_shortage_alerts', verbose_name='下单用户'
    )
    user_email = models.CharField(max_length=254, blank=True, default='', verbose_name='用户邮箱（快照）')
    user_name = models.CharField(max_length=150, blank=True, default='', verbose_name='用户名（快照）')
    sku = models.ForeignKey(
        'commerce.SKU', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='shortage_alerts', verbose_name='SKU'
    )
    sku_code = models.CharField(max_length=100, blank=True, default='', db_index=True,
                                verbose_name='SKU 编码（快照）')
    product_name = models.CharField(max_length=500, blank=True, default='', verbose_name='产品名（快照）')
    requested_quantity = models.IntegerField(default=0, verbose_name='客户下单数量')
    available_quantity = models.IntegerField(default=0, verbose_name='当时可用量')
    occurrences = models.IntegerField(
        default=1,
        verbose_name='重复次数',
        help_text='同一用户对同一 SKU 的连续拦截次数（24h 内合并，避免刷屏）',
    )
    reason = models.CharField(max_length=20, choices=Reason.choices,
                              default=Reason.INSUFFICIENT, verbose_name='拦截原因')
    source = models.CharField(max_length=20, choices=Source.choices,
                              default=Source.PO_SUBMIT, verbose_name='来源')
    status = models.CharField(max_length=20, choices=Status.choices,
                              default=Status.NEW, verbose_name='处理状态', db_index=True)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='处理人'
    )
    handled_at = models.DateTimeField(null=True, blank=True, verbose_name='处理时间')
    note = models.TextField(blank=True, default='', verbose_name='处理备注')

    class Meta:
        db_table = 'stock_shortage_alert'
        verbose_name = '缺货下单拦截'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at'], name='idx_ssa_status_time'),
            models.Index(fields=['user', 'sku'], name='idx_ssa_user_sku'),
        ]

    def __str__(self):
        return (f'{self.sku_code or self.sku_id} x{self.requested_quantity} '
                f'by {self.user_name or self.user_id} [{self.status}]')
