"""密码重置 —— 申请 / 确认 / 安全边界。

覆盖 2026-10-23 之前完全没有的能力（grep password_reset 零命中），
以及四条容易写错的安全规则：
  1. 申请端点必须防用户枚举（存在/不存在返回完全一致）
  2. 畸形 token 不能 500（UUIDField 抛的是 DjangoValidationError）
  3. token 一次性，用过即失效
  4. 换完密码必须吊销该用户全部 auth token（否则旧会话仍有效）
"""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.accounts.models import PasswordReset, User
from apps.notifications.models import EmailOutbox


class PasswordResetRequestTest(TestCase):
    def setUp(self):
        from django.core.management import call_command
        call_command('seed_email_templates', verbosity=0)
        self.client = APIClient()
        self.url = '/api/v1/auth/request-password-reset'
        self.user = User.objects.create_user(
            username='resetme', email='resetme@lab.example.org', password='OldPass#2026'
        )

    def test_registered_email_enqueues_reset_mail_with_rendered_link(self):
        resp = self.client.post(self.url, {'email': 'resetme@lab.example.org'}, format='json')
        self.assertEqual(resp.status_code, 200)

        reset = PasswordReset.objects.get(user=self.user)
        self.assertFalse(reset.is_expired())

        mails = EmailOutbox.objects.filter(template_key='password_reset')
        self.assertEqual(mails.count(), 1)
        m = mails.first()
        self.assertEqual(m.to_emails, 'resetme@lab.example.org')
        self.assertTrue(m.subject.strip())
        self.assertIn(str(reset.token), m.body_text, '邮件正文必须带 token 链接')
        self.assertIn('resetme', m.body_text)

    def test_unregistered_email_returns_identical_response(self):
        """防用户枚举：未知邮箱与已知邮箱的响应必须逐字相同。"""
        known = self.client.post(self.url, {'email': 'resetme@lab.example.org'}, format='json')
        unknown = self.client.post(self.url, {'email': 'nobody@lab.example.org'}, format='json')
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.data.get('detail'), unknown.data.get('detail'))
        self.assertFalse(PasswordReset.objects.filter(user__email='nobody@lab.example.org').exists())

    def test_resend_invalidates_previous_token(self):
        self.client.post(self.url, {'email': 'resetme@lab.example.org'}, format='json')
        first = PasswordReset.objects.get(user=self.user).token
        self.client.post(self.url, {'email': 'resetme@lab.example.org'}, format='json')
        second = PasswordReset.objects.get(user=self.user).token
        self.assertNotEqual(first, second, '重复申请必须换新 token（旧的立即失效）')

    def test_inactive_user_gets_no_token(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        resp = self.client.post(self.url, {'email': 'resetme@lab.example.org'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(PasswordReset.objects.filter(user=self.user).exists())


class PasswordResetConfirmTest(TestCase):
    def setUp(self):
        from django.core.management import call_command
        call_command('seed_email_templates', verbosity=0)
        self.client = APIClient()
        self.url = '/api/v1/auth/reset-password'
        self.user = User.objects.create_user(
            username='confirmme', email='confirmme@lab.example.org', password='OldPass#2026'
        )
        self.reset = PasswordReset.objects.create(user=self.user)

    def test_valid_token_sets_new_password_and_consumes_token(self):
        resp = self.client.post(
            self.url, {'token': str(self.reset.token), 'new_password': 'BrandNew#2026'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('BrandNew#2026'))
        self.assertFalse(PasswordReset.objects.filter(user=self.user).exists(), 'token 必须一次性')

    def test_reset_revokes_existing_auth_tokens(self):
        """换完密码必须踢下线，否则被盗的旧 token 仍能继续操作。"""
        Token.objects.create(user=self.user)
        self.assertEqual(Token.objects.filter(user=self.user).count(), 1)

        self.client.post(
            self.url, {'token': str(self.reset.token), 'new_password': 'BrandNew#2026'},
            format='json',
        )
        self.assertEqual(Token.objects.filter(user=self.user).count(), 0)

    def test_reset_does_not_touch_email_verified(self):
        """重置密码绝不能顺手把邮箱验证置 True —— 那等于绕过验证。"""
        self.user.email_verified = False
        self.user.save(update_fields=['email_verified'])
        self.client.post(
            self.url, {'token': str(self.reset.token), 'new_password': 'BrandNew#2026'},
            format='json',
        )
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_malformed_token_returns_400_not_500(self):
        """UUIDField 遇到畸形串抛 DjangoValidationError，必须被捕获成 400。"""
        for bad in ['not-a-uuid', '123', 'x' * 40]:
            resp = self.client.post(
                self.url, {'token': bad, 'new_password': 'BrandNew#2026'}, format='json'
            )
            self.assertEqual(resp.status_code, 400, f'{bad} 应 400，实际 {resp.status_code}')

    def test_expired_token_rejected_and_cleaned(self):
        PasswordReset.objects.filter(user=self.user).update(
            expires_at=timezone.now() - timedelta(minutes=1)
        )
        resp = self.client.post(
            self.url, {'token': str(self.reset.token), 'new_password': 'BrandNew#2026'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(PasswordReset.objects.filter(user=self.user).exists(), '过期 token 应被清理')

    def test_weak_password_rejected(self):
        resp = self.client.post(
            self.url, {'token': str(self.reset.token), 'new_password': '123'}, format='json'
        )
        self.assertEqual(resp.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('OldPass#2026'), '弱密码不应生效')
