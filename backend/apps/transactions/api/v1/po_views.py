"""PO 门户 P0 端点 — 提交/审核/发货/开票/收款/AR（信封统一，跨模型写入走 Service）。"""
import json
import os

from django.conf import settings
from django.db import transaction
from django.contrib.auth import get_user_model
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.mixins import EnvelopeMixin
from core.permissions import IsProcurementOrAdmin, IsAdmin

from apps.transactions.models import (
    Order, Invoice, ShippingRecord, StatusLog, InvalidTransitionError,
    PoAttachment, OrderItem,
)
from apps.inventory.models import Allocation, InsufficientInventoryError
from apps.inventory.services import InventoryService
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
from apps.inventory.services import StockShortageService
from apps.inventory.models import StockShortageAlert

User = get_user_model()


class POSubmitView(EnvelopeMixin, APIView):
    """POST /api/v1/orders/po/ — 提交 PO → PO_RECEIVED。"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        # 兼容前端 multipart 路径：items 可能以 JSON 字符串字段传入（DRF multipart 不展开方括号）。
        items = data.get('items') if hasattr(data, 'get') else None
        if isinstance(items, str):
            try:
                data = data.copy()
                data['items'] = json.loads(items)
            except (ValueError, TypeError):
                pass
        serializer = PoSubmitSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        # ★ 2026-10-28：缺货拦截（用户要求「缺货的不能下单」）。
        #   位置刻意放在 `PoSubmissionService.submit` **之前**：该服务是 @transaction.atomic，
        #   若在里面抛错，连缺货告警行也会被一起回滚 ⇒ 运营什么也看不到。
        #   口径见 `StockShortageService`：out_of_stock 一律拦；已建库存记录的 SKU 再校验
        #   available < 下单量；**没有库存记录的 SKU 不判定**（生产 inventory 表 0 行，
        #   若把"未建账"当成"没货"，上线当天全部下单都会被拒）。
        shortages = StockShortageService.check_items(
            request.user,
            serializer.validated_data.get('items', []),
            source=StockShortageAlert.Source.PO_SUBMIT,
        )
        if shortages:
            return self.error_response(
                StockShortageService.shortage_message(shortages),
                code='OUT_OF_STOCK',
                status_code=400,
                details=[{
                    'sku_id': s['sku_id'],
                    'sku_code': s['sku_code'],
                    'product_name': s['product_name'],
                    'requested_quantity': s['requested_quantity'],
                    'available_quantity': s['available_quantity'],
                    'reason': s['reason'],
                } for s in shortages],
            )

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
            with transaction.atomic():
                OrderStateMachine.transition_to(
                    order, Order.Status.CONFIRMED, actor=request.user, note='Approved'
                )
                # ★ 2026-10-28：PO 上传单是**意向单**，下单时不锁库；
                #   运营点“批准”这一下才是承诺 ⇒ 在这里锁。
                #   失败整块回滚（状态也不会变成 CONFIRMED）。
                InventoryService.reserve_for_order(
                    order, reason=f'approve:{order.order_no}')
        except InvalidTransitionError as e:
            return self.error_response(str(e), code='INVALID_TRANSITION', status_code=400)
        except InsufficientInventoryError as e:
            return self.error_response(str(e), code='OUT_OF_STOCK', status_code=400)
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
            with transaction.atomic():
                OrderStateMachine.transition_to(
                    order, Order.Status.CANCELLED, actor=request.user,
                    action_type=StatusLog.ActionType.REJECTED,
                    note=reason,
                )
                # ★ 2026-10-28：必须释放占用。不释放的话，那批货会永久锁死、
                #   而且**不会报任何错** —— 只是库存慢慢变少。
                InventoryService.release_for_order(
                    order, reason=f'cancel:{order.order_no}')
        except InvalidTransitionError as e:
            return self.error_response(str(e), code='INVALID_TRANSITION', status_code=400)
        return self.success_response(OrderDetailSerializer(order, context={'request': request}).data)


class CancelOrderView(EnvelopeMixin, APIView):
    """POST /api/v1/orders/<id>/cancel/ — 任意非终态 → CANCELLED。"""
    permission_classes = [IsProcurementOrAdmin]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        reason = request.data.get('reason', '')
        try:
            with transaction.atomic():
                OrderStateMachine.transition_to(
                    order, Order.Status.CANCELLED, actor=request.user,
                    action_type=StatusLog.ActionType.CANCELLED,
                    note=reason,
                )
                # ★ 2026-10-28：必须释放占用。不释放的话，那批货会永久锁死、
                #   而且**不会报任何错** —— 只是库存慢慢变少。
                InventoryService.release_for_order(
                    order, reason=f'cancel:{order.order_no}')
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


class ConfirmQuoteView(EnvelopeMixin, APIView):
    """POST /api/v1/orders/<id>/confirm-quote/ — 客户接受/拒绝报价（legacy 报价流）。

    订单处于 `quoted` 时，客户 accept（→ quote_accepted → confirmed）或 reject（→ quote_rejected）。
    ★ 2026-10-14 补：`OrderDetailPage.vue` 一直调用此端点，但此前后端缺失（前端有、后端无）。
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        if not _is_order_viewer(request.user, order):
            return self.error_response(
                'Not allowed to respond to this order', code='FORBIDDEN', status_code=403
            )
        action = request.data.get('action')
        if action not in ('accept', 'reject'):
            return self.error_response(
                'action must be "accept" or "reject"', code='VALIDATION_ERROR', status_code=400
            )
        if order.status != Order.Status.QUOTED:
            return self.error_response(
                'Order is not awaiting quote response', code='INVALID_OPERATION', status_code=400
            )
        try:
            if action == 'accept':
                OrderStateMachine.transition_to(
                    order, Order.Status.QUOTE_ACCEPTED, actor=request.user, note='Quote accepted'
                )
                OrderStateMachine.transition_to(
                    order, Order.Status.CONFIRMED, actor=request.user, note='Quote accepted → confirmed'
                )
            else:
                OrderStateMachine.transition_to(
                    order, Order.Status.QUOTE_REJECTED, actor=request.user,
                    action_type=StatusLog.ActionType.REJECTED, note='Quote rejected'
                )
        except InvalidTransitionError as e:
            return self.error_response(str(e), code='INVALID_OPERATION', status_code=400)
        return self.success_response(OrderDetailSerializer(order, context={'request': request}).data)


class AllocateView(EnvelopeMixin, APIView):
    """POST /api/v1/orders/<id>/allocate/ — 备货台锁定库存（P1-1 节点 B）。

    body: {lines: [{order_item_id, inventory_id, quantity}]}
    ★ 2026-10-14 补：服务层 `InventoryService.allocate_for_order` 早已实现，本端点仅补 API 入口。
    """

    permission_classes = [IsProcurementOrAdmin]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        if order.status not in (Order.Status.CONFIRMED, Order.Status.IN_PRODUCTION):
            return self.error_response(
                'Order must be CONFIRMED or IN_PRODUCTION to allocate',
                code='INVALID_OPERATION', status_code=400,
            )
        # ★ 2026-10-28：下单 / 审核已自动锁库时，手点 Allocate 会把同一批货占两次
        #   ⇒ 先拦。（allocate() 自身不检查是否已占，所以这一层必须在这里。）
        if Allocation.objects.filter(
                order_item__order=order,
                status=Allocation.Status.RESERVED).exists():
            return self.error_response(
                'Order already holds reserved stock (locked at checkout/approval); '
                'manual allocation would double-count it.',
                code='ALREADY_ALLOCATED', status_code=400,
            )
        lines = request.data.get('lines')
        if not lines:
            return self.error_response('lines is required', code='VALIDATION_ERROR', status_code=400)
        try:
            allocations = InventoryService.allocate_for_order(order, lines)
        except (InsufficientInventoryError, OrderItem.DoesNotExist, KeyError, ValueError, TypeError) as e:
            return self.error_response(str(e), code='INVALID_OPERATION', status_code=400)
        return self.success_response({'allocated_lines': len(allocations)})


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


def _is_order_viewer(user, order) -> bool:
    """订单可见性：订单归属人本人 / 本机构成员 / 采购或管理员。"""
    if not (user and user.is_authenticated):
        return False
    if order.user_id == user.id:
        return True
    if order.organization_id and order.organization_id == getattr(user, 'organization_id', None):
        return True
    # ★ 2026-10-13 修：原写法 `IsProcurementOrAdmin().has_permission(None, None)` 把 **None 当 request**
    #   传给权限类，权限类内 `request.user` 直接抛 `AttributeError` ⇒ 一切「非订单归属人、非同机构」的
    #   访问者（**包含内部采购/管理员**）下载发票 PDF 必然 500（实测：同一张发票客户本人 200、管理员 500）。
    #   这里只需判"是否内部人员"，直接判角色即可 —— 语义与 IsProcurementOrAdmin.has_permission 保持一致。
    return bool(
        getattr(user, 'is_staff', False)
        or getattr(user, 'role', None) in ('procurement', 'admin')
    )


class InvoicePdfDownloadView(EnvelopeMixin, APIView):
    """GET /api/v1/invoices/<pk>/pdf/ — 下载发票 PDF（FileResponse）。

    发票 PDF 由 InvoiceService.generate_invoice_pdf 落盘于
    MEDIA_ROOT/invoices/<invoice_no>.pdf（Invoice 模型暂无 FileField，按
    invoice_no 反查文件，避免改动既有 P0 模型/服务）。
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        if not _is_order_viewer(request.user, invoice.order):
            return self.error_response(
                'Not allowed to view this invoice', code='FORBIDDEN', status_code=403
            )
        pdf_path = os.path.join(
            settings.MEDIA_ROOT, 'invoices', f'{invoice.invoice_no}.pdf'
        )
        if not os.path.exists(pdf_path):
            return self.error_response(
                'Invoice PDF not found', code='NOT_FOUND', status_code=404
            )
        response = FileResponse(open(pdf_path, 'rb'), content_type='application/pdf')
        response['Content-Disposition'] = (
            f'inline; filename="{invoice.invoice_no}.pdf"'
        )
        return response


class PoAttachmentDownloadView(EnvelopeMixin, APIView):
    """GET /api/v1/orders/attachments/<pk>/download/ — 下载 PO 附件（FileResponse）。"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        attachment = get_object_or_404(PoAttachment, pk=pk)
        if not _is_order_viewer(request.user, attachment.order):
            return self.error_response(
                'Not allowed to view this attachment', code='FORBIDDEN', status_code=403
            )
        if not attachment.file or not attachment.file.storage.exists(attachment.file.name):
            return self.error_response(
                'Attachment file not found', code='NOT_FOUND', status_code=404
            )
        content_type = attachment.mime_type or 'application/octet-stream'
        file_obj = attachment.file.open('rb')
        response = FileResponse(file_obj, content_type=content_type)
        fname = attachment.original_filename or os.path.basename(attachment.file.name)
        response['Content-Disposition'] = f'inline; filename="{fname}"'
        return response
