"""T4-08 ~ T4-15: QuoteRequest API tests"""
from django.test import TestCase
from rest_framework.test import APIClient
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.accounts.tests.factories import UserFactory


class QuoteRequestAPICreateTest(TestCase):
    """T4-08 ~ T4-15"""

    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory()
        self.valid_payload = {
            'contact_name': 'Dr. Smith',
            'contact_email': 'smith@lab.edu',
            'company_name': 'MIT BioLab',
            'items': [
                {'product_id': self.product.id, 'quantity': 5},
            ],
        }

    def test_create(self):
        """T4-08: POST creates quote request → 201"""
        resp = self.client.post(
            '/api/v1/quote-requests/',
            self.valid_payload,
            format='json',
        )
        self.assertEqual(resp.status_code, 201)

    def test_create_with_items(self):
        """T4-09: Created quote request has correct item count"""
        resp = self.client.post(
            '/api/v1/quote-requests/',
            self.valid_payload,
            format='json',
        )
        data = resp.json()
        self.assertEqual(len(data['data']['items']), 1)

    def test_create_empty_items_validation(self):
        """T4-10: Empty items → 400"""
        payload = {**self.valid_payload, 'items': []}
        resp = self.client.post(
            '/api/v1/quote-requests/',
            payload,
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_invalid_email_validation(self):
        """T4-11: Invalid email → 400"""
        payload = {**self.valid_payload, 'contact_email': 'not-an-email'}
        resp = self.client.post(
            '/api/v1/quote-requests/',
            payload,
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_retrieve(self):
        """T4-12: GET retrieves quote request → 200 (requires auth)"""
        create_resp = self.client.post(
            '/api/v1/quote-requests/',
            self.valid_payload,
            format='json',
        )
        qr_id = create_resp.json()['data']['id']

        # Login as user with matching email
        user = UserFactory(email='smith@lab.edu')
        self.client.force_authenticate(user=user)

        resp = self.client.get(f'/api/v1/quote-requests/{qr_id}/')
        self.assertEqual(resp.status_code, 200)

    def test_retrieve_includes_items(self):
        """T4-13: Retrieved quote request includes items list (requires auth)"""
        create_resp = self.client.post(
            '/api/v1/quote-requests/',
            self.valid_payload,
            format='json',
        )
        qr_id = create_resp.json()['data']['id']

        # Login as user with matching email
        user = UserFactory(email='smith@lab.edu')
        self.client.force_authenticate(user=user)

        resp = self.client.get(f'/api/v1/quote-requests/{qr_id}/')
        data = resp.json()
        self.assertIsInstance(data['data']['items'], list)
        self.assertEqual(len(data['data']['items']), 1)

    def test_no_auth_required(self):
        """T4-14: Anonymous user can create quote request → 201"""
        # No authentication — anonymous
        resp = self.client.post(
            '/api/v1/quote-requests/',
            self.valid_payload,
            format='json',
        )
        self.assertEqual(resp.status_code, 201)

    def test_envelope_format(self):
        """T4-15: Response uses Envelope format {success, data, meta}"""
        resp = self.client.post(
            '/api/v1/quote-requests/',
            self.valid_payload,
            format='json',
        )
        data = resp.json()
        self.assertIn('success', data)
        self.assertTrue(data['success'])
        self.assertIn('data', data)
        self.assertIn('meta', data)
