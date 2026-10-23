"""文档发布后的客户通知（COA / SDS）。

## 为什么默认关闭

一个 SKU 可能有几十个历史客户。每次 COA 修订、每次 SDS 升版都自动群发，
很快就会变成骚扰，进而伤害域名发信声誉（客户点"投诉"比点"退订"更常见）。
所以做成开关：`DOC_NOTIFY_CUSTOMERS`，默认 **False**，由运营按需开启。

## 为什么一个客户一封

模板内容里含批号/文档号，且**多个客户绝不能出现在同一封的收件人列表里** ——
B2B 场景下把 A 客户和 B 客户的邮箱放在一起是隐私事故。

## 只发给谁

从订单反查：COA → Batch.sku → OrderItem → Order；SDS → Product → OrderItem → Order。
按邮箱去重，并限制在最近 `DOC_NOTIFY_WINDOW_DAYS`（默认 365）天内下单的客户，
避免给多年前的客户发信。
"""
import logging

from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from apps.notifications.services import EmailService

logger = logging.getLogger(__name__)


def _window_days() -> int:
    try:
        return int(getattr(settings, 'DOC_NOTIFY_WINDOW_DAYS', 365))
    except (TypeError, ValueError):
        return 365


def _enabled() -> bool:
    return bool(getattr(settings, 'DOC_NOTIFY_CUSTOMERS', False))


def _dedupe_emails(values) -> list:
    """去重 + 去空 + 小写归一。"""
    out = set()
    for v in values:
        e = (v or '').strip().lower()
        if e and '@' in e:
            out.add(e)
    return sorted(out)


def _order_item_qs(**filters):
    from apps.transactions.models import OrderItem
    cutoff = timezone.now() - timedelta(days=_window_days())
    return OrderItem.objects.filter(order__created_at__gte=cutoff, **filters)


def customer_emails_for_sku(sku_id) -> list:
    qs = _order_item_qs(sku_id=sku_id)
    return _dedupe_emails(qs.values_list('order__shipping_email', flat=True))


def customer_emails_for_product(product_id) -> list:
    qs = _order_item_qs(product_id=product_id)
    return _dedupe_emails(qs.values_list('order__shipping_email', flat=True))


def notify_coa_published(coa) -> int:
    """COA 发布 → 通知买过该批次 SKU 的客户。返回入队封数。

    调用方应包 try/except：**通知失败绝不能回滚审批**。
    """
    if not _enabled():
        logger.info('[documents] COA %s 已发布；DOC_NOTIFY_CUSTOMERS 关闭，跳过客户通知', coa.doc_id)
        return 0

    sku_id = getattr(getattr(coa, 'batch', None), 'sku_id', None)
    if not sku_id:
        logger.warning('[documents] COA %s 无关联 SKU，无法定位客户', coa.doc_id)
        return 0

    emails = customer_emails_for_sku(sku_id)
    if not emails:
        return 0

    ctx = {
        'product_name': coa.product_name,
        'catalog_number': coa.catalog_number,
        'lot_number': getattr(coa.batch, 'lot_number', ''),
        'doc_id': coa.doc_id,
    }
    for e in emails:                      # 一人一封，避免收件人互相可见
        EmailService.enqueue('coa_published', to=[e], ctx=ctx)
    logger.info('[documents] COA %s 通知 %d 位客户', coa.doc_id, len(emails))
    return len(emails)


def notify_sds_published(sds) -> int:
    """SDS 发布 → 通知买过该产品的客户。返回入队封数。"""
    if not _enabled():
        logger.info('[documents] SDS r%s 已发布；DOC_NOTIFY_CUSTOMERS 关闭，跳过客户通知',
                    sds.revision_no)
        return 0

    product = getattr(sds, 'product', None)
    if not product:
        return 0

    emails = customer_emails_for_product(product.pk)
    if not emails:
        return 0

    ctx = {
        'product_name': product.name,
        'catalog_number': getattr(product, 'catalog_no', ''),
        'revision_no': sds.revision_no,
        'revised_at': str(sds.revised_at),
    }
    for e in emails:
        EmailService.enqueue('sds_published', to=[e], ctx=ctx)
    logger.info('[documents] SDS r%s (product=%s) 通知 %d 位客户',
                sds.revision_no, product.pk, len(emails))
    return len(emails)
