"""
documents 应用测试 — Batch / Coa / SdsRevision / PubChemCache 模型
"""
import json
import datetime
from django.test import TestCase
from django.db import IntegrityError

from apps.documents.models import Batch, Coa, SdsRevision, PubChemCache
from apps.commerce.tests.factories import ProductFactory, SKUFactory


class BatchModelTest(TestCase):
    """Batch 模型基础测试"""

    def setUp(self):
        self.product = ProductFactory(catalog_no='SC8001', name='Test Product')
        self.sku = SKUFactory(product=self.product, sku_code='SC8001-SKU1')

    def test_create_batch(self):
        batch = Batch.objects.create(
            sku=self.sku,
            lot_number='SC8001-L2026001',
            produced_at=datetime.date(2026, 1, 15),
            retest_at=datetime.date(2027, 1, 15),
        )
        self.assertEqual(batch.lot_number, 'SC8001-L2026001')
        self.assertEqual(batch.produced_at, datetime.date(2026, 1, 15))
        self.assertEqual(str(batch), 'SC8001-L2026001')

    def test_batch_unique_lot_number(self):
        Batch.objects.create(
            sku=self.sku,
            lot_number='SC8001-L2026001',
            produced_at=datetime.date(2026, 1, 15),
        )
        with self.assertRaises(IntegrityError):
            Batch.objects.create(
                sku=self.sku,
                lot_number='SC8001-L2026001',
                produced_at=datetime.date(2026, 2, 20),
            )

    def test_batch_ordering(self):
        b1 = Batch.objects.create(sku=self.sku, lot_number='LOT-A', produced_at=datetime.date(2026, 3, 1))
        b2 = Batch.objects.create(sku=self.sku, lot_number='LOT-B', produced_at=datetime.date(2026, 1, 1))
        batches = list(Batch.objects.all())
        self.assertEqual(batches[0], b1)  # produced_at 更晚的排前面
        self.assertEqual(batches[1], b2)


class CoaModelTest(TestCase):
    """Coa 模型基础测试"""

    def setUp(self):
        self.product = ProductFactory(catalog_no='SC8001', name='Test Product')
        self.sku = SKUFactory(product=self.product, sku_code='SC8001-SKU1')
        self.batch = Batch.objects.create(
            sku=self.sku,
            lot_number='SC8001-L2026001',
            produced_at=datetime.date(2026, 1, 15),
        )

    def test_create_coa(self):
        coa = Coa.objects.create(
            batch=self.batch,
            doc_id='COA-SC8001-2026-001',
            product_name='Test Product',
            catalog_number='SC8001',
        )
        self.assertEqual(coa.status, Coa.Status.DRAFT)
        self.assertEqual(str(coa), 'COA COA-SC8001-2026-001')

    def test_coa_one_to_one_with_batch(self):
        Coa.objects.create(
            batch=self.batch,
            doc_id='COA-SC8001-2026-001',
            product_name='Test Product',
            catalog_number='SC8001',
        )
        with self.assertRaises(IntegrityError):
            Coa.objects.create(
                batch=self.batch,
                doc_id='COA-SC8001-2026-002',
                product_name='Test Product',
                catalog_number='SC8001',
            )

    def test_coa_status_choices(self):
        self.assertEqual(Coa.Status.DRAFT, 'draft')
        self.assertEqual(Coa.Status.APPROVED, 'approved')
        self.assertEqual(Coa.Status.PUBLISHED, 'published')


class SdsRevisionModelTest(TestCase):
    """SdsRevision 模型基础测试"""

    def setUp(self):
        self.product = ProductFactory(catalog_no='SC8001', name='Test Product')

    def test_create_sds_revision(self):
        sds = SdsRevision.objects.create(
            product=self.product,
            revision_no=1,
            revised_at=datetime.date(2026, 1, 15),
            signal_word='Warning',
            pictograms=json.dumps(['GHS07']),
            hazard_codes=json.dumps(['H302']),
            precaution_codes=json.dumps(['P261']),
        )
        self.assertEqual(str(sds), 'SDS SC8001 v1')
        self.assertEqual(sds.get_pictograms(), ['GHS07'])
        self.assertEqual(sds.get_hazard_codes(), ['H302'])

    def test_sds_unique_constraint(self):
        SdsRevision.objects.create(
            product=self.product, revision_no=1, revised_at=datetime.date(2026, 1, 15))
        with self.assertRaises(IntegrityError):
            SdsRevision.objects.create(
                product=self.product, revision_no=1, revised_at=datetime.date(2026, 6, 1))

    def test_sds_ordering(self):
        SdsRevision.objects.create(product=self.product, revision_no=1, revised_at=datetime.date(2026, 1, 1))
        SdsRevision.objects.create(product=self.product, revision_no=3, revised_at=datetime.date(2026, 6, 1))
        revs = list(SdsRevision.objects.all())
        self.assertEqual(revs[0].revision_no, 3)  # 修订版本号降序

    def test_sds_section_data_json(self):
        data = {'section_1': {'product_name': 'Test'}}
        sds = SdsRevision.objects.create(
            product=self.product, revision_no=1, revised_at=datetime.date(2026, 1, 15))
        sds.set_section_data(data)
        sds.save()
        sds.refresh_from_db()
        self.assertEqual(sds.get_section_data(), data)


class PubChemCacheModelTest(TestCase):
    def test_create_and_retrieve(self):
        data = {'cid': 12345, 'molecular_weight': '123.45'}
        cache = PubChemCache.objects.create(
            cas_number='123-45-6',
            cid=12345,
            data_json=json.dumps(data),
        )
        self.assertEqual(cache.get_data(), data)
        self.assertEqual(str(cache), 'PubChem CAS:123-45-6 (CID:12345)')
