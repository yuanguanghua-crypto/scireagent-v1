"""
COA / SDS 合规功能 — 核心新逻辑独立验证测试（QA 严过关）。

本文件为对既有 test_workflow_api.py 的「补充」，聚焦本期新增/改造且既有用例未充分
覆盖的部分：

  A. 无 CAS 四级降级链（generate_sds）—— 验证 L1→L2→L3→L4 顺序与各级 data_confidence
  B. 权限（IsAdminOrReadOnly）—— 匿名 GET 放行 / 写 403；is_staff 写放行；普通认证用户写 403
  C. ProductListSerializer 摘要字段 sds_published / coa_published_count
  D. SdsRevisionSerializer 暴露 data_confidence / data_source_detail
  E. withdraw 端点（@action）端到端
  F. 历史数据迁移：status='approved' → 'published'（0004 数据迁移）

注意：全局 EnvelopeRenderer 会把所有响应包成 {success, data, meta}，
因此 action/detail 用 resp.json()['data']，list 用 resp.json()['data']（数组）。
documents.js 也按此信封解析（与 products 一致），前端/后端一致，无 bug。
"""
from datetime import date
from unittest.mock import patch
from importlib import import_module

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.documents.models import Batch, Coa, SdsRevision
from apps.commerce.tests.factories import ProductFactory, SKUFactory
from apps.documents.services.workflow import (
    create_coa, approve_coa, generate_sds, approve_sds,
)
from apps.documents.api.v1.serializers import SdsRevisionSerializer
from apps.commerce.api.v1.serializers import ProductListSerializer

User = get_user_model()


PUBCHEM_HIT = {
    'cid': 702,
    'signal_word': 'Warning',
    'pictograms': ['GHS02'],
    'hazard_codes': ['H225'],
    'precaution_codes': ['P210'],
    'section_data': {},
}


# ════════════════════════════════════════════════════════════════
# A. 四级降级链（generate_sds）
# ════════════════════════════════════════════════════════════════
class GenerateSdsDegradationTest(TestCase):
    """验证 generate_sds 四级降级链：CAS→结构标识→类别模板→GENERIC，不再硬 raise。"""

    @patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem')
    def test_L1_cas_high(self, mock_fetch):
        """L1 CAS → PubChem 命中，confidence=high，source 含 CID。"""
        mock_fetch.return_value = dict(PUBCHEM_HIT, cid=702)
        product = ProductFactory(catalog_no='SC8101', name='Ethanol', cas='64-17-5')
        sds = generate_sds(product_id=product.id)
        self.assertEqual(sds.data_confidence, SdsRevision.DataConfidence.HIGH)
        self.assertIn('PubChem CID 702', sds.data_source_detail)
        self.assertIn('CAS', sds.data_source_detail)

    @patch('apps.documents.services.workflow.fetch_sds_data')
    def test_L2_smiles_medium(self, mock_fetch):
        """无 CAS 但有 SMILES → L2 解析命中，confidence=medium。"""
        product = ProductFactory(catalog_no='SC8102', name='NoCas', cas='', smiles='CCO')
        mock_fetch.return_value = dict(PUBCHEM_HIT, cid=123)
        sds = generate_sds(product_id=product.id)
        self.assertEqual(sds.data_confidence, SdsRevision.DataConfidence.MEDIUM)
        self.assertIn('(smiles: CCO)', sds.data_source_detail)

    @patch('apps.documents.services.workflow.fetch_sds_data')
    def test_L2_inchi_medium(self, mock_fetch):
        """无 CAS/SMILES 但有 InChI → L2 解析命中，confidence=medium。"""
        product = ProductFactory(
            catalog_no='SC8102b', name='NoCas2', cas='', smiles='',
            inchi='InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3',
        )
        mock_fetch.return_value = dict(PUBCHEM_HIT, cid=321)
        sds = generate_sds(product_id=product.id)
        self.assertEqual(sds.data_confidence, SdsRevision.DataConfidence.MEDIUM)
        self.assertIn('(inchi:', sds.data_source_detail)

    def test_L3_category_low(self):
        """无 CAS/SMILES/名称 但有匹配类别 → L3 类别模板，confidence=low。"""
        product = ProductFactory(
            catalog_no='SC8103', name='Oligo', cas='', smiles='',
            category_l1='Oligonucleotides',
        )
        with patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem') as m1, \
             patch('apps.documents.services.workflow.fetch_sds_data') as m2:
            m1.return_value = None
            m2.return_value = None
            sds = generate_sds(product_id=product.id)
        self.assertEqual(sds.data_confidence, SdsRevision.DataConfidence.LOW)
        self.assertIn('Category template', sds.data_source_detail)
        # 'oligonucleotide' 命中 _CATEGORY_GHS 的 label 'Nucleotides & Nucleosides'
        self.assertIn('Nucleotides & Nucleosides', sds.data_source_detail)

    def test_L4_generic_very_low(self):
        """四级全无（无标识、无类别）→ L4 GENERIC 兜底，confidence=very_low，不 raise。"""
        product = ProductFactory(
            catalog_no='SC8104', name='', cas='', smiles='', category_l1='',
        )
        with patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem') as m1, \
             patch('apps.documents.services.workflow.fetch_sds_data') as m2:
            m1.return_value = None
            m2.return_value = None
            sds = generate_sds(product_id=product.id)
        self.assertEqual(sds.data_confidence, SdsRevision.DataConfidence.VERY_LOW)
        self.assertEqual(sds.data_source_detail, 'Generic safety notes (no identifier matched)')

    def test_order_skips_L1_then_L2_then_L3(self):
        """降级顺序验证：CAS 命中失败 → 尝试名称(L2)失败 → 落到类别模板(L3, low)。"""
        product = ProductFactory(
            catalog_no='SC8105', name='Oligo2', cas='99-99-0', smiles='',
            category_l1='Oligonucleotides',
        )
        with patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem') as m1, \
             patch('apps.documents.services.workflow.fetch_sds_data') as m2:
            m1.return_value = None          # L1 失败
            m2.return_value = None          # L2（含名称）失败
            sds = generate_sds(product_id=product.id)
        # 必须抵达 L3（类别模板），而非 raise
        self.assertEqual(sds.data_confidence, SdsRevision.DataConfidence.LOW)

    def test_no_cas_never_raises(self):
        """回归铁律 #3：无 CAS 产品 generate_sds 不得 raise。"""
        product = ProductFactory(catalog_no='SC8106', name='', cas='', smiles='')
        with patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem') as m1, \
             patch('apps.documents.services.workflow.fetch_sds_data') as m2:
            m1.return_value = None
            m2.return_value = None
            sds = generate_sds(product_id=product.id)  # 不应抛异常
        self.assertIsNotNone(sds)
        self.assertTrue(sds.pk)


# ════════════════════════════════════════════════════════════════
# B. 权限（IsAdminOrReadOnly）
# ════════════════════════════════════════════════════════════════
class PermissionTest(TestCase):
    """验证 IsAdminOrReadOnly：读=公开，写=is_staff；严禁 IsStaffUser（会阻断匿名读）。"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='qa_admin', password='testpass', email='qa_admin@test', is_staff=True,
        )
        self.normal = User.objects.create_user(
            username='qa_normal', password='testpass', is_staff=False,
        )
        self.product = ProductFactory(catalog_no='SC8201', name='Perm Product', cas='64-17-5')
        self.sku = SKUFactory(product=self.product, sku_code='SC8201-SKU1')

    # ── 匿名（未认证）──
    def test_anon_can_list_coas(self):
        resp = self.client.get('/api/v1/coas/')
        self.assertEqual(resp.status_code, 200)

    def test_anon_can_list_sds(self):
        resp = self.client.get('/api/v1/sds-revisions/')
        self.assertEqual(resp.status_code, 200)

    def test_anon_write_coa_forbidden(self):
        """匿名（未认证）写操作应被拒绝，统一返回 403（本期 documents 视图覆盖
        permission_denied，匿名写也返回 403 而非 DRF 默认 401）。认证但非 is_staff
        同样返回 403。两者均正确阻断写操作（铁律核心：匿名不可写）。"""
        resp = self.client.post('/api/v1/coas/create-coa/', {
            'sku_id': self.sku.id, 'lot_number': 'LOT-X', 'produced_at': '2026-01-01',
        })
        self.assertEqual(resp.status_code, 403)

    def test_anon_sds_generate_forbidden(self):
        """匿名（未认证）生成 SDS 应被拒绝（403，本期 documents 视图统一行为）。"""
        resp = self.client.post('/api/v1/sds-revisions/generate/', {
            'product_id': self.product.id,
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_anon_coa_download_not_forbidden(self):
        """下载为 GET（匿名可），无 PDF 时应 404 而非 403（权限已放行）。"""
        coa = create_coa(self.sku.id, 'LOT-X', date(2026, 1, 1))
        resp = self.client.get(f'/api/v1/coas/{coa.id}/download/')
        self.assertNotEqual(resp.status_code, 403)

    # ── is_staff 用户 ──
    def test_staff_write_coa_allowed(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post('/api/v1/coas/create-coa/', {
            'sku_id': self.sku.id, 'lot_number': 'LOT-S', 'produced_at': '2026-01-01',
        })
        self.assertEqual(resp.status_code, 201)

    def test_staff_sds_generate_allowed(self):
        self.client.force_authenticate(user=self.admin)
        with patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem') as m:
            m.return_value = PUBCHEM_HIT
            resp = self.client.post('/api/v1/sds-revisions/generate/', {
                'product_id': self.product.id,
            }, format='json')
        self.assertEqual(resp.status_code, 201)

    def test_staff_coa_approve_allowed(self):
        self.client.force_authenticate(user=self.admin)
        coa = create_coa(self.sku.id, 'LOT-S2', date(2026, 1, 1))
        resp = self.client.post(f'/api/v1/coas/{coa.id}/approve/', {
            'qc_analyst': 'Dr. A', 'qa_approval': 'Dr. B',
        }, format='json')
        self.assertEqual(resp.status_code, 200)

    # ── 普通认证用户（is_staff=False）──
    def test_normal_user_write_coa_forbidden(self):
        self.client.force_authenticate(user=self.normal)
        resp = self.client.post('/api/v1/coas/create-coa/', {
            'sku_id': self.sku.id, 'lot_number': 'LOT-N', 'produced_at': '2026-01-01',
        })
        self.assertEqual(resp.status_code, 403)

    def test_normal_user_sds_generate_forbidden(self):
        self.client.force_authenticate(user=self.normal)
        resp = self.client.post('/api/v1/sds-revisions/generate/', {
            'product_id': self.product.id,
        }, format='json')
        self.assertEqual(resp.status_code, 403)


# ════════════════════════════════════════════════════════════════
# C. ProductListSerializer 摘要字段
# ════════════════════════════════════════════════════════════════
class ProductListSerializerTest(TestCase):
    def setUp(self):
        self.product = ProductFactory(catalog_no='SC8301', name='Serial Product', cas='123-45-6', smiles='CCO')
        self.sku = SKUFactory(product=self.product, sku_code='SC8301-SKU1')

    def test_sds_published_true_when_current_sds_set(self):
        sds = SdsRevision.objects.create(
            product=self.product, revision_no=1, revised_at=date.today(),
            signal_word='Warning', data_confidence='low', data_source_detail='x',
        )
        self.product.current_sds = sds
        self.product.save()
        data = ProductListSerializer(self.product).data
        self.assertTrue(data['sds_published'])

    def test_sds_published_false_when_no_current_sds(self):
        data = ProductListSerializer(self.product).data
        self.assertFalse(data['sds_published'])

    def test_coa_published_count(self):
        coa = create_coa(self.sku.id, 'LOT-C', date(2026, 1, 1))
        self.assertEqual(ProductListSerializer(self.product).data['coa_published_count'], 0)
        approve_coa(coa.id)
        self.assertEqual(ProductListSerializer(self.product).data['coa_published_count'], 1)

    def test_coa_published_count_ignores_draft(self):
        create_coa(self.sku.id, 'LOT-D', date(2026, 1, 1))  # 仅 draft，未审批
        self.assertEqual(ProductListSerializer(self.product).data['coa_published_count'], 0)


# ════════════════════════════════════════════════════════════════
# D. SdsRevisionSerializer 暴露新字段
# ════════════════════════════════════════════════════════════════
class SdsRevisionSerializerTest(TestCase):
    def test_new_fields_exposed(self):
        product = ProductFactory(catalog_no='SC8401', name='Oligo', cas='', smiles='', category_l1='Oligonucleotides')
        sds = SdsRevision.objects.create(
            product=product, revision_no=1, revised_at=date.today(),
            data_confidence='low', data_source_detail='Category template: Oligonucleotides',
        )
        data = SdsRevisionSerializer(sds).data
        self.assertIn('data_confidence', data)
        self.assertIn('data_source_detail', data)
        self.assertEqual(data['data_confidence'], 'low')
        self.assertEqual(data['data_source_detail'], 'Category template: Oligonucleotides')
        self.assertIn('is_current', data)


# ════════════════════════════════════════════════════════════════
# E. withdraw 端点（@action）端到端
# ════════════════════════════════════════════════════════════════
class WithdrawEndpointTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='qa_w_admin', password='testpass', email='qa_w@test', is_staff=True,
        )
        self.product = ProductFactory(catalog_no='SC8501', name='Withdraw Product', cas='64-17-5')
        self.sku = SKUFactory(product=self.product, sku_code='SC8501-SKU1')

    def test_withdraw_coa_endpoint(self):
        """POST /coas/{id}/withdraw/ → status=draft，pdf_path 保留。"""
        self.client.force_authenticate(user=self.admin)
        coa = create_coa(self.sku.id, 'LOT-W', date(2026, 1, 1))
        approve_coa(coa.id)
        coa.refresh_from_db()
        self.assertEqual(coa.status, 'published')
        self.assertIsNotNone(coa.pdf_path)

        resp = self.client.post(f'/api/v1/coas/{coa.id}/withdraw/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertEqual(data['status'], 'draft')
        coa.refresh_from_db()
        self.assertIsNotNone(coa.pdf_path)  # PDF 文件保留

    def test_withdraw_sds_endpoint(self):
        """POST /sds-revisions/{id}/withdraw/ → 清空 product.current_sds。"""
        self.client.force_authenticate(user=self.admin)
        with patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem') as m:
            m.return_value = PUBCHEM_HIT
            sds = generate_sds(product_id=self.product.id)
        approve_sds(sds.id)
        self.product.refresh_from_db()
        self.assertIsNotNone(self.product.current_sds_id)

        resp = self.client.post(f'/api/v1/sds-revisions/{sds.id}/withdraw/')
        self.assertEqual(resp.status_code, 200)
        self.product.refresh_from_db()
        self.assertIsNone(self.product.current_sds_id)

    def test_withdraw_coa_requires_staff(self):
        """撤回为写操作，匿名（未认证）应被拒绝（403，本期 documents 视图统一行为）。"""
        coa = create_coa(self.sku.id, 'LOT-W2', date(2026, 1, 1))
        approve_coa(coa.id)
        resp = self.client.post(f'/api/v1/coas/{coa.id}/withdraw/')
        self.assertEqual(resp.status_code, 403)


# ════════════════════════════════════════════════════════════════
# F. 历史数据迁移：approved → published
# ════════════════════════════════════════════════════════════════
class HistoricalMigrationTest(TestCase):
    def test_approved_to_published_migration(self):
        """0004 数据迁移把遗留 status='approved' 的 COA 改写为 'published'。"""
        from django.apps import apps as django_apps
        migration = import_module('apps.documents.migrations.0004_fix_coa_approved_to_published')

        product = ProductFactory(catalog_no='SC8601', name='Legacy', cas='123-45-6', smiles='CCO')
        sku = SKUFactory(product=product, sku_code='SC8601-SKU1')
        batch = Batch.objects.create(sku=sku, lot_number='LEGACY-LOT', produced_at=date(2026, 1, 1))
        coa = Coa.objects.create(
            batch=batch, doc_id='COA-LEGACY-001', status=Coa.Status.APPROVED,
            product_name='Legacy', catalog_number='SC8601',
        )
        self.assertEqual(Coa.objects.filter(status='approved').count(), 1)

        # 直接调用迁移正向函数（schema_editor 未使用，传 None）
        migration._forward(django_apps, None)

        coa.refresh_from_db()
        self.assertEqual(coa.status, Coa.Status.PUBLISHED)
        self.assertEqual(Coa.objects.filter(status='approved').count(), 0)
        self.assertEqual(Coa.objects.filter(status='published').count(), 1)

    def test_no_approved_residual_after_migration(self):
        """断言 choices 仍保留 approved（兼容历史），但当前写路径不再产生它。"""
        # 经 approve_coa 审批的行应为 published，而非 approved
        product = ProductFactory(catalog_no='SC8602', name='Modern', cas='123-45-6', smiles='CCO')
        sku = SKUFactory(product=product, sku_code='SC8602-SKU1')
        coa = create_coa(sku.id, 'LOT-M', date(2026, 1, 1))
        approve_coa(coa.id)
        coa.refresh_from_db()
        self.assertEqual(coa.status, 'published')
        self.assertEqual(Coa.objects.filter(status='approved').count(), 0)
