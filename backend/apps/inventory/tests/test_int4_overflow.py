"""★ 库存数量字段int4 溢出防护（P2 缺陷回归）。

缺陷：`available` / `allocated` 是裸 `IntegerField`（Postgres int4，上限 2147483647），
而 `quantity` / `delta` 是**增量**语义（services.py `inv.available += x`）。
⇒ **单字段合法 ≠ 累加后合法**：`available=2_000_000_000` + `quantity=300_000_000`
两个输入各自合法，累加后 2_300_000_000 超出 int4 ⇒ 生产上 500。

⚠️ 本地 SQLite 是 int8，静默接受 2.3e9（**不会**报溢出）⇒ 修复前累加场景返回 **200**
而非 500。正因如此，本文件的累加用例断言的是「**必须被 400 拒绝**」这个契约：
修复前它失败（200），修复后它通过（400）—— 断言的是我们的**主动防御**，不是 DB 的被动溢出。

三层防线：
  ① `api/v1/serializers.py` 单字段 max_value（廉价第一道）
  ② `services.py` 累加上界检查（治本；抛 ValueError ⇒ views 既有 except 转 400）
  ③ `models.py` MinValueValidator(0)（应用层；DB CheckConstraint 见交付说明）
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User, Organization
from apps.commerce.models import Product, SKU
from apps.inventory.models import Inventory, InsufficientInventoryError, Allocation
from apps.inventory.services import InventoryService
from apps.transactions.models import Order, OrderItem

INT4_MAX = 2_147_483_647


class Base(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Lab', org_type='academic')
        self.proc = User.objects.create_user(
            username='ovf_proc', password='x', organization=self.org, role='procurement')
        product = Product.objects.create(name='Reagent', slug='reagent-ovf')
        self.sku = SKU.objects.create(product=product, sku_code='SKU-OVF', price=Decimal('10.00'))
        self.client = APIClient()
        self.client.force_authenticate(user=self.proc)

    def _receipt(self, quantity, reason='入库'):
        return self.client.post('/api/v1/inventory/receipt/', {
            'sku_id': self.sku.id, 'location': 'MAIN',
            'quantity': quantity, 'reason': reason}, format='json')

    def _adjust(self, inv, delta, reason='盘点'):
        return self.client.post(f'/api/v1/inventory/{inv.id}/adjust/',
                                {'delta': delta, 'reason': reason}, format='json')


class QuantityOverInt4Test(Base):
    """① 单字段超int4：超大整数不得 500。"""

    def test_receipt_quantity_over_int4_400(self):
        """超int4 的 quantity ⇒ 400（修复前：Python 层无上界 ⇒ 500 OverflowError）。"""
        r = self._receipt(INT4_MAX + 1)
        self.assertEqual(r.status_code, 400, r.content[:300])

    def test_receipt_quantity_absurdly_large_400(self):
        """远超 int8 的荒谬输入（实测曾 500 OverflowError）⇒ 400。"""
        r = self._receipt(99_999_999_999_999_999_999)
        self.assertEqual(r.status_code, 400, r.content[:300])

    def test_adjust_delta_over_int4_400(self):
        r = self._adjust(Inventory.objects.create(
            sku=self.sku, location='MAIN', available=10), INT4_MAX + 1)
        self.assertEqual(r.status_code, 400, r.content[:300])

    def test_adjust_delta_absurdly_large_400(self):
        r = self._adjust(Inventory.objects.create(
            sku=self.sku, location='MAIN', available=10), 99_999_999_999_999_999_999)
        self.assertEqual(r.status_code, 400, r.content[:300])

    def test_adjust_delta_underflows_int4_400(self):
        """负向同样要有界（delta 是 int4，越界即溢出）。"""
        r = self._adjust(Inventory.objects.create(
            sku=self.sku, location='MAIN', available=10), -INT4_MAX - 1)
        self.assertEqual(r.status_code, 400, r.content[:300])


class AccumulationOverflowTest(Base):
    """★★ 核心：单字段合法 ≠ 累加后合法。

    ⚠️ SQLite 是 int8，会静默接受 2.3e9 ⇒ 修复前这些用例返回 **200**（而非 500）。
    断言 400 锁的是「我们主动拒绝」，正是治本的那一层。
    """

    def test_receipt_accumulation_overflow_400(self):
        """available=2e9 + quantity=3e8 = 2.3e9 > int4⇒ 400 且数据不变。"""
        inv = Inventory.objects.create(sku=self.sku, location='MAIN', available=2_000_000_000)
        r = self._receipt(300_000_000)
        self.assertEqual(r.status_code, 400, r.content[:300])
        inv.refresh_from_db()
        self.assertEqual(inv.available, 2_000_000_000, '拒绝后不得改数据')

    def test_adjust_accumulation_overflow_400(self):
        """正delta 累加越界 ⇒ 400（负向越界是既有防线，此处只补正向缺口）。"""
        inv = Inventory.objects.create(sku=self.sku, location='MAIN', available=2_000_000_000)
        r = self._adjust(inv, 300_000_000)
        self.assertEqual(r.status_code, 400, r.content[:300])
        inv.refresh_from_db()
        self.assertEqual(inv.available, 2_000_000_000, '拒绝后不得改数据')

    def test_accumulation_boundary_exactly_int4_max_accepted(self):
        """边界：累加结果**正好等于** int4 上限必须放行（别把合法值误杀）。"""
        inv = Inventory.objects.create(
            sku=self.sku, location='MAIN', available=INT4_MAX - 1000)
        r = self._receipt(1000)
        self.assertEqual(r.status_code, 200, r.content[:300])
        inv.refresh_from_db()
        self.assertEqual(inv.available, INT4_MAX)

    def test_new_row_receipt_accumulation_overflow_400(self):
        """新建行的入库路径同样要守界（inv.available 从 0 起累加）。"""
        Inventory.objects.create(sku=self.sku, location='MAIN', available=INT4_MAX)
        r = self._receipt(1, reason='再入库')
        self.assertEqual(r.status_code, 400, r.content[:300])

    def test_overflow_message_is_actionable(self):
        """错误信息要让用户知道该改小 ⇒ 含当前值/累加后值/上限。"""
        inv = Inventory.objects.create(sku=self.sku, location='MAIN', available=2_000_000_000)
        r = self._receipt(300_000_000)
        body = r.content.decode('utf-8', 'replace')
        self.assertIn('2000000000', body.replace(',', ''))
        self.assertIn('2300000000', body.replace(',', ''))
        self.assertIn(str(INT4_MAX), body)


class ExistingBehaviourRegressionTest(Base):
    """既有防线不得回归：结果不可为负 / delta=0 / 正常路径。"""

    def test_adjust_overdraw_still_400(self):
        """既有：delta 致结果为负 ⇒ 400 且数据不变。"""
        inv = Inventory.objects.create(sku=self.sku, location='MAIN', available=100)
        r = self._adjust(inv, -999_999)
        self.assertEqual(r.status_code, 400, r.content[:300])
        inv.refresh_from_db()
        self.assertEqual(inv.available, 100)

    def test_adjust_delta_zero_still_400(self):
        inv = Inventory.objects.create(sku=self.sku, location='MAIN', available=100)
        r = self._adjust(inv, 0)
        self.assertEqual(r.status_code, 400, r.content[:300])

    def test_receipt_quantity_zero_still_400(self):
        r = self._receipt(0)
        self.assertEqual(r.status_code, 400, r.content[:300])

    def test_normal_receipt_and_adjust_still_200(self):
        """正常小数量路径不受影响。"""
        r = self._receipt(50)
        self.assertEqual(r.status_code, 200, r.content[:300])
        inv = Inventory.objects.get(sku=self.sku, location='MAIN')
        self.assertEqual(inv.available, 50)
        r = self._adjust(inv, -20)
        self.assertEqual(r.status_code, 200, r.content[:300])
        inv.refresh_from_db()
        self.assertEqual(inv.available, 30)

    def test_allocate_still_works(self):
        """既有 allocate 路径（`allocated += qty` 加界后）行为不变。"""
        researcher = User.objects.create_user(
            username='ovf_buyer', password='x', organization=self.org, role='researcher')
        order = Order.objects.create(
            user=researcher, organization=self.org,
            order_no='ORD-OVF-1', po_number=None, status=Order.Status.CONFIRMED)
        item = OrderItem.objects.create(
            order=order, sku=self.sku, quantity=2, unit_price=Decimal('10.00'))
        inv = Inventory.objects.create(sku=self.sku, location='MAIN', available=10)
        r = self.client.post(f'/api/v1/orders/{order.id}/allocate/', {
            'lines': [{'order_item_id': item.id, 'inventory_id': inv.id, 'quantity': 2}]},
            format='json')
        self.assertIn(r.status_code, (200, 201), r.content[:300])
        inv.refresh_from_db()
        self.assertEqual((inv.available, inv.allocated), (8, 2))

    def test_allocate_allocated_overflow_400(self):
        """★ `allocated += qty` 同样会溢出 int4⇒ 必须 400 而不是 500。

        `allocate()` 有`available >= qty` 兜底，但那只管 available；
        allocated 是**累加**的，反复占用同一行即可推过 int4。
        """
        researcher = User.objects.create_user(
            username='ovf_buyer2', password='x', organization=self.org, role='researcher')
        order = Order.objects.create(
            user=researcher, organization=self.org,
            order_no='ORD-OVF-2', po_number=None, status=Order.Status.CONFIRMED)
        item = OrderItem.objects.create(
            order=order, sku=self.sku, quantity=100, unit_price=Decimal('10.00'))
        # allocated 已接近上限，再占100 即溢出
        inv = Inventory.objects.create(
            sku=self.sku, location='MAIN', available=100, allocated=INT4_MAX - 50)
        r = self.client.post(f'/api/v1/orders/{order.id}/allocate/', {
            'lines': [{'order_item_id': item.id, 'inventory_id': inv.id, 'quantity': 100}]},
            format='json')
        self.assertEqual(r.status_code, 400, r.content[:300])
        inv.refresh_from_db()
        self.assertEqual(inv.allocated, INT4_MAX - 50, '拒绝后不得改数据')


class AllocateGuardOrderTest(Base):
    """★★ 回归：`allocate` 的上界守卫必须在 `inv.allocate(qty)` **之前**取值。

    缺陷：原实现先 `inv.allocate(qty)`（models.py 内部 `allocated += qty`），
    再拿**加完之后的新值**调 `_guard_accumulation(new, qty)` ⇒ qty 被多算一次，
    把本应合法的占用误判为溢出。`receipt`/`adjust` 是「先查后加」，顺序正确。
    """

    def _make_item(self, quantity: int) -> OrderItem:
        researcher = User.objects.create_user(
            username='ovf_guard_buyer', password='x',
            organization=self.org, role='researcher')
        order = Order.objects.create(
            user=researcher, organization=self.org,
            order_no='ORD-OVF-GUARD', po_number=None, status=Order.Status.CONFIRMED)
        return OrderItem.objects.create(
            order=order, sku=self.sku, quantity=quantity, unit_price=Decimal('10.00'))

    def test_allocate_near_limit_but_legal_succeeds(self):
        """★★ 核心：allocated=INT4_MAX-100、available=1000、allocate(60) 必须成功。

        实际结果 2147483607 ≤ INT4_MAX ⇒ 合法。修复前守卫用「已加完的值 + qty」
        算成 2147483667 而误抛 ValueError。
        """
        item = self._make_item(60)
        inv = Inventory.objects.create(
            sku=self.sku, location='MAIN',
            available=1000, allocated=INT4_MAX - 100)
        InventoryService.allocate(item, inv.id, 60)
        inv.refresh_from_db()
        self.assertEqual(inv.allocated, INT4_MAX - 40)
        self.assertEqual(inv.available, 940)

    def test_allocate_result_exactly_int4_max_succeeds(self):
        """★ 边界：占用后 allocated 恰好 == INT4_MAX ⇒ 必须放行（不得误杀）。"""
        item = self._make_item(60)
        inv = Inventory.objects.create(
            sku=self.sku, location='MAIN',
            available=1000, allocated=INT4_MAX - 60)
        InventoryService.allocate(item, inv.id, 60)
        inv.refresh_from_db()
        self.assertEqual(inv.allocated, INT4_MAX)

    def test_allocate_true_overflow_still_rejected(self):
        """★ 真溢出（结果 > INT4_MAX）仍须 ValueError，且不落库。"""
        item = self._make_item(100)
        inv = Inventory.objects.create(
            sku=self.sku, location='MAIN',
            available=100, allocated=INT4_MAX - 50)
        with self.assertRaises(ValueError):
            InventoryService.allocate(item, inv.id, 100)
        inv.refresh_from_db()
        self.assertEqual(inv.allocated, INT4_MAX - 50, '拒绝后不得改数据')
        self.assertEqual(inv.available, 100)

    def test_allocate_insufficient_available_still_raises(self):
        """既有行为不回归：available 不足仍抛 InsufficientInventoryError。"""
        item = self._make_item(10)
        inv = Inventory.objects.create(sku=self.sku, location='MAIN', available=5)
        with self.assertRaises(InsufficientInventoryError):
            InventoryService.allocate(item, inv.id, 10)
        inv.refresh_from_db()
        self.assertEqual((inv.available, inv.allocated), (5, 0))

    def test_release_near_int4_max_has_no_upper_guard(self):
        """release 是减法，不应有上界守卫：allocated=INT4_MAX 时释放正常。"""
        item = self._make_item(60)
        inv = Inventory.objects.create(
            sku=self.sku, location='MAIN',
            available=0, allocated=INT4_MAX)
        allocation = Allocation.objects.create(
            order_item=item, inventory=inv, quantity=60,
            status=Allocation.Status.RESERVED)
        InventoryService.release(allocation)
        inv.refresh_from_db()
        self.assertEqual(inv.allocated, INT4_MAX - 60)
        self.assertEqual(inv.available, 0)


class AllocateGuardDoubleCountTest(Base):
    """★★ 回归：`allocate()` 的上界守卫曾把 quantity 多算一次 ⇒ 合法占用被误拒。

    缺陷：`services.allocate` 先调 `inv.allocate(qty)`（models.py 内部已
    `allocated += qty`），再拿**加完之后的新值** `inv.allocated` 调
    `_guard_accumulation(current=新值, delta=qty)` ⇒ 多算一个 qty。
    实测反例：allocated=INT4_MAX-100、available=1000、allocate(60)
    ⇒ 真实结果 INT4_MAX-40 合法，却被误判为 INT4_MAX+20 而抛 ValueError。

    修法：守卫前移到 `inv.allocate(qty)` **之前**（先查后加），与
    receipt / adjust 的顺序一致。本类锁住「合法必须放行、真溢出必须拦」。
    """

    def _order_and_item(self, suffix: str, qty: int):
        researcher = User.objects.create_user(
            username=f'ovf_alloc_{suffix}', password='x',
            organization=self.org, role='researcher')
        order = Order.objects.create(
            user=researcher, organization=self.org,
            order_no=f'ORD-ALLOC-{suffix}', po_number=None, status=Order.Status.CONFIRMED)
        item = OrderItem.objects.create(
            order=order, sku=self.sku, quantity=qty, unit_price=Decimal('10.00'))
        return order, item

    def _allocate(self, order, item, inv, qty):
        return self.client.post(f'/api/v1/orders/{order.id}/allocate/', {
            'lines': [{'order_item_id': item.id, 'inventory_id': inv.id, 'quantity': qty}]},
            format='json')

    def test_allocate_int4_minus_100_plus_60_accepted(self):
        """★★ 核心回归：allocated=INT4_MAX-100 + 60 = INT4_MAX-40 ≤ 上限 ⇒ 必须成功。

        修复前：守卫用加完后的 INT4_MAX-40 再加 60 ⇒ 判越界 ⇒ ValueError/400（误拒）。
        修复后：先查后加，结果合法 ⇒ 200/201 且落库。
        """
        order, item = self._order_and_item('core', 60)
        inv = Inventory.objects.create(
            sku=self.sku, location='MAIN', available=1000, allocated=INT4_MAX - 100)
        r = self._allocate(order, item, inv, 60)
        self.assertIn(r.status_code, (200, 201), r.content[:300])
        inv.refresh_from_db()
        self.assertEqual(inv.allocated, INT4_MAX - 40)
        self.assertEqual(inv.available, 940)

    def test_allocate_exactly_at_int4_max_accepted(self):
        """★ 边界不误杀：加完恰好 == INT4_MAX 必须放行（守卫是 `>` 不是 `>=`）。"""
        order, item = self._order_and_item('edge', 60)
        inv = Inventory.objects.create(
            sku=self.sku, location='MAIN', available=1000, allocated=INT4_MAX - 60)
        r = self._allocate(order, item, inv, 60)
        self.assertIn(r.status_code, (200, 201), r.content[:300])
        inv.refresh_from_db()
        self.assertEqual(inv.allocated, INT4_MAX)
        self.assertEqual(inv.available, 940)

    def test_allocate_over_int4_max_still_rejected(self):
        """★ 真溢出仍要拦：加完 = INT4_MAX+1 ⇒ 400，且不得落库。"""
        order, item = self._order_and_item('over', 60)
        inv = Inventory.objects.create(
            sku=self.sku, location='MAIN', available=1000, allocated=INT4_MAX - 59)
        r = self._allocate(order, item, inv, 60)
        self.assertEqual(r.status_code, 400, r.content[:300])
        inv.refresh_from_db()
        self.assertEqual(inv.allocated, INT4_MAX - 59, '拒绝后不得改数据')
        self.assertEqual(inv.available, 1000, '拒绝后不得改数据')

    def test_allocate_insufficient_available_still_rejected(self):
        """既有行为不回归：available 不足仍抛 InsufficientInventoryError ⇒ 400 且数据不变。"""
        order, item = self._order_and_item('short', 50)
        inv = Inventory.objects.create(
            sku=self.sku, location='MAIN', available=10, allocated=INT4_MAX - 1000)
        r = self._allocate(order, item, inv, 50)
        self.assertEqual(r.status_code, 400, r.content[:300])
        inv.refresh_from_db()
        self.assertEqual(inv.available, 10)
        self.assertEqual(inv.allocated, INT4_MAX - 1000)