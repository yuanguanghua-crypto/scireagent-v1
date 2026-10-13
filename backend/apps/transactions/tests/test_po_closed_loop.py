"""★ 2026-10-13 PO 闭环走查查出的缺陷闸门（含**状态流转**覆盖缺口）。

背景（以操作员视角做端到端走查时实测发现）：

1. **发票 PDF 下载：内部人员必 500** —— `po_views._is_order_viewer()` 兜底分支把 `None` 当 request
   传给权限类（`IsProcurementOrAdmin().has_permission(None, None)`），权限类内 `request.user`
   直接抛 `AttributeError`。受害面是**非订单归属人、非同机构**的一切访问者，**包括内部采购/管理员**
   （同一张发票：客户本人 200，管理员 500）。

2. **发货单创建：入参结构不对时 500 而非 400** —— `ShipmentCreateSerializer.items` 用
   `ListField(child=DictField())` **完全不校验结构**，服务层直接取 `it['order_item_id']`
   ⇒ 缺字段抛 `KeyError`、引用了不属于本订单的 order_item 抛 `DoesNotExist`，两者都是**未捕获异常**（500）。
   前端 `PoShipmentDesk.vue` 恰好发的结构是对的，所以 UI 不踩；但任何 API 消费者/集成方都会踩。

3. **E2E 覆盖缺口**：`state-matrix.spec.cjs` 是**直接 seed 出目标状态**再断言按钮集，
   **绕过了会坏的转移路径** —— 这正是上述两个缺陷长期未被发现的原因。
   本文件用 API 级用例把「提交 → 审核 → 发货 → 签收 → 开票 → 收款」整条链路钉住。
"""
import os
import tempfile
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Organization
from apps.commerce.models import Product, SKU
from apps.transactions.models import Order, OrderItem, Invoice, ShippingRecord

User = get_user_model()


def _org(name):
    return Organization.objects.create(name=name, org_type='academic')


def _user(username, role='researcher', org=None, is_staff=False):
    return User.objects.create_user(
        username=username, email=f'{username}@example.com', password='x',
        role=role, organization=org, is_staff=is_staff,
    )


def _sku():
    product = Product.objects.create(name='Loop Reagent', slug='loop-reagent')
    return SKU.objects.create(product=product, sku_code='SKU-LOOP-001', price=10)


class _Base(TestCase):
    def setUp(self):
        self.org_a, self.org_b = _org('OrgA'), _org('OrgB')
        self.owner = _user('loop_owner', org=self.org_a)
        self.mate = _user('loop_mate', org=self.org_a)
        self.admin = _user('loop_admin', role='admin', org=self.org_b, is_staff=True)
        self.outsider = _user('loop_outsider', org=self.org_b)

    def _client(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class InvoicePdfViewerPermissionTest(_Base):
    """★ 缺陷 1 闸门：发票 PDF 下载的可见性判定。"""

    def setUp(self):
        super().setUp()
        self.order = Order.objects.create(
            user=self.owner, organization=self.org_a,
            order_no='ORD-PDF-0001', po_number='PO-PDF-0001', status=Order.Status.INVOICED,
        )
        self.invoice = Invoice.objects.create(
            order=self.order, invoice_no='INV-PDF-0001',
            status=Invoice.Status.ISSUED, due_date='2099-01-01',
        )
        d = os.path.join(settings.MEDIA_ROOT, 'invoices')
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'INV-PDF-0001.pdf'), 'wb') as fh:
            fh.write(b'%PDF-1.4 stub')

    def _url(self):
        return f'/api/v1/invoices/{self.invoice.id}/pdf/'

    def test_owner_can_download(self):
        """订单归属人本人：200（既有行为，作为基线）。"""
        self.assertEqual(self._client(self.owner).get(self._url()).status_code, 200)

    def test_same_org_member_can_download(self):
        """本机构成员：200。"""
        self.assertEqual(self._client(self.mate).get(self._url()).status_code, 200)

    def test_internal_admin_can_download(self):
        """★ 内部管理员（非归属人、非同机构）：应 200。

        回归背景：修复前这里抛 AttributeError ⇒ 500；受害面覆盖全部内部台操作者。
        """
        r = self._client(self.admin).get(self._url())
        self.assertEqual(r.status_code, 200, f'内部管理员下载发票 PDF 应 200，实际 {r.status_code}')

    def test_unrelated_customer_is_forbidden(self):
        """无关客户（非本人、非同机构、非内部）：403（不得因修复而放宽）。"""
        r = self._client(self.outsider).get(self._url())
        self.assertEqual(r.status_code, 403, f'无关客户应 403，实际 {r.status_code}')


class ShipmentCreateValidationTest(_Base):
    """★ 缺陷 2 闸门：发货单创建的入参校验（错结构必须 400，不得 500）。"""

    def setUp(self):
        super().setUp()
        self.staff = _user('loop_proc', role='procurement', org=self.org_a, is_staff=True)
        self.sku = _sku()
        self.order = Order.objects.create(
            user=self.owner, organization=self.org_a,
            order_no='ORD-SHIP-0001', po_number='PO-SHIP-0001', status=Order.Status.CONFIRMED,
        )
        self.item = OrderItem.objects.create(
            order=self.order, sku=self.sku, quantity=2, unit_price=Decimal('10.00'),
        )
        self.other_item = OrderItem.objects.create(
            order=Order.objects.create(user=self.owner, order_no='ORD-OTHER-0001', po_number='PO-OTHER-0001'),
            sku=self.sku, quantity=1, unit_price=Decimal('10.00'),
        )

    def _post(self, payload):
        return self._client(self.staff).post(f'/api/v1/orders/{self.order.id}/shipments/', payload, format='json')

    def test_valid_items_creates_shipment(self):
        """正常结构：201，且落一条发货记录（基线）。"""
        r = self._post({'carrier': 'FedEx', 'items': [{'order_item_id': self.item.id, 'quantity': 2}]})
        self.assertEqual(r.status_code, 201, r.content[:300])
        self.assertEqual(ShippingRecord.objects.filter(order=self.order).count(), 1)

    def test_missing_order_item_id_returns_400_not_500(self):
        """★ 缺 order_item_id：应 400 带字段错误（修复前 KeyError ⇒ 500）。"""
        r = self._post({'carrier': 'FedEx', 'items': [{'quantity': 2}]})
        self.assertEqual(r.status_code, 400, f'应 400，实际 {r.status_code}；body={r.content[:300]}')
        self.assertEqual(ShippingRecord.objects.filter(order=self.order).count(), 0, '校验失败不得落库')

    def test_quantity_not_positive_returns_400(self):
        """★ 数量非正：应 400（修复前无校验）。"""
        r = self._post({'items': [{'order_item_id': self.item.id, 'quantity': 0}]})
        self.assertEqual(r.status_code, 400, f'应 400，实际 {r.status_code}')
        self.assertEqual(ShippingRecord.objects.filter(order=self.order).count(), 0)

    def test_foreign_order_item_returns_400_not_500(self):
        """★ order_item 不属于本订单：应 400（修复前 DoesNotExist ⇒ 500）。"""
        r = self._post({'items': [{'order_item_id': self.other_item.id, 'quantity': 1}]})
        self.assertEqual(r.status_code, 400, f'应 400，实际 {r.status_code}；body={r.content[:300]}')
        self.assertEqual(ShippingRecord.objects.filter(order=self.order).count(), 0)

    def test_empty_items_returns_400(self):
        """空 items：应 400。"""
        r = self._post({'items': []})
        self.assertEqual(r.status_code, 400)


class PoClosedLoopStateMachineTest(_Base):
    """★ 覆盖缺口闸门：用 API 真跑「提交 → 审核 → 发货 → 签收 → 开票 → 收款」整条链路。"""

    def setUp(self):
        super().setUp()
        self.staff = _user('loop_staff', role='procurement', org=self.org_a, is_staff=True)
        self.sku = _sku()

    def _submit(self):
        r = self._client(self.owner).post('/api/v1/orders/po/', {
            'po_number': 'PO-LOOP-0001',
            'shipping_name': 'Loop Lab', 'shipping_address': '1 Test St',
            'items': [{'sku_id': self.sku.id, 'quantity': 2, 'unit_price': '10.00'}],
        }, format='json')
        self.assertEqual(r.status_code, 201, r.content[:300])
        return Order.objects.get(po_number='PO-LOOP-0001')

    def test_full_loop_reaches_paid(self):
        staff = self._client(self.staff)
        order = self._submit()
        self.assertEqual(order.status, Order.Status.PO_RECEIVED)

        # 2) 审核
        r = staff.post(f'/api/v1/orders/{order.id}/approve/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CONFIRMED)

        # 3) 建发货单（必须带 order_item_id —— 即缺陷 2 的真实调用约定）
        item = OrderItem.objects.filter(order=order).first()
        r = staff.post(f'/api/v1/orders/{order.id}/shipments/',
                       {'carrier': 'FedEx', 'tracking_number': 'TRK-1',
                        'items': [{'order_item_id': item.id, 'quantity': 2}]}, format='json')
        self.assertEqual(r.status_code, 201, r.content[:300])
        shipment = ShippingRecord.objects.filter(order=order).latest('id')

        # 4) 标记已发货
        r = staff.post(f'/api/v1/shipments/{shipment.id}/mark-shipped/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.SHIPPED)

        # 5) 标记已签收
        r = staff.post(f'/api/v1/shipments/{shipment.id}/mark-delivered/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.DELIVERED)

        # 6) 开票（门槛：必须 delivered）
        r = staff.post(f'/api/v1/orders/{order.id}/invoice/', {}, format='json')
        self.assertEqual(r.status_code, 201, r.content[:300])
        order.refresh_from_db()
        invoice = Invoice.objects.get(order=order)
        self.assertEqual(order.status, Order.Status.INVOICED)
        self.assertEqual(invoice.status, Invoice.Status.ISSUED)

        # 7) 登记收款
        r = staff.post(f'/api/v1/invoices/{invoice.id}/pay/',
                       {'amount': str(order.grand_total), 'method': 'wire'}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        order.refresh_from_db()
        invoice.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertIsNotNone(invoice.paid_at)

    def test_invoice_before_delivered_is_rejected(self):
        """顺序守卫：未签收就开票必须被拒（400），不得静默放行。"""
        staff = self._client(self.staff)
        order = self._submit()
        staff.post(f'/api/v1/orders/{order.id}/approve/', {}, format='json')
        r = staff.post(f'/api/v1/orders/{order.id}/invoice/', {}, format='json')
        self.assertEqual(r.status_code, 400, f'应 400，实际 {r.status_code}')
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CONFIRMED, '失败不得改状态')
