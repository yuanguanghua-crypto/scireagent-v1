"""P1 核心功能测试：发布自动 SEO。

TDD: 先写测试，再在 ProductCreateUpdateSerializer 中实现。
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.tests.factories import UserFactory
from apps.commerce.tests.factories import ProductFactory, SKUFactory


class PublishAutoSeoTest(TestCase):
    """产品从 draft 变为 active 时，若 SEO 为空则自动生成"""

    def setUp(self):
        self.client = APIClient()
        self.staff = UserFactory(is_staff=True)
        self.client.force_authenticate(user=self.staff)

    def test_publish_auto_fills_empty_seo(self):
        """draft→active: SEO 为空 → 自动生成"""
        product = ProductFactory(
            name='Test Product', catalog_no='SC-AUTO-001', category_l1='Nucleotides',
            cas='1927-31-7', seo_title='', seo_description='', status='draft',
        )
        SKUFactory(product=product, is_default=True)
        resp = self.client.patch(
            f'/api/v1/products/{product.pk}/',
            {'status': 'active'}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        product.refresh_from_db()
        self.assertIn('Test Product', product.seo_title)
        self.assertIn('SciReagent', product.seo_title)
        self.assertNotEqual(product.seo_description, '')

    def test_publish_does_not_overwrite_existing_seo(self):
        """draft→active: SEO 已存在 → 不覆盖"""
        product = ProductFactory(
            name='Test Product', catalog_no='SC-AUTO-002', category_l1='Nucleotides',
            seo_title='Manual Title', seo_description='Manual Desc', status='draft',
        )
        SKUFactory(product=product, is_default=True)
        resp = self.client.patch(
            f'/api/v1/products/{product.pk}/',
            {'status': 'active'}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.seo_title, 'Manual Title')
        self.assertEqual(product.seo_description, 'Manual Desc')

    def test_save_draft_does_not_trigger_seo(self):
        """保存 draft 不变状态 → SEO 不变化"""
        product = ProductFactory(
            name='Test Product', catalog_no='SC-AUTO-003', category_l1='Nucleotides',
            seo_title='', seo_description='', status='draft',
        )
        resp = self.client.patch(
            f'/api/v1/products/{product.pk}/',
            {'name': 'Updated Name'}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.seo_title, '')
        self.assertEqual(product.seo_description, '')
