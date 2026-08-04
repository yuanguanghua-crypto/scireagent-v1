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
        org = Organization.objects.create(
            name='Test Org',
            org_type=Organization.OrgType.ACADEMIC,
            created_by=UserFactory(),
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
