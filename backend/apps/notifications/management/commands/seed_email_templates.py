"""建/更新邮件模板种子数据 —— seed_email_templates。

为什么需要这个命令：`EmailService.enqueue()` 会按 `template_key` 查 `EmailTemplate`，
查不到时 subject/body 保持空串（调用方只传 key + ctx）⇒ 生产 outbox 里的 49 条全是空邮件。
本命令把模板补齐，幂等（按 key get_or_create），可重复执行。

用法：
  python manage.py seed_email_templates            # 只补缺失的
  python manage.py seed_email_templates --force    # 覆盖已有（会覆盖 Admin 里手改的内容！）
  python manage.py seed_email_templates --dry-run  # 只看会做什么

⚠️ 模板正文用 `str.format_map` 渲染（见 notifications/services.py:15），占位符是**单花括号**
   `{order_no}`。因此 HTML 里**不能出现裸 `{}`** —— CSS 块会被当成占位符吃掉。
   所有样式必须写成内联 `style="..."`，这是本文件所有模板的硬约束。
"""
from django.core.management.base import BaseCommand

from apps.notifications.models import EmailTemplate

# 所有模板共用的一段签名（避免每封都重复写）
_FOOTER_HTML = (
    '<hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0">'
    '<p style="color:#9ca3af;font-size:12px;line-height:1.6;margin:0">'
    'SciReAgent &middot; AI-native scientific reagent platform<br>'
    'This is an automated message. Please do not reply directly to this address.'
    '</p>'
)
_FOOTER_TEXT = (
    '\n\n---\nSciReAgent · AI-native scientific reagent platform\n'
    'This is an automated message. Please do not reply directly to this address.'
)


def _h(title: str) -> str:
    return f'<h2 style="color:#111827;font-size:18px;margin:0 0 16px">{title}</h2>'


def _p(text: str) -> str:
    return f'<p style="color:#374151;font-size:14px;line-height:1.7;margin:0 0 12px">{text}</p>'


def _box(inner: str) -> str:
    return (
        '<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;'
        f'padding:14px 16px;margin:0 0 16px">{inner}</div>'
    )


def _kv(k: str, v: str) -> str:
    return (
        '<tr>'
        f'<td style="color:#6b7280;font-size:13px;padding:4px 12px 4px 0;white-space:nowrap">{k}</td>'
        f'<td style="color:#111827;font-size:13px;padding:4px 0;font-weight:600">{v}</td>'
        '</tr>'
    )


def _btn(text: str, url: str) -> str:
    return (
        f'<p style="margin:20px 0"><a href="{url}" style="background:#2563eb;color:#ffffff;'
        'text-decoration:none;padding:10px 20px;border-radius:6px;font-size:14px;'
        f'display:inline-block">{text}</a></p>'
    )


# ── 模板定义 ────────────────────────────────────────────────────────────
# (key, subject, html, text, description, language)
TEMPLATES = [
    # 1. 注册验证（原先硬编码在 accounts/email.py，统一到这里）
    (
        'email_verification',
        'Verify your SciReAgent account',
        _h('Confirm your email address')
        + _p('Hi {username},')
        + _p('Thanks for registering with SciReAgent. Click the button below to verify '
             'your email address and activate your account.')
        + _btn('Verify email', '{verify_url}')
        + _p('This link expires in {expire_hours} hours. If the button does not work, '
             'copy this address into your browser:<br>'
             '<span style="color:#2563eb;word-break:break-all">{verify_url}</span>')
        + _p('If you did not create this account, you can safely ignore this email.')
        + _FOOTER_HTML,
        'Hi {username},\n\n'
        'Thanks for registering with SciReAgent. Open the link below to verify your email:\n'
        '{verify_url}\n\n'
        'This link expires in {expire_hours} hours. If you did not create this account, '
        'you can ignore this email.' + _FOOTER_TEXT,
        '注册验证邮件（register → verify → login）',
        'en',
    ),
    # 2. 订单确认
    (
        'order_confirmed',
        'Order {order_no} confirmed — SciReAgent',
        _h('Your order is confirmed')
        + _p('Thank you. We have received your order and it is now being processed.')
        + _box('<table style="border-collapse:collapse">' + _kv('Order number', '{order_no}') + '</table>')
        + _p('We will notify you again when your order ships.')
        + _FOOTER_HTML,
        'Your order {order_no} has been confirmed and is being processed.' + _FOOTER_TEXT,
        '订单确认（客户）',
        'en',
    ),
    # 3. PO 提交
    (
        'po_submitted',
        'Purchase order received for order {order_no}',
        _h('Purchase order received')
        + _p('We have received your purchase order and it is queued for review.')
        + _box('<table style="border-collapse:collapse">'
               + _kv('Order number', '{order_no}')
               + _kv('PO number', '{po_number}')
               + '</table>')
        + _p('Our procurement team will confirm acceptance shortly.')
        + _FOOTER_HTML,
        'We received your purchase order.\nOrder: {order_no}\nPO number: {po_number}' + _FOOTER_TEXT,
        'PO 提交确认（客户）',
        'en',
    ),
    # 4. 发票开具
    (
        'invoice_issued',
        'Invoice {invoice_no} issued for order {order_no}',
        _h('Your invoice is ready')
        + _p('An invoice has been issued for your order.')
        + _box('<table style="border-collapse:collapse">'
               + _kv('Invoice number', '{invoice_no}')
               + _kv('Order number', '{order_no}')
               + _kv('Due date', '{due_date}')
               + '</table>')
        + _p('Please quote the invoice number in any correspondence.')
        + _FOOTER_HTML,
        'Invoice {invoice_no} has been issued for order {order_no}.\nDue date: {due_date}'
        + _FOOTER_TEXT,
        '发票开具（客户）',
        'en',
    ),
    # 5. 已发货
    (
        'shipped',
        'Your order {order_no} has shipped',
        _h('Your order is on the way')
        + _p('Good news — your order has left our facility.')
        + _box('<table style="border-collapse:collapse">'
               + _kv('Order number', '{order_no}')
               + _kv('Tracking number', '{tracking_number}')
               + '</table>')
        + _p('Tracking information may take a few hours to become active with the carrier.')
        + _FOOTER_HTML,
        'Order {order_no} has shipped.\nTracking number: {tracking_number}' + _FOOTER_TEXT,
        '发货通知（客户）',
        'en',
    ),
    # 6. 已送达
    (
        'delivered',
        'Order {order_no} delivered',
        _h('Your order has been delivered')
        + _p('Your order has been recorded as fully received. Thank you for your business.')
        + _box('<table style="border-collapse:collapse">' + _kv('Order number', '{order_no}') + '</table>')
        + _p('If anything is missing or damaged, please contact us with the order number above.')
        + _FOOTER_HTML,
        'Order {order_no} has been delivered.' + _FOOTER_TEXT,
        '送达通知（客户）',
        'en',
    ),
    # 7. 密码重置（新增 P0）
    (
        'password_reset',
        'Reset your SciReAgent password',
        _h('Reset your password')
        + _p('Hi {username},')
        + _p('We received a request to reset the password for your SciReAgent account. '
             'Click the button below to choose a new password.')
        + _btn('Reset password', '{reset_url}')
        + _p('This link expires in {expire_hours} hours and can only be used once.')
        + _p('If you did not request a password reset, no action is needed — your current '
             'password remains active.')
        + _FOOTER_HTML,
        'Hi {username},\n\n'
        'Open the link below to reset your SciReAgent password:\n{reset_url}\n\n'
        'This link expires in {expire_hours} hours and can only be used once.\n'
        'If you did not request this, no action is needed.' + _FOOTER_TEXT,
        '密码重置（客户，P0）',
        'en',
    ),
    # 8. RFQ 提交确认（新增 P0）
    (
        'rfq_submitted',
        'We received your quote request #{rfq_id}',
        _h('Quote request received')
        + _p('Hi {contact_name},')
        + _p('Thank you for your request. Our specialists are reviewing it and will get '
             'back to you with a quotation.')
        + _box('<table style="border-collapse:collapse">'
               + _kv('Request number', '#{rfq_id}')
               + _kv('Items', '{items_count}')
               + '</table>')
        + _p('Please quote the request number above if you need to follow up.')
        + _FOOTER_HTML,
        'Hi {contact_name},\n\nWe received your quote request #{rfq_id} ({items_count} item(s)).\n'
        'Our specialists are reviewing it and will send you a quotation.' + _FOOTER_TEXT,
        'RFQ 提交确认（客户，P0）',
        'en',
    ),
    # 9. 运营收到新询价（新增 P0）
    (
        'rfq_received_internal',
        '[RFQ #{rfq_id}] New quote request from {company}',
        _h('New quote request')
        + _box('<table style="border-collapse:collapse">'
               + _kv('Request', '#{rfq_id}')
               + _kv('Company', '{company}')
               + _kv('Contact', '{contact_name}')
               + _kv('Email', '{contact_email}')
               + _kv('Items', '{items_count}')
               + '</table>')
        + _p('Open the RFQ inbox in the operations console to review and quote.')
        + _FOOTER_HTML,
        'New quote request #{rfq_id}\nCompany: {company}\nContact: {contact_name} <{contact_email}>\n'
        'Items: {items_count}' + _FOOTER_TEXT,
        '新询价通知（运营内部，P0）',
        'en',
    ),
    # 10. 报价已就绪（客户，P1）
    (
        'quote_ready',
        'Your quotation for request #{rfq_id} is ready',
        _h('Your quotation is ready')
        + _p('Hi {contact_name},')
        + _p('We have prepared a quotation for your request.')
        + _box('<table style="border-collapse:collapse">'
               + _kv('Request', '#{rfq_id}')
               + _kv('Items', '{items_count}')
               + _kv('Total', '{quoted_currency} {quoted_total}')
               + _kv('Valid until', '{quoted_valid_until}')
               + '</table>')
        + _p('{quoted_note}')
        + _p('Please reply to this email to confirm the order or discuss any adjustment.')
        + _FOOTER_HTML,
        'Hi {contact_name},\n\n'
        'Quotation for request #{rfq_id}\n'
        'Items: {items_count}\nTotal: {quoted_currency} {quoted_total}\n'
        'Valid until: {quoted_valid_until}\n\n{quoted_note}\n\n'
        'Reply to this email to confirm or discuss.' + _FOOTER_TEXT,
        '报价就绪通知（客户，P1）',
        'en',
    ),
    # 11. COA 发布（客户，P1）
    (
        'coa_published',
        'Certificate of Analysis available for {product_name}',
        _h('Your certificate of analysis is ready')
        + _p('The Certificate of Analysis for a product you ordered has been published.')
        + _box('<table style="border-collapse:collapse">'
               + _kv('Product', '{product_name}')
               + _kv('Catalog number', '{catalog_number}')
               + _kv('Batch / Lot', '{lot_number}')
               + _kv('Document', '{doc_id}')
               + '</table>')
        + _p('You can download it from the order detail page in your account.')
        + _FOOTER_HTML,
        'Certificate of Analysis published\n'
        'Product: {product_name}\nCatalog: {catalog_number}\nLot: {lot_number}\n'
        'Document: {doc_id}\n\nDownload it from your order detail page.' + _FOOTER_TEXT,
        'COA 发布通知（客户，P1）',
        'en',
    ),
    # 11. SDS 发布（客户，P1）
    (
        'sds_published',
        'Safety Data Sheet updated for {product_name}',
        _h('A safety data sheet has been published')
        + _p('A new Safety Data Sheet revision is available for a product you ordered.')
        + _box('<table style="border-collapse:collapse">'
               + _kv('Product', '{product_name}')
               + _kv('Catalog number', '{catalog_number}')
               + _kv('Revision', '{revision_no}')
               + _kv('Revised on', '{revised_at}')
               + '</table>')
        + _p('You can download it from the product page in your account.')
        + _FOOTER_HTML,
        'Safety Data Sheet published\n'
        'Product: {product_name}\nCatalog: {catalog_number}\n'
        'Revision: {revision_no} ({revised_at})\n\nDownload it from the product page.'
        + _FOOTER_TEXT,
        'SDS 发布通知（客户，P1）',
        'en',
    ),
    # 12. 未付款提醒（客户，2026-10-28）
    #   触发：下单满 {remind_days} 天且仍未付款 ⇒ `manage.py remind_unpaid_orders`。
    #   与「超时释放占用」是两件事：这封是**催款**，释放是**还库存**，阈值不同
    #   （默认 3 天提醒 / 7 天释放），所以正文里要明确写出释放阈值，避免客户
    #   收到提醒后以为没后果。
    (
        'order_unpaid_reminder',
        'Payment reminder: order {order_no}',
        _h('Your order is awaiting payment')
        + _p('Hi {contact_name},')
        + _p('Our records show that the order below has not been paid yet. '
             'It was placed {days_since} days ago.')
        + _box('<table style="border-collapse:collapse">'
               + _kv('Order number', '{order_no}')
               + _kv('Amount due', '{currency} {amount_due}')
               + _kv('Status', '{status_label}')
               + '</table>')
        + _p('If payment has already been sent, please disregard this message — '
             'bank transfers can take a few business days to appear on our side.')
        + _p('Please note: if the order remains unpaid for {release_days} days after it was '
             'placed, the stock reserved for it will be released and the order may need to '
             'be confirmed again.')
        + _p('If you need to adjust or cancel the order, just reply to this email.')
        + _FOOTER_HTML,
        'Hi {contact_name},\n\n'
        'Order {order_no} is still awaiting payment (placed {days_since} days ago).\n'
        'Amount due: {currency} {amount_due}\n'
        'Status: {status_label}\n\n'
        'If you have already paid, please ignore this message — bank transfers can take '
        'a few business days to appear on our side.\n\n'
        'If the order remains unpaid for {release_days} days after it was placed, '
        'the stock reserved for it will be released.\n\n'
        'To adjust or cancel the order, simply reply to this email.'
        + _FOOTER_TEXT,
        '未付款提醒（客户，2026-10-28）',
        'en',
    ),
]


class Command(BaseCommand):
    help = '建/更新邮件模板（幂等，按 key）。补齐后 EmailService.enqueue 才有内容可发。'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
                            help='覆盖已存在的模板（会覆盖 Admin 里手改的内容）')
        parser.add_argument('--dry-run', action='store_true', help='只打印，不写库')

    def handle(self, *args, **opts):
        created = updated = skipped = 0
        for key, subject, html, text, desc, lang in TEMPLATES:
            exists = EmailTemplate.objects.filter(key=key).first()
            if exists and not opts['force']:
                skipped += 1
                self.stdout.write(f'  = {key}（已存在，跳过）')
                continue
            if opts['dry_run']:
                self.stdout.write(f'  {"~" if exists else "+"} {key}')
                created += 0 if exists else 1
                updated += 1 if exists else 0
                continue
            obj, is_new = EmailTemplate.objects.update_or_create(
                key=key,
                defaults={
                    'subject': subject,
                    'body_html': html,
                    'body_text': text,
                    'description': desc,
                    'language': lang,
                },
            )
            if is_new:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'  + {key}'))
            else:
                updated += 1
                self.stdout.write(self.style.WARNING(f'  ~ {key}（已覆盖）'))

        if opts['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'[dry-run] 将新增 {created} 个、覆盖 {updated} 个，未写库'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'完成：新增 {created}、覆盖 {updated}、跳过 {skipped}（共 {len(TEMPLATES)} 个模板）'))
