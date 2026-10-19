"""安全加固：RFQ ``items`` 数量上限 + ``create()`` 事务原子性。

背景（已实测的漏洞）：
- ``QuoteRequestItemSerializer`` 的 4 个字段全部可缺省 ⇒ ``{}`` 是合法 item；
- ``items`` 无 ``max_length`` ⇒ ``[{}] * 50000`` 可通过校验（0.26s）；
- ``create()`` 逐条 insert 且无事务 ⇒ 超时被杀后已写入的明细不回滚。

本文件按 TDD 先写红：上限应为 50，超限返回 400 且不落库。
"""
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.commerce.tests.factories import ProductFactory
from apps.quotes.models import QuoteRequest, QuoteRequestItem

URL = '/api/v1/quote-requests/'


class QuoteRequestItemsLimitTest(TestCase):
    """items 数量上限。"""

    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory()

    def _payload(self, count):
        return {
            'contact_name': 'Dr. Lim',
            'contact_email': 'lim@lab.edu',
            'items': [
                {'product_id': self.product.id, 'quantity': 1}
                for _ in range(count)
            ],
        }

    def test_limit_constant_is_50(self):
        """上限必须是模块级命名常量 50。"""
        from apps.quotes.api.v1.serializers import MAX_QUOTE_REQUEST_ITEMS

        self.assertEqual(MAX_QUOTE_REQUEST_ITEMS, 50)

    def test_51_items_rejected_and_nothing_persisted(self):
        """51 条 → 400，且 QuoteRequest / QuoteRequestItem 都不新增行。"""
        response = self.client.post(URL, self._payload(51), format='json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(QuoteRequest.objects.count(), 0)
        self.assertEqual(QuoteRequestItem.objects.count(), 0)

    def test_50_items_accepted(self):
        """50 条 → 201（边界值不因长度报错）。"""
        response = self.client.post(URL, self._payload(50), format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(QuoteRequest.objects.count(), 1)
        self.assertEqual(QuoteRequestItem.objects.count(), 50)

    def test_1_item_still_works(self):
        """正常 1 条 → 201，行为不变。"""
        response = self.client.post(URL, self._payload(1), format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(QuoteRequest.objects.count(), 1)
        self.assertEqual(QuoteRequestItem.objects.count(), 1)

    def test_empty_items_still_rejected(self):
        """空列表 → 400（既有 validate_items 行为不得回归）。"""
        response = self.client.post(URL, self._payload(0), format='json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(QuoteRequest.objects.count(), 0)

    def test_missing_items_still_rejected(self):
        """缺失 items → 400（既有必填行为不得回归）。"""
        payload = self._payload(1)
        payload.pop('items')
        response = self.client.post(URL, payload, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(QuoteRequest.objects.count(), 0)


class QuoteRequestCreateAtomicityTest(TestCase):
    """create() 必须整体原子：明细中途失败时不能留下"半个询价单"。"""

    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory()

    def _payload(self, count):
        return {
            'contact_name': 'Dr. Atomic',
            'contact_email': 'atomic@lab.edu',
            'items': [
                {'product_id': self.product.id, 'quantity': 1}
                for _ in range(count)
            ],
        }

    def test_create_rolls_back_when_item_insert_fails(self):
        """第 2 条明细写入抛异常 → QuoteRequest 也不得残留。"""
        original_create = QuoteRequestItem.objects.create
        calls = {'n': 0}

        def flaky_create(**kwargs):
            calls['n'] += 1
            if calls['n'] == 2:
                raise RuntimeError('boom: simulated item insert failure')
            return original_create(**kwargs)

        with patch.object(
            QuoteRequestItem.objects, 'create', side_effect=flaky_create
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(URL, self._payload(3), format='json')

        self.assertEqual(QuoteRequest.objects.count(), 0)
        self.assertEqual(QuoteRequestItem.objects.count(), 0)
