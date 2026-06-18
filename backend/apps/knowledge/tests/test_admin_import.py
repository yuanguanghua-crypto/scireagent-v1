"""
Tests for the Knowledge Import admin view.
"""
import json
from io import BytesIO
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse

from apps.accounts.tests.factories import UserFactory


SAMPLE_JSON = {
    'metadata': {'version': '3.0', 'description': 'Test import'},
    'ResearchGoal': [
        {'id': 'goal_001', 'name': 'RNA Labeling', 'summary': 'Test'},
    ],
    'Application': [],
    'Method': [],
    'Protocol': [],
    'Product': [],
    'SKU': [],
}


class ImportAdminViewTest(TestCase):
    """Admin import page should be accessible and functional."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(
            username='testadmin', password='testpass123',
            is_staff=True, is_superuser=True,
        )
        self.client.login(username='testadmin', password='testpass123')

    def test_user_is_staff(self):
        """Verify the test user can access admin."""
        self.assertTrue(self.user.is_staff)
        self.assertTrue(self.user.is_superuser)
        # Try accessing the admin index
        resp = self.client.get('/admin/')
        self.assertEqual(resp.status_code, 200)

    def test_import_page_accessible(self):
        """Import page should return 200 for staff."""
        resp = self.client.get('/admin/knowledge-import/')
        self.assertEqual(resp.status_code, 200, msg=f'Status {resp.status_code}, redirect to {resp.get("Location","")}')

    def test_import_page_redirects_anon(self):
        """Anonymous user should be redirected."""
        self.client.logout()
        resp = self.client.get('/admin/knowledge-import/')
        self.assertEqual(resp.status_code, 302)

    def test_upload_valid_json(self):
        """Uploading valid JSON should show preview."""
        file_data = BytesIO(json.dumps(SAMPLE_JSON).encode('utf-8'))
        file_data.name = 'test.json'
        resp = self.client.post('/admin/knowledge-import/', {
            'action': 'upload',
            'json_file': file_data,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'RNA Labeling')
        self.assertContains(resp, 'Goal')  # preview should list entity types

    def test_upload_invalid_json(self):
        """Uploading invalid JSON should show error."""
        file_data = BytesIO(b'not json')
        file_data.name = 'bad.json'
        resp = self.client.post('/admin/knowledge-import/', {
            'action': 'upload',
            'json_file': file_data,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Invalid JSON')

    def test_upload_no_file(self):
        """POST without file should show error."""
        resp = self.client.post('/admin/knowledge-import/', {
            'action': 'upload',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'select')

    def test_import_executes(self):
        """Import action should process validated data."""
        file_data = BytesIO(json.dumps(SAMPLE_JSON).encode('utf-8'))
        file_data.name = 'test.json'
        self.client.post('/admin/knowledge-import/', {
            'action': 'upload',
            'json_file': file_data,
        })
        resp = self.client.post('/admin/knowledge-import/', {
            'action': 'import',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Import Complete')

    def test_import_no_session_data(self):
        """Import without prior upload should show error."""
        resp = self.client.post('/admin/knowledge-import/', {
            'action': 'import',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'No validated data')
