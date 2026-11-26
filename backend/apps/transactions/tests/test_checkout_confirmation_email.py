"""购物车结账的订单确认邮件（S5 P-3 / A-098）。

## 缺陷
`CheckoutView` 建完单**一封邮件都不发**（原来此处直接 return 201），
而 `order_confirmed` 模板只有 PO 上传路径的 `ApproveOrderView` 在发
（`po_views.py:117`）⇒ **购物车结账单永远收不到确认邮件**。

生产实测（2026-11-26）：`email_outbox` 里 `order_confirmed` 共 24 封，全部来自 PO 路径。
QA 的 `ORD-20261110-001` 只有 shipped / delivered / invoice_issued 三封 —— 正是这条缺口。
（它同时缺 `po_submitted` 是**正常的**：购物车单本来就没有 PO 可提交，不该一起"补"。）

## 本文件钉住五条边界
① 结账成功 ⇒ 恰好 1 封 `order_confirmed`，收件人为下单人；
② 填了 `shipping_email` ⇒ 优先用它（收件人是实际收货方，不是账号主）；
③ `payment_method='quote'` ⇒ **不发**（订单落 QUOTE_PENDING，还没确认，发出去就是错的）；
④ 无任何邮箱 ⇒ 不写 `to_emails=''` 的空壳记录（`ApproveOrderView` 有这个缺陷，不复制）；
⑤ ★ 下单失败（缺货 400）⇒ outbox **不留**孤儿邮件（证明 enqueue 在 atomic 之外是对的）。
"""
from decimal import Decimal
from uuid import uuid4

import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.inventory.models import Inventory
from apps.notifications.models import EmailOutbox
from apps.transactions.models import Basket, Order

KEY = 'order_confirmed'


def _basket(user, sku, qty):
    Basket.objects.update_or_create(
        user=user, sku=sku, defaults={'product': sku.product, 'quantity': qty})


@pytest.mark.django_db
class TestCheckoutConfirmationEmail:
    def setup_method(self):
        # 模板必须存在，否则 `EmailService.enqueue` 查到 None ⇒ subject/body 都是空串
        # （本文件第一条断言就靠 subject 验证"模板真的渲染了单号"）。
        # 这个命令是幂等的（按 key upsert），生产上也是它建的。
        from django.core.management import call_command
        call_command('seed_email_templates', verbosity=0)

    def _ready(self, price='100.00', email='buyer@lab.example', stock=10):
        user = UserFactory(email_verified=True, email=email)
        product = ProductFactory(status='active')
        # ★ `is_stock_tracked=True` 是缺货判定**唯一**的"是否纳管"判据
        #   （`StockShortageService._is_tracked`，2026-10-28 改的口径）。
        #   不置 True 的话，哪怕建了 available=0 的库存行也不会被拦 ——
        #   设计如此：没纳管的 SKU 永远是"按需生产、不设库存"，不该拦。
        sku = SKUFactory(
            product=product, price=Decimal(price), is_default=True,
            is_stock_tracked=True,
        )
        Inventory.objects.create(sku=sku, location='MAIN', available=stock, allocated=0)
        _basket(user, sku, 1)
        client = APIClient()
        client.force_authenticate(user=user)
        return user, sku, client

    def _checkout(self, client, **extra):
        payload = {
            'payment_method': 'purchase_order',
            'po_number': 'PROBE-PO-%s' % uuid4().hex[:8],
            'shipping_name': 'Probe',
            'shipping_address': 'Probe Addr',
        }
        payload.update(extra)
        return client.post('/api/v1/checkout/', payload, format='json')

    # ── ① 成功下单 ⇒ 1 封确认邮件 ──────────────────────────────
    def test_successful_checkout_enqueues_confirmation(self):
        user, sku, client = self._ready(email='buyer@lab.example')
        r = self._checkout(client)
        assert r.status_code in (200, 201), r.content[:400]

        order_no = r.json()['data']['order_no']
        mails = EmailOutbox.objects.filter(template_key=KEY)
        assert mails.count() == 1, f'应恰好 1 封 {KEY}，实际 {mails.count()}'
        mail = mails.first()
        assert mail.to_emails == 'buyer@lab.example'
        assert order_no in mail.subject, f'主题应带单号：{mail.subject!r}'
        assert mail.context_json.get('order_no') == order_no
        assert mail.status == EmailOutbox.Status.PENDING

    # ── ② shipping_email 优先 ─────────────────────────────────
    def test_shipping_email_takes_precedence(self):
        user, sku, client = self._ready(email='account@lab.example')
        r = self._checkout(client, shipping_email='receiver@other.example')
        assert r.status_code in (200, 201), r.content[:400]
        mail = EmailOutbox.objects.filter(template_key=KEY).latest('id')
        assert mail.to_emails == 'receiver@other.example', \
            '应发给实际收货人，而不是账号主'

    # ── ③ quote 路径不发 ──────────────────────────────────────
    def test_quote_path_does_not_send_confirmation(self):
        """报价单还没被接受，发「Your order is confirmed」是错的。"""
        user, sku, client = self._ready()
        r = self._checkout(client, payment_method='quote', po_number=None)
        assert r.status_code in (200, 201), r.content[:400]
        order = Order.objects.get(pk=r.json()['data']['id'])
        assert order.status == Order.Status.QUOTE_PENDING
        assert EmailOutbox.objects.filter(template_key=KEY).count() == 0

    # ── ④ 无邮箱 ⇒ 不写空壳 ───────────────────────────────────
    def test_no_recipient_writes_no_empty_record(self):
        """`ApproveOrderView` 在 shipping_email 为空时传 `to=[]`，
        会写出一条 `to_emails=''` 的垃圾记录（永远发不出去、还占着队列）。这里不复制。"""
        user, sku, client = self._ready(email='')
        r = self._checkout(client)
        assert r.status_code in (200, 201), r.content[:400]
        assert EmailOutbox.objects.filter(template_key=KEY).count() == 0
        assert not EmailOutbox.objects.filter(template_key=KEY, to_emails='').exists()

    # ── ⑤ 失败不留孤儿 ────────────────────────────────────────
    def test_failed_checkout_leaves_no_orphan_email(self):
        """★ 缺货 400 时不能留下"订单没建成但邮件已入队"的孤儿。
        这也反证了 enqueue 必须在 `transaction.atomic()` 之外（且在本视图的早退分支之后）。
        """
        user, sku, client = self._ready(stock=0)
        r = self._checkout(client)
        assert r.status_code == 400, r.content[:400]
        assert EmailOutbox.objects.filter(template_key=KEY).count() == 0
