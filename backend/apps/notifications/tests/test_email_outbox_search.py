"""投递队列的订单号搜索（S5 P-3 / A-164）。

## 缺陷
本页此前**只有 `template_key` 精确筛选**。运营手上拿到一个订单号（QA 用例是
`ORD-AD684447`）根本没有输入框可填 —— 填进 `template_key` 自然 0 条
（那不是模板键），于是得出"该订单没有任何邮件"的错误结论。

## 为什么搜三个字段
`EmailOutbox` **没有** order 外键（`notifications/models.py`），订单号只以文本形式存在：

| 字段 | 典型内容 |
|---|---|
| `subject` | "Purchase order received for order ORD-AD684447" |
| `body_text` | 模板渲染后的正文（多数模板正文里也带单号） |
| `context_json` | `{"order_no": "ORD-AD684447", ...}` ← 最可靠的结构化落点 |

生产实测（2026-11-26，180 条 outbox，探针 `ORD-AD684447`）：
`subject` 命中 **6**、`body_text` 命中 **6**、`context_json` 命中 **6**、`to_emails` 命中 **0**。
⇒ 三个都要搜；只搜 subject 会漏掉"主题不含单号"的模板。

## 本文件钉住
① 只存在于 `context_json` 的单号也能被搜到（这是最容易被漏掉的一条）；
② 只存在于 `body_text` 的单号也能被搜到；
③ 不误命中别的单号；
④ 与 `status` 可组合；
⑤ 验收线：搜一个真实单号，命中数 == ORM 用同样三条件数出来的数。
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import EmailOutbox

URL = '/api/v1/ops/email-outbox/'


class EmailOutboxSearchTest(TestCase):
    def setUp(self):
        self.operator = UserFactory(role='procurement', is_staff=False)
        self.client = APIClient()
        self.client.force_authenticate(self.operator)

        # 参照生产上的 6 封（po_submitted / order_confirmed / shipped / delivered /
        # invoice_issued / order_unpaid_reminder），覆盖三种落点组合
        self.m_subject = EmailOutbox.objects.create(
            to_emails='buyer@example.com',
            subject='Purchase order received for order ORD-SEARCH-01',
            body_text='We received your purchase order.',
            context_json={'order_no': 'ORD-SEARCH-01', 'po_number': 'PO-1'},
            template_key='po_submitted',
        )
        self.m_body = EmailOutbox.objects.create(
            to_emails='buyer@example.com',
            subject='A notice',                      # 主题里**没有**单号
            body_text='Your order ORD-SEARCH-01 has shipped.',
            context_json={'tracking_number': 'T-1'},  # ctx 里**也没有**单号
            template_key='shipped',
        )
        self.m_ctx = EmailOutbox.objects.create(
            to_emails='buyer@example.com',
            subject='Reminder',                       # 主题无单号
            body_text='Please pay.',                  # 正文无单号
            context_json={'order_no': 'ORD-SEARCH-01', 'amount_due': '118.00'},
            template_key='order_unpaid_reminder',
        )
        # 干扰项
        self.m_other = EmailOutbox.objects.create(
            to_emails='other@example.com',
            subject='Order ORD-SEARCH-99 confirmed',
            body_text='other',
            context_json={'order_no': 'ORD-SEARCH-99'},
            template_key='order_confirmed',
        )

    def _rows(self, **params):
        r = self.client.get(URL, params)
        self.assertEqual(r.status_code, 200, r.content[:300])
        return r.json()['data']

    # ── ① 只存在于 context_json ────────────────────────────────
    def test_matches_order_no_only_in_context_json(self):
        ids = {r['id'] for r in self._rows(search='ORD-SEARCH-01')}
        self.assertIn(self.m_ctx.id, ids, '单号只在 context_json 里也要能搜到')

    # ── ② 只存在于 body_text ───────────────────────────────────
    def test_matches_order_no_only_in_body_text(self):
        ids = {r['id'] for r in self._rows(search='ORD-SEARCH-01')}
        self.assertIn(self.m_body.id, ids, '单号只在 body_text 里也要能搜到')

    # ── 主题命中 ───────────────────────────────────────────────
    def test_matches_order_no_in_subject(self):
        ids = {r['id'] for r in self._rows(search='ORD-SEARCH-01')}
        self.assertIn(self.m_subject.id, ids)

    # ── ③ 不误命中 ────────────────────────────────────────────
    def test_does_not_match_other_order_no(self):
        ids = {r['id'] for r in self._rows(search='ORD-SEARCH-01')}
        self.assertNotIn(self.m_other.id, ids, '不能因为前缀相同就命中另一单')

        ids99 = {r['id'] for r in self._rows(search='ORD-SEARCH-99')}
        self.assertEqual(ids99, {self.m_other.id})

    # ── ④ 与 status 组合 ──────────────────────────────────────
    def test_combines_with_status_filter(self):
        EmailOutbox.objects.filter(pk=self.m_body.pk).update(
            status=EmailOutbox.Status.FAILED)
        ids = {r['id'] for r in self._rows(search='ORD-SEARCH-01', status='failed')}
        self.assertEqual(ids, {self.m_body.id})

    def test_combines_with_template_key(self):
        ids = {r['id'] for r in self._rows(
            search='ORD-SEARCH-01', template_key='order_unpaid_reminder')}
        self.assertEqual(ids, {self.m_ctx.id})

    # ── 空 search 返回全部 ────────────────────────────────────
    def test_empty_search_returns_everything(self):
        self.assertEqual(len(self._rows()), 4)

    def test_blank_search_param_is_ignored(self):
        self.assertEqual(len(self._rows(search='   ')), 4)

    # ── ⑤ 验收线 ──────────────────────────────────────────────
    def test_hit_count_equals_orm_count(self):
        """★ 验收线：接口命中数 == ORM 用同样三条件数出来的数。"""
        from django.db.models import Q
        api = len(self._rows(search='ORD-SEARCH-01'))
        orm = EmailOutbox.objects.filter(
            Q(subject__icontains='ORD-SEARCH-01')
            | Q(body_text__icontains='ORD-SEARCH-01')
            | Q(context_json__icontains='ORD-SEARCH-01')
        ).count()
        self.assertEqual(api, orm)
        self.assertEqual(orm, 3, '夹具里应有 3 封提到这个单号')
