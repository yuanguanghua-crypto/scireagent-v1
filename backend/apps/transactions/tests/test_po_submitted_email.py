"""PO 提交确认邮件必须带金额（S6 / A-234）。

## 缺陷
`po_submitted` 模板此前只有 `{order_no}` + `{po_number}` 两个占位符，发送点的 ctx
也只有这两个键 ⇒ 客户收到「We have received your purchase order」，
**却不知道这单多少钱**，只能回站点自己查 —— 一封确认信的核心信息是缺的。

## 为什么现在才暴露
`_SafeDict.__missing__` 返回 `''`，`render_template` 遇到缺失占位符**不报错**，
只是渲染成空串。所以「模板少一个字段」在链路上完全静默：
outbox 里 subject/body 都正常、状态 pending/sent 都正常，只有人肉读正文才发现少了一行。

## 本文件钉住三条
① 提交 PO ⇒ outbox 的 `context_json` 里有 `currency` 与 `grand_total`（两位小数）；
② 渲染后的正文真的出现金额（证明模板占位符与 ctx 键**对齐**，不是各写各的）；
③ 金额取自订单快照 `grand_total`，与订单接口返回的值一致（不是另算一份）。
"""
from decimal import Decimal
from uuid import uuid4

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.notifications.models import EmailOutbox
from apps.transactions.models import Order

KEY = 'po_submitted'


@pytest.mark.django_db
class TestPoSubmittedEmailCarriesAmount:
    def setup_method(self):
        # 模板必须先存在：`EmailService.enqueue` 查不到模板时有显式 subject/body 才不空，
        # 而这里走的是"只传 key + ctx"的路径 ⇒ 不 seed 就只有空壳，断言毫无意义。
        call_command('seed_email_templates', verbosity=0)

    def _submit(self, unit_price='123.45', qty=2):
        user = UserFactory(email_verified=True, email='po-buyer@lab.example')
        sku = SKUFactory(
            product=ProductFactory(status='active'),
            price=Decimal(unit_price), is_default=True,
        )
        client = APIClient()
        client.force_authenticate(user=user)
        po_number = 'PROBE-PO-%s' % uuid4().hex[:8]
        r = client.post('/api/v1/orders/po/', {
            'po_number': po_number,
            'shipping_name': 'Probe Lab',
            'shipping_address': 'Probe Addr',
            'items': [{'sku_id': sku.id, 'quantity': qty, 'unit_price': unit_price}],
        }, format='json')
        assert r.status_code in (200, 201), r.content[:400]
        return Order.objects.get(po_number=po_number)

    # ── ① ctx 带金额 ──────────────────────────────────────────
    def test_context_contains_currency_and_total(self):
        order = self._submit()
        mail = EmailOutbox.objects.filter(template_key=KEY).latest('id')
        ctx = mail.context_json or {}
        assert ctx.get('order_no') == order.order_no
        assert ctx.get('po_number') == order.po_number
        assert ctx.get('currency') == (order.currency or 'USD')
        assert ctx.get('grand_total') == f'{order.grand_total:.2f}'

    # ── ② 正文真的渲染出金额（模板与 ctx 对齐） ────────────────
    def test_rendered_body_shows_the_amount(self):
        order = self._submit(unit_price='123.45', qty=2)
        mail = EmailOutbox.objects.filter(template_key=KEY).latest('id')
        amount = f'{order.grand_total:.2f}'
        assert amount in mail.body_text, (
            f'正文里没有金额 {amount}；正文={mail.body_text[:300]!r}')
        # 占位符必须被吃干净 —— 残留说明模板写的键和 ctx 的键不是同一个
        assert '{grand_total}' not in mail.body_text
        assert '{currency}' not in mail.body_text

    # ── ③ 金额 = 订单快照，不另算 ─────────────────────────────
    def test_amount_matches_order_grand_total(self):
        order = self._submit(unit_price='99.99', qty=3)
        order.refresh_from_db()
        mail = EmailOutbox.objects.filter(template_key=KEY).latest('id')
        # 299.97 = 99.99 × 3（无税无运费的单）
        assert order.grand_total == Decimal('299.97')
        assert mail.context_json['grand_total'] == '299.97'
