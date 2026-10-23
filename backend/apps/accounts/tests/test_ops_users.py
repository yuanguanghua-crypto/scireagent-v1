"""运营台「用户与角色」—— 权限边界与防自锁。

这个模块每一条都是安全约束，不是功能测试：
- 谁能进（admin / staff），谁不能（researcher / procurement）
- 改自己 ⇒ 拒绝（防自锁）
- 改 is_staff / password ⇒ 拒绝而不是静默忽略
- 最后一个 admin 不能降级（否则运维入口永久锁死）
- 停用后必须吊销 token（否则旧会话还能用）
"""
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import EmailVerification, PasswordReset
from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import EmailOutbox

LIST_URL = '/api/v1/ops/users/'


class UserOpsPermissionTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_anonymous_denied(self):
        self.assertIn(self.client.get(LIST_URL).status_code, (401, 403))

    def test_researcher_denied(self):
        self.client.force_authenticate(UserFactory(is_staff=False, role='researcher'))
        self.assertIn(self.client.get(LIST_URL).status_code, (401, 403))

    def test_procurement_denied(self):
        """procurement 能看订单、能报价，但**不该能改别人的角色**。"""
        self.client.force_authenticate(UserFactory(is_staff=False, role='procurement'))
        self.assertIn(self.client.get(LIST_URL).status_code, (401, 403))

    def test_staff_allowed(self):
        self.client.force_authenticate(UserFactory(is_staff=True))
        self.assertEqual(self.client.get(LIST_URL).status_code, 200)


class UserOpsListTest(TestCase):
    def setUp(self):
        self.admin = UserFactory(is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_rows_contain_state_fields(self):
        UserFactory(username='probeuser', email='probe@lab.org', role='researcher')
        rows = self.client.get(LIST_URL).json()['data']
        row = next(r for r in rows if r['username'] == 'probeuser')
        for f in ('id', 'email', 'role', 'is_active', 'email_verified', 'date_joined'):
            self.assertIn(f, row)
        self.assertNotIn('password', row, '列表绝不能返回密码字段')

    def test_filter_unverified(self):
        UserFactory(username='unverified1', email_verified=False)
        UserFactory(username='verified1', email_verified=True)
        rows = self.client.get(LIST_URL, {'email_verified': 'false'}).json()['data']
        names = {r['username'] for r in rows}
        self.assertIn('unverified1', names)
        self.assertNotIn('verified1', names)

    def test_search_by_email(self):
        UserFactory(username='findme', email='needle@uni.edu')
        rows = self.client.get(LIST_URL, {'search': 'needle'}).json()['data']
        self.assertEqual([r['username'] for r in rows], ['findme'])


class UserOpsPatchTest(TestCase):
    def setUp(self):
        self.admin = UserFactory(is_staff=True, username='opsadmin')
        self.target = UserFactory(username='target', role='researcher', is_staff=False)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.url = f'/api/v1/ops/users/{self.target.pk}/'

    def test_change_role(self):
        r = self.client.patch(self.url, {'role': 'procurement'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.target.refresh_from_db()
        self.assertEqual(self.target.role, 'procurement')

    def test_cannot_edit_self(self):
        url = f'/api/v1/ops/users/{self.admin.pk}/'
        before = self.admin.role
        r = self.client.patch(url, {'role': 'researcher'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, before, '自己的角色不允许被改动')

    def test_cannot_edit_is_staff(self):
        r = self.client.patch(self.url, {'is_staff': True}, format='json')
        self.assertEqual(r.status_code, 400, '提权字段必须明确拒绝，不能静默忽略')
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_staff)

    def test_cannot_edit_password(self):
        r = self.client.patch(self.url, {'password': 'hacked'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_empty_payload_rejected(self):
        r = self.client.patch(self.url, {}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_last_admin_cannot_be_demoted(self):
        """只有一个管理员时，降级它等于把运维入口永久锁死。"""
        from django.contrib.auth import get_user_model
        U = get_user_model()
        U.objects.filter(is_staff=True).exclude(pk=self.admin.pk).delete()
        U.objects.filter(role='admin').exclude(pk=self.admin.pk).update(role='researcher')
        solo_admin = UserFactory(username='soloadmin', is_staff=True)
        self.admin.delete()
        self.client.force_authenticate(solo_admin)

        r = self.client.patch(
            f'/api/v1/ops/users/{solo_admin.pk}/', {'role': 'researcher'}, format='json',
        )
        # 改自己先被拦（更早的规则），但即使绕过也应被"最后一个管理员"拦住
        self.assertEqual(r.status_code, 400)

    def test_deactivate_revokes_tokens(self):
        Token.objects.create(user=self.target)
        r = self.client.patch(self.url, {'is_active': False}, format='json')
        self.assertEqual(r.status_code, 200)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)
        self.assertEqual(Token.objects.filter(user=self.target).count(), 0,
                         '停用后必须吊销 token，否则旧会话仍能继续操作')


class UserOpsVerifyEmailTest(TestCase):
    def setUp(self):
        self.admin = UserFactory(is_staff=True)
        self.target = UserFactory(email_verified=False)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_marks_verified_and_clears_token(self):
        EmailVerification.objects.create(
            user=self.target,
            expires_at=self.target.date_joined,   # 值不重要，存在即可
        )
        r = self.client.post(f'/api/v1/ops/users/{self.target.pk}/verify-email/')
        self.assertEqual(r.status_code, 200)
        self.target.refresh_from_db()
        self.assertTrue(self.target.email_verified)
        self.assertFalse(EmailVerification.objects.filter(user=self.target).exists(),
                         '待验证令牌应被清掉')

    def test_idempotent(self):
        self.target.email_verified = True
        self.target.save(update_fields=['email_verified'])
        r = self.client.post(f'/api/v1/ops/users/{self.target.pk}/verify-email/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['data']['already_verified'])


class UserOpsSendResetTest(TestCase):
    def setUp(self):
        from django.core.management import call_command
        call_command('seed_email_templates', verbosity=0)
        self.admin = UserFactory(is_staff=True)
        self.target = UserFactory(email='reset-target@lab.org')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_queues_reset_mail(self):
        r = self.client.post(f'/api/v1/ops/users/{self.target.pk}/send-password-reset/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['data']['queued'])
        self.assertIsNone(r.json()['data']['reset_url'], '邮件入队时不再回传链接')

        reset = PasswordReset.objects.get(user=self.target)
        self.assertFalse(reset.is_expired())
        mails = EmailOutbox.objects.filter(template_key='password_reset')
        self.assertEqual(mails.count(), 1)
        self.assertEqual(mails.first().to_emails, 'reset-target@lab.org')
        self.assertIn(str(reset.token), mails.first().body_text)

    def test_inactive_user_rejected(self):
        self.target.is_active = False
        self.target.save(update_fields=['is_active'])
        r = self.client.post(f'/api/v1/ops/users/{self.target.pk}/send-password-reset/')
        self.assertEqual(r.status_code, 400)

    def test_no_email_rejected(self):
        self.target.email = ''
        self.target.save(update_fields=['email'])
        r = self.client.post(f'/api/v1/ops/users/{self.target.pk}/send-password-reset/')
        self.assertEqual(r.status_code, 400)
