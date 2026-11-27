"""S9：RFQ 状态入口 + 客户侧查看/答复报价（A-020 / A-170 / A-264，2026-11-27）。

三条同一族：**枚举里有的状态没写入口、能力存在但界面无门**。

- A-020（P0）：`reviewing` 在枚举里，但全仓没有写它的路径 ⇒ 「Pending 无法改为 Reviewing」；
- A-170（P1）：客户 `/orders` 没有 RFQ 入口，自己的询价看不到（详情 API 明明 200）；
- A-264（P1）：枚举里**连 accepted/rejected 都没有** ⇒ 客户收到报价后无处答复。

本文件钉住三条端点 + 权限边界：
① staff 才能把 pending → reviewing（幂等 409，且不能把 quoted 打回去）；
② 只有**本人**能答复，且只有 quoted 状态可答复；
③ `/mine/` 只返回自己的询价（按 user 或 contact_email 归属）。
"""
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.quotes.models import QuoteRequest


def _rfq(**kw):
    defaults = dict(
        contact_name='Wei', contact_email='wei@example.edu',
        status=QuoteRequest.Status.PENDING,
    )
    defaults.update(kw)
    return QuoteRequest.objects.create(**defaults)


class StartReviewTest(TestCase):
    """A-020：pending → reviewing。"""

    def setUp(self):
        self.staff = UserFactory(is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def test_pending_can_go_to_reviewing(self):
        q = _rfq()
        r = self.client.post(f'/api/v1/quote-requests/{q.id}/review/')
        self.assertEqual(r.status_code, 200, r.content[:300])
        q.refresh_from_db()
        self.assertEqual(q.status, QuoteRequest.Status.REVIEWING)

    def test_repeat_is_conflict(self):
        q = _rfq(status=QuoteRequest.Status.REVIEWING)
        r = self.client.post(f'/api/v1/quote-requests/{q.id}/review/')
        self.assertEqual(r.status_code, 409, '重复操作应 409，不该静默成功')

    def test_quoted_cannot_be_downgraded(self):
        q = _rfq(status=QuoteRequest.Status.QUOTED)
        r = self.client.post(f'/api/v1/quote-requests/{q.id}/review/')
        self.assertEqual(r.status_code, 409, '★ 已报价不能被"标为审核中"打回去')

    def test_customer_cannot_start_review(self):
        q = _rfq()
        c = APIClient()
        c.force_authenticate(UserFactory())
        self.assertEqual(c.post(f'/api/v1/quote-requests/{q.id}/review/').status_code, 403)


class CustomerRespondTest(TestCase):
    """A-264：客户接受 / 拒绝报价。"""

    def setUp(self):
        self.me = UserFactory(email='wei@example.edu')
        self.client = APIClient()
        self.client.force_authenticate(self.me)

    def _quoted(self, **kw):
        return _rfq(status=QuoteRequest.Status.QUOTED, user=self.me,
                    quoted_total=100, **kw)

    def test_accept_sets_status_and_timestamp(self):
        q = self._quoted()
        r = self.client.post(f'/api/v1/quote-requests/{q.id}/respond/',
                             {'action': 'accept'}, format='json')
        self.assertEqual(r.status_code, 200, r.content[:300])
        q.refresh_from_db()
        self.assertEqual(q.status, QuoteRequest.Status.ACCEPTED)
        self.assertIsNotNone(q.customer_responded_at)

    def test_reject_appends_note_without_overwriting(self):
        q = self._quoted(notes='Need 100 mM')
        r = self.client.post(f'/api/v1/quote-requests/{q.id}/respond/',
                             {'action': 'reject', 'note': 'too expensive'}, format='json')
        self.assertEqual(r.status_code, 200)
        q.refresh_from_db()
        self.assertEqual(q.status, QuoteRequest.Status.REJECTED)
        self.assertIn('Need 100 mM', q.notes, '客户原始需求不能被覆盖')
        self.assertIn('[客户拒绝] too expensive', q.notes)

    def test_only_quoted_can_be_answered(self):
        q = _rfq(status=QuoteRequest.Status.PENDING, user=self.me)
        r = self.client.post(f'/api/v1/quote-requests/{q.id}/respond/',
                             {'action': 'accept'}, format='json')
        self.assertEqual(r.status_code, 409)

    def test_second_answer_is_conflict(self):
        q = self._quoted()
        self.client.post(f'/api/v1/quote-requests/{q.id}/respond/',
                         {'action': 'accept'}, format='json')
        r = self.client.post(f'/api/v1/quote-requests/{q.id}/respond/',
                             {'action': 'reject'}, format='json')
        self.assertEqual(r.status_code, 409, '已答复的单子不能再改口径')

    def test_other_customer_gets_404(self):
        q = self._quoted()
        other = APIClient()
        other.force_authenticate(UserFactory(email='someone-else@example.edu'))
        r = other.post(f'/api/v1/quote-requests/{q.id}/respond/',
                       {'action': 'accept'}, format='json')
        self.assertEqual(r.status_code, 404, '不得泄露他人 RFQ 是否存在')

    def test_invalid_action_rejected(self):
        q = self._quoted()
        r = self.client.post(f'/api/v1/quote-requests/{q.id}/respond/',
                             {'action': 'maybe'}, format='json')
        self.assertEqual(r.status_code, 400)


class MyQuoteRequestsTest(TestCase):
    """A-170：客户能看到自己的询价列表。"""

    def setUp(self):
        self.me = UserFactory(email='wei@example.edu')
        self.client = APIClient()
        self.client.force_authenticate(self.me)

    def test_returns_only_my_rfqs(self):
        mine_by_user = _rfq(user=self.me, contact_email='wei@example.edu')
        mine_by_email = _rfq(contact_email='WEI@example.edu')      # 大小写不敏感
        others = _rfq(contact_email='other@example.edu')
        r = self.client.get('/api/v1/quote-requests/mine/')
        self.assertEqual(r.status_code, 200, r.content[:300])
        ids = {row['id'] for row in r.json()['data']}
        self.assertEqual(ids, {mine_by_user.id, mine_by_email.id})
        self.assertNotIn(others.id, ids)

    def test_anonymous_is_rejected(self):
        self.assertEqual(APIClient().get('/api/v1/quote-requests/mine/').status_code, 401)

    def test_payload_carries_quote_fields(self):
        q = _rfq(user=self.me, status=QuoteRequest.Status.QUOTED,
                 quoted_total=88, quoted_currency='USD')
        row = self.client.get('/api/v1/quote-requests/mine/').json()['data'][0]
        self.assertEqual(row['id'], q.id)
        self.assertEqual(str(row['quoted_total']), '88.00')
        self.assertIn('items', row, '客户要能看到自己询的是什么')
