"""SEO 自动生成服务测试。

TDD: 先写测试，再实现功能。
"""
from django.test import TestCase

from apps.commerce.services.seo_generator import generate_seo
from apps.commerce.tests.factories import ProductFactory


class SeoGeneratorTest(TestCase):
    """SEO 自动生成 service 单元测试"""

    def test_generate_seo_with_cas(self):
        """有 CAS → SEO 描述包含 CAS 号"""
        product = ProductFactory(
            name='dATP (100mM)',
            cas='1927-31-7',
            seo_title='',
            seo_description='',
        )
        product, changed = generate_seo(product)
        self.assertTrue(changed)
        self.assertEqual(product.seo_title, 'dATP (100mM) | SciReagent')
        self.assertIn('(CAS: 1927-31-7)', product.seo_description)
        self.assertIn('Buy dATP (100mM)', product.seo_description)

    def test_generate_seo_without_cas(self):
        """无 CAS → 描述不包含 CAS 号"""
        product = ProductFactory(
            name='Biotin-11-CTP',
            cas='',
            seo_title='',
            seo_description='',
        )
        product, changed = generate_seo(product)
        self.assertTrue(changed)
        self.assertEqual(product.seo_title, 'Biotin-11-CTP | SciReagent')
        self.assertNotIn('(CAS:', product.seo_description)

    def test_generate_seo_does_not_overwrite_existing_seo_title(self):
        """已有 SEO 标题 → 不覆盖"""
        product = ProductFactory(
            name='Cy3-dUTP',
            seo_title='Custom SEO Title',
            seo_description='',
        )
        product, changed = generate_seo(product)
        self.assertTrue(changed)  # description changed
        self.assertEqual(product.seo_title, 'Custom SEO Title')

    def test_generate_seo_does_not_overwrite_existing_seo_description(self):
        """已有 SEO 描述 → 不覆盖"""
        product = ProductFactory(
            name='Cy5-dUTP',
            seo_title='',
            seo_description='Custom description',
        )
        product, changed = generate_seo(product)
        self.assertTrue(changed)  # title changed
        self.assertEqual(product.seo_description, 'Custom description')

    def test_generate_seo_no_change_when_both_exist(self):
        """两个 SEO 字段都已存在 → 不修改"""
        product = ProductFactory(
            name='Test Product',
            seo_title='Already Set',
            seo_description='Already described',
        )
        product, changed = generate_seo(product)
        self.assertFalse(changed)
        self.assertEqual(product.seo_title, 'Already Set')
        self.assertEqual(product.seo_description, 'Already described')
