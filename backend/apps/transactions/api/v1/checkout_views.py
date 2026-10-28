"""Checkout endpoint — creates order from basket."""
import logging
from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from core.business_time import business_today
from apps.transactions.models import Order, OrderItem, Basket, Invoice
from apps.transactions.services import OrderNoService
from apps.transactions.api.v1.serializers import CheckoutSerializer, OrderDetailSerializer
from core.db_retry import retry_on_deadlock
from apps.inventory.services import StockShortageService
from apps.inventory.models import StockShortageAlert

logger = logging.getLogger(__name__)


class CheckoutView(APIView):
    """POST /api/v1/checkout — create order from basket."""
    permission_classes = [IsAuthenticated]

    @retry_on_deadlock()
    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user
        basket_items = Basket.objects.filter(user=user).select_related('product', 'sku')

        # Validate basket not empty
        if not basket_items.exists():
            return Response(
                {'success': False, 'meta': {'error': {'code': 'EMPTY_BASKET', 'message': 'Basket is empty'}}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ★ 2026-10-28：缺货拦截统一到 `StockShortageService`。
        #   此前这里只查 `sku.inventory_status == 'out_of_stock'` 这个枚举
        #   —— 完全不看真实可用量（`inventory` 表的 available），也**不给运营留痕**。
        #   现在两条下单路径（购物车结账 / PO 提交）共用同一份口径，被拦时同步写
        #   `StockShortageAlert`，运营在「缺货告警台」能看到是谁、什么时候、要买什么。
        #   ⚠️ 必须放在 `with transaction.atomic()` **之前**：万一之后回滚，告警行不该跟着消失。
        shortages = StockShortageService.check_items(
            user,
            [{'sku_id': it.sku_id, 'quantity': it.quantity}
             for it in basket_items if it.sku_id],
            source=StockShortageAlert.Source.CHECKOUT,
        )
        if shortages:
            return Response(
                {'success': False, 'meta': {'error': {
                    'code': 'OUT_OF_STOCK',
                    'message': StockShortageService.shortage_message(shortages),
                    'details': [{
                        'sku_id': s['sku_id'],
                        'sku_code': s['sku_code'],
                        'product_name': s['product_name'],
                        'requested_quantity': s['requested_quantity'],
                        'available_quantity': s['available_quantity'],
                        'reason': s['reason'],
                    } for s in shortages],
                }}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Calculate totals
            subtotal = sum(item.sku.price * item.quantity for item in basket_items if item.sku)
            grand_total = subtotal  # No tax for now

            # Determine initial status
            payment_method = data['payment_method']
            if payment_method == 'quote':
                initial_status = Order.Status.QUOTE_PENDING
            else:
                initial_status = Order.Status.CONFIRMED

            # Generate order number
            # ★ 日切与单号前缀必须用**同一个**业务日历日，故先取一次 biz_date，
            #   再把它同时喂给取号器（计数器分桶键）和前缀格式化。
            #   1) 键不能用 `created_at__date=`：Django 的 `__date` lookup 按
            #      settings.TIME_ZONE（生产为 UTC）截断，不是按 BUSINESS_TIME_ZONE
            #      ⇒ 东八区 00:00-07:59 期间会切错日。改用显式 biz_date 分桶。
            #   2) 前缀不能直接用 `timezone.now().strftime('%Y%m%d')`：那是 UTC 日期，
            #      与业务日差一天 ⇒ 同一业务日的订单被拆到两个前缀里。
            #
            # ★ 2026-10-17：取号从 `count()+1` 改为专用计数器 OrderNoService。
            #   旧写法的两个缺陷（生产已实际发生跳号）：
            #     a) count() 不区分单据来源 ⇒ uuid 版 PO 单（PoSubmissionService.submit）
            #        也落在当日窗口内被计入 ⇒ 生产 2026-07-17 出现 004-007 跳号；
            #     b) 删单后 count() 回退 ⇒ 可能生成与已存在单号冲突的编号。
            #   新写法用 OrderSequence(biz_date, last_number) 只数 checkout 单，
            #   且单调不回退；单号格式 ORD-YYYYMMDD-NNN 保持不变。
            biz_date = business_today()
            order_no = OrderNoService.next_checkout_order_no(biz_date)

            # Create order
            order = Order.objects.create(
                user=user,
                organization=getattr(user, 'organization', None),
                order_no=order_no,
                status=initial_status,
                payment_method=payment_method,
                po_number=data.get('po_number') or None,
                po_contact=data.get('po_contact', ''),
                subtotal=subtotal,
                grand_total=grand_total,
                currency='USD',
                shipping_name=data.get('shipping_name', ''),
                shipping_address=data.get('shipping_address', ''),
                shipping_phone=data.get('shipping_phone', ''),
                shipping_email=data.get('shipping_email', ''),
                billing_name=data.get('billing_name', ''),
                billing_address=data.get('billing_address', ''),
                notes=data.get('notes', ''),
            )

            # Create order items
            for item in basket_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    sku=item.sku,
                    quantity=item.quantity,
                    unit_price=item.sku.price if item.sku else 0,
                    subtotal=(item.sku.price * item.quantity) if item.sku else 0,
                )

            # Clear basket
            basket_items.delete()

        logger.info('Checkout completed: order_no=%s user_id=%s',
                    order.order_no, order.user_id)
        return Response(
            OrderDetailSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )
