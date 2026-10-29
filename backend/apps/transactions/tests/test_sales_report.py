# -*- coding: utf-8 -*-
"""销售报表口径（`ops/sales-report`）—— 2026-10-29。

报表的失效方式不是崩溃，而是**数字悄悄错**，而且没人能一眼发现：
  · 把报价单当成交 ⇒ GMV 虚高；
  · 把 pending 付款当实收 ⇒ 收款虚高；
  · 按 UTC 截日 ⇒ 东八区凌晨的单算到前一天；
  · USD 和 CNY 相加 ⇒ 得到一个没有意义的数。
所以每条口径都要有一条测试钉住。
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Organization, User
from apps.commerce.models import Product, SKU
from apps.transactions.models import Invoice, Order, PaymentRecord

URL = '/api/v1/ops/sales-report/'


class ReportBase(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Lab', org_type='academic')
        self.admin = User.objects.create_user(
            username='sr_admin', password='x', email='a@lab.edu',
            organization=self.org, role='admin', is_staff=True)
        self.res = User.objects.create_user(
            username='sr_res', password='x', email='r@lab.edu',
            organization=self.org, role='researcher')
        self.product = Product.objects.create(name='Pseudo-UTP', slug='pseudo-utp-sr')
        self.sku = SKU.objects.create(
            product=self.product, sku_code='SC9800-1', price=Decimal('100.00'))
        self.client = APIClient()
        self._n = 0

    def _order(self, status, total, currency='USD', days_ago=0, user=None):
        self._n += 1
        o = Order.objects.create(
            user=user or self.res,
            order_no=f'ORD-SR-{self._n}',
            status=status,
            grand_total=Decimal(str(total)),
            currency=currency,
        )
        if days_ago:
            Order.objects.filter(pk=o.pk).update(
                created_at=timezone.now() - timedelta(days=days_ago))
            o.refresh_from_db()
        return o

    def _payment(self, order, amount, status, currency='USD'):
        inv, _ = Invoice.objects.get_or_create(
            order=order,
            defaults={
                'invoice_no': f'INV-{order.order_no}',
                # due_date 是 NOT NULL：漏了会 IntegrityError，看起来像报表逻辑错
                'due_date': timezone.now().date() + timedelta(days=30),
            })
        return PaymentRecord.objects.create(
            invoice=inv, method=PaymentRecord.Method.WIRE,
            amount=Decimal(str(amount)), currency=currency, status=status)

    def _get(self, user=None, **params):
        self.client.force_authenticate(user=user or self.admin)
        return self.client.get(URL, params, format='json')

    def _summary(self, **params):
        r = self._get(**params)
        self.assertEqual(r.status_code, 200, r.content[:400])
        return r.json()['data']


class GmvScopeTest(ReportBase):
    def test_counts_only_sales_statuses(self):
        """报价流程与草稿不是成交，不能计入 GMV。"""
        self._order(Order.Status.CONFIRMED, '100')
        self._order(Order.Status.PAID, '200')
        # 下面这些都不算
        self._order(Order.Status.CANCELLED, '999')
        self._order(Order.Status.QUOTE_PENDING, '888')
        self._order(Order.Status.QUOTED, '777')
        self._order(Order.Status.QUOTE_ACCEPTED, '666')
        self._order(Order.Status.QUOTE_REJECTED, '555')
        self._order(Order.Status.DRAFT, '444')

        s = self._summary()['summary']
        self.assertEqual(Decimal(s['gmv']), Decimal('300.00'))
        self.assertEqual(s['order_count'], 2)

    def test_excludes_orders_outside_range(self):
        self._order(Order.Status.CONFIRMED, '100')
        self._order(Order.Status.CONFIRMED, '500', days_ago=60)

        today = timezone.now().date()
        s = self._summary(start=str(today - timedelta(days=7)),
                          end=str(today))['summary']
        self.assertEqual(Decimal(s['gmv']), Decimal('100.00'),
                         '60 天前的单不该落进近 7 天')

    def test_avg_order_value(self):
        self._order(Order.Status.CONFIRMED, '100')
        self._order(Order.Status.CONFIRMED, '200')
        self._order(Order.Status.CONFIRMED, '300')
        s = self._summary()['summary']
        self.assertEqual(Decimal(s['avg_order_value']), Decimal('200.00'))

    def test_empty_range_yields_zero_not_null(self):
        s = self._summary()['summary']
        self.assertEqual(Decimal(s['gmv']), Decimal('0.00'))
        self.assertEqual(s['order_count'], 0)
        self.assertEqual(Decimal(s['avg_order_value']), Decimal('0.00'),
                         '无订单时客单价应为 0，不是 null（前端会渲染成 0）')


class CollectedScopeTest(ReportBase):
    def test_only_verified_payments_count(self):
        o = self._order(Order.Status.PAID, '300')
        self._payment(o, '100', PaymentRecord.Status.VERIFIED)
        self._payment(o, '50', PaymentRecord.Status.PENDING)
        self._payment(o, '150', PaymentRecord.Status.REJECTED)

        s = self._summary()['summary']
        self.assertEqual(Decimal(s['paid_amount']), Decimal('100.00'),
                         '只有 verified 才是实收；pending 是待核、rejected 是无效')
        self.assertEqual(s['paid_count'], 1)

    def test_gmv_and_collected_are_independent(self):
        """GMV 含未付款，实收只算已付 —— 两个数本来就该不同。"""
        o = self._order(Order.Status.CONFIRMED, '500')
        self._payment(o, '200', PaymentRecord.Status.VERIFIED)
        s = self._summary()['summary']
        self.assertEqual(Decimal(s['gmv']), Decimal('500.00'))
        self.assertEqual(Decimal(s['paid_amount']), Decimal('200.00'))


class MultiCurrencyTest(ReportBase):
    def test_currencies_are_not_summed_together(self):
        self._order(Order.Status.CONFIRMED, '100', currency='USD')
        self._order(Order.Status.CONFIRMED, '700', currency='CNY')

        s = self._summary()['summary']
        self.assertEqual(len(s['by_currency']), 2, '必须分组返回，不能相加')
        by = {r['currency']: Decimal(r['gmv']) for r in s['by_currency']}
        self.assertEqual(by['USD'], Decimal('100.00'))
        self.assertEqual(by['CNY'], Decimal('700.00'))
        # 主展示币种 = GMV 最大的那个（CNY 700 > USD 100）
        self.assertEqual(s['primary_currency'], 'CNY')
        self.assertEqual(Decimal(s['gmv']), Decimal('700.00'))


class TrendTest(ReportBase):
    def test_trend_fills_empty_days(self):
        """补齐空白日：否则折线会"跳过"某天，看起来像连续增长。"""
        self._order(Order.Status.CONFIRMED, '100')
        today = timezone.now().date()
        start = str(today - timedelta(days=2))
        d = self._summary(start=start, end=str(today))
        self.assertEqual(len(d['trend']), 3, '3 天区间应返回 3 行，含 0 值日')
        self.assertEqual(d['trend'][-1]['date'], str(today))

    def test_rejects_absurdly_long_range(self):
        r = self._get(start='2000-01-01', end='2026-12-31')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['meta']['error']['code'], 'RANGE_TOO_LARGE')


class ParamsAndPermissionTest(ReportBase):
    def test_bad_date_is_400(self):
        r = self._get(start='2026-13-99')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['meta']['error']['code'], 'BAD_DATE')

    def test_end_before_start_is_400(self):
        r = self._get(start='2026-10-10', end='2026-10-01')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['meta']['error']['code'], 'BAD_RANGE')

    def test_anonymous_unauthorized(self):
        r = APIClient().get(URL)
        self.assertIn(r.status_code, (401, 403))

    def test_researcher_forbidden(self):
        r = self._get(user=self.res)
        self.assertEqual(r.status_code, 403, '销售报表是内部数据，研究员不该看到')


class TopListTest(ReportBase):
    def test_top_products_excludes_cancelled_orders(self):
        from apps.transactions.models import OrderItem

        ok = self._order(Order.Status.CONFIRMED, '200')
        bad = self._order(Order.Status.CANCELLED, '900')
        OrderItem.objects.create(order=ok, product=self.product, sku=self.sku,
                                 quantity=2, unit_price=Decimal('100.00'))
        OrderItem.objects.create(order=bad, product=self.product, sku=self.sku,
                                 quantity=9, unit_price=Decimal('100.00'))

        rows = self._summary()['top_products']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['quantity'], 2, '取消订单的行不能进 Top 产品')
        self.assertEqual(Decimal(rows[0]['amount']), Decimal('200.00'))
