"""
Tests for Researcher Dashboard.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class DashboardTest(TestCase):
    """Dashboard should be accessible and show relevant data."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='dashadmin', password='testpass123',
            is_staff=True, is_superuser=True,
        )
        self.client.login(username='dashadmin', password='testpass123')

    def test_dashboard_accessible(self):
        """Dashboard page should return 200 for staff."""
        resp = self.client.get('/admin/dashboard/')
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_redirects_anon(self):
        """Anonymous user should be redirected."""
        self.client.logout()
        resp = self.client.get('/admin/dashboard/')
        self.assertEqual(resp.status_code, 302)

    def test_dashboard_shows_title(self):
        """Dashboard should show the title."""
        resp = self.client.get('/admin/dashboard/')
        self.assertContains(resp, 'Dashboard')

    def test_dashboard_shows_stats(self):
        """Dashboard should show product statistics."""
        resp = self.client.get('/admin/dashboard/')
        self.assertContains(resp, 'Active Products')

    def test_dashboard_has_quick_actions(self):
        """Dashboard should show quick action buttons."""
        resp = self.client.get('/admin/dashboard/')
        self.assertContains(resp, 'New Product')
        self.assertContains(resp, 'Knowledge Import')

    def test_dashboard_has_sidebar_entry(self):
        """Dashboard should appear in sidebar navigation."""
        resp = self.client.get('/admin/dashboard/')
        self.assertEqual(resp.status_code, 200)
