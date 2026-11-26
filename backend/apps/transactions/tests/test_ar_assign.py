"""补测试盲区：assign-rep（分配 Rep）与 ar-aging（AR 账龄）两端的回归测试。

背景：完成度实测发现这两个端点「有 view + 有前端接线，但 0 测试」。本文件补齐。
"""
from datetime import timedelta

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Organization
from apps.transactions.models import Order, Invoice, StatusLog

User = get_user_model()


def _org(name='Lab'):
    return Organization.objects.create(name=name, org_type='academic')


def _user(username, role, org, is_staff=False):
    return User.objects.create_user(
        username=username, email=f'{username}@example.com', password='x',
        role=role, organization=org, is_staff=is_staff,
    )


def _order(user, org, order_no='ORD-X-0001'):
    return Order.objects.create(
        user=user, organization=org, order_no=order_no,
        po_number=None,  # 测试订单无需 PO 号；显式 None 避免 unique 空串冲突
        status=Order.Status.PO_RECEIVED,
        subtotal=Decimal('100.00'), grand_total=Decimal('100.00'),
    )


def _invoice(order, invoice_no, due_days, grand_total='100.00', status=Invoice.Status.ISSUED):
    return Invoice.objects.create(
        order=order, invoice_no=invoice_no, status=status,
        issued_at=timezone.now(),
        due_date=(timezone.now() + timedelta(days=due_days)).date(),
        subtotal=Decimal(grand_total), grand_total=Decimal(grand_total),
    )


class AssignRepTest(TestCase):
    def setUp(self):
        self.org = _org()
        self.admin = _user('adm', 'admin', self.org)
        self.procurement = _user('proc', 'procurement', self.org)
        self.researcher = _user('rsr', 'researcher', self.org)
        self.order = _order(self.researcher, self.org)

    def _assign(self, user, rep_id=None):
        c = APIClient()
        c.force_authenticate(user)
        payload = {'rep_id': rep_id} if rep_id is not None else {}
        return c.post(f'/api/v1/orders/{self.order.id}/assign-rep/', payload, format='json')

    def test_admin_can_assign_rep(self):
        r = self._assign(self.admin, self.procurement.id)
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.order.refresh_from_db()
        self.assertEqual(self.order.assigned_rep, self.procurement)
        self.assertTrue(
            StatusLog.objects.filter(
                order=self.order, action_type=StatusLog.ActionType.REP_ASSIGNED
            ).exists(),
            '分配应写 StatusLog',
        )

    def test_missing_rep_id_returns_400(self):
        r = self._assign(self.admin)
        self.assertEqual(r.status_code, 400)

    def test_nonexistent_rep_id_returns_404(self):
        r = self._assign(self.admin, 999999)
        self.assertEqual(r.status_code, 404)

    def test_researcher_as_rep_returns_404(self):
        """rep 必须是 procurement/admin；传 researcher 应 404。"""
        r = self._assign(self.admin, self.researcher.id)
        self.assertEqual(r.status_code, 404)

    def test_procurement_cannot_assign_returns_403(self):
        """assign-rep 是 Admin 专属，procurement 应 403。"""
        r = self._assign(self.procurement, self.procurement.id)
        self.assertEqual(r.status_code, 403)


class ArAgingTest(TestCase):
    def setUp(self):
        self.org = _org()
        self.procurement = _user('proc2', 'procurement', self.org)
        self.researcher = _user('rsr2', 'researcher', self.org)

    def _get_aging(self, user):
        c = APIClient()
        c.force_authenticate(user)
        r = c.get('/api/v1/ar/aging/')
        self.assertEqual(r.status_code, 200, r.content[:300])
        return r.json()['data']

    def _make_invoice(self, invoice_no, due_days, grand_total='100.00', status=Invoice.Status.ISSUED):
        order = _order(self.researcher, self.org, order_no=f'ORD-{invoice_no}')
        return _invoice(order, invoice_no, due_days, grand_total=grand_total, status=status)

    def test_empty_aging_all_buckets_zero(self):
        data = self._get_aging(self.procurement)
        buckets = data['buckets']
        for b in ('current', '30', '60', '90', '90_plus'):
            self.assertEqual(buckets[b]['count'], 0)
            self.assertEqual(buckets[b]['amount'], 0)
        self.assertEqual(data['total_outstanding'], 0.0)
        self.assertIn('as_of', data)

    def test_bucket_assignment_by_due_date(self):
        # ★ 2026-11-26（A-009）：61–90 与 90+ 已拆开，五档逐档验证。
        #   改前 90 天会落进 90_plus（61-90 无归属），所以下面的 -90 现在应落 '90'。
        self._make_invoice('INV-CUR', due_days=+10)    # current
        self._make_invoice('INV-30', due_days=-10)     # 1-30
        self._make_invoice('INV-60', due_days=-40)     # 31-60
        self._make_invoice('INV-90', due_days=-90)     # 61-90 ← 本轮新增的一档
        self._make_invoice('INV-120', due_days=-120)   # >90
        buckets = self._get_aging(self.procurement)['buckets']
        self.assertEqual(buckets['current']['count'], 1)
        self.assertEqual(buckets['30']['count'], 1)
        self.assertEqual(buckets['60']['count'], 1)
        self.assertEqual(buckets['90']['count'], 1, '逾期 90 天应落 61-90 档')
        self.assertEqual(buckets['90_plus']['count'], 1, '逾期 120 天才落 90+ 档')
        self.assertEqual(buckets['30']['amount'], 100.0)

    def test_sixty_one_to_ninety_is_its_own_bucket(self):
        """★ A-009 核心：逾期第 61 天起必须离开 '60' 档、且不要直接跳到 '90_plus'。"""
        self._make_invoice('INV-61', due_days=-61)
        b = self._get_aging(self.procurement)['buckets']
        self.assertEqual(b['90']['count'], 1, '逾期 61 天应进 61-90 档')
        self.assertEqual(b['60']['count'], 0, '逾期 61 天不该还在 31-60 档')
        self.assertEqual(b['90_plus']['count'], 0, '逾期 61 天不该被算作 90+')

    def test_ninety_one_goes_to_90_plus(self):
        self._make_invoice('INV-91', due_days=-91)
        b = self._get_aging(self.procurement)['buckets']
        self.assertEqual(b['90_plus']['count'], 1)
        self.assertEqual(b['90']['count'], 0)

    def test_paid_invoice_excluded(self):
        self._make_invoice('INV-PAID', due_days=-10, status=Invoice.Status.PAID)
        buckets = self._get_aging(self.procurement)['buckets']
        self.assertEqual(buckets['30']['count'], 0, '已付发票不应计入账龄')

    def test_amount_accumulates_per_bucket(self):
        self._make_invoice('INV-A', due_days=-10, grand_total='100.00')
        self._make_invoice('INV-B', due_days=-20, grand_total='250.00')
        data = self._get_aging(self.procurement)
        self.assertEqual(data['buckets']['30']['count'], 2)
        self.assertEqual(data['buckets']['30']['amount'], 350.0)
        self.assertEqual(data['total_outstanding'], 350.0)

    def test_non_procurement_forbidden(self):
        c = APIClient()
        c.force_authenticate(self.researcher)
        r = c.get('/api/v1/ar/aging/')
        self.assertEqual(r.status_code, 403)
