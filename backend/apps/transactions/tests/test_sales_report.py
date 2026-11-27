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


class AllTimeRangeTest(ReportBase):
    """A-163：`?all=1` = 全部历史。

    ## 为什么必须是独立开关，而不是"前端传一个很早的 start"
    后端对显式区间有硬上限 400 天（`RANGE_TOO_LARGE`，见 `TrendTest
    ::test_rejects_absurdly_long_range`）。那个守卫说的是"区间太长，请缩小"；
    "我要全部历史"是完全不同的诉求。第一版实现就是塞 `start=2000-01-01`，
    实测被**自己的守卫**打回 400 —— 所以这里改成显式开关，两条语义各自成立。
    """

    def test_all_covers_orders_outside_default_range(self):
        """默认区间是"本月"，100 天前的单不在默认区间内，但 all=1 要算进来。"""
        self._order(Order.Status.CONFIRMED, '100', days_ago=100)
        default = self._summary()
        self.assertEqual(default['summary']['order_count'], 0,
                         '默认口径是本月，不该含 100 天前的单')

        d = self._summary(all=1)
        self.assertEqual(d['summary']['order_count'], 1)
        self.assertTrue(d['range']['all_time'])
        self.assertFalse(d['range']['trend_truncated'])

    def test_all_truncates_trend_but_keeps_full_totals(self):
        """跨度 > 400 天：趋势裁到最近 400 天，KPI/汇总仍按全区间。"""
        self._order(Order.Status.CONFIRMED, '100', days_ago=500)
        d = self._summary(all=1)
        # 汇总必须含 500 天前那单（否则"全部历史"名不副实）
        self.assertEqual(d['summary']['order_count'], 1)
        self.assertTrue(d['range']['trend_truncated'])
        self.assertLessEqual(len(d['trend']), 400)
        self.assertNotEqual(d['range']['trend_from'], d['range']['start'],
                            '趋势起点应被裁到 400 天窗口内')

    def test_all_flag_does_not_loosen_the_guard(self):
        """加了 all=1 之后，显式超长区间**仍必须 400**（守卫不能被顺手放宽）。"""
        r = self._get(start='2000-01-01', end='2026-12-31')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['meta']['error']['code'], 'RANGE_TOO_LARGE')

    def test_all_on_empty_dataset_does_not_crash(self):
        """库里一单都没有时，all=1 也不能 500（earliest 为 None 的分支）。"""
        d = self._summary(all=1)
        self.assertEqual(d['summary']['order_count'], 0)
        # 没有订单时 start=end=今天 ⇒ 趋势补 1 行 0 值（"补齐空白日"的既有行为），不是空数组
        self.assertLessEqual(len(d['trend']), 1)
