"""F4 回归 — POST /api/v1/orders/ 是孤儿写口：可造 `user=NULL` 孤儿订单。

修复前缺陷（已核实）：
- `OrderViewSet` 是 `ModelViewSet`，`get_permissions()` 对非 list/retrieve 返回
  `IsAuthenticated`，但**无 `perform_create`**；`Order.user` 是 `null=True`
  ⇒ 登录用户可造 `user=NULL` 的孤儿单（谁都不拥有、审核台永远查不到）。
- `order_no` 在 `OrderListSerializer` 里**不是 read_only**，`unique=True` 且无默认值
  ⇒ 不传就 `IntegrityError` → **500**。
- 还能顺手改 `payment_method` / `po_number` / `currency`。

已核实：前端对 `/orders/` **只有 GET**（`api/orders.js`、`api/poPortal.js`、
`api/adminPo.js` 全是 `http.get`，全仓无 `post('/orders/'`）。真实下单走
`CheckoutView` / `POSubmitView` ⇒ 本 CRUD 的写口是**孤儿写口**，只读化零功能损失。

本文件钉住只读化后的契约：
1. 登录 POST → 405
2. 登录 PATCH → 405 且库中订单未被改动
3. 登录 DELETE → 405 且订单仍存在
4. 匿名 GET → 200 且 data == []（守住既有匿名空列表契约）
5. 登录 GET → 200 且只看到自己的单（守住行级隔离）

注意：DRF `ModelViewSet.dispatch()` 先 `check_permissions()` 再查方法
⇒ 匿名写仍返回 401/403（非 405），故本文件只用**登录用户**验证 405。
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.accounts.models import Organization
from apps.transactions.models import Order

User = get_user_model()


class OrderViewSetReadonlyTests(APITestCase):
    def setUp(self):
        self.url = '/api/v1/orders/'
        self.org = Organization.objects.create(name='Lab A', org_type='academic')
        self.me = User.objects.create_user(
            username='me', password='x', role='researcher', organization=self.org)
        self.other = User.objects.create_user(
            username='other', password='x', role='researcher', organization=self.org)
        self.mine = Order.objects.create(
            user=self.me, organization=self.org, order_no='ORD-MINE-001',
            status='confirmed', grand_total=Decimal('10.00'))
        self.theirs = Order.objects.create(
            user=self.other, organization=self.org, order_no='ORD-OTHER-001',
            status='confirmed', grand_total=Decimal('99.00'))
        self.orphan_target = self.mine  # 被 PATCH/DELETE 的目标

    # ── 1. POST → 405（修复前 201，且造出 user=NULL 孤儿单）──
    def test_post_returns_405(self):
        self.client.force_authenticate(self.me)
        before = Order.objects.count()
        resp = self.client.post(self.url, {
            'order_no': 'ORD-INJECTED-001',
            'status': 'confirmed',
            'payment_method': 'po',
        }, format='json')
        self.assertEqual(resp.status_code, 405, resp.content[:300])
        self.assertEqual(Order.objects.count(), before, '405 不得落库')
        self.assertFalse(Order.objects.filter(order_no='ORD-INJECTED-001').exists())

    # ── 2. PATCH → 405 且未被改动 ──
    def test_patch_returns_405_and_no_write(self):
        self.client.force_authenticate(self.me)
        resp = self.client.patch(
            f'{self.url}{self.orphan_target.id}/',
            {'status': 'cancelled', 'grand_total': '0.01'}, format='json')
        self.assertEqual(resp.status_code, 405, resp.content[:300])
        fresh = Order.objects.get(pk=self.orphan_target.pk)
        self.assertEqual(fresh.status, 'confirmed')
        self.assertEqual(fresh.grand_total, Decimal('10.00'))

    # ── 3. DELETE → 405 且订单仍在 ──
    def test_delete_returns_405_and_order_survives(self):
        self.client.force_authenticate(self.me)
        resp = self.client.delete(f'{self.url}{self.orphan_target.id}/')
        self.assertEqual(resp.status_code, 405, resp.content[:300])
        self.assertTrue(Order.objects.filter(pk=self.orphan_target.pk).exists())

    # ── 4. 匿名 GET → 200 空列表（既有契约，不许动）──
    def test_anonymous_list_is_empty(self):
        self.client.force_authenticate(None)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data'], [])

    # ── 5. 登录 GET → 只看自己的单（行级隔离）──
    def test_authenticated_list_only_own_orders(self):
        self.client.force_authenticate(self.me)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        ids = [row['id'] for row in resp.json()['data']]
        self.assertIn(self.mine.id, ids)
        self.assertNotIn(self.theirs.id, ids)
