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


# ---------------------------------------------------------------------------
# F2 功能回退修复 —— 运维台「机构管理」全量列表端点
#
# 收紧 `OrganizationSearchView` 之后，`/ops/po/organizations`
# （frontend/src/views/admin/PoOrgManagement.vue:16）用 `page_size: 100` **不带 q**
# 去取左栏列表，于是恒得空数组 —— 左栏 Organizations 表格空白。
# 修法不是放开匿名搜索（那等于把刚堵的洞重新打开），而是另开受权限保护的管理端点。
# 本组用例钉住：谁能访问、按什么排序、分页边界、以及字段面与匿名面**刻意不同**。
# ---------------------------------------------------------------------------
from apps.accounts.tests.factories import UserFactory  # noqa: E402


class OrganizationManageListTests(APITestCase):
    URL = '/api/v1/organizations/manage/'

    def setUp(self):
        self.org = Organization.objects.create(
            name='Zeta Labs', org_type='academic', country='China', status='active',
            contact_email='pi@zeta.example.com',
            address_line1='9 Zeta Rd',
        )
        Organization.objects.create(
            name='Alpha Labs', org_type='industry', country='China', status='active')
        # 非 active 不应出现
        Organization.objects.create(
            name='Beta Suspended', org_type='industry', status='suspended')

    def _login(self, *, role='procurement', is_staff=False):
        u = UserFactory(role=role, is_staff=is_staff)
        self.client.force_authenticate(user=u)
        return u

    def test_anonymous_denied(self):
        self.client.force_authenticate(None)
        resp = self.client.get(self.URL)
        self.assertIn(resp.status_code, (401, 403), f'匿名不该拿到全量机构：{resp.status_code}')

    def test_plain_researcher_denied(self):
        self._login(role='researcher')
        resp = self.client.get(self.URL)
        self.assertIn(resp.status_code, (401, 403), f'普通研究员不该拿到全量机构：{resp.status_code}')

    def test_procurement_allowed_and_gets_active_orgs(self):
        self._login(role='procurement')
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        names = [o['name'] for o in body['data']]
        self.assertIn('Zeta Labs', names)
        self.assertIn('Alpha Labs', names)
        self.assertNotIn('Beta Suspended', names, '非 active 机构不得返回')

    def test_admin_allowed(self):
        self._login(role='admin', is_staff=True)
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)

    def test_sorted_by_name(self):
        self._login(role='procurement')
        names = [o['name'] for o in self.client.get(self.URL).json()['data']]
        self.assertEqual(names, sorted(names), '左栏列表应按 name 排序，否则同一批数据每次顺序都可能不同')

    def test_manage_exposes_full_fields_unlike_anonymous_search(self):
        """管理面**刻意**比匿名面宽：机构管理要看到联系人/地址。

        这条是"两条路径字段面不同"的显式契约 —— 若将来有人把管理面也换成
        OrganizationSummarySerializer，这里会红，提醒他先确认管理台是否还需要这些列。
        """
        self._login(role='procurement')
        rows = self.client.get(self.URL).json()['data']
        zeta = next(o for o in rows if o['name'] == 'Zeta Labs')
        self.assertIn('contact_email', zeta)
        self.assertIn('address_line1', zeta)
        # 但匿名面必须仍然不含（对照组，防止"顺手把两边统一"）
        anon = self.client.get('/api/v1/organizations', {'q': 'Zeta'}).json()['data']
        self.assertEqual(set(anon[0].keys()), PUBLIC_FIELDS)

    def test_pagination_meta_and_clamping(self):
        self._login(role='procurement')
        body = self.client.get(self.URL, {'page_size': 1}).json()
        self.assertEqual(len(body['data']), 1, 'page_size=1 应只返回 1 条')
        self.assertGreaterEqual(body['meta']['pagination']['count'], 2,
                                'meta.pagination.count 应是全量条数，不是本页条数')

    def test_invalid_page_size_falls_back(self):
        self._login(role='procurement')
        for bad in ('0', '-5', 'abc', ''):
            resp = self.client.get(self.URL, {'page_size': bad})
            self.assertEqual(resp.status_code, 200, f'page_size={bad!r} 不该报错')
            self.assertGreaterEqual(len(resp.json()['data']), 1,
                                    f'page_size={bad!r} 被夹紧后应至少返回 1 条')

    def test_page_size_upper_bound(self):
        self._login(role='procurement')
        resp = self.client.get(self.URL, {'page_size': 999999})
        self.assertEqual(resp.status_code, 200)
        self.assertLessEqual(resp.json()['meta']['pagination']['page_size'], 500)
