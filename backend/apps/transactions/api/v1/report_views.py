# -*- coding: utf-8 -*-
"""销售报表（2026-10-29）。

## 口径（这是报表的全部价值所在，写死在代码里，改之前先想清楚）

| 指标 | 定义 |
|---|---|
| **GMV（下单额）** | 区间内**创建**的、状态属于 `SALES_STATUSES` 的订单 `grand_total` 之和 |
| **订单数** | 同上的订单条数 |
| **客单价** | GMV ÷ 订单数（无订单时为 0，不是 null） |
| **实收（Revenue）** | 区间内**发生**的、`status='verified'` 的 `PaymentRecord.amount` 之和 |

三条容易搞错、这里刻意钉死的点：

1. **GMV ≠ 实收**。GMV 按**下单时间**归期、含未付款；实收按**付款时间**归期、只算已核验。
   两者放在同一天会差很多，指标名必须让人一眼看出区别 —— 所以分成 `gmv` 和 `paid_amount`。
2. **报价流程不算销售**。`quote_pending / quoted / quote_accepted / quote_rejected / draft`
   都不是订单，计入会把"询价"当"成交"。这里用**白名单** `SALES_STATUSES`：
   将来新增状态默认不计入，要计入必须显式改这张表（比黑名单安全）。
3. **按业务时区聚合，不是 UTC**。生产 `TIME_ZONE='UTC'`，而"按日"业务语义必须用
   `BUSINESS_TIME_ZONE`（东八区）—— 否则东八区 00:00-07:59 下的单会被算到前一天。
   `TruncDate(..., tzinfo=business_timezone())` 就是干这个的。

4. **多币种不混算**。订单有 `currency`，把 USD 和 CNY 相加是错的。
   所有金额指标按币种分组返回（`by_currency`），再单独给出 GMV 最大的那个币种作为
   「主展示币种」（`primary_currency`）。目前生产全 USD，但代码不能假设。

## 性能

订单量级小（生产几十张），全部走 ORM 聚合，一个请求 5 次查询。
不缓存：报表看的是实时数，缓存会让人怀疑"明明刚下的单怎么没有"。
"""
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from rest_framework.views import APIView

from core.business_time import business_day_bounds, business_timezone, business_today
from core.mixins import EnvelopeMixin
from core.permissions import IsProcurementOrAdmin
from apps.transactions.models import Order, OrderItem, PaymentRecord

#: 计入销售的订单状态（**白名单**：新增状态默认不计入）
SALES_STATUSES = (
    Order.Status.PO_RECEIVED,
    Order.Status.CONFIRMED,
    Order.Status.IN_PRODUCTION,
    Order.Status.SHIPPED,
    Order.Status.DELIVERED,
    Order.Status.INVOICED,
    Order.Status.PAID,
    Order.Status.COMPLETED,
    Order.Status.PROCESSING,
)

#: 趋势图最多返回多少天（防有人传 start=2000-01-01 拖出几千行）
MAX_TREND_DAYS = 400


def _money(v) -> str:
    return str((Decimal(v or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _parse_day(raw, default):
    if not raw:
        return default
    try:
        return datetime.strptime(str(raw), '%Y-%m-%d').date()
    except ValueError:
        return None


class SalesReportView(EnvelopeMixin, APIView):
    """GET /api/v1/ops/sales-report/?start=YYYY-MM-DD&end=YYYY-MM-DD

    默认区间 = 本月 1 日 ~ 今天（业务时区）。
    """
    permission_classes = [IsProcurementOrAdmin]

    def get(self, request):
        today = business_today()
        default_start = today.replace(day=1)

        start_day = _parse_day(request.query_params.get('start'), default_start)
        end_day = _parse_day(request.query_params.get('end'), today)
        if start_day is None or end_day is None:
            return self.error_response(
                'start/end 必须是 YYYY-MM-DD', code='BAD_DATE', status_code=400)
        if end_day < start_day:
            return self.error_response(
                'end 不能早于 start', code='BAD_RANGE', status_code=400)

        start_dt, _ = business_day_bounds(start_day)
        _, end_dt = business_day_bounds(end_day)

        orders = Order.objects.filter(
            created_at__gte=start_dt, created_at__lt=end_dt,
            status__in=SALES_STATUSES)

        # ── 1) 按币种汇总 GMV ──────────────────────────────────────────
        by_ccy = list(orders.values('currency')
                      .annotate(gmv=Sum('grand_total'), n=Count('id'))
                      .order_by('-gmv'))
        order_count = sum(r['n'] for r in by_ccy)
        primary = by_ccy[0]['currency'] if by_ccy else (orders.values_list(
            'currency', flat=True).first() or 'USD')
        primary_row = next((r for r in by_ccy if r['currency'] == primary), None)
        primary_gmv = Decimal(primary_row['gmv']) if primary_row else Decimal('0')
        primary_n = primary_row['n'] if primary_row else 0
        aov = (primary_gmv / primary_n) if primary_n else Decimal('0')

        # ── 2) 实收（只算已验证的付款，按下单区间无关、按付款发生时间）──
        payments = PaymentRecord.objects.filter(
            status=PaymentRecord.Status.VERIFIED,
            created_at__gte=start_dt, created_at__lt=end_dt)
        paid_by_ccy = list(payments.values('currency')
                           .annotate(amount=Sum('amount'), n=Count('id'))
                           .order_by('-amount'))
        paid_primary = sum(
            (Decimal(r['amount']) for r in paid_by_ccy if r['currency'] == primary),
            Decimal('0'))
        paid_primary_n = sum(r['n'] for r in paid_by_ccy if r['currency'] == primary)

        # ── 3) 状态分布 ────────────────────────────────────────────────
        by_status = list(orders.values('status').annotate(n=Count('id')).order_by('-n'))

        # ── 4) 按日趋势（业务时区）────────────────────────────────────
        tz = business_timezone()
        span_days = (end_day - start_day).days + 1
        if span_days > MAX_TREND_DAYS:
            return self.error_response(
                f'区间最多 {MAX_TREND_DAYS} 天（当前 {span_days}），请缩小区间',
                code='RANGE_TOO_LARGE', status_code=400)
        trend_rows = (orders
                      .annotate(d=TruncDate('created_at', tzinfo=tz))
                      .values('d', 'currency')
                      .annotate(gmv=Sum('grand_total'), n=Count('id'))
                      .order_by('d'))
        trend_map = {}
        for r in trend_rows:
            key = r['d'].isoformat()
            slot = trend_map.setdefault(key, {'date': key, 'gmv': Decimal('0'),
                                              'orders': 0, 'by_currency': {}})
            slot['orders'] += r['n']
            slot['by_currency'][r['currency']] = _money(r['gmv'])
            if r['currency'] == primary:
                slot['gmv'] = Decimal(r['gmv'])
        # 补齐区间内没有订单的日期（否则折线会"跳过"空白日，看起来像连续增长）
        trend = []
        cur = start_day
        while cur <= end_day:
            key = cur.isoformat()
            slot = trend_map.get(key, {'date': key, 'gmv': Decimal('0'), 'orders': 0})
            trend.append({'date': key, 'gmv': _money(slot['gmv']),
                          'orders': slot['orders']})
            cur = cur.fromordinal(cur.toordinal() + 1)

        # ── 5) Top 产品 / Top 客户 ────────────────────────────────────
        top_products = list(
            OrderItem.objects.filter(order__in=orders)
            .values('product_id', 'product__name', 'product__catalog_no')
            .annotate(qty=Sum('quantity'), amount=Sum('subtotal'))
            .order_by('-amount')[:10])
        top_customers = list(
            orders.values('user_id', 'user__username', 'organization__name')
            .annotate(amount=Sum('grand_total'), n=Count('id'))
            .order_by('-amount')[:10])

        return self.success_response({
            'range': {
                'start': start_day.isoformat(),
                'end': end_day.isoformat(),
                'days': span_days,
            },
            'summary': {
                'primary_currency': primary,
                'gmv': _money(primary_gmv),
                'order_count': order_count,
                'avg_order_value': _money(aov),
                'paid_amount': _money(paid_primary),
                'paid_count': paid_primary_n,
                'by_currency': [{
                    'currency': r['currency'],
                    'gmv': _money(r['gmv']),
                    'order_count': r['n'],
                } for r in by_ccy],
                'paid_by_currency': [{
                    'currency': r['currency'],
                    'amount': _money(r['amount']),
                    'count': r['n'],
                } for r in paid_by_ccy],
            },
            'by_status': [{'status': r['status'], 'count': r['n']} for r in by_status],
            'trend': trend,
            'top_products': [{
                'product_id': r['product_id'],
                'name': r['product__name'],
                'catalog_no': r['product__catalog_no'],
                'quantity': r['qty'],
                'amount': _money(r['amount']),
            } for r in top_products],
            'top_customers': [{
                'user_id': r['user_id'],
                'username': r['user__username'],
                'organization': r['organization__name'],
                'amount': _money(r['amount']),
                'orders': r['n'],
            } for r in top_customers],
        })
