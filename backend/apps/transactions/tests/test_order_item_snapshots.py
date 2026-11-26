"""A-080 止损：OrderItem 商品标识快照。

## 背景（生产实测 2026-11-26）
89 行明细里 **32 行（36%）的 `sku_id` 与 `product_id` 同时为 NULL** ——
涉及 16 单、合计 7,730,065.00（占全库订单总额 99%）。那 32 行已无法恢复。

本文件钉住三件止损措施：
① 新建明细自动写快照（放在 `save()` 里，覆盖全部创建点）
② 序列化器**快照优先**：SKU/Product 被删后，历史明细仍能读出"卖的是什么"
③ 删 SKU 前**先冻结引用它的明细快照**，再删（而不是禁止删除）
④ 回填命令必须**不改 subtotal**（历史行可能有折扣，`save()` 会把它重算掉）
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Organization
from apps.commerce.models import Product, SKU
from apps.transactions.api.v1.serializers import OrderItemSerializer
from apps.transactions.models import Order, OrderItem

User = get_user_model()


def _setup(status=Order.Status.CONFIRMED):
    org = Organization.objects.create(name='SnapOrg', org_type='academic')
    user = User.objects.create_user(
        username='snap_user', email='snap@lab.edu', password='x', organization=org)
    product = Product.objects.create(
        name='Snap Reagent', slug='snap-reagent', catalog_no='SC-SNAP')
    sku = SKU.objects.create(
        product=product, sku_code='SC-SNAP-1', price=Decimal('100.00'),
        pack_size='10 µL', concentration='100 mM')
    order = Order.objects.create(
        user=user, organization=org, order_no='ORD-SNAP-1',
        po_number=None, status=status)
    return order, product, sku


class OrderItemSnapshotFillTest(TestCase):
    """① 新建即写快照"""

    def test_create_fills_all_three_snapshots(self):
        order, product, sku = _setup()
        it = OrderItem.objects.create(
            order=order, product=product, sku=sku, quantity=2,
            unit_price=Decimal('100.00'))
        it.refresh_from_db()
        self.assertEqual(it.sku_code_snapshot, 'SC-SNAP-1')
        self.assertEqual(it.product_name_snapshot, 'Snap Reagent')
        self.assertEqual(it.sku_spec_snapshot, '10 µL · 100 mM')

    def test_snapshot_not_overwritten_on_resave(self):
        """已有快照不能被主数据的后续改动带跑 —— 快照记的是**下单当时**的值。"""
        order, product, sku = _setup()
        it = OrderItem.objects.create(
            order=order, product=product, sku=sku, quantity=1,
            unit_price=Decimal('100.00'))
        sku.sku_code = 'SC-SNAP-RENAMED'
        sku.save(update_fields=['sku_code'])
        it.save()   # 触发 save() 里的快照逻辑
        it.refresh_from_db()
        self.assertEqual(it.sku_code_snapshot, 'SC-SNAP-1', '快照不该被改名影响')


class SerializerPrefersSnapshotTest(TestCase):
    """② 快照优先，实时回退"""

    def test_returns_snapshot_after_sku_deletion(self):
        """★ 核心：SKU 被删后，历史明细仍能读出编码与产品名。"""
        order, product, sku = _setup()
        it = OrderItem.objects.create(
            order=order, product=product, sku=sku, quantity=1,
            unit_price=Decimal('100.00'))
        sku.delete()          # 模拟运营删掉 SKU（SET_NULL 生效）
        it.refresh_from_db()
        self.assertIsNone(it.sku_id)

        data = OrderItemSerializer(it).data
        self.assertEqual(data['sku_code'], 'SC-SNAP-1', 'SKU 已删，但快照还应在')
        self.assertEqual(data['product_name'], 'Snap Reagent')
        self.assertEqual(data['pack_size'], '10 µL · 100 mM')

    def test_returns_snapshot_after_product_deletion(self):
        order, product, sku = _setup()
        it = OrderItem.objects.create(
            order=order, product=product, sku=sku, quantity=1,
            unit_price=Decimal('100.00'))
        product.delete()      # 级联删 SKU
        it.refresh_from_db()
        self.assertIsNone(it.product_id)

        data = OrderItemSerializer(it).data
        self.assertEqual(data['product_name'], 'Snap Reagent')
        self.assertEqual(data['sku_code'], 'SC-SNAP-1')

    def test_falls_back_to_live_when_no_snapshot(self):
        """存量行（还没回填）在主数据还在时，仍应正常显示 —— 不能因为加了快照就变空。"""
        order, product, sku = _setup()
        it = OrderItem.objects.create(
            order=order, product=product, sku=sku, quantity=1,
            unit_price=Decimal('100.00'))
        # 手工清空快照，模拟"加字段之前的存量行"
        OrderItem.objects.filter(pk=it.pk).update(
            sku_code_snapshot='', product_name_snapshot='', sku_spec_snapshot='')
        it.refresh_from_db()
        data = OrderItemSerializer(it).data
        self.assertEqual(data['sku_code'], 'SC-SNAP-1', '无快照时应回退到实时 SKU')
        self.assertEqual(data['product_name'], 'Snap Reagent')


class BackfillCommandTest(TestCase):
    """④ 回填命令：填快照但**绝不改 subtotal**"""

    def test_apply_fills_snapshot_and_keeps_subtotal(self):
        """★ 最关键的一条：历史行可能有折扣，subtotal ≠ unit_price × qty。
        如果回填走 `save()`，`OrderItem.save()` 里的
        `subtotal = unit_price * quantity` 会把它静默改写（铁律 15 禁止）。"""
        order, product, sku = _setup()
        it = OrderItem.objects.create(
            order=order, product=product, sku=sku, quantity=3,
            unit_price=Decimal('100.00'))
        # 制造"折扣后的历史金额"：3×100=300，但实收 250
        OrderItem.objects.filter(pk=it.pk).update(
            subtotal=Decimal('250.00'),
            sku_code_snapshot='', product_name_snapshot='', sku_spec_snapshot='')
        it.refresh_from_db()
        self.assertEqual(it.subtotal, Decimal('250.00'))

        call_command('backfill_order_item_snapshots', '--apply', verbosity=0)

        it.refresh_from_db()
        self.assertEqual(it.sku_code_snapshot, 'SC-SNAP-1', '快照应被回填')
        self.assertEqual(it.product_name_snapshot, 'Snap Reagent')
        self.assertEqual(it.subtotal, Decimal('250.00'),
                         '★ subtotal 必须原封不动 —— 回填不得重算历史金额')

    def test_dry_run_writes_nothing(self):
        order, product, sku = _setup()
        it = OrderItem.objects.create(
            order=order, product=product, sku=sku, quantity=1,
            unit_price=Decimal('100.00'))
        OrderItem.objects.filter(pk=it.pk).update(
            sku_code_snapshot='', product_name_snapshot='')
        call_command('backfill_order_item_snapshots', verbosity=0)
        it.refresh_from_db()
        self.assertEqual(it.sku_code_snapshot, '', 'dry-run（默认）不该写库')

    def test_reports_unfillable_rows(self):
        """sku 与 product 都被删的行要能统计出来（生产有 32 行这种）。"""
        order, product, sku = _setup()
        it = OrderItem.objects.create(
            order=order, product=product, sku=sku, quantity=1,
            unit_price=Decimal('100.00'))
        OrderItem.objects.filter(pk=it.pk).update(
            sku=None, product=None,
            sku_code_snapshot='', product_name_snapshot='', sku_spec_snapshot='')
        from io import StringIO
        out = StringIO()
        call_command('backfill_order_item_snapshots', '--apply', stdout=out)
        self.assertIn('无法回填', out.getvalue())
