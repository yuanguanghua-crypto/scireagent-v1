"""PO 门户 P0 端点 — 提交/审核/发货/开票/收款/AR（信封统一，跨模型写入走 Service）。"""
import json
import os

from django.conf import settings
from django.db import transaction
from django.contrib.auth import get_user_model
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
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
            # ★ 2026-11-27（A-149）：补 `id` —— 前端提交成功后要跳到订单详情
            #   （之前只有 order_no，前端无处可跳，于是停留在 /po/submit 只显示一行
            #   "PO submitted successfully"，用户以为没成功）。加字段是纯增量，
            #   不改既有键，消费方可继续只读 order_no。
            {'id': order.id, 'order_no': order.order_no, 'status': order.status},
            status_code=201,
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


def _void_unreceived_shipments(order):
    """订单被取消/拒审时，作废该单下**未签收**的发货记录（A-262）。

    改前 `RejectOrderView` 与 `CancelOrderView` 都只做
    `transition_to(CANCELLED)` + `release_for_order`，**完全不碰 ShippingRecord**
    ⇒ 实测（QA Batch 21，TEST 单 ORD-20261115-001）：订单已 Cancelled，
    Shipment id24 仍是 `shipped`，详情页 Shipments 区照旧显示
    「Shipped / TEST-FU7-01-TRACK」。运营会一直去催一个已作废订单的物流。

    DELIVERED 的**不动**：货已签收是物理事实，取消订单不改变"它已经到达"这件事；
    把它改成 cancelled 反而会让对账时少了签收证据。

    返回作废条数（供调用方打日志）。用 queryset.update() 而非逐条 save()：
    无需触发任何钩子，且必须显式带 `updated_at`（auto_now 只在 save() 时生效）。
    """
    return ShippingRecord.objects.filter(
        order=order,
        status__in=[
            ShippingRecord.Status.PREPARING,
            ShippingRecord.Status.SHIPPED,
            ShippingRecord.Status.IN_TRANSIT,
        ],
    ).update(
        status=ShippingRecord.Status.CANCELLED,
        updated_at=timezone.now(),
    )


class RejectOrderView(EnvelopeMixin, APIView):
    """POST /api/v1/orders/<id>/reject/ — → CANCELLED。"""
    permission_classes = [IsProcurementOrAdmin]

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        # ★ 2026-11-26（A-159）：拒审必须写理由。
        #
        #   改前 `reason = request.data.get('reason', '')` 直接带进状态机 note
        #   ⇒ 空原因也能把 PO 单推进到 CANCELLED（实测 QA Batch 15：对 ORD-6942185F
        #   点 Reject、原因留空，未被拦截，订单由 PO Received 变 Cancelled 并移出待审列表）。
        #
        #   为什么必须拦：拒审是**不可逆的状态跃迁**，理由是该单唯一的书面依据 ——
        #   采购方追问"为什么拒"时，数据库里只留一个空 note。
        #   前端 `PoReviewDesk.reject` 原本也是 `rejectReason[id] || ''` 直接发。
        #
        #   ⚠️ 只给 Reject 加，**不给 CancelOrderView 加**：`api/orders.js` 的 cancel
        #   调用是 `http.post('/orders/<id>/cancel/')`，**完全不传 body** ⇒ 加必填会
        #   直接把现有的"运营手动取消"打 400。
        reason = (request.data.get('reason') or '').strip()
        if not reason:
            return self.error_response(
                '拒绝订单必须填写原因（采购方会据此追问，也会写入状态日志）。',
                code='REASON_REQUIRED', status_code=400,
            )
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
                # ★ 2026-11-26（A-262）：作废该单下未签收的发货记录
                #   （DELIVERED 的不动 —— 已签收是物理事实）
                _void_unreceived_shipments(order)
        except InvalidTransitionError as e:
            return self.error_response(str(e), code='INVALID_TRANSITION', status_code=400)
        return self.success_response(OrderDetailSerializer(order, context={'request': request}).data)


class CancelOrderView(EnvelopeMixin, APIView):
    """POST /api/v1/orders/<id>/cancel/ — 取消订单（运营 + 客户本人）。

    ★ 2026-11-27（A-171）：**客户侧原本没有任何取消入口** —— 详情页实测
    buttons=['', '', 'T']、全文无 "Cancel Order"，而运营端 Confirmed 及之后
    各阶段都有按钮。同一件事在两侧可用性完全不同：客户想撤单只能发邮件。

    口径（授权按"谁 + 什么状态"两维同时收敛）：
      · 运营/管理员（is_staff 或 role ∈ procurement/admin）：维持原行为，
        任意非终态可取消（状态机自己会拒绝非法转移）。
      · 客户本人：只能取消**自己的**单，且仅限生产开始前的两个阶段
        （`po_received` / `confirmed`）。一旦 `in_production` 之后，物料与
        排产已经动过，取消要人工核算，不能给自助入口。
      · 别人的单：**404**（不泄露订单是否存在）。

    刻意**不新增端点**：说明书里的端点数是被 `audit_manual_numbers.py` 审的
    固定口径，多一个端点就要连带改文档；这里是同一个动作的授权范围扩展。
    """
    permission_classes = [IsAuthenticated]

    #: 客户自助取消的允许状态（生产开始即关闭）
    CUSTOMER_CANCELLABLE = frozenset({
        Order.Status.PO_RECEIVED.value,
        Order.Status.CONFIRMED.value,
    })

    @staticmethod
    def _is_internal(user) -> bool:
        return bool(user.is_staff or user.role in ('procurement', 'admin'))

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        reason = request.data.get('reason', '')
        if not self._is_internal(request.user):
            if order.user_id != request.user.pk:
                # 不是自己的单：当作不存在，避免用 403/404 差异探测订单号
                raise Http404
            if order.status not in self.CUSTOMER_CANCELLABLE:
                return self.error_response(
                    'This order can no longer be cancelled online. '
                    'Please contact us and our team will help.',
                    code='CANCEL_NOT_ALLOWED',
                    status_code=400,
                )
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
                # ★ 2026-11-26（A-262）：作废该单下未签收的发货记录
                #   （DELIVERED 的不动 —— 已签收是物理事实）
                _void_unreceived_shipments(order)
        except InvalidTransitionError as e:
            return self.error_response(str(e), code='INVALID_TRANSITION', status_code=400)
        return self.success_response(OrderDetailSerializer(order, context={'request': request}).data)


class AssignableRepListView(EnvelopeMixin, APIView):
    """GET /api/v1/orders/assignable-reps/ —— 可指派的 Rep 候选（A-160，2026-11-26 新增）。

    ## 改前是什么样
    审核台要求运营**手填数字 user id**（`<input placeholder="Rep ID">`），而
    `AssignRepView` 只接受 `role in ['procurement','admin']`。QA Batch 15 实测：
    填 `REP-TEST-20261112` → "Action failed"；填 `1` → "Invalid rep_id"。
    运营既不知道该填谁，也无从知道有哪些人可选 —— 这个功能上线以来**一次都没被用过**
    （生产 66 单里 0 单有 assigned_rep）。

    ## 为什么不放开到所有角色
    `assigned_rep` 的业务语义是"这笔应收的催款责任人" —— 证据见 `test_ar_assign.py`
    把 assign-rep 与 AR 账龄放在同一个测试文件里。与研究员的职责无关；
    放开到所有角色会让这个字段彻底失去含义。

    ## 为什么"不过滤测试账号"，而是把 email 一并给出
    `User` **没有** `is_test_fixture` 之类的字段，无法可靠区分测试号与真号
    （生产实测两个候选 `smoke`/`s@e.com`、`proc_mgr`/`proc@example.com` 都是占位邮箱）。
    与其用不可靠的规则误删真实账号，不如把 username + email 一起返回，
    让运营自己判断 —— 占位邮箱一眼可辨。
    """

    permission_classes = [IsProcurementOrAdmin]

    def get(self, request):
        qs = (User.objects
              .filter(role__in=['procurement', 'admin'], is_active=True)
              .order_by('username'))
        return self.success_response([
            {'id': u.pk, 'username': u.username, 'email': u.email, 'role': u.role}
            for u in qs
        ])


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


class InvoiceListView(EnvelopeMixin, APIView):
    """GET /api/v1/invoices/ —— 发票列表（A-167，2026-11-26 新增）。

    ## 改前是什么样
    `/api/v1/invoices/` 与 `/api/v1/invoices` **都是 Resolver404** —— 路由确实不存在，
    不是"对匿名不可见"。发票 id 只能进容器跑 ORM 才拿得到，而运营/客服对账时
    第一句话就是"这单的发票号是什么、金额多少、付了没"。

    ## 可见性
    与 `OrderViewSet.get_queryset` 同口径：
      · 内部人员（`is_staff` 或 role ∈ procurement/admin）看全部
      · 客户只看**自己订单**的发票（经 `order__user` 过滤）
    这是刻意的：发票含金额与付款记录，跨客户可见就是财务数据事故。

    ## 参数
      status —— draft / issued / paid / overdue / void，非法值 400（不静默忽略）
      order  —— 订单 id，精确过滤（对账时按单查）
      page / page_size —— 默认 20 / 上限 500（与 core/pagination 的同口径）
    """
    permission_classes = [IsAuthenticated]

    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 500

    def get(self, request):
        user = request.user
        qs = (Invoice.objects
              .select_related('order')
              .prefetch_related('payments')
              .order_by('-created_at'))

        if not (user.is_staff or getattr(user, 'role', '') in ('procurement', 'admin')):
            qs = qs.filter(order__user=user)

        status_param = (request.query_params.get('status') or '').strip()
        if status_param:
            if status_param not in Invoice.Status.values:
                return self.error_response(
                    f'未知的发票状态：{status_param}。可选：{", ".join(Invoice.Status.values)}',
                    code='INVALID_STATUS', status_code=400,
                )
            qs = qs.filter(status=status_param)

        order_param = (request.query_params.get('order') or '').strip()
        if order_param:
            if not order_param.isdigit():
                return self.error_response(
                    'order 参数必须是订单 id（数字）', code='INVALID_ORDER', status_code=400,
                )
            qs = qs.filter(order_id=int(order_param))

        try:
            page = max(int(request.query_params.get('page', 1)), 1)
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = min(int(request.query_params.get('page_size', self.DEFAULT_PAGE_SIZE)),
                            self.MAX_PAGE_SIZE)
        except (TypeError, ValueError):
            page_size = self.DEFAULT_PAGE_SIZE
        page_size = max(page_size, 1)

        total = qs.count()
        start = (page - 1) * page_size
        rows = qs[start:start + page_size]

        return self.success_response(
            InvoiceSerializer(rows, many=True).data,
            meta={'pagination': {
                'count': total, 'page': page, 'page_size': page_size,
                'next': page * page_size < total,
            }},
        )
