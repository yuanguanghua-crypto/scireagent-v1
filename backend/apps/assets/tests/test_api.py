"""
Tests for assets app — PdfFileViewSet CRUD.
"""
from django.test import TestCase
from rest_framework.test import APIClient
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.tests.factories import UserFactory
from apps.assets.models import PdfFile
from apps.assets.tests.factories import PdfFileFactory


class PdfFileAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.list_url = '/api/v1/pdf-files/'
        # Use a staff user for write operations (IsAdminOrReadOnly)
        self.admin = UserFactory(is_staff=True)
        self.user = UserFactory()

    def _make_pdf_file(self, name='test.pdf'):
        """Create a simple in-memory file for upload testing."""
        return SimpleUploadedFile(
            name=name,
            content=b'%PDF-1.4 fake pdf content for testing',
            content_type='application/pdf',
        )

    # ── List ──

    def test_list_empty(self):
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, 200)

    def test_list_with_data(self):
        PdfFileFactory.create_batch(3)
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 3)

    def test_list_pagination(self):
        PdfFileFactory.create_batch(3)
        resp = self.client.get(self.list_url)
        self.assertIn('results', resp.data)
        self.assertIn('count', resp.data)

    # ── Create ──

    def test_create_requires_staff(self):
        """PdfFile creation requires admin (IsAdminOrReadOnly)."""
        self.client.force_authenticate(user=self.user)
        resp = self.client.post(self.list_url, {
            'file': self._make_pdf_file(),
        }, format='multipart')
        self.assertEqual(resp.status_code, 403)

    def test_create_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.list_url, {
            'file': self._make_pdf_file(),
        }, format='multipart')
        self.assertEqual(resp.status_code, 201)

    def test_create_without_file(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(self.list_url, {}, format='multipart')
        self.assertEqual(resp.status_code, 400)

    # ── Retrieve ──

    def test_retrieve(self):
        pdf = PdfFileFactory()
        resp = self.client.get(f'{self.list_url}{pdf.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('id', resp.data)
        self.assertEqual(resp.data['id'], pdf.id)

    def test_retrieve_not_found(self):
        resp = self.client.get(f'{self.list_url}99999/')
        self.assertEqual(resp.status_code, 404)

    # ── Update ──

    def test_update_requires_staff(self):
        self.client.force_authenticate(user=self.user)
        pdf = PdfFileFactory()
        resp = self.client.patch(
            f'{self.list_url}{pdf.id}/',
            {'page_count': 42},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_update_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        pdf = PdfFileFactory()
        resp = self.client.patch(
            f'{self.list_url}{pdf.id}/',
            {'page_count': 42},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        pdf.refresh_from_db()
        self.assertEqual(pdf.page_count, 42)

    # ── Delete ──

    def test_delete_requires_staff(self):
        self.client.force_authenticate(user=self.user)
        pdf = PdfFileFactory()
        resp = self.client.delete(f'{self.list_url}{pdf.id}/')
        self.assertEqual(resp.status_code, 403)

    def test_delete_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        pdf = PdfFileFactory()
        resp = self.client.delete(f'{self.list_url}{pdf.id}/')
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(PdfFile.objects.filter(id=pdf.id).exists())

    # ── Unauthenticated access ──

    def test_list_public(self):
        """List is read-only public (IsAdminOrReadOnly)."""
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, 200)

    def test_retrieve_public(self):
        pdf = PdfFileFactory()
        resp = self.client.get(f'{self.list_url}{pdf.id}/')
        self.assertEqual(resp.status_code, 200)

    def test_create_unauthenticated(self):
        resp = self.client.post(self.list_url, {
            'file': self._make_pdf_file(),
        }, format='multipart')
        self.assertEqual(resp.status_code, 401)

    def test_delete_unauthenticated(self):
        pdf = PdfFileFactory()
        resp = self.client.delete(f'{self.list_url}{pdf.id}/')
        self.assertEqual(resp.status_code, 401)
