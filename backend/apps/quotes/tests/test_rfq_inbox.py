"""RFQ 收件箱（`/quote-requests/manage/`）与详情放宽 —— 权限边界测试。

背景：2026-10-22 之前 RFQ **没有任何查询入口**（详情按 contact_email 过滤，连 staff 也 404），
运营只能进 Django admin 看客户询价。本组测试钉死三件事：
  1. 内部人（含 `is_staff=False` 的 procurement）能看全量
  2. 客户只能看自己的（不能借道详情看别人的）
  3. 匿名提交这条获客入口**没有被收紧**（回归）
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.quotes.models import QuoteRequest, QuoteRequestItem

LIST_URL = '/api/v1/quote-requests/manage/'


def _rfq(email='buyer@example.com', name='Buyer', **kw):
    return QuoteRequest.objects.create(
        contact_name=name, contact_email=email,
        company_name=kw.get('company_name', 'Probe Co'),
        country=kw.get('country', 'US'),
        status=kw.get('status', QuoteRequest.Status.PENDING),
        notes=kw.get('notes', ''),
    )


@pytest.mark.django_db
class TestRfqInboxPermissions:
    def _client(self, **user_kw):
        u = UserFactory(**user_kw)
        c = APIClient()
        c.force_authenticate(user=u)
        return c, u

    def test_staff_can_list(self):
        _rfq()
        c, _ = self._client(is_staff=True, email_verified=True)
        r = c.get(LIST_URL)
        assert r.status_code == 200, r.content[:300]
        payload = r.json()
        assert payload['success'] is True
        assert len(payload['data']) >= 1
        assert 'items_count' in payload['data'][0]
        assert payload['meta']['pagination']['count'] >= 1

    def test_procurement_non_staff_can_list(self):
        """★ 关键：采购通常 is_staff=False，必须能看（否则运营拿不到线索）。"""
        _rfq()
        c, u = self._client(role='procurement', is_staff=False, email_verified=True)
        assert u.is_staff is False
        r = c.get(LIST_URL)
        assert r.status_code == 200, f'采购被拒：{r.status_code} {r.content[:200]}'

    def test_admin_role_non_staff_can_list(self):
        _rfq()
        c, _ = self._client(role='admin', is_staff=False, email_verified=True)
        assert c.get(LIST_URL).status_code == 200

    def test_researcher_cannot_list(self):
        _rfq()
        c, _ = self._client(role='researcher', is_staff=False, email_verified=True)
        assert c.get(LIST_URL).status_code == 403

    def test_anonymous_cannot_list(self):
        _rfq()
        assert APIClient().get(LIST_URL).status_code in (401, 403)

    def test_search_and_status_filter(self):
        _rfq(email='alice@uni.edu', name='Alice', status=QuoteRequest.Status.PENDING)
        _rfq(email='bob@corp.com', name='Bob', status=QuoteRequest.Status.CLOSED)
        c, _ = self._client(is_staff=True, email_verified=True)

        r = c.get(LIST_URL, {'search': 'alice'})
        rows = r.json()['data']
        assert [x['contact_name'] for x in rows] == ['Alice']

        r2 = c.get(LIST_URL, {'status': 'closed'})
        assert [x['contact_name'] for x in r2.json()['data']] == ['Bob']

        # 非法 status 不报错、不过滤
        r3 = c.get(LIST_URL, {'status': 'not-a-status'})
        assert r3.status_code == 200
        assert len(r3.json()['data']) == 2


@pytest.mark.django_db
class TestRfqDetailWidening:
    def test_staff_can_read_any_rfq(self):
        """修前：staff 读别人的 RFQ 是 404（按 contact_email 过滤）。"""
        r = _rfq(email='someone-else@example.com')
        u = UserFactory(is_staff=True, email='staff@example.com', email_verified=True)
        c = APIClient(); c.force_authenticate(user=u)
        resp = c.get(f'/api/v1/quote-requests/{r.id}/')
        assert resp.status_code == 200, resp.content[:200]
        # 全局 EnvelopeRenderer 会把响应包成 {success,data,meta}
        assert resp.json()['data']['contact_email'] == 'someone-else@example.com'

    def test_customer_sees_only_own(self):
        mine = _rfq(email='me@example.com', name='Me')
        other = _rfq(email='other@example.com', name='Other')
        u = UserFactory(role='researcher', is_staff=False, email='me@example.com',
                        email_verified=True)
        c = APIClient(); c.force_authenticate(user=u)

        assert c.get(f'/api/v1/quote-requests/{mine.id}/').status_code == 200
        assert c.get(f'/api/v1/quote-requests/{other.id}/').status_code == 404

    def test_anonymous_cannot_read_detail(self):
        r = _rfq()
        assert APIClient().get(f'/api/v1/quote-requests/{r.id}/').status_code in (401, 403)


@pytest.mark.django_db
class TestRfqCreateStillOpen:
    def test_anonymous_can_submit(self):
        """回归：查询面收紧了权限，但**创建面必须保持匿名可用**。"""
        payload = {
            'contact_name': 'Anon', 'contact_email': 'anon@example.com',
            'items': [{'quantity': 2, 'note': 'probe'}],
        }
        r = APIClient().post('/api/v1/quote-requests/', payload, format='json')
        assert r.status_code == 201, r.content[:300]
        created = QuoteRequest.objects.get(id=r.json()['data']['id'])
        assert created.contact_email == 'anon@example.com'
        assert QuoteRequestItem.objects.filter(quote_request=created).count() == 1
