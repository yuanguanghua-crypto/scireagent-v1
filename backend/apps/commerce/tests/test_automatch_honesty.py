"""A-018 / A-056 止损：AUTO MATCH 的三处诚实性修正。

## 三个独立问题（生产实测 2026-11-26）
① **ChEMBL 不可达时长挂起**：`ebi.ac.uk` SSL UNEXPECTED_EOF，30s 超时 × 3 次重试
   ⇒ 一次 AUTO MATCH 白等 44s（QA 报的"挂起 43 秒以上"）。
② **`found=True` 假阳性**：`confidence='rejected'`（找到了但 CAS/结构不符）
   也返回 `found=True` 且无 `properties` ⇒ 前端渲染 `CID: None / Resolved Name: —`。
③ **CAS 无法检索**：PubChem 的 name/synonym/xref 端点全部不支持 CAS（实测），
   但提示语让用户以为是自己填错了。

## 本文件钉住
① ChEMBL 超时降到 8s 且只试 1 次
② rejected ⇒ `found=False` + `rejected=True`
③ CAS 形态的 identifier 得到"CAS 不能作为检索键"的专门提示
"""
import re
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.commerce.services.validators.pubchem_enhancer import PubChemEnhancer


class ChemblResilienceParamsTest(SimpleTestCase):
    """① 超时与重试：不可达时最多等 8 秒，而不是 90 秒"""

    def test_timeout_is_eight_seconds(self):
        self.assertEqual(PubChemEnhancer.CHEMBL_TIMEOUT, 8,
                         '30s 超时在不可达时只会放大等待（可达时 1-2s 就返回）')

    def test_chembl_call_does_not_retry(self):
        """源码里必须显式传 retries=1 —— 否则会退回默认的 3 次。"""
        import inspect
        src = inspect.getsource(PubChemEnhancer._chembl_search)
        self.assertIn('retries=1', src,
                      'ChEMBL 不可达时不该重试；默认 retries=3 会让每次请求多等 3 倍')


class RejectedIsNotFoundTest(SimpleTestCase):
    """② rejected 不能冒充 found"""

    def test_rejected_returns_found_false(self):
        enh = PubChemEnhancer()
        # 造一个"找到了化合物但 CAS 不符"的场景：compound_cas_set 返回不含 expected_cas
        fake_compound = object()
        # `available` 是只读 property（依赖库是否安装），不能 patch；这里只替换
        # CAS 集合，让"输入的 CAS 不在候选同义词里"这条判据成立即可。
        with patch.object(enh, '_compound_cas_set', return_value={'999-99-9'}):
            ok, conf = enh._validate_identity('63-39-2', 'name', fake_compound,
                                              expected_cas='63-39-2')
        self.assertFalse(ok)
        self.assertEqual(conf, 'rejected')

    def test_rejected_branch_returns_found_false(self):
        """源码级断言：rejected 分支的返回里 found 必须是 False，且带 rejected=True。"""
        import inspect
        src = inspect.getsource(PubChemEnhancer._resolve_to_properties_impl)
        # 找到 rejected 分支那段
        idx = src.find("if confidence == 'rejected':")
        self.assertGreater(idx, 0, '找不到 rejected 分支')
        seg = src[idx:idx + 700]
        self.assertIn("'found': False", seg,
                      'rejected 必须是"没找到可用结果"；found=True 会让前端渲染空预览')
        self.assertIn("'rejected': True", seg,
                      '需要独立标记，前端据此给"查到的是另一个化合物"的专门文案')


class CasHintTest(SimpleTestCase):
    """③ CAS 形态的 identifier 要有专门提示"""

    def setUp(self):
        self.enh = PubChemEnhancer()

    def test_cas_identifier_gets_dedicated_hint(self):
        r = self.enh._not_found('63-39-2')
        self.assertFalse(r['found'])
        self.assertIn('CAS', r['search_hint'])
        self.assertIn('不支持按 CAS', r['search_hint'],
                      '必须明确告知"CAS 不能作为检索键"，否则用户会以为是自己填错')
        self.assertIn('SMILES', r['search_hint'], '要给出可行的替代输入')

    def test_non_cas_identifier_keeps_generic_hint(self):
        r = self.enh._not_found('some unknown compound name')
        self.assertFalse(r['found'])
        self.assertIn('not found', r['search_hint'])
        self.assertNotIn('不支持按 CAS', r['search_hint'])

    def test_cas_pattern_matches_real_formats(self):
        cases = {
            '63-39-2': True,
            '2140-79-6': True,
            '50-78-2': True,
            '1234567-89-0': True,
            'uridine triphosphate': False,
            'SC8001-1': False,        # 我们的 SKU 编码不能被误判成 CAS
            '63-39': False,
            '63-39-2-1': False,
        }
        for s, expected in cases.items():
            got = bool(PubChemEnhancer._CAS_RE.match(s))
            self.assertEqual(got, expected, f'{s!r} 的 CAS 形态判定应为 {expected}')

    def test_sku_code_not_mistaken_for_cas(self):
        """★ SKU 编码（SC8001-1）绝不能被当成 CAS —— 否则会给错提示。"""
        r = self.enh._not_found('SC8001-1')
        self.assertNotIn('不支持按 CAS', r['search_hint'])
