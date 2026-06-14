"""Phase 1 TDD: ProductDocument tests (TC-D-001 ~ TC-D-009)"""
from django.test import TestCase
from apps.commerce.models import ProductDocument
from apps.commerce.tests.factories import ProductFactory, ProductDocumentFactory


class ProductDocumentTest(TestCase):
    def test_create_document(self):
        """TC-D-001: Create document linked to Product"""
        product = ProductFactory()
        doc = ProductDocumentFactory(product=product)
        self.assertEqual(doc.product_id, product.id)

    def test_document_type_datasheet(self):
        """TC-D-002: type DATASHEET"""
        doc = ProductDocumentFactory(document_type='datasheet')
        self.assertEqual(doc.document_type, 'datasheet')

    def test_document_type_msds(self):
        """TC-D-003: type MSDS"""
        doc = ProductDocumentFactory(document_type='msds')
        self.assertEqual(doc.document_type, 'msds')

    def test_document_type_coa(self):
        """TC-D-004: type COA"""
        doc = ProductDocumentFactory(document_type='coa')
        self.assertEqual(doc.document_type, 'coa')

    def test_document_type_application_note(self):
        """TC-D-005: type APPLICATION_NOTE"""
        doc = ProductDocumentFactory(document_type='application_note')
        self.assertEqual(doc.document_type, 'application_note')

    def test_language_default_en(self):
        """TC-D-006: language defaults to 'en'"""
        doc = ProductDocumentFactory()
        self.assertEqual(doc.language, 'en')

    def test_version_default_1(self):
        """TC-D-007: version defaults to '1.0'"""
        doc = ProductDocumentFactory()
        self.assertEqual(doc.version, '1.0')

    def test_original_filename_storage(self):
        """TC-D-008: original_filename stores value"""
        doc = ProductDocumentFactory(original_filename='datasheet.pdf')
        self.assertEqual(doc.original_filename, 'datasheet.pdf')

    def test_delete_document_not_affect_product(self):
        """TC-D-009: Deleting document does not affect Product"""
        product = ProductFactory()
        doc = ProductDocumentFactory(product=product)
        doc_id = doc.id
        doc.delete()
        self.assertFalse(ProductDocument.objects.filter(id=doc_id).exists())
        self.assertTrue(product.__class__.objects.filter(id=product.id).exists())

    def test_product_has_documents_relation(self):
        """TC-D-010: Product can access related documents"""
        product = ProductFactory()
        ProductDocumentFactory(product=product, original_filename='a.pdf')
        ProductDocumentFactory(product=product, original_filename='b.pdf')
        self.assertEqual(product.documents.count(), 2)

    def test_str_representation(self):
        """TC-D-011: __str__ shows product name + document type"""
        product = ProductFactory(name='Cy3-NHS')
        doc = ProductDocumentFactory(product=product, document_type='datasheet')
        self.assertIn('Cy3-NHS', str(doc))
        self.assertIn('datasheet', str(doc))
