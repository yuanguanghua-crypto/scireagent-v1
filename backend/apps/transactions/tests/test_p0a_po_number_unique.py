"""
P0-A 红/绿测试：Order.po_number 唯一约束缺陷。

缺陷：`Order.po_number` 声明为 `CharField(default='', null=True, unique=True)`。
`unique=True` 对空串 '' 同样生效 ⇒ 任何走`Order.objects.create()` 不显式传
po_number 的路径会落空串，第二个这样的订单必然 IntegrityError（HTTP 500）。
字段注释写着「存 NULL 而非空串以免撞唯一键」，但 default='' 与之矛盾。

修法：去掉 `unique=True`，改为 Meta 上的条件唯一约束
`UniqueConstraint(fields=['po_number'], condition=~Q(po_number=''))`
⇒ 非空 PO 号仍全局唯一；NULL 与空串行不进入唯一索引，可共存。

注意：本文件在修复前必须失败（红），修复后必须通过（绿）。
"""
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import Organization
from apps.commerce.models import Product, SKU
from apps.transactions.models import Order

User = get_user_model()


class PoNumberUniquenessTest(TestCase):
    """模型层：直接 Order.objects.create() 路径。"""

    def setUp(self):
        self.org = Organization.objects.create(name='Lab-A', org_type='academic')

    def test_two_orders_without_po_number_both_succeed(self):
        """回归核心缺陷：不传 po_number 连建2 单，第二单不得 IntegrityError。"""
        o1 = Order.objects.create(order_no='P0A-001', organization=self.org)
        o2 = Order.objects.create(order_no='P0A-002', organization=self.org)
        self.assertEqual(o1.pk, o2.pk - 1)
        for o in (o1, o2):
            self.assertIn(o.po_number, (None, ''))

    def test_explicit_none_twice_both_succeed(self):
        """显式传 None 两次 ⇒ 都应成功（NULL 不受唯一约束限制）。"""
        o1 = Order.objects.create(order_no='P0A-101', po_number=None)
        o2 = Order.objects.create(order_no='P0A-102', po_number=None)
        self.assertIsNone(o1.po_number)
        self.assertIsNone(o2.po_number)

    def test_duplicate_non_empty_po_number_rejected(self):
        """非空 PO 号仍必须唯一（业务硬要求，不能因修bug 而放松）。"""
        Order.objects.create(order_no='P0A-201', po_number='PO-UNIQ-001')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Order.objects.create(order_no='P0A-202', po_number='PO-UNIQ-001')
        self.assertEqual(
            Order.objects.filter(po_number='PO-UNIQ-001').count(), 1)

    def test_three_orders_mixed_po_number(self):
        """混合场景：空串 / None / 非空 各一单，重复的非空必须被拒。"""
        Order.objects.create(order_no='P0A-301')
        Order.objects.create(order_no='P0A-302', po_number=None)
        Order.objects.create(order_no='P0A-303', po_number='PO-MIX-001')
        self.assertEqual(Order.objects.count(), 3)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Order.objects.create(order_no='P0A-304', po_number='PO-MIX-001')


class PoNumberUniquenessApiTest(TestCase):
    """API 层：`OrderViewSet` 的孤儿写口已于 2026-10-21（F4）只读化。

    历史：本用例原本钉住「OrderViewSet.create 连建两单，第二单不因 po_number
    空串唯一约束而 500」。此后 F4 判定该 CRUD 写口是**孤儿写口**（前端只 GET，
    真实下单走 CheckoutView / POSubmitView），已整体 405 ⇒ 原断言不再适用。
    条件唯一约束本身的正确性由本文件上方 `PoNumberUniquenessTest` 的**模型层**
    用例（P0A-201..304）继续覆盖，未丢失。
    现在改为钉住「写口不会再被打开」。
    """

    def setUp(self):
        from rest_framework.test import APIClient
        self.org = Organization.objects.create(name='Lab-B', org_type='academic')
        self.user = User.objects.create_user(
            username='p0a_api', email='p0a_api@example.com', password='x',
            role='researcher', organization=self.org,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        product = Product.objects.create(name='ReagentA', slug='reagent-a')
        self.sku = SKU.objects.create(
            product=product, sku_code='SKU-P0A-001', price='10.00')

    def test_viewset_write_is_closed(self):
        payload = {
            'order_no': 'P0A-API-001',
            'payment_method': 'purchase_order',
            'items': [{'sku_id': self.sku.id, 'quantity': 1, 'unit_price': '10.00'}],
        }
        r1 = self.client.post('/api/v1/orders/', payload, format='json')
        self.assertEqual(r1.status_code, 405, r1.content[:400])
        self.assertEqual(Order.objects.filter(order_no__startswith='P0A-API').count(), 0)