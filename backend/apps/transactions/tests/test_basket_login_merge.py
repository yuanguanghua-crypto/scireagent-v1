"""P0-2 回归测试：登录后游客购物车必须合并进账户。

缺陷背景（实测）：
  匿名用户加购时，后端 `AddToBasketView` 按 `X-Session-Key` 把行写库
  （Basket.user=NULL），而 `BasketItemSerializer` 不输出 `_local` 字段。
  前端 `mergeLocalBasket` 旧实现按 `_local` 筛选 ⇒ 恒为空 ⇒ 从不调合并端点。
  登录后 `GET /basket` 切到 user 作用域 ⇒ 游客行不可见 ⇒ 商品"消失"。

这些用例锁定**后端已具备的能力**（合并端点可用 + 叠加语义 + 鉴权要求），
前端调用点由 frontend 侧一次性验证脚本覆盖（项目无前端单测框架）。
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.transactions.models import Basket


class BasketLoginMergeTest(TestCase):
    """游客 → 登录 的购物车合并契约。"""

    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory(name='P', status='active')
        self.sku = SKUFactory(product=self.product, sku_code='SKU-M1')
        self.user = UserFactory()
        self.skey = 'guest_merge_key'

    def _guest_add(self, qty, session_key=None):
        """模拟游客加购：API 成功 ⇒ 落在服务端 session_key 行上（无 _local）。"""
        return self.client.post(
            '/api/v1/basket/items',
            {'sku_id': self.sku.id, 'quantity': qty},
            HTTP_X_SESSION_KEY=session_key or self.skey,
            format='json',
        )

    def _guest_snapshot(self):
        """游客视角取到的行 —— 注意：不含 _local（这正是原缺陷的根因）。"""
        data = self.client.get(
            '/api/v1/basket', HTTP_X_SESSION_KEY=self.skey
        ).json()['data']
        return data['items']

    def test_guest_items_land_server_side_without_local_flag(self):
        """前提锁定：游客条目在服务端，且序列化结果**不带** _local。"""
        self._guest_add(3)
        items = self._guest_snapshot()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['quantity'], 3)
        self.assertNotIn('_local', items[0])
        row = Basket.objects.get(session_key=self.skey)
        self.assertIsNone(row.user)

    def test_guest_basket_invisible_after_login_until_merged(self):
        """缺陷现象：登录后按 user 取购物车，游客行不可见 ⇒ 看起来"消失"了。"""
        self._guest_add(3)
        self.client.force_authenticate(user=self.user)
        data = self.client.get('/api/v1/basket').json()['data']
        self.assertEqual(data['count'], 0, '合并前账户购物车应为空（这就是用户看到的现象）')

    def test_merge_endpoint_transfers_guest_items(self):
        """合并端点可用：游客条目合并进账户后，登录态可见。"""
        self._guest_add(3)
        payload = [{'sku_id': i['sku'], 'quantity': i['quantity']}
                   for i in self._guest_snapshot()]
        self.client.force_authenticate(user=self.user)
        resp = self.client.post('/api/v1/basket/merge', {'items': payload}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['merged'], 1)

        data = self.client.get('/api/v1/basket').json()['data']
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['items'][0]['quantity'], 3)

    def test_merge_is_additive_not_overwriting(self):
        """叠加语义：账户已有同 SKU 时，数量相加而非覆盖。"""
        Basket.objects.create(
            user=self.user, product=self.product, sku=self.sku, quantity=1
        )
        self.client.force_authenticate(user=self.user)
        self.client.post(
            '/api/v1/basket/merge',
            {'items': [{'sku_id': self.sku.id, 'quantity': 5}]},
            format='json',
        )
        item = self.client.get('/api/v1/basket').json()['data']['items'][0]
        self.assertEqual(item['quantity'], 6,'1 + 5 = 6，合并是叠加语义')

    def test_merge_requires_authentication(self):
        """鉴权要求：必须在 token 写入之后调用，否则 401。"""
        resp = self.client.post(
            '/api/v1/basket/merge',
            {'items': [{'sku_id': self.sku.id, 'quantity': 1}]},
            format='json',
        )
        self.assertEqual(resp.status_code, 401)

    def test_replaying_own_items_would_double_quantity(self):
        """⚠️ 记录一个已实测的危险：重复合并同一批行会翻倍。

        这正是前端必须只合并 `_guest` 条目、且成功后清除 session key 的原因
        （否则登出→再登录会二次合并）。

        这里先直接种一行账户行（数量 2），再把同样的内容合并两次 ⇒ 2→4→6，
        直观演示"叠加语义 + 重复回传 = 翻倍"。
        """
        self.client.force_authenticate(user=self.user)
        Basket.objects.create(
            user=self.user, product=self.product, sku=self.sku, quantity=2
        )
        payload = [{'sku_id': self.sku.id, 'quantity': 2}]
        self.client.post('/api/v1/basket/merge', {'items': payload}, format='json')
        after_one = self.client.get('/api/v1/basket').json()['data']['items'][0]['quantity']
        self.client.post('/api/v1/basket/merge', {'items': payload}, format='json')
        after_two = self.client.get('/api/v1/basket').json()['data']['items'][0]['quantity']
        self.assertEqual((after_one, after_two), (4, 6),
                         '重复合并同一批行 ⇒ 数量累加翻倍（前端必须只传游客行）')

    def test_merge_leaves_guest_session_rows_in_db(self):
        """记录当前后端行为：合并**不会**删除游客的 session_key 行。

        影响：合并成功后前端必须清掉 `scireagent_session_key`，否则同一批陈旧行
        仍可达（见 test_replaying_own_items_would_double_quantity）。
        """
        self._guest_add(1)
        payload = [{'sku_id': i['sku'], 'quantity': i['quantity']}
                   for i in self._guest_snapshot()]
        self.client.force_authenticate(user=self.user)
        self.client.post('/api/v1/basket/merge', {'items': payload}, format='json')

        orphans = Basket.objects.filter(
            session_key=self.skey, user__isnull=True
        ).count()
        self.assertEqual(orphans, 1, '后端不做级联清理，属已知残留（前端负责失效）')