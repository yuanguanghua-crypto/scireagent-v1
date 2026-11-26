"""A-160：可指派 Rep 候选列表。

## 改前
审核台要求运营**手填数字 user id**（`<input placeholder="Rep ID">`），而
`AssignRepView` 只接受 `role in ['procurement','admin']`。QA Batch 15 实测：
填 `REP-TEST-20261112` → "Action failed"；填 `1` → "Invalid rep_id"。
运营既不知道该填谁，也无从知道有谁可选 —— 生产 66 单里 0 单有 assigned_rep。

## 本文件钉住
① 内部人员能拿到列表，且只含 procurement / admin 且 is_active 的账号
② 每项至少含 id / username / email（email 用来让运营识别占位邮箱的测试号）
③ 客户与匿名拿不到（线索归运营侧管）
④ 停用账号不出现在候选里
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()
URL = '/api/v1/orders/assignable-reps/'


class AssignableRepListTest(TestCase):
    def setUp(self):
        self.proc = User.objects.create_user(
            username='ar_proc', email='ar_proc@corp.com', password='x', role='procurement')
        self.admin = User.objects.create_user(
            username='ar_admin', email='ar_admin@corp.com', password='x',
            role='admin', is_staff=True)
        self.researcher = User.objects.create_user(
            username='ar_res', email='ar_res@lab.edu', password='x', role='researcher')
        self.inactive = User.objects.create_user(
            username='ar_off', email='ar_off@corp.com', password='x',
            role='procurement', is_active=False)
        self.client = APIClient()
        self.client.force_authenticate(self.proc)

    def _names(self):
        r = self.client.get(URL)
        self.assertEqual(r.status_code, 200, r.content[:300])
        return {x['username'] for x in r.json()['data']}

    # ── ① 只含 procurement / admin 且 active ─────────────────
    def test_includes_procurement_and_admin(self):
        names = self._names()
        self.assertIn('ar_proc', names)
        self.assertIn('ar_admin', names)

    def test_excludes_researcher(self):
        self.assertNotIn('ar_res', self._names())

    def test_excludes_inactive(self):
        self.assertNotIn('ar_off', self._names())

    # ── ② 字段齐备（email 用来识别占位邮箱的测试号）──────────
    def test_rows_have_id_username_email_role(self):
        rows = self.client.get(URL).json()['data']
        mine = next(x for x in rows if x['username'] == 'ar_proc')
        for key in ('id', 'username', 'email', 'role'):
            self.assertIn(key, mine)
        self.assertEqual(mine['email'], 'ar_proc@corp.com')
        self.assertTrue(isinstance(mine['id'], int))

    # ── ③ 权限 ──────────────────────────────────────────────
    def test_researcher_forbidden(self):
        c = APIClient()
        c.force_authenticate(self.researcher)
        self.assertIn(c.get(URL).status_code, (401, 403))

    def test_anonymous_forbidden(self):
        self.assertIn(APIClient().get(URL).status_code, (401, 403))

    # ── ④ 拿到的 id 能真的指派成功（端到端闭环）──────────────
    def test_returned_id_actually_assignable(self):
        from apps.accounts.models import Organization
        from apps.transactions.models import Order

        org = Organization.objects.create(name='ArOrg', org_type='academic')
        order = Order.objects.create(
            user=self.researcher, organization=org, order_no='ORD-AR-1',
            po_number=None, status=Order.Status.PO_RECEIVED)

        rep = next(x for x in self.client.get(URL).json()['data']
                   if x['username'] == 'ar_proc')
        # ⚠️ assign-rep 的权限是 IsAdmin（改派属管理员动作），
        #    而候选列表是 IsProcurementOrAdmin —— 两个端点权限不同，测试要分开用账号
        admin_client = APIClient()
        admin_client.force_authenticate(self.admin)
        r = admin_client.post(f'/api/v1/orders/{order.id}/assign-rep/',
                              {'rep_id': rep['id']}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        order.refresh_from_db()
        self.assertEqual(order.assigned_rep_id, rep['id'],
                         '候选列表给出的 id 必须能被 assign-rep 接受')
