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
from decimal import Decimal

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


class AdminOrderDateRangeAndProductSearchTest(TestCase):
    """A-162：`/admin/orders/` 的**日期区间**与**产品维度搜索**（销售报表明细用）。

    ## 为什么用业务日而不是 `created_at__date`
    生产 `TIME_ZONE=UTC`、`BUSINESS_TIME_ZONE=Asia/Shanghai`。直接按日期截断会把
    东八区 00:00–07:59 的订单算到前一天。这里用 `business_day_bounds` 换算成时间戳
    再比，与报表的归期口径一致。
    """

    def setUp(self):
        from apps.accounts.models import Organization, User
        self.admin = User.objects.create_user(
            username='a162_admin', password='x', email='a162@lab.edu',
            role='admin', is_staff=True,
        )
        self.org = Organization.objects.create(name='A162 Org', org_type='academic')
        self.user = User.objects.create_user(
            username='a162_user', password='x', email='u@lab.edu',
            organization=self.org, role='researcher',
        )
        from apps.commerce.models import Product, SKU
        self.p1 = Product.objects.create(name='Pseudo-UTP', slug='a162-p1', catalog_no='SC9001')
        self.p2 = Product.objects.create(name='Cy5-dUTP', slug='a162-p2', catalog_no='SC9002')
        self.s1 = SKU.objects.create(product=self.p1, sku_code='SC9001-1', price='10.00')
        self.s2 = SKU.objects.create(product=self.p2, sku_code='SC9002-1', price='20.00')
        self.client = APIClient()

    def _order(self, order_no, when, product=None, sku=None, lines=1):
        from django.utils import timezone
        from datetime import timedelta
        from apps.transactions.models import Order, OrderItem
        o = Order.objects.create(
            user=self.user, organization=self.org, order_no=order_no,
            status=Order.Status.CONFIRMED, grand_total=Decimal('10.00'),
        )
        Order.objects.filter(pk=o.pk).update(created_at=when)
        for _ in range(lines):
            OrderItem.objects.create(
                order=o, product=product or self.p1, sku=sku or self.s1,
                quantity=1, unit_price=Decimal('10.00'),
            )
        return o

    def _get(self, **params):
        self.client.force_authenticate(self.admin)
        return self.client.get('/api/v1/admin/orders/', params, format='json')

    def test_date_range_filters_orders(self):
        from django.utils import timezone
        from datetime import timedelta
        now = timezone.now()
        self._order('ORD-A162-IN', now - timedelta(days=1))
        self._order('ORD-A162-OUT', now - timedelta(days=40))
        day = (now - timedelta(days=1)).date().isoformat()
        r = self._get(created_from=day, created_to=day)
        self.assertEqual(r.status_code, 200)
        nos = [x['order_no'] for x in r.json()['data']]
        self.assertIn('ORD-A162-IN', nos)
        self.assertNotIn('ORD-A162-OUT', nos)

    def test_bad_date_returns_400(self):
        r = self._get(created_from='2026-13-99')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['meta']['error']['code'], 'BAD_DATE')

    def test_search_matches_product_name_and_catalog_no(self):
        from django.utils import timezone
        now = timezone.now()
        self._order('ORD-A162-P1', now, product=self.p1, sku=self.s1)
        self._order('ORD-A162-P2', now, product=self.p2, sku=self.s2)
        r1 = self._get(search='Pseudo')
        self.assertEqual([x['order_no'] for x in r1.json()['data']], ['ORD-A162-P1'])
        r2 = self._get(search='SC9002')
        self.assertEqual([x['order_no'] for x in r2.json()['data']], ['ORD-A162-P2'])

    def test_search_does_not_duplicate_multi_line_orders(self):
        """跨 items 的 JOIN 会产生重复行 ⇒ 必须 distinct（否则同一单出现多次、total 虚高）。"""
        from django.utils import timezone
        now = timezone.now()
        self._order('ORD-A162-MULTI', now, product=self.p1, sku=self.s1, lines=3)
        r = self._get(search='SC9001')
        rows = r.json()['data']
        self.assertEqual(len(rows), 1, f'一单三行只能出现一次，实际 {len(rows)} 行')
        self.assertEqual(r.json()['meta']['pagination']['count'], 1)
