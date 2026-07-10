"""PO 门户 P0 端点 — 提交/审核/发货/开票/收款/AR（信封统一，跨模型写入走 Service）。"""
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.mixins import EnvelopeMixin
from core.permissions import IsProcurementOrAdmin, IsAdmin

from apps.transactions.models import (
    Order, Invoice, ShippingRecord, StatusLog, InvalidTransitionError,
)
from apps.transactions.api.v1.serializers import (
    OrderDetailSerializer, InvoiceSerializer, ShippingRecordSerializer,
    PoSubmitSerializer, ShipmentCreateSerializer, InvoiceIssueSerializer,
    PaymentCreateSerializer,
)
from apps.transactions.services import (
    OrderStateMachine, PoSubmissionService, ShippingService,
    InvoiceService, PaymentArService, PoNumberConflictError,
)
from apps.notifications.services import EmailService

User = get_user_model()


class POSubmitView(EnvelopeMixin, APIView):
    """POST /api/v1/orders/po/ — 提交 PO → PO_RECEIVED。"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PoSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        files = request.FILES.getlist('attachments') or request.FILES.getlist('file')
        try:
            order = PoSubmissionService.submit(
                request.user, serializer.validated_data, files=files
            )
        except PoNumberConflictError as e:
            return self.error_response(
                f'PO number already exists: {e}', code='PO_NUMBER_CONFLICT', status_code=409
            )
        except ValueError as e:
            return self.error_response(str(e), code='VALIDATION_ERROR', status_code=400)
        return self.success_response(
            {'order_no': order.order_no, 'status': order.status}, status_code=201
        )


class ApproveOrderView(EnvelopeMixin, APIView):
    """POST /api/v1/orders/<id>/approve/ — PO_RECEIVED → CONFIRMED。"""
    permission_classes = [IsProcurementOrAdmin]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        try:
            OrderStateMachine.transition_to(
                order, Order.Status.CONFIRMED, actor=request.user, note='Approved'
            )
        except InvalidTransitionError as e:
            return self.error_response(str(e), code='INVALID_TRANSITION', status_code=400)
        EmailService.enqueue(
            'order_confirmed', to=[order.shipping_email] if order.shipping_email else [],
            ctx={'order_no': order.order_no},
        )
        return self.success_response(OrderDetailSerializer(order, context={'request': request}).data)


class RejectOrderView(EnvelopeMixin, APIView):
    """POST /api/v1/orders/<id>/reject/ — → CANCELLED。"""
    permission_classes = [IsProcurementOrAdmin]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        reason = request.data.get('reason', '')
        try:
            OrderStateMachine.transition_to(
                order, Order.Status.CANCELLED, actor=request.user,
                action_type=StatusLog.ActionType.REJECTED,
                note=reason,
            )
        except InvalidTransitionError as e:
            return self.error_response(str(e), code='INVALID_TRANSITION', status_code=400)
        return self.success_response(OrderDetailSerializer(order, context={'request': request}).data)


class AssignRepView(EnvelopeMixin, APIView):
    """POST /api/v1/orders/<id>/assign-rep/ — 分配/改派 Rep（Admin）。"""
    permission_classes = [IsAdmin]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        rep_id = request.data.get('rep_id')
        if not rep_id:
            return self.error_response('rep_id is required', code='VALIDATION_ERROR', status_code=400)
        try:
            rep = User.objects.get(pk=rep_id, role__in=['procurement', 'admin'])
        except User.DoesNotExist:
            return self.error_response('Invalid rep_id', code='NOT_FOUND', status_code=404)
        order.assigned_rep = rep
        order.save(update_fields=['assigned_rep', 'updated_at'])
        from apps.transactions.models import StatusLog
        StatusLog.objects.create(
            order=order, actor=request.user,
            action_type=StatusLog.ActionType.REP_ASSIGNED,
            from_status=order.status, to_status=order.status,
            note=f'Assigned rep {rep.username}',
        )
        return self.success_response(OrderDetailSerializer(order, context={'request': request}).data)


class ShipmentCreateView(EnvelopeMixin, APIView):
    """POST /api/v1/orders/<id>/shipments/ — 新建发货记录（分批发）。"""
    permission_classes = [IsProcurementOrAdmin]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        serializer = ShipmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            shipment = ShippingService.create_shipment(
                order, carrier=data['carrier'], items=data['items'],
                tracking_number=data['tracking_number'],
                tracking_url=data['tracking_url'],
                estimated_delivery=data.get('estimated_delivery'),
                notes=data['notes'], actor=request.user,
            )
        except (InvalidTransitionError, ValueError) as e:
            return self.error_response(str(e), code='INVALID_OPERATION', status_code=400)
        return self.success_response(
            ShippingRecordSerializer(shipment).data, status_code=201
        )


class MarkShippedView(EnvelopeMixin, APIView):
    """POST /api/v1/shipments/<id>/mark-shipped/"""
    permission_classes = [IsProcurementOrAdmin]

    def post(self, request, pk):
        shipment = get_object_or_404(ShippingRecord, pk=pk)
        try:
            shipment = ShippingService.mark_shipped(shipment.id, actor=request.user)
        except InvalidTransitionError as e:
            return self.error_response(str(e), code='INVALID_TRANSITION', status_code=400)
        return self.success_response(ShippingRecordSerializer(shipment).data)


class MarkDeliveredView(EnvelopeMixin, APIView):
    """POST /api/v1/shipments/<id>/mark-delivered/"""
    permission_classes = [IsProcurementOrAdmin]

    def post(self, request, pk):
        shipment = get_object_or_404(ShippingRecord, pk=pk)
        received_by = request.data.get('received_by', '')
        try:
            shipment = ShippingService.mark_delivered(shipment.id, received_by=received_by, actor=request.user)
        except InvalidTransitionError as e:
            return self.error_response(str(e), code='INVALID_TRANSITION', status_code=400)
        return self.success_response(ShippingRecordSerializer(shipment).data)


class InvoiceIssueView(EnvelopeMixin, APIView):
    """POST /api/v1/orders/<id>/invoice/ — 开票（原子 INV 编号 + PDF）。"""
    permission_classes = [IsProcurementOrAdmin]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        serializer = InvoiceIssueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invoice = InvoiceService.issue(
                order, payment_terms=serializer.validated_data['payment_terms'], actor=request.user
            )
        except InvalidTransitionError as e:
            return self.error_response(str(e), code='INVALID_TRANSITION', status_code=400)
        except ValueError as e:
            return self.error_response(str(e), code='INVALID_OPERATION', status_code=400)
        return self.success_response(InvoiceSerializer(invoice).data, status_code=201)


class PaymentCreateView(EnvelopeMixin, APIView):
    """POST /api/v1/invoices/<id>/pay/ — 收款。"""
    permission_classes = [IsProcurementOrAdmin]

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            invoice = PaymentArService.pay(
                invoice, amount=data['amount'], method=data['method'],
                paid_at=data.get('paid_at'), actor=request.user,
                reference=data.get('reference', ''), notes=data.get('notes', ''),
            )
        except ValueError as e:
            return self.error_response(str(e), code='INVALID_OPERATION', status_code=400)
        return self.success_response(InvoiceSerializer(invoice).data)


class ArAgingView(EnvelopeMixin, APIView):
    """GET /api/v1/ar/aging/ — AR 30/60/90 聚合。"""
    permission_classes = [IsProcurementOrAdmin]

    def get(self, request):
        return self.success_response(PaymentArService.ar_aging())
