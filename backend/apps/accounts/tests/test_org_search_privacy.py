"""F2 回归 — 匿名 GET /api/v1/organizations 泄露客户名录与联系人 PII。

修复前缺陷（已核实）：
- `OrganizationSearchView` 是 `AllowAny` + `authentication_classes = []`；
- `q = request.query_params.get('q', '')` ⇒ 不传 q 时 `name__icontains=''` 命中全部
  active 机构，一次返回 10 条；
- `OrganizationSerializer` 输出 `contact_email / contact_phone / address_line1 /
  address_line2 / city / state / postal_code` 以及 `member_count`（该机构用户数），
  而 `OrganizationCreateView` 任意登录用户可写 ⇒ 字段一填就匿名可见。

本文件钉住修复后的契约：
1. 匿名搜索的每条记录键集合**恰好** == 白名单（加字段立刻红）
2. 匿名不带 q → `data == []`
3. 匿名 `?q=a`（长度 1）→ `data == []`
4. 响应原始 JSON 不含 contact_*/address_line*（防止换序列化器时漏掉）
5. 正向 `?q=Beijing` 能搜到 `Beijing Chemistry Lab`（功能没被砍死）

注意：本项目全局 `EnvelopeRenderer` 把 Response.data 包成
`{"success":..., "data":..., "meta":...}`（core/renderers.py），故断言取 `['data']`。
"""
import json

from rest_framework.test import APITestCase

from apps.accounts.models import Organization

PUBLIC_FIELDS = {'id', 'name', 'short_name', 'org_type', 'country'}


class OrganizationSearchPrivacyTests(APITestCase):
    def setUp(self):
        self.url = '/api/v1/organizations'
        self.client.force_authenticate(None)  # 匿名
        self.org = Organization.objects.create(
            name='Beijing Chemistry Lab',
            short_name='BCL',
            org_type=Organization.OrgType.ACADEMIC,
            country='China',
            status='active',
            contact_email='pi@bcl.example.com',
            contact_phone='+86-10-1234-5678',
            address_line1='1 Zhongguancun Rd',
            address_line2='Building 7',
            city='Beijing',
            state='Beijing',
            postal_code='100190',
        )

    # ── 1. 键集合必须恰好是白名单 ──
    def test_search_returns_exact_public_field_set(self):
        resp = self.client.get(self.url, {'q': 'Chemistry'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertTrue(data, '正向搜索不应为空')
        for item in data:
            self.assertEqual(
                set(item.keys()), PUBLIC_FIELDS,
                f'匿名搜索字段漂移：多出 {set(item.keys()) - PUBLIC_FIELDS}，'
                f'缺少 {PUBLIC_FIELDS - set(item.keys())}',
            )

    # ── 2. 不带 q → 空列表（修复前返回最多 10 条全表）──
    def test_search_without_q_returns_empty(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data'], [])

    # ── 3. q 长度 1 → 空列表 ──
    def test_search_single_char_query_returns_empty(self):
        resp = self.client.get(self.url, {'q': 'a'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data'], [])

    # ── 3b. 纯空白 q → 空列表（去空白后长度为 0）──
    def test_search_blank_query_returns_empty(self):
        resp = self.client.get(self.url, {'q': '   '})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data'], [])

    # ── 4. 兜底：原始 JSON 里不得出现 PII 键 ──
    def test_raw_response_contains_no_pii_keys(self):
        resp = self.client.get(self.url, {'q': 'Beijing'})
        self.assertEqual(resp.status_code, 200)
        raw = json.dumps(resp.json(), ensure_ascii=False)
        for leaked in ('contact_email', 'contact_phone', 'address_line1',
                       'address_line2', 'postal_code', 'member_count'):
            self.assertNotIn(leaked, raw, f'匿名响应泄露 {leaked}')

    # ── 5. 正向：功能仍在 ──
    def test_search_by_name_still_works(self):
        resp = self.client.get(self.url, {'q': 'Beijing'})
        self.assertEqual(resp.status_code, 200)
        rows = resp.json()['data']
        mine = [r for r in rows if r['id'] == self.org.id]
        self.assertEqual(len(mine), 1, f'未搜到 Beijing Chemistry Lab：{rows}')
        self.assertEqual(mine[0]['name'], 'Beijing Chemistry Lab')
        self.assertEqual(mine[0]['short_name'], 'BCL')
        self.assertEqual(mine[0]['org_type'], 'academic')
        self.assertEqual(mine[0]['country'], 'China')

    # ── 6. 仍受 status='active' 过滤 + [:10] 上限约束 ──
    def test_suspended_org_not_returned(self):
        suspended = Organization.objects.create(
            name='Beijing Suspended Lab', org_type='academic', status='suspended')
        resp = self.client.get(self.url, {'q': 'Beijing Suspended'})
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in resp.json()['data']]
        self.assertNotIn(suspended.id, ids)

    def test_at_most_10_results(self):
        for i in range(15):
            Organization.objects.create(
                name=f'Beijing Bulk Lab {i}', org_type='academic', status='active')
        resp = self.client.get(self.url, {'q': 'Beijing Bulk'})
        self.assertEqual(resp.status_code, 200)
        self.assertLessEqual(len(resp.json()['data']), 10)
