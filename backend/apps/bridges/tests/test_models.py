from django.test import TestCase
from django.db import IntegrityError
from apps.bridges.models import (
    ProductMethod, MethodProtocol, ProductReference, ProductCompatibility, ProductProduct
)
from apps.bridges.tests.factories import (
    ProductMethodFactory, MethodProtocolFactory, ProductReferenceFactory,
    ProductCompatibilityFactory, ProductProductFactory
)
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.tests.factories import MethodFactory, ProtocolFactory


class ProductMethodModelTest(TestCase):
    def test_create(self):
        pm = ProductMethodFactory(role='reagent', evidence_level='high')
        self.assertEqual(pm.role, 'reagent')
        self.assertEqual(pm.evidence_level, 'high')

    def test_unique_together(self):
        product = ProductFactory()
        method = MethodFactory()
        ProductMethodFactory(product=product, method=method, role='reagent')
        with self.assertRaises(IntegrityError):
            ProductMethodFactory(product=product, method=method, role='reagent')

    def test_same_product_different_role_allowed(self):
        product = ProductFactory()
        method = MethodFactory()
        pm1 = ProductMethodFactory(product=product, method=method, role='reagent')
        pm2 = ProductMethodFactory(product=product, method=method, role='enzyme')
        self.assertNotEqual(pm1.id, pm2.id)

    def test_role_choices(self):
        choices = dict(ProductMethod.Role.choices)
        self.assertIn('reagent', choices)
        self.assertIn('buffer', choices)
        self.assertIn('control', choices)
        self.assertIn('enzyme', choices)
        self.assertIn('label', choices)
        self.assertIn('solvent', choices)
        self.assertIn('other', choices)

    def test_evidence_level_choices(self):
        choices = dict(ProductMethod.EvidenceLevel.choices)
        self.assertIn('low', choices)
        self.assertIn('medium', choices)
        self.assertIn('high', choices)
        self.assertIn('curated', choices)

    def test_role_default(self):
        pm = ProductMethodFactory()
        self.assertEqual(pm.role, 'reagent')

    def test_evidence_level_default(self):
        pm = ProductMethodFactory()
        self.assertEqual(pm.evidence_level, 'medium')

    def test_display_order_default(self):
        pm = ProductMethodFactory()
        self.assertEqual(pm.display_order, 0)

    def test_str(self):
        pm = ProductMethodFactory(role='enzyme')
        result = str(pm)
        self.assertIn('enzyme', result)

    def test_related_name_product(self):
        product = ProductFactory()
        ProductMethodFactory(product=product)
        ProductMethodFactory(product=product)
        self.assertEqual(product.product_methods.count(), 2)

    def test_related_name_method(self):
        method = MethodFactory()
        ProductMethodFactory(method=method)
        ProductMethodFactory(method=method)
        self.assertEqual(method.product_methods.count(), 2)

    def test_order_index_exists(self):
        indexes = ProductMethod._meta.indexes
        order_indexes = [i for i in indexes if i.name == 'product_method_order_idx']
        self.assertEqual(len(order_indexes), 1)

    def test_table_name(self):
        self.assertEqual(ProductMethod._meta.db_table, 'product_method')


class MethodProtocolModelTest(TestCase):
    def test_create(self):
        mp = MethodProtocolFactory(featured=True)
        self.assertTrue(mp.featured)

    def test_unique_together(self):
        method = MethodFactory()
        protocol = ProtocolFactory(method=method)
        MethodProtocolFactory(method=method, protocol=protocol)
        with self.assertRaises(IntegrityError):
            MethodProtocolFactory(method=method, protocol=protocol)

    def test_featured_default(self):
        mp = MethodProtocolFactory()
        self.assertFalse(mp.featured)

    def test_status_default(self):
        mp = MethodProtocolFactory()
        self.assertEqual(mp.status, 'active')

    def test_display_order_default(self):
        mp = MethodProtocolFactory()
        self.assertEqual(mp.display_order, 0)

    def test_str(self):
        mp = MethodProtocolFactory()
        result = str(mp)
        self.assertIn('->', result)

    def test_related_name_method(self):
        method = MethodFactory()
        MethodProtocolFactory(method=method)
        self.assertEqual(method.method_protocols.count(), 1)

    def test_related_name_protocol(self):
        protocol = ProtocolFactory()
        MethodProtocolFactory(protocol=protocol)
        self.assertEqual(protocol.method_protocols.count(), 1)

    def test_order_index_exists(self):
        indexes = MethodProtocol._meta.indexes
        order_indexes = [i for i in indexes if i.name == 'method_protocol_order_idx']
        self.assertEqual(len(order_indexes), 1)

    def test_table_name(self):
        self.assertEqual(MethodProtocol._meta.db_table, 'method_protocol')


class ProductReferenceModelTest(TestCase):
    def test_create(self):
        pr = ProductReferenceFactory(citation_role='primary')
        self.assertEqual(pr.citation_role, 'primary')

    def test_unique_together(self):
        from apps.knowledge.tests.factories import ReferenceFactory
        product = ProductFactory()
        reference = ReferenceFactory()
        ProductReferenceFactory(product=product, reference=reference, citation_role='supporting')
        with self.assertRaises(IntegrityError):
            ProductReferenceFactory(product=product, reference=reference, citation_role='supporting')

    def test_same_product_different_citation_role_allowed(self):
        from apps.knowledge.tests.factories import ReferenceFactory
        product = ProductFactory()
        reference = ReferenceFactory()
        pr1 = ProductReferenceFactory(product=product, reference=reference, citation_role='primary')
        pr2 = ProductReferenceFactory(product=product, reference=reference, citation_role='supporting')
        self.assertNotEqual(pr1.id, pr2.id)

    def test_citation_role_choices(self):
        choices = dict(ProductReference.CitationRole.choices)
        self.assertIn('primary', choices)
        self.assertIn('supporting', choices)
        self.assertIn('validation', choices)
        self.assertIn('background', choices)

    def test_citation_role_default(self):
        pr = ProductReferenceFactory()
        self.assertEqual(pr.citation_role, 'supporting')

    def test_display_order_default(self):
        pr = ProductReferenceFactory()
        self.assertEqual(pr.display_order, 0)

    def test_order_index_exists(self):
        indexes = ProductReference._meta.indexes
        order_indexes = [i for i in indexes if i.name == 'product_ref_order_idx']
        self.assertEqual(len(order_indexes), 1)

    def test_table_name(self):
        self.assertEqual(ProductReference._meta.db_table, 'product_reference')


class ProductCompatibilityModelTest(TestCase):
    def test_create(self):
        pc = ProductCompatibilityFactory(verdict='compatible')
        self.assertEqual(pc.verdict, 'compatible')

    def test_unique_together(self):
        source = ProductFactory()
        target = ProductFactory()
        from apps.knowledge.tests.factories import CompatibilityFactory
        compat = CompatibilityFactory()
        ProductCompatibilityFactory(
            source_product=source, target_product=target, compatibility=compat
        )
        with self.assertRaises(IntegrityError):
            ProductCompatibilityFactory(
                source_product=source, target_product=target, compatibility=compat
            )

    def test_verdict_choices(self):
        choices = dict(ProductCompatibility.Verdict.choices)
        self.assertIn('compatible', choices)
        self.assertIn('incompatible', choices)
        self.assertIn('conditional', choices)
        self.assertIn('warning', choices)

    def test_notes_default(self):
        pc = ProductCompatibilityFactory()
        self.assertEqual(pc.notes, '')

    def test_str(self):
        pc = ProductCompatibilityFactory(verdict='compatible')
        result = str(pc)
        self.assertIn('compatible', result)
        self.assertIn('<->', result)

    def test_related_name_source(self):
        source = ProductFactory()
        ProductCompatibilityFactory(source_product=source)
        self.assertEqual(source.compatibility_as_source.count(), 1)

    def test_related_name_target(self):
        target = ProductFactory()
        ProductCompatibilityFactory(target_product=target)
        self.assertEqual(target.compatibility_as_target.count(), 1)

    def test_table_name(self):
        self.assertEqual(ProductCompatibility._meta.db_table, 'product_compatibility')


class ProductProductModelTest(TestCase):
    def test_create(self):
        pp = ProductProductFactory(relation_type='substitute', direction='bidirectional')
        self.assertEqual(pp.relation_type, 'substitute')
        self.assertEqual(pp.direction, 'bidirectional')

    def test_unique_together(self):
        source = ProductFactory()
        target = ProductFactory()
        ProductProductFactory(source_product=source, target_product=target, relation_type='related')
        with self.assertRaises(IntegrityError):
            ProductProductFactory(source_product=source, target_product=target, relation_type='related')

    def test_same_pair_different_relation_allowed(self):
        source = ProductFactory()
        target = ProductFactory()
        pp1 = ProductProductFactory(source_product=source, target_product=target, relation_type='related')
        pp2 = ProductProductFactory(source_product=source, target_product=target, relation_type='substitute')
        self.assertNotEqual(pp1.id, pp2.id)

    def test_relation_type_choices(self):
        choices = dict(ProductProduct.RelationType.choices)
        self.assertIn('substitute', choices)
        self.assertIn('complement', choices)
        self.assertIn('alternate', choices)
        self.assertIn('bundle', choices)
        self.assertIn('related', choices)

    def test_direction_choices(self):
        choices = dict(ProductProduct.Direction.choices)
        self.assertIn('one_way', choices)
        self.assertIn('bidirectional', choices)

    def test_defaults(self):
        pp = ProductProductFactory()
        self.assertEqual(pp.relation_type, 'related')
        self.assertEqual(pp.direction, 'bidirectional')
        self.assertEqual(pp.strength, 0)

    def test_str(self):
        pp = ProductProductFactory(relation_type='substitute')
        result = str(pp)
        self.assertIn('substitute', result)
        self.assertIn('->', result)

    def test_table_name(self):
        self.assertEqual(ProductProduct._meta.db_table, 'product_product')
