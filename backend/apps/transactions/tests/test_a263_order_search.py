"""客户订单列表的单号搜索（A-263，2026-11-27）。

## 改前
`/orders` 页面**没有单号搜索**；全站搜索框只搜产品/方法/协议，填订单号回车会被带到
搜索页 ⇒ 客户无法按单号定位自己的订单（QA Batch 22 实测）。
后端 `OrderViewSet.get_queryset` 也不认 `search` 参数。

## 本文件钉三条
① `?search=` 能按 ``order_no`` / ``po_number`` 模糊命中；
② 搜索**只在本人可见范围内**收窄（不能搜出别人的单）；
③ 搜不到时返回空列表，而不是"忽略参数返回全量"。
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.transactions.models import Order


class CustomerOrderSearchTest(TestCase):
    def setUp(self):
        self.me = UserFactory(email='me@example.edu')
        self.other = UserFactory(email='other@example.edu')
        self.client = APIClient()
        self.client.force_authenticate(self.me)
        self.mine = Order.objects.create(
            user=self.me, order_no='ORD-20260710-003', po_number='PO-MINE-1',
            status=Order.Status.CONFIRMED, grand_total=10, subtotal=10,
            shipping_name='Me', shipping_address='Addr')
        self.others = Order.objects.create(
            user=self.other, order_no='ORD-20260710-999', po_number='PO-OTHER-9',
            status=Order.Status.CONFIRMED, grand_total=10, subtotal=10,
            shipping_name='Other', shipping_address='Addr')

    def _ids(self, **params):
        r = self.client.get('/api/v1/orders/', params)
        self.assertEqual(r.status_code, 200, r.content[:300])
        return [row['id'] for row in r.json()['data']]

    def test_search_by_order_no(self):
        self.assertEqual(self._ids(search='20260710-003'), [self.mine.id])

    def test_search_by_po_number(self):
        self.assertEqual(self._ids(search='PO-MINE'), [self.mine.id])

    def test_search_cannot_reach_other_peoples_orders(self):
        self.assertEqual(self._ids(search='PO-OTHER'), [])
        self.assertEqual(self._ids(search='20260710-999'), [])

    def test_unknown_term_returns_empty_not_everything(self):
        """★ 关键：参数被忽略而返回全量是最坏的"假搜索"。"""
        self.assertEqual(self._ids(search='NO-SUCH-ORDER'), [])
