"""T5-01 ~ T5-09: PostgreSQL FTS model tests"""
import os
from unittest import skipUnless, skipIf
from django.test import TestCase

_USE_POSTGRES = os.getenv('DB_ENGINE', 'postgres') != 'sqlite'


@skipIf(not _USE_POSTGRES, 'PostgreSQL FTS requires PostgreSQL backend (set DB_ENGINE=postgres)')
class FTSSearchVectorFieldTest(TestCase):
    """T5-01 ~ T5-05: SearchVector field existence"""

    def test_product_has_search_vector(self):
        """T5-01"""
        from apps.commerce.models import Product
        field_names = [f.name for f in Product._meta.get_fields()]
        self.assertIn('search_vector', field_names)

    def test_application_has_search_vector(self):
        """T5-02"""
        from apps.knowledge.models import Application
        field_names = [f.name for f in Application._meta.get_fields()]
        self.assertIn('search_vector', field_names)

    def test_method_has_search_vector(self):
        """T5-03"""
        from apps.knowledge.models import Method
        field_names = [f.name for f in Method._meta.get_fields()]
        self.assertIn('search_vector', field_names)

    def test_protocol_has_search_vector(self):
        """T5-04"""
        from apps.knowledge.models import Protocol
        field_names = [f.name for f in Protocol._meta.get_fields()]
        self.assertIn('search_vector', field_names)

    def test_reference_has_search_vector(self):
        """T5-05"""
        from apps.knowledge.models import Reference
        field_names = [f.name for f in Reference._meta.get_fields()]
        self.assertIn('search_vector', field_names)


@skipIf(not _USE_POSTGRES, 'PostgreSQL FTS requires PostgreSQL backend')
class FTSQueryTest(TestCase):
    """T5-06 ~ T5-09: FTS query tests"""

    def test_product_search_vector_populated(self):
        """T5-06"""
        from apps.commerce.models import Product
        p = Product.objects.create(name='RNA Labeling Kit', cas='12345-67-8')
        self.assertIsNotNone(p.search_vector)

    def test_fts_finds_by_name(self):
        """T5-07"""
        from apps.commerce.models import Product
        from django.contrib.postgres.search import SearchQuery
        Product.objects.create(name='RNA Labeling Kit', cas='12345-67-8')
        Product.objects.create(name='Click Chemistry Reagent', cas='99999-00-0')
        results = Product.objects.filter(search_vector=SearchQuery('rna'))
        self.assertEqual(results.count(), 1)

    def test_fts_finds_by_cas(self):
        """T5-08"""
        from apps.commerce.models import Product
        from django.contrib.postgres.search import SearchQuery
        Product.objects.create(name='RNA Kit', cas='12345-67-8')
        results = Product.objects.filter(search_vector=SearchQuery('12345-67-8'))
        self.assertEqual(results.count(), 1)

    def test_fts_rank_order(self):
        """T5-09"""
        from apps.commerce.models import Product
        from django.contrib.postgres.search import SearchQuery, SearchRank
        Product.objects.create(name='RNA Labeling Kit', cas='11111-11-1')
        Product.objects.create(name='Advanced RNA Extraction', cas='22222-22-2')
        results = Product.objects.annotate(
            rank=SearchRank('search_vector', SearchQuery('rna'))
        ).filter(search_vector=SearchQuery('rna')).order_by('-rank')
        self.assertTrue(results[0].rank >= results[1].rank)


class FTSFieldDeclarationTest(TestCase):
    """T5-01~05 cross-check: SearchVectorField is declared in model source code.
    This runs on both SQLite and PostgreSQL — verifies the field exists in the model class
    when PostgreSQL mode is active."""

    def test_product_search_vector_declared(self):
        """T5-01: Product model declares search_vector (SearchVectorField when PG, absent on SQLite)"""
        from apps.commerce.models import Product
        if _USE_POSTGRES:
            from django.contrib.postgres.search import SearchVectorField
            field = Product._meta.get_field('search_vector')
            self.assertIsInstance(field, SearchVectorField)
        else:
            # SQLite: field should not exist on model
            with self.assertRaises(Exception):
                Product._meta.get_field('search_vector')

    def test_application_search_vector_declared(self):
        """T5-02"""
        from apps.knowledge.models import Application
        if _USE_POSTGRES:
            from django.contrib.postgres.search import SearchVectorField
            field = Application._meta.get_field('search_vector')
            self.assertIsInstance(field, SearchVectorField)
        else:
            with self.assertRaises(Exception):
                Application._meta.get_field('search_vector')

    def test_method_search_vector_declared(self):
        """T5-03"""
        from apps.knowledge.models import Method
        if _USE_POSTGRES:
            from django.contrib.postgres.search import SearchVectorField
            field = Method._meta.get_field('search_vector')
            self.assertIsInstance(field, SearchVectorField)
        else:
            with self.assertRaises(Exception):
                Method._meta.get_field('search_vector')

    def test_protocol_search_vector_declared(self):
        """T5-04"""
        from apps.knowledge.models import Protocol
        if _USE_POSTGRES:
            from django.contrib.postgres.search import SearchVectorField
            field = Protocol._meta.get_field('search_vector')
            self.assertIsInstance(field, SearchVectorField)
        else:
            with self.assertRaises(Exception):
                Protocol._meta.get_field('search_vector')

    def test_reference_search_vector_declared(self):
        """T5-05"""
        from apps.knowledge.models import Reference
        if _USE_POSTGRES:
            from django.contrib.postgres.search import SearchVectorField
            field = Reference._meta.get_field('search_vector')
            self.assertIsInstance(field, SearchVectorField)
        else:
            with self.assertRaises(Exception):
                Reference._meta.get_field('search_vector')
