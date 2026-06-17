"""
Tests for accounts app — RegisterView, LoginView, LogoutView, MeView, ProfileView,
OrganizationSearchView, OrganizationCreateView.
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from apps.accounts.tests.factories import UserFactory
from apps.accounts.models import Organization, User


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
        self.assertIn('token', resp.data)
        self.assertIn('user', resp.data)
        self.assertEqual(resp.data['user']['username'], 'newuser')
        self.assertTrue(User.objects.filter(username='newuser').exists())
        user = User.objects.get(username='newuser')
        self.assertIsNotNone(user.organization)
        self.assertTrue(user.is_org_admin)

    def test_register_creates_token(self):
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
        self.assertTrue(Token.objects.filter(user=user).exists())

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
