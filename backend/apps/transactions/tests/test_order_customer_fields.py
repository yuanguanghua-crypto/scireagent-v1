"""订单「客户身份」三字段（S5 P-3 / A-077）。

## 为什么需要
`AdminOrdersPage.vue:117` 的 CUSTOMER 列渲染的是 `{{ order.user_id }}` —— 一个**裸数字 id**，
`user` 为 NULL 时整列空白（QA Batch 8 实测 21 行全空白）；
`AdminOrderDetail.vue:258-259` 的 Customer 区也只有 "User ID 12 / Org ID 16"。
运营拿这两样既联系不上客户，也判断不出这单是谁下的。

## 本文件钉住四件事
① 列表与详情都返回 `customer_name` / `customer_email` / `organization_name`，且**值正确**；
② `user`/`organization` 为 NULL 时返回**空串**而不是崩（历史 e2e 单 user 就是 NULL）；
③ ★ 客户视角**不会**因为多了这三个字段而看到别人的信息（横向越权守卫）；
④ 列表查询数不随行数增长（`select_related('user','organization')` 真的生效）。
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Organization
from apps.transactions.models import Order

User = get_user_model()
LIST_URL = '/api/v1/orders/'
ADMIN_LIST_URL = '/api/v1/admin/orders/'


class OrderCustomerFieldsTest(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Acme Labs', org_type='academic')
        self.alice = User.objects.create_user(
            username='alice_cust', email='alice@acme.example', password='x',
            role='researcher', organization=self.org,
        )
        self.bob = User.objects.create_user(
            username='bob_cust', email='bob@other.example', password='x',
            role='researcher',
        )
        self.staff = User.objects.create_user(
            username='cust_staff', email='staff@internal.example', password='x',
            role='admin', is_staff=True,
        )

        self.alice_order = Order.objects.create(
            user=self.alice, organization=self.org,
            order_no='ORD-CUST-A', po_number=None, status=Order.Status.CONFIRMED,
        )
        self.bob_order = Order.objects.create(
            user=self.bob, organization=None,
            order_no='ORD-CUST-B', po_number=None, status=Order.Status.CONFIRMED,
        )
        # 历史 e2e 单：user 为 NULL（生产上这类单真实存在，CUSTOMER 列因此整列空白）
        self.orphan = Order.objects.create(
            user=None, organization=None,
            order_no='ORD-CUST-ORPHAN', po_number=None, status=Order.Status.DRAFT,
        )

    def _rows(self, user, url=LIST_URL, query=''):
        c = APIClient()
        c.force_authenticate(user)
        r = c.get(url + query)
        self.assertEqual(r.status_code, 200, r.content[:300])
        data = r.json()['data']
        return data if isinstance(data, list) else (data.get('results') or [])

    # ── ① 值正确 ────────────────────────────────────────────────
    def test_staff_list_has_customer_fields(self):
        """运营视角：三字段齐全且取值正确（姓名回落 username、组织名、邮箱）。"""
        rows = self._rows(self.staff)
        by_no = {r['order_no']: r for r in rows}
        a = by_no['ORD-CUST-A']
        self.assertEqual(a['customer_name'], 'alice_cust')
        self.assertEqual(a['customer_email'], 'alice@acme.example')
        self.assertEqual(a['organization_name'], 'Acme Labs')

        # bob 没有组织 ⇒ 空串，不是 None（前端 `|| '—'` 对 '' 和 null 都能兜，
        # 但空串能让契约固定，避免前端两套判断）
        b = by_no['ORD-CUST-B']
        self.assertEqual(b['customer_name'], 'bob_cust')
        self.assertEqual(b['organization_name'], '')

    def test_first_last_name_wins_over_username(self):
        """有 first/last name 时优先用它（`get_full_name()`），否则回落 username。"""
        self.alice.first_name = 'Alice'
        self.alice.last_name = 'Zhang'
        self.alice.save(update_fields=['first_name', 'last_name'])
        rows = self._rows(self.staff)
        a = {r['order_no']: r for r in rows}['ORD-CUST-A']
        self.assertEqual(a['customer_name'], 'Alice Zhang')

    # ── ② NULL 容错 ────────────────────────────────────────────
    def test_null_user_and_org_yield_empty_strings(self):
        """user/org 都为 NULL 的老单：必须是空串，不能 500。"""
        rows = self._rows(self.staff)
        orphan = {r['order_no']: r for r in rows}['ORD-CUST-ORPHAN']
        self.assertEqual(orphan['customer_name'], '')
        self.assertEqual(orphan['customer_email'], '')
        self.assertEqual(orphan['organization_name'], '')

    # ── ③ 横向越权守卫 ─────────────────────────────────────────
    def test_customer_sees_only_own_identity(self):
        """★ 客户登录后只能看到**自己**的单，三个新字段不构成横向泄露。"""
        rows = self._rows(self.alice)
        self.assertEqual([r['order_no'] for r in rows], ['ORD-CUST-A'],
                         'researcher 不应看到别人的单')
        self.assertEqual(rows[0]['customer_email'], 'alice@acme.example')

    def test_customer_never_sees_other_customers_email(self):
        """把两个客户的单都过一遍，断言 alice 的响应里**从未**出现 bob 的邮箱。"""
        c = APIClient()
        c.force_authenticate(self.alice)
        body = c.get(LIST_URL).content.decode()
        self.assertNotIn('bob@other.example', body)

    # ── ④ 详情也带 ────────────────────────────────────────────
    def test_detail_has_customer_fields(self):
        """详情页 Customer 区要显示姓名/邮箱/组织名，不再只有 User ID / Org ID。"""
        c = APIClient()
        c.force_authenticate(self.staff)
        r = c.get(f'{LIST_URL}{self.alice_order.id}/')
        self.assertEqual(r.status_code, 200, r.content[:300])
        d = r.json()['data']
        self.assertEqual(d['customer_name'], 'alice_cust')
        self.assertEqual(d['customer_email'], 'alice@acme.example')
        self.assertEqual(d['organization_name'], 'Acme Labs')
        # 原有裸 id 字段保留（前端/第三方可能还在用，不能悄悄删）
        self.assertEqual(d['user_id'], self.alice.id)
        self.assertEqual(d['organization_id'], self.org.id)

    # ── ⑤ N+1 守卫 ────────────────────────────────────────────
    def test_list_query_count_does_not_grow_with_rows(self):
        """★ `select_related('user','organization')` 必须生效：
        多 8 行订单，查询数**不得**跟着涨（每行 2 次查询 = 典型 N+1）。
        """
        c = APIClient()
        c.force_authenticate(self.staff)

        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as small:
            r = c.get(LIST_URL)
            self.assertEqual(r.status_code, 200, r.content[:300])
            _ = r.json()

        for i in range(8):
            Order.objects.create(
                user=self.alice, organization=self.org,
                order_no=f'ORD-CUST-BULK-{i}', po_number=None,
                status=Order.Status.CONFIRMED,
            )

        with CaptureQueriesContext(connection) as big:
            r = c.get(LIST_URL)
            self.assertEqual(r.status_code, 200, r.content[:300])
            _ = r.json()

        # 允许 +2 的余量（认证/查 user 相关），但绝不允许 +16（8 行 × 2）
        self.assertLessEqual(
            len(big.captured_queries), len(small.captured_queries) + 2,
            f'查询数从 {len(small.captured_queries)} 涨到 {len(big.captured_queries)}，'
            f'疑似 N+1（select_related 未生效）。实际 SQL:\n'
            + '\n'.join(q['sql'][:160] for q in big.captured_queries),
        )

    # ── ⑥ 管理端列表同样生效 ───────────────────────────────────
    def test_admin_order_list_endpoint_has_customer_fields(self):
        rows = self._rows(self.staff, url=ADMIN_LIST_URL)
        by_no = {r['order_no']: r for r in rows}
        self.assertEqual(by_no['ORD-CUST-A']['customer_name'], 'alice_cust')

    def test_admin_order_detail_endpoint_has_customer_fields(self):
        c = APIClient()
        c.force_authenticate(self.staff)
        r = c.get(f'{ADMIN_LIST_URL}{self.alice_order.id}/')
        self.assertEqual(r.status_code, 200, r.content[:300])
        self.assertEqual(r.json()['data']['customer_email'], 'alice@acme.example')
