"""A-030：管理员建号 —— 但密码仍由本人设置。

## 这条的核心不是"能建号"，而是"建号不能顺手把密码也定了"
本项目原有设计：「密码只能由本人通过邮件链接设置；管理员能设密码 = 能冒充用户」。
QA Batch 3 的痛点是**无法代建账号**（只能让对方自助注册再改角色，而自助注册一律落
researcher，多绕一步且容易忘改）。本轮把「创建账号」与「设置密码」彻底分开：

  · 建号用 `set_unusable_password()` ⇒ 拿不到任何可用密码
  · 随即签发一封 `password_reset` 邮件，密码仍由本人设置
  · 入参里**没有 password 字段**（有就是漏洞）

## 本文件钉住
① 建号成功返回 201，且 `password_reset_queued=True`（邮件入队）
② 新账号**不能**用任何密码登录（`has_usable_password() == False`）
③ 入参带 `password` 也不生效（白名单序列化器会忽略它，但密码仍不可用）
④ 用户名/邮箱重复 ⇒ 400
⑤ role 非枚举 ⇒ 400
⑥ 权限：非 admin 不能建号
⑦ 建号后能在列表里查到、且 email_verified=True
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Organization
from apps.notifications.models import EmailOutbox

User = get_user_model()
URL = '/api/v1/ops/users/'


class OpsUserCreateTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='create_admin', email='create_admin@x.com', password='x',
            role='admin', is_staff=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.org = Organization.objects.create(name='CreateOrg', org_type='academic')

    def _create(self, **over):
        payload = {
            'username': 'new_researcher',
            'email': 'new_researcher@lab.edu',
            'role': 'researcher',
        }
        payload.update(over)
        return self.client.post(URL, payload, format='json')

    # ── ① 建号成功 + 邮件入队 ──────────────────────────────────
    def test_create_returns_201_and_queues_reset_mail(self):
        before = EmailOutbox.objects.filter(template_key='password_reset').count()
        r = self._create()
        self.assertEqual(r.status_code, 201, r.content[:400])
        d = r.json()['data']
        self.assertEqual(d['username'], 'new_researcher')
        self.assertEqual(d['role'], 'researcher')
        self.assertTrue(d['password_reset_queued'], '必须发出一封重置邮件')
        after = EmailOutbox.objects.filter(template_key='password_reset').count()
        self.assertEqual(after, before + 1)

    # ── ② 新账号没有可用密码（安全边界）─────────────────────────
    def test_new_user_has_no_usable_password(self):
        r = self._create()
        uid = r.json()['data']['id']
        u = User.objects.get(pk=uid)
        self.assertFalse(u.has_usable_password(),
                         '建号不应给出任何可用密码 —— 密码必须由本人邮件设置')

    def test_cannot_login_with_empty_or_any_password(self):
        self._create(username='nologin', email='nologin@lab.edu')
        c = APIClient()
        for pw in ('', 'password', 'x', '12345678'):
            r = c.post('/api/v1/auth/login',
                       {'username': 'nologin', 'password': pw}, format='json')
            self.assertNotEqual(r.status_code, 200,
                                f'不应能用 "{pw}" 登录成功')

    # ── ③ 传 password 也不生效 ────────────────────────────────
    def test_password_in_payload_is_ignored(self):
        r = self._create(username='withpw', email='withpw@lab.edu',
                         password='Hacker123!')
        uid = r.json()['data']['id']
        u = User.objects.get(pk=uid)
        self.assertFalse(u.has_usable_password(), '入参里的 password 不得被采纳')
        c = APIClient()
        login = c.post('/api/v1/auth/login',
                       {'username': 'withpw', 'password': 'Hacker123!'}, format='json')
        self.assertNotEqual(login.status_code, 200)

    # ── ④ 重复用户名 / 邮箱 ───────────────────────────────────
    def test_duplicate_username_rejected(self):
        self._create(username='dup1', email='dup1@lab.edu')
        r = self._create(username='dup1', email='other@lab.edu')
        self.assertEqual(r.status_code, 400, r.content[:300])

    def test_duplicate_email_rejected(self):
        self._create(username='dup2', email='dup2@lab.edu')
        r = self._create(username='other_name', email='dup2@lab.edu')
        self.assertEqual(r.status_code, 400, r.content[:300])

    def test_duplicate_check_is_case_insensitive(self):
        self._create(username='caseuser', email='case@lab.edu')
        r = self._create(username='CASEUSER', email='CASE2@lab.edu')
        self.assertEqual(r.status_code, 400, r.content[:300])

    # ── ⑤ role 非法 ──────────────────────────────────────────
    def test_invalid_role_rejected(self):
        r = self._create(username='badrole', email='badrole@lab.edu', role='superuser')
        self.assertEqual(r.status_code, 400, r.content[:300])

    # ── ⑥ 权限 ──────────────────────────────────────────────
    def test_non_admin_cannot_create(self):
        for role in ('researcher', 'procurement', 'editor'):
            u = User.objects.create_user(
                username=f'no_{role}', email=f'no_{role}@x.com', password='x', role=role)
            c = APIClient()
            c.force_authenticate(u)
            r = c.post(URL, {'username': f'x_{role}', 'email': f'x_{role}@x.com'},
                       format='json')
            self.assertIn(r.status_code, (401, 403), f'{role} 不该能建号')

    def test_anonymous_cannot_create(self):
        r = APIClient().post(URL, {'username': 'anon', 'email': 'anon@x.com'},
                             format='json')
        self.assertIn(r.status_code, (401, 403))

    # ── ⑦ 建号后可见且 email_verified ────────────────────────
    def test_created_user_visible_and_email_verified(self):
        self._create(username='visible_one', email='visible_one@lab.edu')
        rows = self.client.get(URL, {'search': 'visible_one'}).json()['data']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['username'], 'visible_one')
        self.assertTrue(rows[0]['email_verified'],
                        '管理员建号意味着邮箱已线下确认，否则用户既收不到验证信又进不去')

    # ── 机构可选 ────────────────────────────────────────────
    def test_organization_can_be_set(self):
        r = self._create(username='withorg', email='withorg@lab.edu',
                         organization_id=self.org.id)
        self.assertEqual(r.status_code, 201, r.content[:300])
        u = User.objects.get(pk=r.json()['data']['id'])
        self.assertEqual(u.organization_id, self.org.id)

    def test_invalid_organization_rejected(self):
        r = self._create(username='badorg', email='badorg@lab.edu', organization_id=999999)
        self.assertEqual(r.status_code, 400, r.content[:300])
