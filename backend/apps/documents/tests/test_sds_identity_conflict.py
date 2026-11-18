"""A-254 ②③ — CAS 走 PubChem 结构化端点 + 身份矛盾禁止发布。

背景（2026-11-18 S2 乙组，生产实测）：
  产品 5456：cas='63-39-2'（ATP）、smiles='CCO'（乙醇）。
  旧实现把 CAS 当「名字」查 /compound/name/63-39-2/cids/JSON → HTTP 404 PUGREST.NotFound
  ⇒ L1 静默落空 ⇒ 降级用 SMILES 查到 CID 702（乙醇）⇒ 一份描述乙醇的 SDS 被标成 ATP 的，
  而且还能审批发布成对外合规文件。

修法两层：
  ② CAS 改走 /compound/xref/RegistryID/{cas}/cids/JSON（注册号专用端点），
     失败再退回 name 端点（部分 CAS 只出现在同义词里）。
  ③ 产品给了 CAS、CAS 却解析不出任何 CID、只能用 SMILES/InChI 兜底 ⇒
     identity_conflict=True ⇒ 草稿照存，approve_sds **硬拒发布**（用户拍板 (b)）。
"""
from unittest.mock import patch

from django.test import TestCase

from apps.commerce.tests.factories import ProductFactory
from apps.documents.services import pubchem_fetcher as pf
from apps.documents.services.workflow import approve_sds, generate_sds


PUBCHEM_HIT = {
    'cid': 702,
    'signal_word': 'Warning',
    'pictograms': ['GHS02'],
    'hazard_codes': ['H225'],
    'precaution_codes': ['P210'],
    'section_data': {},
}


# ════════════════════════════════════════════════════════════════
# ② CAS → xref/RegistryID 端点
# ════════════════════════════════════════════════════════════════
class CasEndpointTest(TestCase):
    """CAS 必须走注册号端点，而不是当名字查。"""

    def test_cas_prefers_xref_registry_id(self):
        """CAS 查询的第一跳必须是 compound/xref/RegistryID/…。"""
        calls = []

        def _fake(path, diag=None):
            calls.append(path)
            return {'IdentifierList': {'CID': [5957]}}

        with patch.object(pf, '_pubchem_get', side_effect=_fake):
            cid = pf._get_cid_from_identifier('63-39-2', 'cas')

        self.assertEqual(cid, 5957)
        self.assertTrue(calls and calls[0].startswith('compound/xref/RegistryID/'),
                        f'第一跳必须是 xref/RegistryID，实际: {calls}')

    def test_cas_falls_back_to_name_when_xref_misses(self):
        """xref 未收录时退回 name 端点（历史行为），不直接判 miss。"""
        calls = []

        def _fake(path, diag=None):
            calls.append(path)
            if 'xref' in path:
                if diag is not None:
                    diag['error'] = 'HTTP Error 404: PUGREST.NotFound'
                return None
            return {'IdentifierList': {'CID': [12345]}}

        with patch.object(pf, '_pubchem_get', side_effect=_fake):
            cid = pf._get_cid_from_identifier('99-99-9', 'cas')

        self.assertEqual(cid, 12345)
        self.assertTrue(any(p.startswith('compound/name/') for p in calls))

    def test_cas_miss_records_combined_error(self):
        """两跳都失败时 diag 必须留下原因（供 data_source_detail 说明降级）。"""
        def _fake(path, diag=None):
            if diag is not None:
                diag['error'] = 'HTTP Error 404: PUGREST.NotFound'
            return None

        diag = {}
        with patch.object(pf, '_pubchem_get', side_effect=_fake):
            cid = pf._get_cid_from_identifier('63-39-2', 'cas', diag=diag)

        self.assertIsNone(cid)
        self.assertIn('404', diag['error'])
        self.assertIn('xref/RegistryID', diag['error'])
        self.assertIn('compound/name', diag['error'])

    def test_smiles_still_uses_smiles_endpoint(self):
        """SMILES 路径不受 CAS 改动影响。"""
        calls = []

        def _fake(path, diag=None):
            calls.append(path)
            return {'IdentifierList': {'CID': [702]}}

        with patch.object(pf, '_pubchem_get', side_effect=_fake):
            cid = pf._get_cid_from_identifier('CCO', 'smiles')

        self.assertEqual(cid, 702)
        self.assertTrue(calls[0].startswith('compound/smiles/'))

    def test_cas_hit_clears_stale_error(self):
        """xref 失败但 name 命中 → diag 不得残留上一跳的错误。"""
        def _fake(path, diag=None):
            if 'xref' in path:
                if diag is not None:
                    diag['error'] = 'HTTP Error 404: PUGREST.NotFound'
                return None
            return {'IdentifierList': {'CID': [999]}}

        diag = {}
        with patch.object(pf, '_pubchem_get', side_effect=_fake):
            cid = pf._get_cid_from_identifier('99-99-9', 'cas', diag=diag)

        self.assertEqual(cid, 999)
        self.assertNotIn('error', diag)


# ════════════════════════════════════════════════════════════════
# ③ 身份矛盾：草稿可存、禁止发布
# ════════════════════════════════════════════════════════════════
class IdentityConflictGateTest(TestCase):
    """生产实例 5456 的回归：CAS 解析不出 → 用 SMILES 兜底 ⇒ 禁发布。"""

    @patch('apps.documents.services.workflow.fetch_sds_data')
    @patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem')
    def test_cas_unresolved_with_smiles_fallback_flags_conflict(self, m1, m2):
        m1.return_value = None                                  # L1 CAS 解析失败
        m2.return_value = dict(PUBCHEM_HIT, cid=702)            # L2 SMILES 命中乙醇
        product = ProductFactory(
            catalog_no='SC8120', name='ATP', cas='63-39-2', smiles='CCO')

        sds = generate_sds(product_id=product.id)

        self.assertTrue(sds.identity_conflict, 'CAS 解析失败却用 SMILES 兜底，必须标记矛盾')
        self.assertIn('CAS 63-39-2', sds.identity_conflict_detail)
        self.assertIn('CID 702', sds.identity_conflict_detail)
        # 草稿照存 —— 研究员的草稿区是工作区，不阻断
        self.assertEqual(sds.status, 'draft')

    @patch('apps.documents.services.workflow.fetch_sds_data')
    @patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem')
    def test_inchi_fallback_also_flags_conflict(self, m1, m2):
        m1.return_value = None
        m2.return_value = dict(PUBCHEM_HIT, cid=321)
        product = ProductFactory(
            catalog_no='SC8121', name='X', cas='63-39-2', smiles='',
            inchi='InChI=1S/C2H6O/c1-2-3/h3H,2H2,1H3')

        sds = generate_sds(product_id=product.id)

        self.assertTrue(sds.identity_conflict)
        self.assertIn('inchi', sds.identity_conflict_detail)

    @patch('apps.documents.services.workflow.fetch_sds_data')
    @patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem')
    def test_approve_is_blocked_on_conflict(self, m1, m2):
        """★ 核心：有身份矛盾的修订版，审批必须抛错且**不产生任何副作用**。"""
        m1.return_value = None
        m2.return_value = dict(PUBCHEM_HIT, cid=702)
        product = ProductFactory(
            catalog_no='SC8122', name='ATP', cas='63-39-2', smiles='CCO')
        sds = generate_sds(product_id=product.id)

        with self.assertRaises(ValueError) as ctx:
            approve_sds(sds.id)
        self.assertIn('禁止审批发布', str(ctx.exception))
        self.assertIn('63-39-2', str(ctx.exception))

        sds.refresh_from_db()
        product.refresh_from_db()
        self.assertEqual(sds.status, 'draft', '被拒后不得变成 published')
        self.assertFalse(sds.pdf_path, '被拒后不应生成 PDF')
        self.assertIsNone(product.current_sds_id, '被拒后不得设为当前版本')

    @patch('apps.documents.services.workflow.fetch_sds_data')
    @patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem')
    def test_cas_hit_never_flags_conflict(self, m1, m2):
        """L1 CAS 命中 ⇒ SDS 按权威注册号生成，不标矛盾（哪怕产品 SMILES 不同）。"""
        m1.return_value = dict(PUBCHEM_HIT, cid=5957)
        product = ProductFactory(
            catalog_no='SC8123', name='ATP', cas='63-39-2', smiles='CCO')

        sds = generate_sds(product_id=product.id)

        self.assertFalse(sds.identity_conflict)
        self.assertEqual(sds.identity_conflict_detail, '')
        approve_sds(sds.id)          # 不应抛错
        sds.refresh_from_db()
        self.assertEqual(sds.status, 'published')

    @patch('apps.documents.services.workflow.fetch_sds_data')
    @patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem')
    def test_no_cas_structural_hit_no_conflict(self, m1, m2):
        """产品本来没有 CAS（纯结构标识）⇒ 无「矛盾」可言，不得误拦。"""
        m2.return_value = dict(PUBCHEM_HIT, cid=702)
        product = ProductFactory(
            catalog_no='SC8124', name='NoCas', cas='', smiles='CCO')

        sds = generate_sds(product_id=product.id)

        self.assertFalse(sds.identity_conflict)
        approve_sds(sds.id)

    @patch('apps.documents.services.workflow.fetch_sds_data')
    @patch('apps.documents.services.workflow.fetch_sds_data_from_pubchem')
    def test_name_fallback_does_not_flag_conflict(self, m1, m2):
        """按「产品名称」兜底不算身份矛盾（名称不是结构标识，本批不纳入闸门）。"""
        m1.return_value = None
        m2.return_value = dict(PUBCHEM_HIT, cid=702)
        product = ProductFactory(
            catalog_no='SC8125', name='Ethanol', cas='63-39-2', smiles='', inchi='')

        sds = generate_sds(product_id=product.id)

        self.assertFalse(sds.identity_conflict,
                         'name 兜底不构成身份矛盾，避免把闸门扩成无差别误杀')
