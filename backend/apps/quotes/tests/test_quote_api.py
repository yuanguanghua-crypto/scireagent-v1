"""
TDD Sprint 2.1: Quote Request API
Tests for quote request API endpoint.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.commerce.tests.factories import ProductFactory
from apps.quotes.models import QuoteRequest, QuoteRequestItem


class QuoteRequestAPITest(TestCase):
    """Test Quote Request API endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.product = ProductFactory(
            name="2'-Azido-dATP",
            catalog_no="SC8047",
            status='active',
        )

    def test_create_quote_request_anonymous(self):
        """Anonymous users should be able to create quote requests."""
        response = self.client.post('/api/v1/quote-requests/', {
            'contact_name': 'John Doe',
            'contact_email': 'john@example.com',
            'items': [{'product_id': self.product.id, 'quantity': 2}],
        }, format='json')

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['contact_name'], 'John Doe')
        self.assertEqual(data['data']['status'], 'pending')

    def test_create_quote_request_with_items(self):
        """Quote request should include items."""
        response = self.client.post('/api/v1/quote-requests/', {
            'contact_name': 'Jane Doe',
            'contact_email': 'jane@example.com',
            'items': [
                {'product_id': self.product.id, 'quantity': 3},
            ],
        }, format='json')

        self.assertEqual(response.status_code, 201)
        data = response.json()
        items = data['data']['items']
        self.assertGreaterEqual(len(items), 1)

    def test_create_quote_request_validates_email(self):
        """Quote request should validate email format."""
        response = self.client.post('/api/v1/quote-requests/', {
            'contact_name': 'Test User',
            'contact_email': 'invalid-email',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        }, format='json')

        self.assertEqual(response.status_code, 400)

    def test_create_quote_request_validates_items(self):
        """Quote request should require at least one item."""
        response = self.client.post('/api/v1/quote-requests/', {
            'contact_name': 'Test User',
            'contact_email': 'test@example.com',
            'items': [],
        }, format='json')

        self.assertEqual(response.status_code, 400)

    def test_create_quote_request_requires_contact_name(self):
        """Quote request should require contact_name."""
        response = self.client.post('/api/v1/quote-requests/', {
            'contact_email': 'test@example.com',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        }, format='json')

        self.assertEqual(response.status_code, 400)

    def test_create_quote_request_requires_contact_email(self):
        """Quote request should require contact_email."""
        response = self.client.post('/api/v1/quote-requests/', {
            'contact_name': 'Test User',
            'items': [{'product_id': self.product.id, 'quantity': 1}],
        }, format='json')

        self.assertEqual(response.status_code, 400)

    def test_quote_request_saved_to_database(self):
        """Quote request should be saved to database."""
        self.client.post('/api/v1/quote-requests/', {
            'contact_name': 'DB Test',
            'contact_email': 'db@example.com',
            'items': [{'product_id': self.product.id, 'quantity': 5}],
        }, format='json')

        self.assertEqual(QuoteRequest.objects.count(), 1)
        qr = QuoteRequest.objects.first()
        self.assertEqual(qr.contact_name, 'DB Test')
        self.assertEqual(qr.items.count(), 1)

    def test_quote_request_item_quantity(self):
        """Quote request item should have correct quantity."""
        self.client.post('/api/v1/quote-requests/', {
            'contact_name': 'Qty Test',
            'contact_email': 'qty@example.com',
            'items': [{'product_id': self.product.id, 'quantity': 7}],
        }, format='json')

        item = QuoteRequestItem.objects.first()
        self.assertEqual(item.quantity, 7)
