"""S6 第三批（Orders / PO 运营）的后端闸门。

覆盖 6 条，每条都钉住"改前会红"的那个点：

A-078 订单列表排序必须全序稳定 —— `created_at` 相等时靠主键兜底，
      否则 PG 返回顺序不定，翻页成员会漂移（QA 实测首行两次不同）。
A-089 订单详情 `payment_due_date` 在订单自身为空时回退到发票 `due_date`
      （这个字段全仓没有任何写入点，否则 Payment 区永远 "—"）。
A-097 购物车结账必须写第一条时间线（此前只有 PO 路径写，结账单查不到"何时下单"）。
A-127 时间线必须带人可读的执行者名（此前只有 `actor_id`，界面渲染成裸 "user #1"）。
A-161 超量发货的报错不得包含内部主键 `order_item <id>`，应是运营认得的 SKU 码。
A-084 AR 账龄每个桶必须带发票明细行（此前只有 count/amount，点不动也看不到明细）。
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.transactions.models import Invoice, Order, OrderItem, StatusLog
from apps.transactions.services import PaymentArService, ShippingService


@pytest.fixture
def admin_client(db):
    u = UserFactory(is_staff=True, username='ops_admin')
    c = APIClient()
    c.force_authenticate(user=u)
    return c, u


def _order(user, **kw):
    defaults = dict(
        user=user,
        order_no=kw.pop('order_no'),
        status=Order.Status.CONFIRMED,
        grand_total=Decimal('100.00'),
        subtotal=Decimal('100.00'),
        currency='USD',
        shipping_name='Lab',
        shipping_address='1 St',
    )
    defaults.update(kw)
    return Order.objects.create(**defaults)


# ── A-078 ────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_order_list_pagination_is_stable_when_created_at_ties(admin_client):
    client, _ = admin_client
    user = UserFactory()
    ts = timezone.now()
    orders = [
        _order(user, order_no=f'ORD-TIE-{i}', created_at=ts) for i in range(4)
    ]
    for o in orders:                       # created_at 由 auto_now_add 生成，这里强制对齐
        Order.objects.filter(pk=o.pk).update(created_at=ts)

    seen = []
    for _ in range(3):
        r = client.get('/api/v1/admin/orders/?page=1&page_size=2')
        assert r.status_code == 200, r.content[:300]
        seen.append([row['id'] for row in r.json()['data']])

    assert seen[0] == seen[1] == seen[2], (
        f'同一排序键下三次分页结果不一致：{seen}')
    # 兜底键是 -id ⇒ 同 created_at 时 id 大的在前
    expected = sorted([o.pk for o in orders], reverse=True)[:2]
    assert seen[0] == expected, f'期望 {expected}，实得 {seen[0]}'

    # 两页并起来既不重复也不丢行
    p1 = client.get('/api/v1/admin/orders/?page=1&page_size=2').json()['data']
    p2 = client.get('/api/v1/admin/orders/?page=2&page_size=2').json()['data']
    ids = [r['id'] for r in p1] + [r['id'] for r in p2]
    assert len(ids) == len(set(ids)) == 4


# ── A-089 ────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_detail_payment_due_date_falls_back_to_invoice_due_date(admin_client):
    client, _ = admin_client
    user = UserFactory()
    order = _order(user, order_no='ORD-DUE-1', status=Order.Status.INVOICED)
    assert order.payment_due_date is None          # 前提：订单自身没有到期日
    due = timezone.localdate() + timedelta(days=30)
    Invoice.objects.create(
        order=order, invoice_no='INV-DUE-1', status=Invoice.Status.ISSUED,
        grand_total=Decimal('100.00'), currency='USD', due_date=due,
    )

    d = client.get(f'/api/v1/admin/orders/{order.pk}/').json()['data']
    assert d['payment_due_date'] == str(due), (
        f'详情页 Due Date 必须回退到发票到期日，实得 {d["payment_due_date"]!r}')


@pytest.mark.django_db
def test_detail_payment_due_date_keeps_own_value_when_present(admin_client):
    """自己有值时不许被发票覆盖（回退只在空值时发生）。"""
    client, _ = admin_client
    user = UserFactory()
    own = timezone.localdate() + timedelta(days=7)
    order = _order(user, order_no='ORD-DUE-2', payment_due_date=own,
                   status=Order.Status.INVOICED)
    Invoice.objects.create(
        order=order, invoice_no='INV-DUE-2', status=Invoice.Status.ISSUED,
        grand_total=Decimal('100.00'), currency='USD',
        due_date=timezone.localdate() + timedelta(days=30),
    )
    d = client.get(f'/api/v1/admin/orders/{order.pk}/').json()['data']
    assert d['payment_due_date'] == str(own)


# ── A-097 ────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_checkout_writes_first_timeline_entry(db):
    """结账必须留下"何时下单"的时间线；此前只有 PO 路径会写。"""
    from apps.commerce.tests.factories import ProductFactory, SKUFactory
    from apps.inventory.models import Inventory
    from apps.transactions.models import Basket

    user = UserFactory(email_verified=True, email='tl@lab.example')
    sku = SKUFactory(product=ProductFactory(status='active'),
                     price=Decimal('10.00'), is_default=True, is_stock_tracked=True)
    Inventory.objects.create(sku=sku, location='MAIN', available=5, allocated=0)
    Basket.objects.create(user=user, sku=sku, product=sku.product, quantity=1)

    client = APIClient()
    client.force_authenticate(user=user)
    r = client.post('/api/v1/checkout/', {
        'payment_method': 'purchase_order',
        'po_number': 'PO-TL-1',
        'shipping_name': 'Lab', 'shipping_address': '1 St',
    }, format='json')
    assert r.status_code in (200, 201), r.content[:400]

    order = Order.objects.get(po_number='PO-TL-1')
    logs = list(StatusLog.objects.filter(order=order).order_by('id'))
    assert logs, '结账单必须至少有一条时间线'
    first = logs[0]
    assert first.from_status == ''
    assert first.to_status == order.status
    assert first.actor_id == user.id, '执行者必须是下单人'
    assert 'placed' in (first.note or '').lower()


# ── A-127 ────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_timeline_exposes_actor_name(admin_client):
    client, admin = admin_client
    user = UserFactory()
    order = _order(user, order_no='ORD-ACTOR-1')
    StatusLog.objects.create(
        order=order, actor=admin,
        action_type=StatusLog.ActionType.STATUS_CHANGE,
        from_status='', to_status=Order.Status.CONFIRMED, note='placed',
    )
    d = client.get(f'/api/v1/admin/orders/{order.pk}/').json()['data']
    log = d['status_logs'][0]
    assert log['actor_name'] == admin.username, (
        f'必须给出可读执行者名，实得 {log["actor_name"]!r}')
    assert log['actor_id'] == admin.id


# ── A-161 ────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_overship_error_has_no_internal_pk(db):
    user = UserFactory()
    order = _order(user, order_no='ORD-OVER-1', status=Order.Status.CONFIRMED)
    sku = SKUFactory(product=ProductFactory(status='active'),
                     price=Decimal('10.00'), is_default=True)
    item = OrderItem.objects.create(
        order=order, sku=sku, product=sku.product, quantity=1,
        unit_price=Decimal('10.00'), subtotal=Decimal('10.00'))
    assert item.sku_code_snapshot == sku.sku_code   # save() 自动补齐快照

    with pytest.raises(ValueError) as ei:
        ShippingService.create_shipment(
            order=order, carrier='DHL', tracking_number='T1',
            items=[{'order_item_id': item.pk, 'quantity': 2}], actor=user)

    msg = str(ei.value)
    assert f'order_item {item.pk}' not in msg, f'报错里不许出现内部主键：{msg}'
    assert sku.sku_code in msg, f'报错应指出是哪个 SKU：{msg}'


# ── A-084 ────────────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_ar_aging_returns_invoice_rows_per_bucket(db):
    user = UserFactory()
    today = timezone.localdate()
    # current（未到期）
    o1 = _order(user, order_no='ORD-AR-1', status=Order.Status.INVOICED)
    Invoice.objects.create(order=o1, invoice_no='INV-AR-1', status=Invoice.Status.ISSUED,
                           grand_total=Decimal('118.00'), currency='USD',
                           due_date=today + timedelta(days=5))
    # 1–30 天
    o2 = _order(user, order_no='ORD-AR-2', status=Order.Status.INVOICED)
    Invoice.objects.create(order=o2, invoice_no='INV-AR-2', status=Invoice.Status.OVERDUE,
                           grand_total=Decimal('50.00'), currency='USD',
                           due_date=today - timedelta(days=10))

    data = PaymentArService.ar_aging()
    cur = data['buckets']['current']
    assert cur['count'] == 1
    assert len(cur['invoices']) == 1
    row = cur['invoices'][0]
    assert row['invoice_no'] == 'INV-AR-1'
    assert row['order_no'] == 'ORD-AR-1'
    assert row['order_id'] == o1.pk
    assert row['days_overdue'] == 0
    assert row['grand_total'] == 118.0

    b30 = data['buckets']['30']
    assert b30['count'] == 1 and b30['invoices'][0]['days_overdue'] == 10
