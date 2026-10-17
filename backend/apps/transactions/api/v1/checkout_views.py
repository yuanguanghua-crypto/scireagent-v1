"""Checkout endpoint — creates order from basket."""
from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from core.business_time import business_day_bounds
from apps.transactions.models import Order, OrderItem, Basket, Invoice
from apps.transactions.api.v1.serializers import CheckoutSerializer, OrderDetailSerializer


class CheckoutView(APIView):
    """POST /api/v1/checkout — create order from basket."""
    permission_classes = [IsAuthenticated]

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

        # Validate SKUs are in stock
        for item in basket_items:
            if item.sku and item.sku.inventory_status == 'out_of_stock':
                return Response(
                    {'success': False, 'meta': {'error': {
                        'code': 'OUT_OF_STOCK',
                        'message': f'SKU {item.sku.sku_code} is out of stock',
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
            from django.utils import timezone
            now = timezone.now()
            # ★ 日切必须按业务日历日，不能用 `created_at__date=`：
            #   Django 的 `__date` lookup 按 settings.TIME_ZONE（生产为 UTC）截断，
            #   不是按 BUSINESS_TIME_ZONE ⇒ 东八区 00:00-07:59 期间会切错日，
            #   单号序列错位 8 小时。改用业务日的显式 [00:00, 次日00:00) 区间。
            #   （单号生成本身——序号算法/唯一性——是另一条 P1，此处不动。）
            day_start, day_end = business_day_bounds()
            seq = Order.objects.filter(
                created_at__gte=day_start, created_at__lt=day_end,
            ).count() + 1
            order_no = f'ORD-{now.strftime("%Y%m%d")}-{seq:03d}'

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

        return Response(
            OrderDetailSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )
