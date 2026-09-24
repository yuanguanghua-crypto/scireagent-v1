"""★ 主数据端点权限显式化回归（2026-09-24，③ 批）。

这 5 个 view 此前**未声明** `permission_classes` ⇒ 落到 DRF 默认 `AllowAny`
（项目未设 `DEFAULT_PERMISSION_CLASSES`）⇒ 匿名可读写。现统一补 `IsAdminOrReadOnly`：

    SKUViewSet · ProductClassViewSet · CatalogGroupViewSet
    ProductDocumentViewSet · ProductDetailAPIView

口径 = **读全部放开（SAFE_METHODS），写仅 staff** —— 与 `ProductViewSet` 一致。
其中 `ProductDocumentViewSet` 的 `DELETE /api/v1/documents/{id}/` 是**不可逆写**，此前匿名可用，
是本批里风险最高的一条。

本文件锁住三件事：① 匿名写被拒；② 匿名读不受影响；③ staff 写仍然可用（不是把口子全焊死）。
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.models import ProductDocument
from apps.commerce.tests.factories import (
    CatalogGroupFactory, ProductClassFactory, ProductDocumentFactory,
    ProductFactory, SKUFactory,
)


class AnonymousWriteDeniedTest(TestCase):
    """匿名写一律 401。"""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=None)

    def test_anon_post_sku_denied(self):
        product = ProductFactory()
        resp = self.client.post('/api/v1/skus/', {
            'product_id': product.id, 'sku_code': 'SKU-ANON-1',
            'pack_size': '100mg', 'price': '9.99',
        }, format='json')
        self.assertEqual(resp.status_code, 401, resp.content[:300])

    def test_anon_delete_document_denied_and_row_survives(self):
        """不可逆写：既要 401，也要确认行还在（防止"拦了但已删"）。"""
        doc = ProductDocumentFactory()
        resp = self.client.delete(f'/api/v1/documents/{doc.id}/')
        self.assertEqual(resp.status_code, 401, resp.content[:300])
        self.assertTrue(ProductDocument.objects.filter(id=doc.id).exists())

    def test_anon_post_document_denied(self):
        product = ProductFactory()
        resp = self.client.post('/api/v1/documents/', {
            'product_id': product.id, 'document_type': 'datasheet',
            'original_filename': 'x.pdf',
        }, format='json')
        self.assertEqual(resp.status_code, 401, resp.content[:300])


class AnonymousReadAllowedTest(TestCase):
    """读必须保持放开 —— 收紧只针对写。"""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=None)

    def test_anon_get_sku_list_200(self):
        SKUFactory()
        self.assertEqual(self.client.get('/api/v1/skus/').status_code, 200)

    def test_anon_get_product_classes_200(self):
        ProductClassFactory()
        self.assertEqual(self.client.get('/api/v1/product-classes/').status_code, 200)

    def test_anon_get_catalog_groups_200(self):
        CatalogGroupFactory()
        self.assertEqual(self.client.get('/api/v1/catalog-groups/').status_code, 200)

    def test_anon_get_product_detail_200(self):
        product = ProductFactory()
        self.assertEqual(
            self.client.get(f'/api/v1/products/{product.id}/detail/').status_code, 200
        )


class StaffWriteAllowedTest(TestCase):
    """收紧不得把写口焊死：staff 仍可写。"""

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.client.force_authenticate(user=self.staff)

    def test_staff_delete_document_204(self):
        doc = ProductDocumentFactory()
        resp = self.client.delete(f'/api/v1/documents/{doc.id}/')
        self.assertIn(resp.status_code, (200, 204), resp.content[:300])
        self.assertFalse(ProductDocument.objects.filter(id=doc.id).exists())


class NonStaffWriteDeniedTest(TestCase):
    """登录但非 staff：读可以，写仍拒。"""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=UserFactory(is_staff=False))

    def test_non_staff_read_ok(self):
        SKUFactory()
        self.assertEqual(self.client.get('/api/v1/skus/').status_code, 200)

    def test_non_staff_delete_document_denied(self):
        doc = ProductDocumentFactory()
        resp = self.client.delete(f'/api/v1/documents/{doc.id}/')
        self.assertIn(resp.status_code, (401, 403), resp.content[:300])
        self.assertTrue(ProductDocument.objects.filter(id=doc.id).exists())
