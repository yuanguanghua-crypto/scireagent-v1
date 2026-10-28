import logging
import os
import uuid
from datetime import timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction

from core.db_retry import retry_on_deadlock
from django.db.models import Sum
from django.utils import timezone

logger = logging.getLogger(__name__)

from .models import (
    Order, OrderItem, Invoice, PaymentRecord, ShippingRecord,
    ShippingRecordItem, PoAttachment, StatusLog, InvoiceSequence,
    OrderSequence, InvalidTransitionError, Basket, business_today,
)
from apps.inventory.models import Allocation
from apps.inventory.services import InventoryService
from apps.notifications.services import EmailService


class TransactionService:
    """交易层域服务"""

    @staticmethod
    @transaction.atomic
    def create_order(user, items_data: list) -> Order:
        """创建订单及其明细"""
        order = Order.objects.create(
            user=user,
            order_no=f'ORD-{uuid.uuid4().hex[:8].upper()}',
        )
        total = 0
        for item in items_data:
            OrderItem.objects.create(order=order, **item)
            total += item.get('unit_price', 0) * item.get('quantity', 1)
        order.subtotal = total
        order.grand_total = total
        order.save(update_fields=['subtotal', 'grand_total'])
        return order

    @staticmethod
    def add_to_basket(user, product_id, sku_id, quantity=1):
        """添加商品到购物车"""
        basket_item, created = Basket.objects.update_or_create(
            user=user, sku_id=sku_id,
            defaults={'product_id': product_id, 'quantity': quantity}
        )
        return basket_item


class PoNumberConflictError(Exception):
    """PO 号唯一冲突 — View 捕获后返回 409 信封。"""
    pass


class OrderStateMachine:
    """订单状态机 — 唯一推进入口，每次变更写 StatusLog。"""

    VALID_TRANSITIONS = Order.VALID_TRANSITIONS

    @classmethod
    def can_transition(cls, order: Order, new_status: str) -> bool:
        return new_status in cls.VALID_TRANSITIONS.get(order.status, [])

    @classmethod
    def transition_to(cls, order: Order, new_status: str, actor=None,
                      note: str = '', action_type=None):
        if not cls.can_transition(order, new_status):
            raise InvalidTransitionError(
                f'Cannot transition from {order.status} to {new_status}'
            )
        from_status = order.status
        order.status = new_status
        order.save(update_fields=['status', 'updated_at'])
        StatusLog.objects.create(
            order=order,
            actor=actor,
            action_type=action_type or StatusLog.ActionType.STATUS_CHANGE,
            from_status=from_status,
            to_status=new_status,
            note=note,
        )
        return order


class PoSubmissionService:
    """PO 提交 — 建 Order(PO_RECEIVED)+附件+StatusLog+入队邮件。"""

    PO_ATTACHMENT_ALLOWED_MIME = {'application/pdf', 'image/png', 'image/jpeg'}
    PO_ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024

    @classmethod
    @retry_on_deadlock()          # 必须在 atomic **外面**：死锁时事务已被回滚
    @transaction.atomic
    def submit(cls, user, data: dict, files: list = None, actor=None) -> Order:
        # ★ PO 号不强制（口径 2026-10-14）：空/未填 → 存 None（unique 允许多个 NULL，不冲突）。
        po_number = (data.get('po_number') or '').strip() or None
        if po_number:
            # 唯一冲突 → 由 View 转 409 信封（仅非空时校验）
            if Order.objects.filter(po_number=po_number).exists():
                raise PoNumberConflictError(po_number)

        org = getattr(user, 'organization', None)
        order = Order.objects.create(
            user=user,
            organization=org,
            order_no=f'ORD-{uuid.uuid4().hex[:8].upper()}',
            status=Order.Status.PO_RECEIVED,
            po_number=po_number,
            grant_code=data.get('grant_code', '') or '',
            shipping_method=data.get('shipping_method', '') or '',
            requested_delivery_date=data.get('requested_delivery_date'),
            shipping_name=data.get('shipping_name', '') or '',
            shipping_address=data.get('shipping_address', '') or '',
            shipping_phone=data.get('shipping_phone', '') or '',
            shipping_email=data.get('shipping_email', '') or '',
            billing_name=data.get('billing_name', '') or '',
            billing_address=data.get('billing_address', '') or '',
            notes=data.get('notes', '') or '',
            payment_terms=data.get('payment_terms', Order.PaymentTerms.NET30),
        )
        if data.get('shipping_address_ref_id'):
            order.shipping_address_ref_id = data['shipping_address_ref_id']
        if data.get('billing_address_ref_id'):
            order.billing_address_ref_id = data['billing_address_ref_id']
        if data.get('quote_id'):
            order.quote_id = data['quote_id']
        order.save(update_fields=['shipping_address_ref_id', 'billing_address_ref_id', 'quote_id'])

        total = 0
        for item in data.get('items', []):
            # ★ v4.1 对抗性自测 Fix：unit_price 服务端按 SKU 现价覆盖（客户端提交不可信）
            from apps.commerce.models import SKU
            sku = SKU.objects.select_related('product').get(pk=item['sku_id'])
            unit_price = sku.price or Decimal('0')
            oi = OrderItem.objects.create(
                order=order,
                product_id=item.get('product_id') or sku.product_id,
                sku_id=item['sku_id'],
                quantity=item['quantity'],
                unit_price=unit_price,
            )
            total += unit_price * item['quantity']
        if total:
            order.subtotal = total
            order.grand_total = total
            # ★ D1 免税（P0-5）：当前税制恒 0；免税机构税为零，非免税机构行为不变。
            #   未来若引入税率，须按 order.tax_exempt_id 决定是否计税。
            order.tax_total = 0
            order.save(update_fields=['subtotal', 'grand_total', 'tax_total'])

        # 附件（双校验：白名单 + 10MB）
        for f in (files or []):
            cls._validate_attachment(f)
            PoAttachment.objects.create(
                order=order,
                file=f,
                original_filename=getattr(f, 'name', ''),
                mime_type=getattr(f, 'content_type', ''),
                file_size=getattr(f, 'size', 0),
                uploaded_by=user,
            )

        # 初始状态日志
        StatusLog.objects.create(
            order=order, actor=actor or user,
            action_type=StatusLog.ActionType.STATUS_CHANGE,
            from_status='', to_status=Order.Status.PO_RECEIVED,
            note='PO submitted',
        )
        # 入队邮件（不实际发送）
        EmailService.enqueue(
            'po_submitted',
            to=[user.email] if getattr(user, 'email', None) else [],
            ctx={'order_no': order.order_no, 'po_number': po_number},
        )
        logger.info('PO submitted: order_no=%s po_number=%s user_id=%s',
                      order.order_no, order.po_number, user.id)
        return order

    @classmethod
    def _validate_attachment(cls, f):
        ctype = getattr(f, 'content_type', '')
        if ctype not in cls.PO_ATTACHMENT_ALLOWED_MIME:
            raise ValueError(f"Unsupported attachment type '{ctype}'. Allowed: pdf, png, jpeg.")
        if getattr(f, 'size', 0) > cls.PO_ATTACHMENT_MAX_BYTES:
            raise ValueError('Attachment too large (max 10MB).')


class OrderNoService:
    """checkout 订单号原子取号 — 独立日计数器（OrderSequence）。

    ★ 修的是什么：checkout 曾用
      `Order.objects.filter(created_at__gte=day_start, created_at__lt=day_end).count() + 1`
      取序号。该count() 不区分单据来源 ⇒ uuid 版 PO 单被计入（生产 2026-07-17
      实测 004-007 跳号），且删单后会回退 ⇒ 撞已存在单号。
      改用专用计数器后，序号只数 checkout 单，且单调不回退。

    ★ 口径：只服务 checkout（ORD-YYYYMMDD-NNN，日粒度）。
      PO 提交走 `PoSubmissionService.submit` 的 uuid 版单号，与本计数器无关，
      不得改动那条路径（生产 po_views 在调）。
    """

    @classmethod
    @transaction.atomic
    def next_checkout_order_no(cls, biz_date=None) -> str:
        """返回下一个 checkout 单号 `ORD-YYYYMMDD-NNN`。

        :param biz_date: 业务日历日；None 表示取当前业务日。
            ⚠️ 必须与调用方用于订单落库的口径一致（同一业务日）。
        """
        if biz_date is None:
            biz_date = business_today()
        seq, _ = OrderSequence.objects.select_for_update().get_or_create(
            biz_date=biz_date, defaults={'last_number': 0},
        )
        seq.last_number += 1
        seq.save(update_fields=['last_number'])
        return f'ORD-{biz_date.strftime("%Y%m%d")}-{seq.last_number:03d}'


class InvoiceService:
    """开票 — 独立计数器原子取号 + reportlab PDF + 推进订单状态。"""

    NET_DAYS = {
        Order.PaymentTerms.NET30: 30,
        Order.PaymentTerms.NET45: 45,
        Order.PaymentTerms.NET60: 60,
    }

    @classmethod
    @transaction.atomic
    def _next_invoice_no(cls, year: int) -> str:
        seq, _ = InvoiceSequence.objects.select_for_update().get_or_create(
            year=year, defaults={'last_number': 0}
        )
        seq.last_number += 1
        seq.save(update_fields=['last_number'])
        return f'INV-{year}-{seq.last_number:04d}'

    @classmethod
    @retry_on_deadlock()          # 必须在 atomic **外面**：死锁时事务已被回滚
    @transaction.atomic
    def issue(cls, order: Order, payment_terms: str = None, actor=None) -> Invoice:
        if order.status != Order.Status.DELIVERED:
            raise InvalidTransitionError('Order must be DELIVERED before invoicing')
        if hasattr(order, 'invoice') and order.invoice:
            raise ValueError('Invoice already exists for this order')

        terms = payment_terms or order.payment_terms
        issued_at = timezone.now()
        days = cls.NET_DAYS.get(terms, 30)
        # 账期与票号年份都按业务日历日（默认东八区）判定：生产 TIME_ZONE='UTC'，
        # 东八区 00:00-08:00 期间 UTC 仍在前一天，用 UTC 会让 due_date 早一天、
        # 跨年时开出上一年份的票号。
        issued_biz = issued_at.astimezone(ZoneInfo(settings.BUSINESS_TIME_ZONE))
        due_date = (issued_biz + timedelta(days=days)).date()
        invoice_no = cls._next_invoice_no(issued_biz.year)

        invoice = Invoice.objects.create(
            order=order,
            invoice_no=invoice_no,
            status=Invoice.Status.ISSUED,
            issued_at=issued_at,
            due_date=due_date,
            payment_terms=terms,
            subtotal=order.subtotal,
            tax_total=order.tax_total,
            grand_total=order.grand_total,
            currency=order.currency,
        )
        cls.generate_invoice_pdf(invoice)
        OrderStateMachine.transition_to(
            order, Order.Status.INVOICED, actor=actor,
            action_type=StatusLog.ActionType.INVOICE,
            note=f'Invoice {invoice_no} issued',
        )
        EmailService.enqueue(
            'invoice_issued',
            to=[order.shipping_email] if order.shipping_email else [],
            ctx={'order_no': order.order_no, 'invoice_no': invoice_no,
                 'due_date': str(due_date)},
        )
        logger.info('Invoice issued: invoice_no=%s order_no=%s',
                      invoice.invoice_no, order.order_no)
        return invoice

    @classmethod
    def generate_invoice_pdf(cls, invoice: Invoice) -> str:
        """reportlab 生成 Invoice PDF，存 media/invoices/，返回路径。"""
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet

        out_dir = os.path.join(settings.MEDIA_ROOT, 'invoices')
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f'{invoice.invoice_no}.pdf')

        doc = SimpleDocTemplate(path, pagesize=letter)
        styles = getSampleStyleSheet()
        story = [
            Paragraph('INVOICE', styles['Title']),
            Spacer(1, 6 * mm),
            Paragraph(f'Invoice No: {invoice.invoice_no}', styles['Normal']),
            Paragraph(f'Order: {invoice.order.order_no}', styles['Normal']),
            Paragraph(f'Issued: {invoice.issued_at.date()}', styles['Normal']),
            Paragraph(f'Due: {invoice.due_date}', styles['Normal']),
            Paragraph(f'Terms: {invoice.payment_terms}', styles['Normal']),
        ]
        # ★ D1 免税（P0-5）：免税机构在发票上标注 Tax Exempt ID
        if invoice.order.tax_exempt_id:
            story.append(Paragraph(
                f'Tax Exempt ID: {invoice.order.tax_exempt_id}', styles['Normal']
            ))
        story.append(Spacer(1, 4 * mm))
        rows = [['SKU', 'Qty', 'Unit', 'Subtotal']]
        for item in invoice.order.items.all():
            rows.append([
                item.sku.sku_code if item.sku else '-',
                str(item.quantity),
                f'{item.unit_price}',
                f'{item.subtotal}',
            ])
        rows.append(['', '', 'Total', f'{invoice.grand_total} {invoice.currency}'])
        table = Table(rows, colWidths=[60 * mm, 20 * mm, 30 * mm, 40 * mm])
        table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ]))
        story.append(table)
        # ★ v4.1 DEV-4：RUO 法定标注 — 发票 PDF 页脚
        if any(item.sku and getattr(item.sku, 'is_ruo', True) for item in invoice.order.items.all()):
            story.append(Spacer(1, 6 * mm))
            story.append(Paragraph(
                'For Research Use Only. Not for use in diagnostic or therapeutic procedures.',
                styles['Normal']
            ))
        doc.build(story)
        return path


class ShippingService:
    """发货 — 分批发建记录；mark_shipped/delivered 释放 Allocation 并推进订单状态。"""

    @classmethod
    @transaction.atomic
    def create_shipment(cls, order: Order, carrier: str, items: list,
                        tracking_number: str = '', tracking_url: str = '',
                        estimated_delivery=None, notes: str = '', actor=None) -> ShippingRecord:
        # ★ 2026-10-13：**先校验全部 order_item 归属本订单，再落库**。
        #   此前在循环内 `OrderItem.objects.get(pk=..., order=order)` 且**未捕获 DoesNotExist**，
        #   异常一路上抛 ⇒ 500（本该是 400）。本方法本就有 @transaction.atomic ⇒ 数据不会残留半成品，
        #                 缺的只是"错误语义"。（实测：前端发的结构恰好正确，所以 UI 不踩；API 消费者/集成方会踩。）
        # ★ v4.1 对抗性自测 Fix 2：发货单创建必须校验订单状态（此前任意状态都能挂 shipment）
        if order.status not in ('confirmed', 'in_production'):
            raise InvalidTransitionError(
                f'Cannot create shipment for order in status {order.status}; '
                f'expected confirmed or in_production')
        item_ids = [it['order_item_id'] for it in items]
        items_by_id = {
            oi.pk: oi for oi in OrderItem.objects.filter(order=order, pk__in=item_ids)
        }
        invalid = [i for i in item_ids if i not in items_by_id]
        if invalid:
            raise ValueError(
                f'order_item(s) {invalid} do not belong to order {order.pk}'
            )

        shipment = ShippingRecord.objects.create(
            order=order,
            status=ShippingRecord.Status.PREPARING,
            carrier=carrier or '',
            tracking_number=tracking_number or '',
            tracking_url=tracking_url or '',
            estimated_delivery=estimated_delivery,
            notes=notes or '',
        )
        for it in items:
            ShippingRecordItem.objects.create(
                shipping_record=shipment,
                order_item=items_by_id[it['order_item_id']],
                quantity=it['quantity'],
            )
        StatusLog.objects.create(
            order=order, actor=actor, action_type=StatusLog.ActionType.SHIPMENT,
            from_status=order.status, to_status=order.status,
            note=f'Shipment #{shipment.id} created',
        )
        return shipment

    @classmethod
    @transaction.atomic
    def mark_shipped(cls, shipment_id: int, actor=None) -> ShippingRecord:
        shipment = ShippingRecord.objects.select_for_update().get(pk=shipment_id)
        if shipment.status == ShippingRecord.Status.SHIPPED:
            return shipment
        shipment.status = ShippingRecord.Status.SHIPPED
        shipment.shipped_at = timezone.now()
        shipment.save(update_fields=['status', 'shipped_at', 'updated_at'])

        # 释放对应 Allocation（实物已出）
        # ★ 2026-10-16 修 P0：原代码 `remaining` 只决定何时停止遍历，释放量仍是
        #   alloc.quantity 整额（InventoryService.release 无条件全额释放）
        #   ⇒ 部分发货（占用 10 / 发货 5）把 allocated 直接归零，账实不符。
        #   现按 `min(remaining, alloc 剩余占用量)` 部分释放；发完整批才转 SHIPPED。
        for item in shipment.items.select_related('order_item').all():
            remaining = item.quantity
            for alloc in Allocation.objects.filter(
                order_item=item.order_item, status=Allocation.Status.RESERVED
            ).order_by('id'):
                if remaining <= 0:
                    break
                released = InventoryService.release(alloc, quantity=remaining)
                remaining -= released

        # 任一批 shipped → 推进订单到 SHIPPED（仅当状态机允许）
        order = shipment.order
        if OrderStateMachine.can_transition(order, Order.Status.SHIPPED):
            OrderStateMachine.transition_to(
                order, Order.Status.SHIPPED, actor=actor,
                action_type=StatusLog.ActionType.SHIPMENT,
                note=f'Shipment #{shipment.id} marked shipped',
            )
        else:
            # ★ 2026-10-28 修：**后续批次**发货时订单已是 shipped，`can_transition` 为假
            #   ⇒ 原来整段被跳过，「第 2 批已发货」这个动作**在 status_log 里完全丢失**。
            #   实测（订单 1297，两批）：实际发生 4 个动作（2 发 2 签），日志只留 2 条，
            #   丢的正是 #548 marked shipped 与 #547 delivered ⇒ 订单详情的 Status Timeline 缺条，
            #   运营/客服查不到某一批到底什么时候发的。
            #   与 `create_shipment` 的行为也不一致（建单无条件写 `Shipment #N created`）。
            #   ⇒ 状态不变的批次动作也必须留痕（from=to=当前状态）。
            StatusLog.objects.create(
                order=order, actor=actor,
                action_type=StatusLog.ActionType.SHIPMENT,
                from_status=order.status, to_status=order.status,
                note=f'Shipment #{shipment.id} marked shipped',
            )
        EmailService.enqueue(
            'shipped',
            to=[order.shipping_email] if order.shipping_email else [],
            ctx={'order_no': order.order_no, 'tracking_number': shipment.tracking_number},
        )
        return shipment

    @classmethod
    @transaction.atomic
    def mark_delivered(cls, shipment_id: int, received_by: str = '', actor=None) -> ShippingRecord:
        shipment = ShippingRecord.objects.select_for_update().get(pk=shipment_id)
        # ★ 2026-10-28：幂等保护。此前重复调用会重复写时间线（双击/重试即产生重复条目）。
        if shipment.status == ShippingRecord.Status.DELIVERED:
            return shipment
        shipment.status = ShippingRecord.Status.DELIVERED
        shipment.received_by = received_by or ''
        shipment.delivered_at = timezone.now()
        shipment.save(update_fields=['status', 'received_by', 'delivered_at', 'updated_at'])

        order = shipment.order
        if cls._all_items_delivered(order):
            OrderStateMachine.transition_to(
                order, Order.Status.DELIVERED, actor=actor,
                action_type=StatusLog.ActionType.SHIPMENT,
                note=f'Shipment #{shipment.id} delivered — order fully received',
            )
            EmailService.enqueue(
                'delivered',
                to=[order.shipping_email] if order.shipping_email else [],
                ctx={'order_no': order.order_no},
            )
        else:
            # ★ 2026-10-28 修（同 mark_shipped）：**中间批次**签收时订单还不能转 delivered
            #   ⇒ 原来不写日志，「第 1 批已签收、还差 1 批」这个事实在时间线上不可见。
            #   实测订单 1297 丢了 `#547 delivered` 这条。
            StatusLog.objects.create(
                order=order, actor=actor,
                action_type=StatusLog.ActionType.SHIPMENT,
                from_status=order.status, to_status=order.status,
                note=f'Shipment #{shipment.id} delivered — awaiting remaining items',
            )
        return shipment

    @staticmethod
    def _all_items_delivered(order: Order) -> bool:
        items = list(order.items.all())
        if not items:
            return False
        if order.shipments.exclude(status=ShippingRecord.Status.DELIVERED).exists():
            return False
        for oi in items:
            delivered = sum(
                sri.quantity for sri in ShippingRecordItem.objects.filter(
                    order_item=oi,
                    shipping_record__status=ShippingRecord.Status.DELIVERED,
                )
            )
            if delivered < oi.quantity:
                return False
        return True

    @classmethod
    def generate_packing_list(cls, shipment: ShippingRecord) -> str:
        """reportlab 生成 Packing List PDF。"""
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet

        out_dir = os.path.join(settings.MEDIA_ROOT, 'invoices')
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f'packing_list_{shipment.id}.pdf')

        doc = SimpleDocTemplate(path, pagesize=letter)
        styles = getSampleStyleSheet()
        story = [
            Paragraph('PACKING LIST', styles['Title']),
            Spacer(1, 6 * mm),
            Paragraph(f'Shipment #{shipment.id} — Order {shipment.order.order_no}', styles['Normal']),
            Paragraph(f'Carrier: {shipment.carrier}  Tracking: {shipment.tracking_number}', styles['Normal']),
            Spacer(1, 4 * mm),
        ]
        rows = [['SKU', 'Qty']]
        for item in shipment.items.select_related('order_item__sku').all():
            sku_code = item.order_item.sku.sku_code if item.order_item.sku else '-'
            rows.append([sku_code, str(item.quantity)])
        table = Table(rows, colWidths=[80 * mm, 30 * mm])
        table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ]))
        story.append(table)
        doc.build(story)
        return path


class PaymentArService:
    """收款与 AR Aging 聚合。"""

    @classmethod
    @retry_on_deadlock()          # 必须在 atomic **外面**：死锁时事务已被回滚
    @transaction.atomic
    def pay(cls, invoice: Invoice, amount, method: str, paid_at=None,
            actor=None, reference: str = '', notes: str = '') -> Invoice:
        paid_at = paid_at or timezone.now()
        PaymentRecord.objects.create(
            invoice=invoice,
            method=method,
            amount=amount,
            currency=invoice.currency,
            reference=reference or '',
            status=PaymentRecord.Status.VERIFIED,
            verified_by=actor,
            verified_at=paid_at,
            notes=notes or '',
        )
        # ★ D2 部分付款：用 Invoice.amount_paid 派生属性（含刚入账的这笔）判断是否付清。
        if invoice.amount_paid >= invoice.grand_total:
            invoice.status = Invoice.Status.PAID
            invoice.paid_at = paid_at
            invoice.save(update_fields=['status', 'paid_at', 'updated_at'])
            OrderStateMachine.transition_to(
                invoice.order, Order.Status.PAID, actor=actor,
                action_type=StatusLog.ActionType.INVOICE, note='Invoice paid'
            )
        logger.info('Payment recorded: invoice_no=%s amount=%s method=%s',
                      invoice.invoice_no, amount, method)
        return invoice

    @staticmethod
    def ar_aging() -> dict:
        """按 due_date 聚合未付发票到 30/60/90 桶。"""
        # 必须用 business_today()：is_overdue 用业务日历日，这里若用 UTC 日期，
        # 东八区 00:00-08:00 会同时出现"已逾期"且"落在 current 桶"的自相矛盾状态。
        today = business_today()
        unpaid = Invoice.objects.filter(
            status__in=[Invoice.Status.ISSUED, Invoice.Status.OVERDUE]
        ).select_related('order')
        buckets = {
            'current': {'count': 0, 'amount': 0},
            '30': {'count': 0, 'amount': 0},
            '60': {'count': 0, 'amount': 0},
            '90_plus': {'count': 0, 'amount': 0},
        }
        for inv in unpaid:
            age = (today - inv.due_date).days
            if age <= 0:
                b = 'current'
            elif age <= 30:
                b = '30'
            elif age <= 60:
                b = '60'
            else:
                b = '90_plus'
            buckets[b]['count'] += 1
            buckets[b]['amount'] += float(inv.grand_total)
        total_outstanding = sum(v['amount'] for v in buckets.values())
        return {
            'as_of': str(today),
            'buckets': buckets,
            'total_outstanding': total_outstanding,
        }

