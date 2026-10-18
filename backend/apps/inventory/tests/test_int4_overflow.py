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
from apps.inventory.models import Inventory
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