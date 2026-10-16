"""★ 库存管理工具 API 测试（v4.1 DEV-1）。

覆盖：角色矩阵（匿名 401 / 客户 403 / procurement+admin 200）· 入库（新建/累加/非法入参）·
盘点调整（正常/超提取 400/ delta=0）· 既有 allocate 路径回归（行为不变 + 新增流水）· 流水查询。
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User, Organization
from apps.commerce.models import Product, SKU
from apps.inventory.models import Inventory, InventoryMovement
from apps.transactions.models import Order, OrderItem


class Base(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Lab', org_type='academic')
        self.proc = User.objects.create_user(
            username='inv_proc', password='x', organization=self.org, role='procurement')
        self.researcher = User.objects.create_user(
            username='inv_res', password='x', organization=self.org, role='researcher')
        self.admin = User.objects.create_user(
            username='inv_admin', password='x', organization=self.org, role='admin')
        product = Product.objects.create(name='Reagent', slug='reagent-inv')
        self.sku = SKU.objects.create(product=product, sku_code='SKU-INV-API', price=Decimal('10.00'))
        self.client = APIClient()

    def _auth(self, user):
        self.client.force_authenticate(user=user)


class RoleMatrixTest(Base):
    """内部工具：匿名 401 / 客户 403 / procurement+admin 200。"""

    def test_anon_get_401(self):
        r = self.client.get('/api/v1/inventory/')
        self.assertEqual(r.status_code, 401, r.content[:200])

    def test_researcher_get_403(self):
        self._auth(self.researcher)
        r = self.client.get('/api/v1/inventory/')
        self.assertEqual(r.status_code, 403, r.content[:200])

    def test_procurement_get_200(self):
        self._auth(self.proc)
        r = self.client.get('/api/v1/inventory/')
        self.assertEqual(r.status_code, 200, r.content[:200])

    def test_admin_get_200(self):
        self._auth(self.admin)
        r = self.client.get('/api/v1/inventory/')
        self.assertEqual(r.status_code, 200)

    def test_anon_receipt_401(self):
        r = self.client.post('/api/v1/inventory/receipt/', {
            'sku_id': 1, 'location': 'MAIN', 'quantity': 1, 'reason': 'x'}, format='json')
        self.assertEqual(r.status_code, 401)


class ReceiptTest(Base):
    def test_receipt_creates_row_and_movement(self):
        self._auth(self.proc)
        r = self.client.post('/api/v1/inventory/receipt/', {
            'sku_id': self.sku.id, 'location': 'MAIN', 'quantity': 5, 'reason': '首收入库',
        }, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        inv = Inventory.objects.get(sku=self.sku, location='MAIN')
        self.assertEqual(inv.available, 5)
        self.assertTrue(InventoryMovement.objects.filter(
            inventory=inv, kind=InventoryMovement.Kind.RECEIPT, delta_available=5,
            created_by=self.proc).exists())

    def test_receipt_accumulates_existing_row(self):
        Inventory.objects.create(sku=self.sku, location='MAIN', available=2)
        self._auth(self.proc)
        r = self.client.post('/api/v1/inventory/receipt/', {
            'sku_id': self.sku.id, 'location': 'MAIN', 'quantity': 3, 'reason': '补货',
        }, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Inventory.objects.filter(sku=self.sku).count(), 1)
        inv = Inventory.objects.get(sku=self.sku, location='MAIN')
        self.assertEqual(inv.available, 5)

    def test_receipt_rejects_zero_quantity(self):
        self._auth(self.proc)
        r = self.client.post('/api/v1/inventory/receipt/', {
            'sku_id': self.sku.id, 'location': 'MAIN', 'quantity': 0, 'reason': 'x'},
            format='json')
        self.assertEqual(r.status_code, 400)

    def test_receipt_rejects_blank_reason(self):
        self._auth(self.proc)
        r = self.client.post('/api/v1/inventory/receipt/', {
            'sku_id': self.sku.id, 'location': 'MAIN', 'quantity': 1, 'reason': '  '},
            format='json')
        self.assertEqual(r.status_code, 400)


class AdjustTest(Base):
    def setUp(self):
        super().setUp()
        self.inv = Inventory.objects.create(sku=self.sku, location='MAIN', available=10)

    def test_adjust_ok(self):
        self._auth(self.proc)
        r = self.client.post(f'/api/v1/inventory/{self.inv.id}/adjust/',
                             {'delta': -3, 'reason': '盘点'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.available, 7)
        self.assertTrue(InventoryMovement.objects.filter(
            inventory=self.inv, kind=InventoryMovement.Kind.ADJUST, delta_available=-3,
            created_by=self.proc).exists())

    def test_adjust_overdraw_400_and_unchanged(self):
        self._auth(self.proc)
        r = self.client.post(f'/api/v1/inventory/{self.inv.id}/adjust/',
                             {'delta': -99, 'reason': '盘点'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.available, 10)
        self.assertFalse(InventoryMovement.objects.filter(
            kind=InventoryMovement.Kind.ADJUST).exists())

    def test_adjust_delta_zero_400(self):
        self._auth(self.proc)
        r = self.client.post(f'/api/v1/inventory/{self.inv.id}/adjust/',
                             {'delta': 0, 'reason': 'x'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_adjust_researcher_403(self):
        self._auth(self.researcher)
        r = self.client.post(f'/api/v1/inventory/{self.inv.id}/adjust/',
                             {'delta': 1, 'reason': 'x'}, format='json')
        self.assertEqual(r.status_code, 403)


class AllocateMovementRegressionTest(Base):
    """既有 allocate 路径行为必须不变，且新增 ALLOCATE 流水（回归 DEV-1 对存量代码的触碰）。"""

    def test_allocate_writes_movement(self):
        researcher = User.objects.create_user(
            username='inv_buyer', password='x', organization=self.org, role='researcher')
        order = Order.objects.create(
            user=researcher, organization=self.org,
            order_no='ORD-MOV-1', po_number=None, status=Order.Status.CONFIRMED,
        )
        item = OrderItem.objects.create(
            order=order, sku=self.sku, quantity=2, unit_price=Decimal('10.00'))
        inv = Inventory.objects.create(sku=self.sku, location='MAIN', available=10)
        self._auth(self.proc)
        r = self.client.post(f'/api/v1/orders/{order.id}/allocate/', {
            'lines': [{'order_item_id': item.id, 'inventory_id': inv.id, 'quantity': 2}]},
            format='json')
        self.assertIn(r.status_code, (200, 201), r.content[:300])
        inv.refresh_from_db()
        self.assertEqual(inv.available, 8)
        self.assertTrue(InventoryMovement.objects.filter(
            inventory=inv, kind=InventoryMovement.Kind.ALLOCATE, delta_available=-2).exists())


class MovementListTest(Base):
    def test_procurement_can_list_movements(self):
        inv = Inventory.objects.create(sku=self.sku, location='MAIN', available=5)
        self._auth(self.proc)
        r = self.client.get('/api/v1/inventory/movements/', {'inventory_id': inv.id})
        self.assertEqual(r.status_code, 200)


class PrefetchRegressionTest(Base):
    """回归：Prefetch slice 曾致 500（空表测试盲区）—— 有数据行时 list/detail 必须正常。"""

    def test_list_with_rows_200(self):
        Inventory.objects.create(sku=self.sku, location='MAIN', available=3)
        self._auth(self.proc)
        r = self.client.get('/api/v1/inventory/')
        self.assertEqual(r.status_code, 200, r.content[:300])

    def test_detail_with_movements_200(self):
        inv = Inventory.objects.create(sku=self.sku, location='MAIN', available=3)
        InventoryMovement.objects.create(
            inventory=inv, kind=InventoryMovement.Kind.RECEIPT,
            delta_available=3, quantity=3, reason='seed')
        self._auth(self.proc)
        r = self.client.get(f'/api/v1/inventory/{inv.id}/')
        self.assertEqual(r.status_code, 200, r.content[:300])
        data = r.json().get('data') or {}
        self.assertEqual(len(data.get('movements') or []), 1)


class RetrieveMissingTest(Base):
    """★ v4.1 缺陷：GET /api/v1/inventory/{不存在的pk}/ 曾返回 500。

    与 InventoryAdjustView 上轮已修的 404 处理是同一类遗漏 —— adjust 路径
    加了 `if not Inventory.objects.filter(pk=pk).exists(): raise NotFound`，
    但 retrieve 路径（views.py:52-57）仍直接 `.get(pk=...)`，未捕获
    `Inventory.DoesNotExist`，导致生产实测 500。

    生产实测证据（容器内直连，admin 有效token）：
        GET /api/v1/inventory/1/  →  500 Internal Server Error
        Traceback: apps.inventory.api.v1.views:56 in retrieve
                    .get(pk=kwargs['pk'])
                    apps.inventory.models.Inventory.DoesNotExist
    """

    def test_detail_missing_pk_returns_404(self):
        self._auth(self.proc)
        r = self.client.get('/api/v1/inventory/999999/')
        self.assertEqual(r.status_code, 404, r.content[:300])

    def test_detail_missing_pk_as_admin_returns_404(self):
        self._auth(self.admin)
        r = self.client.get('/api/v1/inventory/999999/')
        self.assertEqual(r.status_code, 404, r.content[:300])

    def test_detail_missing_pk_anon_still_401(self):
        """不存在 pk 不应绕过认证 —— 匿名仍是 401，不是 404（防资源枚举）。"""
        r = self.client.get('/api/v1/inventory/999999/')
        self.assertEqual(r.status_code, 401, r.content[:300])

    def test_detail_existing_still_200(self):
        """回归：存在的 pk 必须仍然 200。"""
        inv = Inventory.objects.create(sku=self.sku, location='MAIN', available=7)
        self._auth(self.proc)
        r = self.client.get(f'/api/v1/inventory/{inv.id}/')
        self.assertEqual(r.status_code, 200, r.content[:300])
