"""A-223：已报价 RFQ 的关闭入口（S5 P-5）。

## 改前
`QuoteRequest.Status.CLOSED` 在枚举里定义了，但**全仓没有任何写它的代码路径** ——
QA Batch 16 实测：RFQ #10 状态 `quoted`，详情面板找不到关闭按钮。
后果是收件箱只增不减：客户撤回、重复提交、明显无效的询价都清不出去。

## 本文件钉住
① `quoted` / `pending` 都能关闭（垃圾询价也要能清出去）
② 已 `closed` 再关 ⇒ **409**，且不重复写 notes（幂等）
③ 可选 reason 以 `[关闭]` 前缀**追加**到 notes —— 不覆盖客户原文
④ 权限：客户 / 匿名不能关（内部线索归运营侧管）
⑤ 关闭后列表按 `status=closed` 能筛到、按 `status=quoted` 筛不到
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.quotes.models import QuoteRequest

User = get_user_model()


def _internal(username='rfq_proc', role='procurement', is_staff=False):
    return User.objects.create_user(
        username=username, email=f'{username}@example.com', password='x',
        role=role, is_staff=is_staff,
    )


def _qr(name='Dr. Close', email='close@lab.edu', status=QuoteRequest.Status.QUOTED):
    return QuoteRequest.objects.create(
        contact_name=name, contact_email=email,
        company_name='Close Lab', notes='客户原始需求：需要 10mg',
        status=status,
    )


class RfqCloseTest(TestCase):
    def setUp(self):
        self.proc = _internal()
        self.client = APIClient()
        self.client.force_authenticate(self.proc)

    def _close(self, pk, **body):
        return self.client.post(f'/api/v1/quote-requests/{pk}/close/', body, format='json')

    # ── ① 能从 quoted / pending 关闭 ──────────────────────────
    def test_close_quoted(self):
        q = _qr()
        r = self._close(q.id)
        self.assertEqual(r.status_code, 200, r.content[:300])
        q.refresh_from_db()
        self.assertEqual(q.status, QuoteRequest.Status.CLOSED)

    def test_close_pending(self):
        """垃圾询价/客户撤回也要能清出待办，否则「待处理」只增不减。"""
        q = _qr(name='Spam', email='spam@x.com', status=QuoteRequest.Status.PENDING)
        r = self._close(q.id)
        self.assertEqual(r.status_code, 200, r.content[:300])
        q.refresh_from_db()
        self.assertEqual(q.status, QuoteRequest.Status.CLOSED)

    # ── ② 幂等：已关闭再关 409 ────────────────────────────────
    def test_close_twice_returns_409(self):
        q = _qr()
        self._close(q.id)
        r2 = self._close(q.id, reason='again')
        self.assertEqual(r2.status_code, 409, r2.content[:300])
        self.assertEqual(r2.json()['meta']['error']['code'], 'ALREADY_CLOSED')

    def test_second_close_does_not_append_reason(self):
        q = _qr()
        self._close(q.id, reason='第一次')
        before = QuoteRequest.objects.get(pk=q.id).notes
        self._close(q.id, reason='第二次不该写进去')
        after = QuoteRequest.objects.get(pk=q.id).notes
        self.assertEqual(before, after, '409 时不得再改 notes')

    # ── ③ reason 追加不覆盖 ──────────────────────────────────
    def test_reason_is_appended_not_overwritten(self):
        q = _qr()
        self._close(q.id, reason='客户改用其他供应商')
        q.refresh_from_db()
        self.assertIn('客户原始需求：需要 10mg', q.notes, '客户原文不能被冲掉')
        self.assertIn('[关闭] 客户改用其他供应商', q.notes)

    def test_close_without_reason_keeps_notes_intact(self):
        q = _qr()
        before = q.notes
        self._close(q.id)
        q.refresh_from_db()
        self.assertEqual(q.notes, before)

    # ── ④ 权限 ──────────────────────────────────────────────
    def test_customer_cannot_close(self):
        q = _qr(email='me@lab.edu')
        cust = User.objects.create_user(
            username='rfq_cust', email='me@lab.edu', password='x', role='researcher')
        c = APIClient()
        c.force_authenticate(cust)
        r = c.post(f'/api/v1/quote-requests/{q.id}/close/', {}, format='json')
        self.assertIn(r.status_code, (401, 403), r.content[:200])
        q.refresh_from_db()
        self.assertEqual(q.status, QuoteRequest.Status.QUOTED)

    def test_anonymous_cannot_close(self):
        q = _qr()
        r = APIClient().post(f'/api/v1/quote-requests/{q.id}/close/', {}, format='json')
        self.assertIn(r.status_code, (401, 403), r.content[:200])

    # ── ⑤ 关闭后能被筛到 / 从原状态筛不到 ─────────────────────
    def test_closed_shows_under_closed_filter_only(self):
        q = _qr()
        self._close(q.id)
        closed = self.client.get('/api/v1/quote-requests/manage/',
                                 {'status': 'closed'}).json()['data']
        self.assertIn(q.id, [x['id'] for x in closed])
        quoted = self.client.get('/api/v1/quote-requests/manage/',
                                 {'status': 'quoted'}).json()['data']
        self.assertNotIn(q.id, [x['id'] for x in quoted])

    def test_not_found_returns_404(self):
        r = self._close(999999)
        self.assertEqual(r.status_code, 404)
