"""T4-01 ~ T4-07: QuoteRequest model tests"""
from django.test import TestCase
from apps.quotes.models import QuoteRequest, QuoteRequestItem
from apps.commerce.tests.factories import ProductFactory, SKUFactory


class QuoteRequestModelTest(TestCase):
    """T4-01 ~ T4-07"""

    def test_creation(self):
        """T4-01: QuoteRequest creation"""
        qr = QuoteRequest.objects.create(
            contact_name='Dr. Smith',
            contact_email='smith@lab.edu',
            company_name='MIT BioLab',
        )
        self.assertEqual(qr.contact_name, 'Dr. Smith')
        self.assertEqual(qr.contact_email, 'smith@lab.edu')
        self.assertEqual(qr.company_name, 'MIT BioLab')

    def test_default_status(self):
        """T4-02: QuoteRequest default status is 'pending'"""
        qr = QuoteRequest.objects.create(
            contact_name='Dr. Smith',
            contact_email='smith@lab.edu',
        )
        self.assertEqual(qr.status, 'pending')

    def test_item_creation(self):
        """T4-03: QuoteRequestItem creation"""
        product = ProductFactory()
        qr = QuoteRequest.objects.create(
            contact_name='Dr. Smith',
            contact_email='smith@lab.edu',
        )
        item = QuoteRequestItem.objects.create(
            quote_request=qr,
            product=product,
            quantity=5,
        )
        self.assertEqual(item.quantity, 5)

    def test_item_fk_to_product(self):
        """T4-04: QuoteRequestItem FK to product"""
        product = ProductFactory()
        qr = QuoteRequest.objects.create(
            contact_name='Dr. Smith',
            contact_email='smith@lab.edu',
        )
        item = QuoteRequestItem.objects.create(
            quote_request=qr,
            product=product,
            quantity=3,
        )
        self.assertEqual(item.product_id, product.id)

    def test_item_sku_nullable(self):
        """T4-05: QuoteRequestItem FK to sku is nullable"""
        product = ProductFactory()
        qr = QuoteRequest.objects.create(
            contact_name='Dr. Smith',
            contact_email='smith@lab.edu',
        )
        item = QuoteRequestItem.objects.create(
            quote_request=qr,
            product=product,
            quantity=1,
        )
        self.assertIsNone(item.sku)

    def test_cascade_delete(self):
        """T4-06: Deleting QuoteRequest cascades to items"""
        product = ProductFactory()
        qr = QuoteRequest.objects.create(
            contact_name='Dr. Smith',
            contact_email='smith@lab.edu',
        )
        QuoteRequestItem.objects.create(quote_request=qr, product=product, quantity=2)
        QuoteRequestItem.objects.create(quote_request=qr, product=product, quantity=3)
        self.assertEqual(QuoteRequestItem.objects.count(), 2)
        qr.delete()
        self.assertEqual(QuoteRequestItem.objects.count(), 0)

    def test_ordering_newest_first(self):
        """T4-07: QuoteRequest ordering — newest first"""
        qr1 = QuoteRequest.objects.create(
            contact_name='First', contact_email='first@lab.edu',
        )
        qr2 = QuoteRequest.objects.create(
            contact_name='Second', contact_email='second@lab.edu',
        )
        qrs = list(QuoteRequest.objects.all())
        self.assertEqual(qrs[0].id, qr2.id)
        self.assertEqual(qrs[1].id, qr1.id)
