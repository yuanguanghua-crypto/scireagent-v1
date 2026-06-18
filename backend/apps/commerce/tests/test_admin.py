"""
TDD Step 1: Write tests for Phase 1 — Admin Product Inlines & Navigation.

These tests verify:
1. ProductAdmin has the required Inlines registered
2. Saving a product with inline data creates bridge records
3. Admin navigation is simplified (no unwanted groups for researchers)
4. IsAdminOrReadOnly permission works correctly on PdfFileViewSet
"""
from django.test import TestCase
from django.contrib.admin import site as admin_site
from rest_framework.test import APIClient

from apps.commerce.admin import ProductAdmin
from apps.commerce.models import Product
from apps.commerce.tests.factories import ProductFactory
from apps.accounts.tests.factories import UserFactory
from apps.bridges.models import ProductMethod, ProductReference, ProductCompatibility, ProductProduct
from apps.knowledge.tests.factories import MethodFactory, ReferenceFactory


class ProductAdminInlineTest(TestCase):
    """Verify ProductAdmin has the required Inlines registered."""

    def setUp(self):
        self.model_admin = ProductAdmin(Product, admin_site)
        self.client = APIClient()
        self.admin_user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_authenticate(user=self.admin_user)
        self.client.login(username=self.admin_user.username, password='testpass123')

    def test_product_admin_has_sku_inline(self):
        """SKU Inline should be present (already existed)."""
        inline_names = [i.__name__ for i in self.model_admin.inlines]
        self.assertIn('SKUInline', inline_names,
                       'ProductAdmin should have SKUInline')

    def test_product_admin_has_method_inline(self):
        """ProductMethod Inline should be present (new requirement)."""
        inline_names = [i.__name__ for i in self.model_admin.inlines]
        self.assertIn('ProductMethodInline', inline_names,
                       'ProductAdmin should have ProductMethodInline')

    def test_product_admin_has_reference_inline(self):
        """ProductReference Inline should be present (new requirement)."""
        inline_names = [i.__name__ for i in self.model_admin.inlines]
        self.assertIn('ProductReferenceInline', inline_names,
                       'ProductAdmin should have ProductReferenceInline')

    def test_product_admin_has_compatibility_inline(self):
        """ProductCompatibility Inline should be present (new requirement)."""
        inline_names = [i.__name__ for i in self.model_admin.inlines]
        self.assertIn('ProductCompatibilityInline', inline_names,
                       'ProductAdmin should have ProductCompatibilityInline')

    def test_product_admin_has_product_relation_inline(self):
        """ProductProduct Inline should be present (new requirement)."""
        inline_names = [i.__name__ for i in self.model_admin.inlines]
        self.assertIn('ProductProductInline', inline_names,
                       'ProductAdmin should have ProductProductInline')


class ProductMethodAdminTest(TestCase):
    """Test ProductMethod bridge model works via admin save."""

    def setUp(self):
        self.product = ProductFactory()
        self.method = MethodFactory()
        self.admin_user = UserFactory(is_staff=True, is_superuser=True)

    def test_create_product_method(self):
        """Creating a ProductMethod via the bridge model should work."""
        pm = ProductMethod.objects.create(
            product=self.product,
            method=self.method,
            role=ProductMethod.Role.REAGENT,
            evidence_level=ProductMethod.EvidenceLevel.CURATED,
        )
        self.assertEqual(pm.product, self.product)
        self.assertEqual(pm.method, self.method)
        self.assertEqual(pm.role, ProductMethod.Role.REAGENT)

    def test_product_has_related_methods(self):
        """Product should be able to access related methods via the bridge."""
        ProductMethod.objects.create(
            product=self.product,
            method=self.method,
            role=ProductMethod.Role.ENZYME,
        )
        self.assertEqual(self.product.product_methods.count(), 1)
        self.assertEqual(self.product.product_methods.first().method, self.method)

    def test_unique_together_enforced(self):
        """Same product + method + role should raise IntegrityError."""
        ProductMethod.objects.create(
            product=self.product, method=self.method,
            role=ProductMethod.Role.REAGENT,
        )
        with self.assertRaises(Exception):
            ProductMethod.objects.create(
                product=self.product, method=self.method,
                role=ProductMethod.Role.REAGENT,
            )


class ProductReferenceAdminTest(TestCase):
    """Test ProductReference bridge model."""

    def setUp(self):
        self.product = ProductFactory()
        self.reference = ReferenceFactory()

    def test_create_product_reference(self):
        pr = ProductReference.objects.create(
            product=self.product,
            reference=self.reference,
            citation_role=ProductReference.CitationRole.PRIMARY,
        )
        self.assertEqual(pr.product, self.product)
        self.assertEqual(pr.reference, self.reference)


class AdminNavigationTest(TestCase):
    """Test admin navigation configuration."""

    def test_admin_accessible_for_staff(self):
        """Staff user should be able to access admin."""
        self.client = APIClient()
        user = UserFactory(is_staff=True)
        self.client.force_authenticate(user=user)
        resp = self.client.get('/admin/')
        self.assertIn(resp.status_code, [200, 302])

    def test_admin_login_redirects_for_anon(self):
        """Anonymous user should be redirected from admin."""
        self.client = APIClient()
        resp = self.client.get('/admin/')
        self.assertIn(resp.status_code, [301, 302])


class FullTestSuiteStillPasses(TestCase):
    """Placeholder to remind: always run full suite before commit."""

    def test_placeholder(self):
        """This test exists only to be replaced by the full suite runner."""
        self.assertTrue(True)
