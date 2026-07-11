import os
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (
    Order, OrderItem, Invoice, PaymentRecord, ShippingRecord,
    ShippingRecordItem, PoAttachment, StatusLog, InvoiceSequence,
    InvalidTransitionError, Basket,
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
    @transaction.atomic
    def submit(cls, user, data: dict, files: list = None, actor=None) -> Order:
        po_number = data.get('po_number', '').strip()
        if not po_number:
            raise ValueError('po_number is required')
        # 唯一冲突 → 由 View 转 409 信封
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
            unit_price = Decimal(str(item.get('unit_price', 0) or 0))
            oi = OrderItem.objects.create(
                order=order,
                product_id=item.get('product_id'),
                sku_id=item['sku_id'],
                quantity=item['quantity'],
                unit_price=unit_price,
            )
            total += unit_price * item['quantity']
        if total:
            order.subtotal = total
            order.grand_total = total
            order.save(update_fields=['subtotal', 'grand_total'])

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
        return order

    @classmethod
    def _validate_attachment(cls, f):
        ctype = getattr(f, 'content_type', '')
        if ctype not in cls.PO_ATTACHMENT_ALLOWED_MIME:
            raise ValueError(f"Unsupported attachment type '{ctype}'. Allowed: pdf, png, jpeg.")
        if getattr(f, 'size', 0) > cls.PO_ATTACHMENT_MAX_BYTES:
            raise ValueError('Attachment too large (max 10MB).')


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
    @transaction.atomic
    def issue(cls, order: Order, payment_terms: str = None, actor=None) -> Invoice:
        if order.status != Order.Status.DELIVERED:
            raise InvalidTransitionError('Order must be DELIVERED before invoicing')
        if hasattr(order, 'invoice') and order.invoice:
            raise ValueError('Invoice already exists for this order')

        terms = payment_terms or order.payment_terms
        issued_at = timezone.now()
        days = cls.NET_DAYS.get(terms, 30)
        due_date = (issued_at + timedelta(days=days)).date()
        invoice_no = cls._next_invoice_no(issued_at.year)

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
            Spacer(1, 4 * mm),
        ]
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
        doc.build(story)
        return path


class ShippingService:
    """发货 — 分批发建记录；mark_shipped/delivered 释放 Allocation 并推进订单状态。"""

    @classmethod
    @transaction.atomic
    def create_shipment(cls, order: Order, carrier: str, items: list,
                        tracking_number: str = '', tracking_url: str = '',
                        estimated_delivery=None, notes: str = '', actor=None) -> ShippingRecord:
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
            oi = OrderItem.objects.get(pk=it['order_item_id'], order=order)
            ShippingRecordItem.objects.create(
                shipping_record=shipment, order_item=oi, quantity=it['quantity']
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
        for item in shipment.items.select_related('order_item').all():
            remaining = item.quantity
            for alloc in Allocation.objects.filter(
                order_item=item.order_item, status=Allocation.Status.RESERVED
            ).order_by('id'):
                if remaining <= 0:
                    break
                InventoryService.release(alloc)
                remaining -= alloc.quantity

        # 任一批 shipped → 推进订单到 SHIPPED（仅当状态机允许）
        order = shipment.order
        if OrderStateMachine.can_transition(order, Order.Status.SHIPPED):
            OrderStateMachine.transition_to(
                order, Order.Status.SHIPPED, actor=actor,
                action_type=StatusLog.ActionType.SHIPMENT,
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
        total_paid = invoice.payments.filter(
            status=PaymentRecord.Status.VERIFIED
        ).aggregate(s=Sum('amount'))['s'] or 0
        if total_paid >= invoice.grand_total:
            invoice.status = Invoice.Status.PAID
            invoice.paid_at = paid_at
            invoice.save(update_fields=['status', 'paid_at', 'updated_at'])
            OrderStateMachine.transition_to(
                invoice.order, Order.Status.PAID, actor=actor,
                action_type=StatusLog.ActionType.INVOICE, note='Invoice paid'
            )
        return invoice

    @staticmethod
    def ar_aging() -> dict:
        """按 due_date 聚合未付发票到 30/60/90 桶。"""
        today = timezone.now().date()
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

