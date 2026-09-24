"""★ 权限收紧回归（2026-09-24，③④ 批）。

背景：项目**未设** `DEFAULT_PERMISSION_CLASSES` ⇒ view 不写 `permission_classes` 就落到
DRF 默认 `AllowAny`。`transactions` 的 Order / Quote / Wishlist 三个 viewset 此前属"隐式公开"，
其中两条已实测为**实锤缺陷**：

  1. `POST /api/v1/wishlist/`：`Wishlist.user` 是 NOT NULL，而 `WishlistSerializer` 不含 `user`
     ⇒ 匿名（乃至任何）创建都 `IntegrityError` ⇒ **HTTP 500**（不是 400，也不是 401）。
  2. `POST /api/v1/orders/`：`OrderListSerializer` 的 `status` / `grand_total` 当时可写
     ⇒ 匿名可造出「`status=completed`、`grand_total=0.01`」的订单。

修法：**写要求登录**（与真实下单路径 `CheckoutView` / `POSubmitView` 的 `IsAuthenticated` 一致），
**读维持原契约**（匿名 GET → 200 空列表，`get_queryset()` 已 `.none()`），
并把这两个字段改为服务端决定（`read_only`）。

本文件同时锁住"读契约不许被误伤"这一反向约束 —— 一刀切 `IsAuthenticated` 会让
既有的 `test_list_unauthenticated_returns_empty` 变红，故必须逐条守住。
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.transactions.models import Order, Wishlist
from apps.transactions.tests.factories import WishlistFactory


def _unwrap(payload):
    """兼容 EnvelopeRenderer 的 `{success,data,meta}` 与裸列表两种形态。"""
    if isinstance(payload, dict) and 'data' in payload:
        return payload['data']
    return payload


class AnonymousWriteDeniedTest(TestCase):
    """匿名写必须被权限层拦下 —— 且**不能再是 500**。"""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=None)

    def test_anon_post_wishlist_is_401_not_500(self):
        """原缺陷 ①：此前落到 `IntegrityError` ⇒ 500；修复后应在权限层就断。"""
        resp = self.client.post('/api/v1/wishlist/', {'name': 'anon-list'}, format='json')
        self.assertEqual(resp.status_code, 401, resp.content[:300])
        self.assertFalse(Wishlist.objects.filter(name='anon-list').exists())

    def test_anon_post_order_denied_and_writes_nothing(self):
        """原缺陷 ②：此前匿名可造订单；修复后既拦权限，也不落库。"""
        resp = self.client.post('/api/v1/orders/', {
            'order_no': 'ORD-ANON-1', 'status': 'completed', 'grand_total': '0.01',
        }, format='json')
        self.assertEqual(resp.status_code, 401, resp.content[:300])
        self.assertFalse(Order.objects.filter(order_no='ORD-ANON-1').exists())

    def test_anon_post_quote_denied(self):
        resp = self.client.post('/api/v1/quotes/', {'quote_no': 'QT-ANON-1'}, format='json')
        self.assertEqual(resp.status_code, 401, resp.content[:300])


class AnonymousReadContractUnchangedTest(TestCase):
    """既有公开读契约：匿名 GET 一律 200（空列表），不得被收紧误伤。"""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=None)

    def test_anon_get_orders_200(self):
        self.assertEqual(self.client.get('/api/v1/orders/').status_code, 200)

    def test_anon_get_quotes_200(self):
        self.assertEqual(self.client.get('/api/v1/quotes/').status_code, 200)

    def test_anon_get_wishlist_200(self):
        self.assertEqual(self.client.get('/api/v1/wishlist/').status_code, 200)

    def test_anon_get_wishlist_returns_empty_even_if_rows_exist(self):
        WishlistFactory()  # 属于某个真实用户
        body = _unwrap(self.client.get('/api/v1/wishlist/').json())
        self.assertEqual(len(body), 0)


class OrderServerControlledFieldsTest(TestCase):
    """`status` / `grand_total` 属服务端字段：客户端传值必须被**忽略**（不是报错）。"""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_client_cannot_forge_status_and_grand_total(self):
        resp = self.client.post('/api/v1/orders/', {
            'order_no': 'ORD-FORGE-1',
            'status': 'completed',
            'grand_total': '0.01',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content[:300])
        order = Order.objects.get(order_no='ORD-FORGE-1')
        self.assertEqual(order.status, 'draft')          # 回落到模型默认 DRAFT
        self.assertEqual(order.grand_total, Decimal('0'))

    def test_retrieve_still_exposes_both_fields(self):
        """改 `read_only` 不得把字段从输出里删掉（前端列表要显示）。"""
        order = Order.objects.create(
            order_no='ORD-SHOW-1', user=self.user, grand_total=Decimal('12.34'),
        )
        body = _unwrap(self.client.get(f'/api/v1/orders/{order.id}/').json())
        self.assertIn('status', body)
        self.assertIn('grand_total', body)


class WishlistOwnershipTest(TestCase):
    """登录用户创建收藏：不再 500，且归属由服务端强制为 `request.user`。"""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)

    def test_authenticated_create_succeeds_and_sets_owner(self):
        resp = self.client.post('/api/v1/wishlist/', {'name': 'My List'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content[:300])
        wl = Wishlist.objects.get(name='My List')
        self.assertEqual(wl.user_id, self.user.id)

    def test_client_cannot_forge_owner(self):
        """serializer 本就不含 `user`；即便客户端塞进去也不得生效。"""
        other = UserFactory()
        resp = self.client.post(
            '/api/v1/wishlist/', {'name': 'Sneaky', 'user': other.id}, format='json'
        )
        self.assertEqual(resp.status_code, 201, resp.content[:300])
        self.assertEqual(Wishlist.objects.get(name='Sneaky').user_id, self.user.id)

    def test_authenticated_list_only_own(self):
        WishlistFactory(user=self.user)
        WishlistFactory(user=UserFactory())
        body = _unwrap(self.client.get('/api/v1/wishlist/').json())
        self.assertEqual(len(body), 1)
