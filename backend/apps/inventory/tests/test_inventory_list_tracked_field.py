"""库存列表必须暴露 `is_stock_tracked` —— A-260（2026-11-18 / S4）。

## 缺口是什么
`POST /inventory/track/ {tracked: false}` 只翻 `SKU.is_stock_tracked`，**不动 Inventory 行**。
于是脱管成功后：

  · 那一行仍然出现在库存台表格里（`Inventory` 行还在）；
  · 长得和普通库存行一模一样 —— 只是 `available=0`；
  · 运营看不出它已经**退出缺货校验**（等价于"按需生产/不限量"）。

前端要渲染 `Tracked: Yes/No` 并对未纳管行置灰，就必须能在列表响应里拿到这个布尔值。
改动前 `InventoryListSerializer.Meta.fields` 里没有它，前端**无从判断**，只能猜。

## 为什么单列一个测试文件
这是**跨 app 的字段契约**（inventory 的序列化器读 commerce 的 `SKU.is_stock_tracked`），
最容易在后续重构里被"顺手删掉"而没有任何测试变红。这里把它钉死，并顺带钉住
「脱管后行不消失」这个反直觉行为 —— 它是前端"标 No 而不是删行"的前提。

## 铁律 14 影响面（改序列化器前已全仓 grep）
`InventoryListSerializer` 的四个消费方：list / retrieve（`InventoryDetailSerializer` 继承）/
`InventoryReceiptView` / `InventoryAdjustView`。本次是**纯追加字段**，既有键一个不动。
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User, Organization
from apps.commerce.models import Product, SKU
from apps.inventory.models import Inventory


class InventoryListTrackedFieldTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Lab', org_type='academic')
        self.proc = User.objects.create_user(
            username='inv_lf_proc', password='x', organization=self.org, role='procurement')
        product = Product.objects.create(name='Reagent', slug='reagent-inv-lf')
        self.sku = SKU.objects.create(
            product=product, sku_code='SKU-INV-LF', price=Decimal('10.00'))
        self.client = APIClient()
        self.client.force_authenticate(user=self.proc)

    def _row(self):
        r = self.client.get('/api/v1/inventory/')
        self.assertEqual(r.status_code, 200, r.content[:300])
        rows = [x for x in r.json()['data'] if x['sku_code'] == self.sku.sku_code]
        self.assertEqual(len(rows), 1, f'应恰好一行，实际 {rows}')
        return rows[0]

    def test_list_exposes_is_stock_tracked_true(self):
        """已纳管 ⇒ True。"""
        SKU.objects.filter(pk=self.sku.pk).update(is_stock_tracked=True)
        Inventory.objects.create(sku=self.sku, location='MAIN', available=3)
        row = self._row()
        self.assertIn('is_stock_tracked', row, '★ 列表没暴露 is_stock_tracked，前端无法渲染 Tracked 列')
        self.assertIs(row['is_stock_tracked'], True)

    def test_untracked_row_is_still_listed_with_flag_false(self):
        """★ 核心：脱管后 **行不消失**，只是标记变 False。

        这是前端"标 No + 置灰"而不是"删除行"的依据。行若消失，运营会以为
        数据被删了（这正是 QA 报 A-260 时的直觉反应）。
        """
        SKU.objects.filter(pk=self.sku.pk).update(is_stock_tracked=True)
        inv = Inventory.objects.create(sku=self.sku, location='MAIN', available=0)

        r = self.client.post('/api/v1/inventory/track/',
                             {'sku_id': self.sku.id, 'tracked': False}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])

        row = self._row()
        self.assertEqual(row['id'], inv.pk, '★ 脱管后库存行消失了 —— 后端行为变了，前端假设失效')
        self.assertIs(row['is_stock_tracked'], False)

    def test_detail_also_carries_the_flag(self):
        """详情走 `InventoryDetailSerializer(InventoryListSerializer)` 继承，必须同样有。"""
        SKU.objects.filter(pk=self.sku.pk).update(is_stock_tracked=False)
        inv = Inventory.objects.create(sku=self.sku, location='EU', available=0)
        r = self.client.get(f'/api/v1/inventory/{inv.pk}/')
        self.assertEqual(r.status_code, 200, r.content[:300])
        data = r.json()['data']
        self.assertIn('is_stock_tracked', data)
        self.assertIs(data['is_stock_tracked'], False)

    def test_receipt_response_also_carries_the_flag(self):
        """入库响应复用同一个序列化器 ⇒ 入库即 True（自动纳管）必须立刻体现在返回值里。"""
        r = self.client.post('/api/v1/inventory/receipt/', {
            'sku_id': self.sku.id, 'location': 'MAIN', 'quantity': 5, 'reason': 'test receipt',
        }, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertIn('is_stock_tracked', r.json()['data'])
        self.assertIs(r.json()['data']['is_stock_tracked'], True)
