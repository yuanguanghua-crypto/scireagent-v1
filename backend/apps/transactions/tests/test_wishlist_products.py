"""★ Wishlist 产品读写（2026-10-19）。

背景：`WishlistSerializer` 此前**只有 `id/name/product_count/created_at`**，
`Wishlist.products`（M2M）**既不可读也不可写** ⇒ 前端就算做了「收藏」按钮，
也没有任何端点能往收藏夹里增/删产品（只能靠 Django admin）。这是「Wishlist 无前端」的真根因。

契约（本文件锁住）：
- 读：`products` 内嵌 `ProductListSerializer`（复用 commerce 的列表序列化器，非精简版）
- 写：`product_ids`（`PrimaryKeyRelatedField(many=True, source='products')`），
  **整体替换**语义 —— `PATCH {"product_ids": [1,2]}` ⇒ 收藏恰好是 {1,2}，多出的被移除；
  `[]` ⇒ 清空；**不传该键** ⇒ 产品保持不变（`required=False`）。
- 校验：`queryset=Product.objects.filter(archived=False)` ⇒ 归档产品不可收藏（400，且不落库）。
- 权限口径不变：匿名读 200 空列表；匿名写 401/403。
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory
from apps.transactions.models import Wishlist
from apps.transactions.tests.factories import WishlistFactory

URL = '/api/v1/wishlist/'


def _unwrap(payload):
    """兼容 EnvelopeRenderer 的 `{success,data,meta}` 与裸对象两种形态。"""
    if isinstance(payload, dict) and 'data' in payload:
        return payload['data']
    return payload


def _product_ids_of(wishlist):
    return set(wishlist.products.values_list('id', flat=True))


class WishlistProductWriteTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.p1 = ProductFactory()
        self.p2 = ProductFactory()
        self.p3 = ProductFactory()

    # ── 1. 创建并带产品 ──
    def test_create_with_product_ids(self):
        resp = self.client.post(
            URL, {'name': 'X', 'product_ids': [self.p1.id, self.p2.id]}, format='json'
        )
        self.assertEqual(resp.status_code, 201, resp.content[:400])
        data = _unwrap(resp.json())
        self.assertEqual(data['product_count'], 2)
        self.assertEqual(len(data['products']), 2)
        self.assertEqual({p['id'] for p in data['products']}, {self.p1.id, self.p2.id})
        # 内嵌产品必须是可用的列表形态（至少 id/name），前端要能直接渲染
        for p in data['products']:
            self.assertIn('name', p)
            self.assertIn('catalog_no', p)

        wl = Wishlist.objects.get(name='X')
        self.assertEqual(wl.user_id, self.user.id)  # 归属仍由服务端决定
        self.assertEqual(_product_ids_of(wl), {self.p1.id, self.p2.id})

    # ── 2. 整体替换 ──
    def test_patch_replaces_products_entirely(self):
        wl = WishlistFactory(user=self.user)
        wl.products.add(self.p1, self.p2)
        self.assertEqual(wl.products.count(), 2)

        resp = self.client.patch(
            f'{URL}{wl.id}/', {'product_ids': [self.p3.id]}, format='json'
        )
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        data = _unwrap(resp.json())
        self.assertEqual(data['product_count'], 1)
        self.assertEqual([p['id'] for p in data['products']], [self.p3.id])

        wl.refresh_from_db()
        self.assertEqual(_product_ids_of(wl), {self.p3.id})  # 原来的 p1/p2 已移除

    # ── 3. 移空 ──
    def test_patch_empty_list_clears_products(self):
        wl = WishlistFactory(user=self.user)
        wl.products.add(self.p1, self.p2)

        resp = self.client.patch(f'{URL}{wl.id}/', {'product_ids': []}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        data = _unwrap(resp.json())
        self.assertEqual(data['product_count'], 0)
        self.assertEqual(data['products'], [])
        wl.refresh_from_db()
        self.assertEqual(wl.products.count(), 0)

    # ── 4. 不含 product_ids ⇒ 产品不变（required=False） ──
    def test_patch_without_product_ids_keeps_products(self):
        wl = WishlistFactory(user=self.user, name='Old')
        wl.products.add(self.p1, self.p2)

        resp = self.client.patch(f'{URL}{wl.id}/', {'name': 'Renamed'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content[:400])
        data = _unwrap(resp.json())
        self.assertEqual(data['name'], 'Renamed')
        self.assertEqual(data['product_count'], 2)
        wl.refresh_from_db()
        self.assertEqual(wl.name, 'Renamed')
        self.assertEqual(_product_ids_of(wl), {self.p1.id, self.p2.id})

    # ── 5. 不能收藏已归档产品 ──
    def test_create_with_archived_product_is_400_and_not_persisted(self):
        archived = ProductFactory(archived=True)
        resp = self.client.post(
            URL, {'name': 'Archived list', 'product_ids': [archived.id]}, format='json'
        )
        self.assertEqual(resp.status_code, 400, resp.content[:400])
        self.assertFalse(Wishlist.objects.filter(name='Archived list').exists())

    def test_patch_with_archived_product_is_400_and_keeps_old_products(self):
        wl = WishlistFactory(user=self.user)
        wl.products.add(self.p1)
        archived = ProductFactory(archived=True)

        resp = self.client.patch(
            f'{URL}{wl.id}/', {'product_ids': [self.p2.id, archived.id]}, format='json'
        )
        self.assertEqual(resp.status_code, 400, resp.content[:400])
        wl.refresh_from_db()
        self.assertEqual(_product_ids_of(wl), {self.p1.id})  # 校验失败 ⇒ 整体不落库


class WishlistPermissionContractTest(TestCase):
    """既有权限口径不得回归（读 AllowAny / 写 IsAuthenticated）。"""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=None)
        self.p1 = ProductFactory()

    def test_anon_list_returns_200_empty(self):
        WishlistFactory()  # 属于某个真实用户
        resp = self.client.get(URL)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(_unwrap(resp.json()), [])

    def test_anon_retrieve_not_leaked(self):
        wl = WishlistFactory()
        wl.products.add(self.p1)
        resp = self.client.get(f'{URL}{wl.id}/')
        self.assertIn(resp.status_code, (403, 404))

    def test_anon_create_with_product_ids_is_denied(self):
        resp = self.client.post(
            URL, {'name': 'anon', 'product_ids': [self.p1.id]}, format='json'
        )
        self.assertIn(resp.status_code, (401, 403), resp.content[:400])
        self.assertFalse(Wishlist.objects.filter(name='anon').exists())

    def test_anon_patch_is_denied(self):
        wl = WishlistFactory()
        resp = self.client.patch(f'{URL}{wl.id}/', {'product_ids': []}, format='json')
        self.assertIn(resp.status_code, (401, 403), resp.content[:400])

    def test_anon_delete_is_denied(self):
        wl = WishlistFactory()
        resp = self.client.delete(f'{URL}{wl.id}/')
        self.assertIn(resp.status_code, (401, 403), resp.content[:400])
        self.assertTrue(Wishlist.objects.filter(id=wl.id).exists())
