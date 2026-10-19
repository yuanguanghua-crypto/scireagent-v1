"""安全加固：``X-Session-Key`` 长度校验。

背景：header 无长度校验，超过 ``Basket.session_key`` 的 ``max_length=100``
在 Postgres 上会撞 ``varchar(100)`` 抛异常 → 500。
SQLite 不强制长度，所以这里用显式断言覆盖，不依赖 DB 报错。

设计决策：超长一律 400（ValidationError），**不截断**（不同超长 key 前 N
字符相同会被截成同一个值 ⇒ 串号风险）；上限从模型字段读取，不硬编码。
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.transactions.models import Basket

URL = '/api/v1/basket/items'


class SessionKeyLengthTest(TestCase):
    """101 → 400；100 / 42 → 正常。"""

    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory()
        self.sku = SKUFactory(product=self.product)

    def _post(self, session_key):
        kwargs = {}
        if session_key is not None:
            kwargs['HTTP_X_SESSION_KEY'] = session_key
        return self.client.post(
            URL,
            {'sku_id': self.sku.id, 'quantity': 1},
            format='json',
            **kwargs,
        )

    def test_101_chars_rejected_with_400(self):
        """模型上限 100，101 字符 → 400（不是 500）。"""
        response = self._post('k' * 101)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Basket.objects.count(), 0)

    def test_100_chars_accepted(self):
        """恰好等于上限 100 → 正常建行。"""
        response = self._post('k' * 100)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            Basket.objects.filter(session_key='k' * 100).count(), 1
        )

    def test_42_chars_accepted(self):
        """前端真实值 ``guest_`` + uuid ≈ 42 字符 → 正常。"""
        key = 'guest_' + 'a' * 36
        self.assertEqual(len(key), 42)

        response = self._post(key)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Basket.objects.filter(session_key=key).count(), 1)

    def test_missing_header_still_returns_empty_string(self):
        """缺失 header → 既有行为：空串（端点返回 400 Session key required）。"""
        from apps.transactions.api.v1.basket_views import _get_session_key

        class _Request:
            headers = {}

        self.assertEqual(_get_session_key(_Request()), '')

        response = self._post(None)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Basket.objects.count(), 0)

    def test_overflow_key_not_truncated(self):
        """两个 100+ 相同前缀的 key 都必须被拒，不能截断成同一个值。"""
        prefix = 'guest_' + 'b' * 94  # 100 chars
        self.assertEqual(len(prefix), 100)

        first = self._post(prefix + 'X')
        second = self._post(prefix + 'Y')

        self.assertEqual(first.status_code, 400)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(Basket.objects.count(), 0)
