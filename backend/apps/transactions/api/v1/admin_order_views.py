"""Admin order management endpoints."""
from datetime import date, timedelta
from django.db.models import Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from apps.transactions.models import (
    Order, OrderItem, Invoice, PaymentRecord, ShippingRecord,
    InvalidTransitionError,
)
from apps.transactions.services import InvoiceService
from apps.transactions.api.v1.serializers import (
    OrderListSerializer, OrderDetailSerializer, InvoiceSerializer,
    AdminShipSerializer, AdminQuoteSerializer, AdminVerifyPaymentSerializer,
    ShippingRecordSerializer, PaymentRecordSerializer,
)


class AdminOrderListView(APIView):
    """GET /api/v1/admin/orders — list all orders."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        orders = Order.objects.all().order_by('-created_at')
        # Filters
        status_filter = request.query_params.get('status', '')
        if status_filter:
            orders = orders.filter(status=status_filter)
        search = request.query_params.get('search', '')
        if search:
            q = Q(order_no__icontains=search) | Q(po_number__icontains=search)
            orders = orders.filter(q)

        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        total = orders.count()
        start = (page - 1) * page_size
        items = orders[start:start + page_size]

        return Response({
            'success': True,
            'data': OrderListSerializer(items, many=True).data,
            'meta': {'pagination': {'page': page, 'pageSize': page_size, 'count': total}},
        })


class AdminOrderDetailView(APIView):
    """GET /api/v1/admin/orders/{id} — order detail."""
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'success': False, 'meta': {'error': {'code': 'NOT_FOUND'}}}, status=404)
        return Response({'success': True, 'data': OrderDetailSerializer(order).data})


class AdminConfirmOrderView(APIView):
    """POST /api/v1/admin/orders/{id}/confirm — confirm a draft order."""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'success': False, 'meta': {'error': {'code': 'NOT_FOUND'}}}, status=404)
        try:
            order.transition_to('confirmed')
        except InvalidTransitionError as e:
            return Response({'success': False, 'meta': {'error': {'code': 'INVALID_TRANSITION', 'message': str(e)}}}, status=400)
        return Response({'success': True, 'data': OrderDetailSerializer(order).data})


class AdminInvoiceOrderView(APIView):
    """POST /api/v1/admin/orders/{id}/invoice — generate invoice."""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'success': False, 'meta': {'error': {'code': 'NOT_FOUND'}}}, status=404)

        # New P0 state machine: invoicing requires DELIVERED (confirmed→invoiced
        # is illegal). Delegated to the unified InvoiceService.issue flow.
        if order.status != Order.Status.DELIVERED:
            return Response(
                {'success': False, 'meta': {'error': {
                    'code': 'INVALID_STATUS',
                    'message': 'Order must be delivered before invoicing',
                }}},
                status=400,
            )

        try:
            invoice = InvoiceService.issue(order, actor=request.user)
        except InvalidTransitionError as e:
            return Response({'success': False, 'meta': {'error': {'code': 'INVALID_TRANSITION', 'message': str(e)}}}, status=400)
        except ValueError as e:
            return Response({'success': False, 'meta': {'error': {'code': 'INVALID_STATE', 'message': str(e)}}}, status=400)

        return Response({'success': True, 'data': InvoiceSerializer(invoice).data})


# NOTE: AdminShipOrderView removed — it depended on the deprecated `processing`
# state, which is no longer in VALID_TRANSITIONS and would 500 under the new P0
# state machine. Shipping is now handled by the new PO flow
# (MarkShippedView / MarkDeliveredView in po_views.py). See decision ①A.
# deprecated: replaced by new PO flow


class AdminCompleteOrderView(APIView):
    """POST /api/v1/admin/orders/{id}/complete — mark order as completed."""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'success': False, 'meta': {'error': {'code': 'NOT_FOUND'}}}, status=404)
        try:
            order.transition_to('completed')
        except InvalidTransitionError as e:
            return Response({'success': False, 'meta': {'error': {'code': 'INVALID_TRANSITION', 'message': str(e)}}}, status=400)
        return Response({'success': True, 'data': OrderDetailSerializer(order).data})


class AdminQuoteOrderView(APIView):
    """POST /api/v1/admin/orders/{id}/quote — enter quote price."""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            order = Order.objects.get(pk=pk)
        except Order.DoesNotExist:
            return Response({'success': False, 'meta': {'error': {'code': 'NOT_FOUND'}}}, status=404)

        serializer = AdminQuoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if order.status != 'quote_pending':
            return Response(
                {'success': False, 'meta': {'error': {'code': 'INVALID_STATUS', 'message': 'Order must be quote_pending'}}},
                status=400,
            )

        order.grand_total = data['grand_total']
        if data.get('valid_until'):
            order.notes = f"Quote valid until: {data['valid_until']}"
        order.transition_to('quoted')
        order.save()

        return Response({'success': True, 'data': OrderDetailSerializer(order).data})


class AdminVerifyPaymentView(APIView):
    """POST /api/v1/admin/invoices/{id}/verify-payment — verify/reject payment."""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            invoice = Invoice.objects.get(pk=pk)
        except Invoice.DoesNotExist:
            return Response({'success': False, 'meta': {'error': {'code': 'NOT_FOUND'}}}, status=404)

        serializer = AdminVerifyPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            payment = PaymentRecord.objects.get(pk=data['payment_id'], invoice=invoice)
        except PaymentRecord.DoesNotExist:
            return Response({'success': False, 'meta': {'error': {'code': 'NOT_FOUND'}}}, status=404)

        if data['action'] == 'verify':
            payment.status = 'verified'
            payment.verified_by = request.user
            payment.verified_at = timezone.now()
            if data.get('notes'):
                payment.notes = data['notes']
            payment.save()

            # Update invoice
            invoice.status = 'paid'
            invoice.paid_at = timezone.now()
            invoice.save()

            # Update order
            invoice.order.transition_to('paid')
        else:
            payment.status = 'rejected'
            if data.get('notes'):
                payment.notes = data['notes']
            payment.save()

        return Response({'success': True, 'data': PaymentRecordSerializer(payment).data})


# Import at bottom to avoid circular
from django.db import models
