"""
Tests for accounts app — RegisterView, LoginView, LogoutView, MeView, ProfileView,
OrganizationSearchView, OrganizationCreateView, and email verification.
"""
import uuid
from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from apps.accounts.models import EmailVerification, Organization, User
from apps.accounts.tests.factories import UserFactory


class RegisterAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/auth/register'

    def test_register_solo_creates_user_and_org(self):
        resp = self.client.post(self.url, {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'testpass123',
            'password_confirm': 'testpass123',
            'role': 'researcher',
            'organization_choice': 'solo',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        # Registration must NOT mint a token — the user must verify email first.
        self.assertNotIn('token', resp.data)
        self.assertIn('detail', resp.data)
        self.assertEqual(resp.data['email'], 'new@example.com')
        self.assertTrue(User.objects.filter(username='newuser').exists())
        user = User.objects.get(username='newuser')
        self.assertIsNotNone(user.organization)
        self.assertTrue(user.is_org_admin)
        # Newly registered accounts start unverified.
        self.assertFalse(user.email_verified)

    def test_register_does_not_create_token(self):
        resp = self.client.post(self.url, {
            'username': 'tokenuser',
            'email': 'token@example.com',
            'password': 'testpass123',
            'password_confirm': 'testpass123',
            'role': 'researcher',
            'organization_choice': 'solo',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        user = User.objects.get(username='tokenuser')
        # No token is minted at registration — verification is required first.
        self.assertFalse(Token.objects.filter(user=user).exists())
        self.assertFalse(user.email_verified)

    def test_register_duplicate_username(self):
        UserFactory(username='existing')
        resp = self.client.post(self.url, {
            'username': 'existing',
            'email': 'new@example.com',
            'password': 'testpass123',
            'password_confirm': 'testpass123',
            'role': 'researcher',
            'organization_choice': 'solo',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_register_duplicate_email(self):
        UserFactory(email='dup@example.com')
        resp = self.client.post(self.url, {
            'username': 'unique_user',
            'email': 'dup@example.com',
            'password': 'testpass123',
            'password_confirm': 'testpass123',
            'role': 'researcher',
            'organization_choice': 'solo',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_register_password_mismatch(self):
        resp = self.client.post(self.url, {
            'username': 'failuser',
            'email': 'fail@example.com',
            'password': 'testpass123',
            'password_confirm': 'different',
            'role': 'researcher',
            'organization_choice': 'solo',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_register_short_password(self):
        resp = self.client.post(self.url, {
            'username': 'shortpw',
            'email': 'short@example.com',
            'password': '1234567',
            'password_confirm': '1234567',
            'role': 'researcher',
            'organization_choice': 'solo',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_register_invalid_role_admin(self):
        resp = self.client.post(self.url, {
            'username': 'badrole',
            'email': 'bad@example.com',
            'password': 'testpass123',
            'password_confirm': 'testpass123',
            'role': 'admin',
            'organization_choice': 'solo',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_register_invalid_role_editor(self):
        resp = self.client.post(self.url, {
            'username': 'badrole2',
            'email': 'bad2@example.com',
            'password': 'testpass123',
            'password_confirm': 'testpass123',
            'role': 'editor',
            'organization_choice': 'solo',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_register_join_existing_org(self):
        # ★ 2026-10-21 L7：join 改为「注册邮箱域名必须等于机构登记的 contact_email 域名」，
        #   故桩数据必须给机构登记一个**非公共域名**的邮箱（example.com 保留给测试，
        #   不在 PUBLIC_MAILBOX_DOMAINS 黑名单里）。注册邮箱 join@example.com 与之同域。
        org = Organization.objects.create(
            name='Test Org',
            org_type=Organization.OrgType.ACADEMIC,
            created_by=UserFactory(),
            contact_email='pi@example.com',
        )
        resp = self.client.post(self.url, {
            'username': 'joiner',
            'email': 'join@example.com',
            'password': 'testpass123',
            'password_confirm': 'testpass123',
            'role': 'researcher',
            'organization_choice': 'join',
            'organization_id': org.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        user = User.objects.get(username='joiner')
        self.assertEqual(user.organization, org)
        self.assertFalse(user.is_org_admin)

    def test_register_join_missing_org_id(self):
        resp = self.client.post(self.url, {
            'username': 'noorg',
            'email': 'noorg@example.com',
            'password': 'testpass123',
            'password_confirm': 'testpass123',
            'role': 'researcher',
            'organization_choice': 'join',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_register_join_nonexistent_org(self):
        resp = self.client.post(self.url, {
            'username': 'badorg',
            'email': 'badorg@example.com',
            'password': 'testpass123',
            'password_confirm': 'testpass123',
            'role': 'researcher',
            'organization_choice': 'join',
            'organization_id': 99999,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_register_create_org(self):
        resp = self.client.post(self.url, {
            'username': 'creator',
            'email': 'creator@example.com',
            'password': 'testpass123',
            'password_confirm': 'testpass123',
            'role': 'procurement',
            'organization_choice': 'create',
            'organization_name': 'My New Org',
            'organization_type': Organization.OrgType.ENTERPRISE,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        user = User.objects.get(username='creator')
        self.assertEqual(user.organization.name, 'My New Org')
        self.assertTrue(user.is_org_admin)

    def test_register_create_org_missing_name(self):
        resp = self.client.post(self.url, {
            'username': 'noname',
            'email': 'noname@example.com',
            'password': 'testpass123',
            'password_confirm': 'testpass123',
            'role': 'researcher',
            'organization_choice': 'create',
            'organization_name': '',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_register_missing_required_fields(self):
        resp = self.client.post(self.url, {}, format='json')
        self.assertEqual(resp.status_code, 400)


class RegisterJoinOrgRaceTest(TestCase):
    """`organization_choice='join'` 的机构解析在 create() 里不得抛未捕获异常。

    背景：`validate()` 与 `create()` 各自独立查了一次 `Organization`。两次查询
    之间机构可能被停用（管理员操作 / 批量任务），此时 `create()` 里的裸
    `Organization.objects.get(...)` 会把 `DoesNotExist` 抛到视图外 ⇒ HTTP 500。

    注意：单次 HTTP 请求里「机构已停用」会被 `validate()` 先拦住并返回 400，
    所以**只有 validate 通过后再停用**（下面对序列化器直接做的 TOCTOU 用例）
    才真正覆盖 create() 这条路径。
    """

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/auth/register'

    def _payload(self, **overrides):
        payload = {
            'username': 'raceuser',
            'email': 'race@example.com',
            'password': 'testpass123',
            'password_confirm': 'testpass123',
            'role': 'researcher',
            'organization_choice': 'join',
        }
        payload.update(overrides)
        return payload

    def _org(self, name='Join Race Org', status=Organization.Status.ACTIVE):
        # ★ 2026-10-21 L7：join 需机构登记邮箱，且域名 == 注册邮箱域名
        #   （本类注册邮箱固定 race@example.com）。
        return Organization.objects.create(
            name=name,
            org_type=Organization.OrgType.ACADEMIC,
            created_by=UserFactory(),
            status=status,
            contact_email='pi@example.com',
        )

    def _error_details(self, resp):
        """本项目响应统一裹了 envelope，字段级错误在 meta.error.details。"""
        return resp.data['meta']['error']['details']

    def test_join_active_org_registers_successfully(self):
        """回归：合法机构必须仍能注册成功（别把正常路径搞坏）。"""
        org = self._org()
        resp = self.client.post(
            self.url, self._payload(organization_id=org.id), format='json')
        self.assertEqual(resp.status_code, 201)
        user = User.objects.get(username='raceuser')
        self.assertEqual(user.organization, org)
        self.assertFalse(user.is_org_admin)

    def test_join_missing_org_id_returns_400(self):
        resp = self.client.post(self.url, self._payload(), format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('organization_id', self._error_details(resp))
        self.assertFalse(User.objects.filter(username='raceuser').exists())

    def test_join_nonexistent_org_returns_400(self):
        resp = self.client.post(
            self.url, self._payload(organization_id=99999), format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('organization_id', self._error_details(resp))
        self.assertFalse(User.objects.filter(username='raceuser').exists())

    def test_join_suspended_org_returns_400(self):
        """已停用机构在 validate() 阶段即被拦 ⇒ 400，且不残留用户。"""
        org = self._org(status=Organization.Status.SUSPENDED)
        resp = self.client.post(
            self.url, self._payload(organization_id=org.id), format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('organization_id', self._error_details(resp))
        self.assertFalse(User.objects.filter(username='raceuser').exists())

    def test_register_endpoint_is_allow_any(self):
        """确认注册端点确实匿名可打（RegisterView.permission_classes）。"""
        from apps.accounts.api.v1.views import RegisterView
        from rest_framework.permissions import AllowAny

        self.assertEqual(list(RegisterView.permission_classes), [AllowAny])
        self.assertEqual(list(RegisterView.authentication_classes), [])

        # 不带任何凭据，匿名注册成功
        org = self._org()
        resp = self.client.post(
            self.url, self._payload(organization_id=org.id), format='json')
        self.assertEqual(resp.status_code, 201)

    def test_org_deactivated_between_validate_and_create_raises_validation_error(self):
        """★ 真正的回归靶点：validate() 通过后机构被停用，create() 不得抛
        `Organization.DoesNotExist`（那会变成 HTTP 500），而应抛可读的
        `serializers.ValidationError`。"""
        from rest_framework import serializers as drf_serializers

        from apps.accounts.api.v1.serializers import RegisterSerializer

        org = self._org()
        serializer = RegisterSerializer(
            data=self._payload(organization_id=org.id))
        self.assertTrue(serializer.is_valid(), serializer.errors)

        # TOCTOU：validate() 已通过，此刻机构被停用
        Organization.objects.filter(pk=org.pk).update(
            status=Organization.Status.SUSPENDED)

        with self.assertRaises(drf_serializers.ValidationError) as ctx:
            serializer.save()

        self.assertIn('organization_id', ctx.exception.detail)

    def test_org_deactivated_mid_request_does_not_leave_orphan_user(self):
        """竞态失败时不得残留半成品用户（否则匿名可打 ⇒ 脏数据/账号占用）。"""
        from rest_framework import serializers as drf_serializers

        from apps.accounts.api.v1.serializers import RegisterSerializer

        org = self._org()
        serializer = RegisterSerializer(
            data=self._payload(organization_id=org.id))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        Organization.objects.filter(pk=org.pk).update(
            status=Organization.Status.SUSPENDED)

        with self.assertRaises(drf_serializers.ValidationError):
            serializer.save()

        self.assertFalse(
            User.objects.filter(username='raceuser').exists(),
            '竞态失败后残留了孤儿用户，匿名注册路径会堆积脏账号',
        )


class RegisterPasswordPolicyTest(TestCase):
    """AUTH_PASSWORD_VALIDATORS must actually reject weak passwords on the
    registration path (regression guard for the previously-unwired validators)."""

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/auth/register'

    def _payload(self, password):
        return {
            'username': 'pwpolicy',
            'email': 'pwpolicy@example.com',
            'password': password,
            'password_confirm': password,
            'role': 'researcher',
            'organization_choice': 'solo',
        }

    def test_common_password_rejected(self):
        resp = self.client.post(self.url, self._payload('password'), format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertNotEqual(resp.status_code, 201)

    def test_numeric_password_rejected(self):
        resp = self.client.post(self.url, self._payload('12345678'), format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertNotEqual(resp.status_code, 201)

    def test_strong_password_accepted(self):
        resp = self.client.post(
            self.url, self._payload('Str0ng!Pass#2026'), format='json'
        )
        self.assertEqual(resp.status_code, 201)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class EmailVerificationAPITest(TestCase):
    """Registration email verification: register → (no token) → verify → login.

    EMAIL_BACKEND is forced to locmem so we can assert on ``mail.outbox``
    without touching any real mail server.
    """
    def setUp(self):
        self.client = APIClient()
        self.register_url = '/api/v1/auth/register'
        self.verify_url = '/api/v1/auth/verify-email'
        self.resend_url = '/api/v1/auth/resend-verification'
        self.login_url = '/api/v1/auth/login'

    def _register_unverified(self, username='newbie'):
        return self.client.post(self.register_url, {
            'username': username,
            'email': f'{username}@example.com',
            'password': 'testpass123',
            'password_confirm': 'testpass123',
            'role': 'researcher',
            'organization_choice': 'solo',
        }, format='json')

    def test_register_sends_verification_email(self):
        resp = self._register_unverified('newbie')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('verify', mail.outbox[0].body.lower())
        self.assertIn('newbie@example.com', mail.outbox[0].to)

    def test_register_does_not_mint_token(self):
        self._register_unverified('tokenless')
        user = User.objects.get(username='tokenless')
        self.assertFalse(Token.objects.filter(user=user).exists())

    def test_verify_email_success_returns_token_and_verifies(self):
        self._register_unverified('verifyme')
        user = User.objects.get(username='verifyme')
        verification = EmailVerification.objects.get(user=user)
        resp = self.client.get(self.verify_url, {'token': str(verification.token)})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('token', resp.data)
        self.assertTrue(Token.objects.filter(user=user).exists())
        user.refresh_from_db()
        self.assertTrue(user.email_verified)
        # Token is consumed after use.
        self.assertFalse(EmailVerification.objects.filter(user=user).exists())

    def test_verify_email_invalid_token(self):
        resp = self.client.get(self.verify_url, {'token': str(uuid.uuid4())})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('detail', resp.data)

    def test_verify_email_missing_token(self):
        resp = self.client.get(self.verify_url)
        self.assertEqual(resp.status_code, 400)

    def test_verify_email_expired_token(self):
        self._register_unverified('expiredguy')
        user = User.objects.get(username='expiredguy')
        verification = EmailVerification.objects.get(user=user)
        verification.expires_at = timezone.now() - timedelta(hours=1)
        verification.save()
        resp = self.client.get(self.verify_url, {'token': str(verification.token)})
        self.assertEqual(resp.status_code, 400)
        user.refresh_from_db()
        self.assertFalse(user.email_verified)

    def test_resend_verification_sends_email(self):
        self._register_unverified('resendguy')
        mail.outbox.clear()
        resp = self.client.post(
            self.resend_url, {'email': 'resendguy@example.com'}, format='json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        # Resend rewrites a fresh token (still exactly one active record).
        self.assertEqual(
            EmailVerification.objects.filter(user__username='resendguy').count(), 1
        )

    def test_resend_verification_unknown_email_is_safe(self):
        resp = self.client.post(
            self.resend_url, {'email': 'nobody@example.com'}, format='json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_login_blocked_when_unverified(self):
        self._register_unverified('blockedguy')
        resp = self.client.post(self.login_url, {
            'username': 'blockedguy',
            'password': 'testpass123',
        }, format='json')
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(Token.objects.filter(user__username='blockedguy').exists())

    def test_login_allowed_after_verification(self):
        self._register_unverified('laterverified')
        user = User.objects.get(username='laterverified')
        verification = EmailVerification.objects.get(user=user)
        self.client.get(self.verify_url, {'token': str(verification.token)})
        resp = self.client.post(self.login_url, {
            'username': 'laterverified',
            'password': 'testpass123',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('token', resp.data)


class LoginAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/auth/login'
        self.user = UserFactory(username='loginuser')
        self.user.set_password('testpass123')
        self.user.save()

    def test_login_success(self):
        resp = self.client.post(self.url, {
            'username': 'loginuser',
            'password': 'testpass123',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('token', resp.data)
        self.assertIn('user', resp.data)
        self.assertEqual(resp.data['user']['username'], 'loginuser')

    def test_login_invalid_password(self):
        resp = self.client.post(self.url, {
            'username': 'loginuser',
            'password': 'wrongpassword',
        }, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_login_nonexistent_user(self):
        resp = self.client.post(self.url, {
            'username': 'ghost',
            'password': 'testpass123',
        }, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_login_missing_fields(self):
        resp = self.client.post(self.url, {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_login_returns_existing_token(self):
        Token.objects.create(user=self.user)
        resp = self.client.post(self.url, {
            'username': 'loginuser',
            'password': 'testpass123',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        # Token should be reused (get_or_create)
        self.assertEqual(Token.objects.filter(user=self.user).count(), 1)


class LogoutAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/auth/logout'
        self.user = UserFactory()
        self.token = Token.objects.create(user=self.user)

    def test_logout_deletes_token(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Token.objects.filter(user=self.user).exists())

    def test_logout_unauthenticated(self):
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 401)

    def test_logout_no_token_graceful(self):
        """Logout should not fail even if user has no token."""
        self.token.delete()
        # Refresh user from DB to clear cached auth_token relation
        self.user.refresh_from_db()
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, 200)


class MeAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/auth/me'
        self.user = UserFactory(
            username='meuser',
            email='me@example.com',
        )

    def test_me_authenticated(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['username'], 'meuser')
        self.assertEqual(resp.data['email'], 'me@example.com')

    def test_me_unauthenticated(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 401)


class ProfileAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/auth/profile'
        self.user = UserFactory()

    def test_profile_update(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.put(self.url, {
            'nickname': 'TestNick',
            'phone': '1234567890',
            'department': 'Chemistry',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.nickname, 'TestNick')
        self.assertEqual(self.user.phone, '1234567890')

    def test_profile_unauthenticated(self):
        resp = self.client.put(self.url, {}, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_profile_no_changes(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.put(self.url, {}, format='json')
        self.assertEqual(resp.status_code, 200)


class OrganizationSearchAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/organizations'
        self.org = Organization.objects.create(
            name='Alpha Research Lab',
            org_type=Organization.OrgType.ACADEMIC,
            status='active',
            created_by=UserFactory(),
        )

    def test_search_by_name(self):
        resp = self.client.get(self.url, {'q': 'Alpha'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['name'], 'Alpha Research Lab')

    def test_search_by_name_case_insensitive(self):
        resp = self.client.get(self.url, {'q': 'alpha'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_search_no_match(self):
        resp = self.client.get(self.url, {'q': 'Nonexistent'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 0)

    def test_search_empty_query(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_search_max_10_results(self):
        user = UserFactory()
        for i in range(15):
            Organization.objects.create(
                name=f'Test Org {i}',
                org_type=Organization.OrgType.ACADEMIC,
                status='active',
                created_by=user,
            )
        resp = self.client.get(self.url, {'q': 'Test'})
        self.assertEqual(resp.status_code, 200)
        self.assertLessEqual(len(resp.data), 10)


class OrganizationCreateAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/v1/organizations/create'
        self.user = UserFactory()

    def test_create_organization(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.url, {
            'name': 'New Lab',
            'org_type': Organization.OrgType.ACADEMIC,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Organization.objects.count(), 1)
        org = Organization.objects.first()
        self.assertEqual(org.name, 'New Lab')
        self.assertEqual(org.created_by, self.user)

    def test_create_org_auto_joins_creator(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.url, {
            'name': 'Creator Org',
            'org_type': Organization.OrgType.ENTERPRISE,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.user.refresh_from_db()
        self.assertEqual(self.user.organization.name, 'Creator Org')
        self.assertTrue(self.user.is_org_admin)

    def test_create_org_unauthenticated(self):
        resp = self.client.post(self.url, {
            'name': 'Bad Org',
        }, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_create_org_missing_name(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.url, {}, format='json')
        self.assertEqual(resp.status_code, 400)
