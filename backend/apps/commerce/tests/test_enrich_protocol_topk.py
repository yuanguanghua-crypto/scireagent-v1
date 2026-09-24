"""★ F2 后端闸门（2026-09-24）：enrich 的 `protocol_top_k` 参数。

背景：`recommend_protocols_for_enrich` 本就在**全库**排序、只切片输出 ⇒ 放大 `top_k`
**几乎不增计算**，只增响应体。实测（14,084 协议，品名 `fluorescent labeled nucleotide`）：
`top_k=5 → 7.2KB/0.003s`｜`20 → 25.9KB/0.005s`｜`50 → 60.4KB/0.010s`｜`200 → 416.6KB/0.036s`
⇒ 上限取 **50**，默认仍 **5**。

本文件锁死的契约（三条都关乎"不引入新错误"）：
1. **默认 5** ⇒ 既有调用方（前端当前不传该参数、既有 spec）行为**逐字不变**。
2. **非法值静默回落 5，绝不 400/500** —— 这是"展示条数"的偏好参数，
   不该因为一个可选参数让整个 enrich（化学/文献/jena 全在其中）失败。
3. **上限 50** ⇒ 防止把响应体推到 400KB+（`top_k=200` 实测 416.6KB）。

⚠️ 端点用例的 mock **必须给 JSON 安全的显式返回值**：实测裸 `MagicMock` 会被塞进 DRF 响应，
序列化阶段 CPU spin 成"伪 hang"而**被 SIGTERM 杀掉**（本机历史坑，见 MEMORY「MagicMock CPU spin」）。
"""
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.commerce.api.v1.ai_views import (
    PROTOCOL_TOP_K_DEFAULT,
    PROTOCOL_TOP_K_MAX,
    _normalize_protocol_top_k,
)

User = get_user_model()


def _fake_validation_report():
    """与 test_ai_views._fake_validation_report 同形（字段显式赋值，避免裸 MagicMock 进序列化）。"""
    r = MagicMock()
    r.status = 'completed'
    r.pubchem_cid = None
    r.overall_match = True
    r.mismatches = []
    r.similar_compounds = []
    return r


def _fake_chemical():
    return {
        'source': 'pubchem', 'found': True, 'cid': 2244,
        'properties': {
            'canonical_smiles': 'CC(=O)OC1=CC=CC=C1C(=O)O',
            'molecular_formula': 'C9H8O4',
            'molecular_weight': 180.16,
            'synonyms': ['50-78-2', '2-Acetoxybenzoic acid'],
        },
        'cas_resolved': '50-78-2',
        'candidates': [],
    }


def _fake_literature():
    return {
        'applications': [], 'methods': [], 'references': [], 'protocols': [],
        'matched_apps': [], 'matched_methods': [],
        'unmatched_app_keywords': [], 'unmatched_method_keywords': [],
    }


class NormalizeProtocolTopKTest(TestCase):
    """归一化函数：非法/越界一律回落默认值。"""

    def test_defaults_and_bounds(self):
        self.assertEqual(_normalize_protocol_top_k(None), PROTOCOL_TOP_K_DEFAULT)
        self.assertEqual(_normalize_protocol_top_k(''), PROTOCOL_TOP_K_DEFAULT)
        self.assertEqual(_normalize_protocol_top_k('abc'), PROTOCOL_TOP_K_DEFAULT)
        self.assertEqual(_normalize_protocol_top_k(0), PROTOCOL_TOP_K_DEFAULT)
        self.assertEqual(_normalize_protocol_top_k(-7), PROTOCOL_TOP_K_DEFAULT)
        self.assertEqual(_normalize_protocol_top_k([1, 2]), PROTOCOL_TOP_K_DEFAULT)
        self.assertEqual(_normalize_protocol_top_k({'a': 1}), PROTOCOL_TOP_K_DEFAULT)

    def test_in_range_passthrough_and_clamp(self):
        self.assertEqual(_normalize_protocol_top_k(1), 1)
        self.assertEqual(_normalize_protocol_top_k('20'), 20)
        self.assertEqual(_normalize_protocol_top_k(PROTOCOL_TOP_K_MAX), PROTOCOL_TOP_K_MAX)
        self.assertEqual(_normalize_protocol_top_k(PROTOCOL_TOP_K_MAX + 1), PROTOCOL_TOP_K_MAX)
        self.assertEqual(_normalize_protocol_top_k(999999), PROTOCOL_TOP_K_MAX)


class EnrichProtocolTopKApiTest(TestCase):
    """端点级：参数被正确转发；非法值不得让端点失败。"""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            username='admin_topk', password='pass123', email='tk@test.com'
        )
        self.client.force_authenticate(user=self.admin)

    def _post(self, payload):
        """屏蔽一切外网依赖（PubChem / 文献 / 校验），只观察 top_k 转发。

        ★ 用 ExitStack 而非 `patch.stopall()`：后者会连带撤销框架自身安装的 patch，
          实测会把测试进程直接搞崩（SIGTERM）。
        """
        with ExitStack() as st:
            mock_proto = st.enter_context(
                patch('apps.commerce.api.v1.ai_views.recommend_protocols_for_enrich'))
            mock_proto.return_value = []
            st.enter_context(
                patch('apps.commerce.api.v1.ai_views.recommend_methods_for_enrich', return_value=[]))
            st.enter_context(patch(
                'apps.commerce.services.validators.product_validator.ProductValidator.validate',
                return_value=_fake_validation_report()))
            st.enter_context(patch(
                'apps.commerce.services.validators.pubchem_enhancer.PubChemEnhancer.resolve_to_properties',
                return_value=_fake_chemical()))
            st.enter_context(patch(
                'apps.knowledge.services.literature_recommender.LiteratureRecommender.recommend',
                return_value=_fake_literature()))
            resp = self.client.post('/api/v1/products/enrich/', payload, format='json')
        return resp, mock_proto

    def test_default_is_5_when_param_absent(self):
        resp, mock_proto = self._post({'product_name': 'pcr primer'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_proto.call_args.kwargs.get('top_k'), PROTOCOL_TOP_K_DEFAULT,
                         '不传参数时必须为默认 5（既有调用方行为不变）')

    def test_explicit_50_is_forwarded(self):
        resp, mock_proto = self._post({'product_name': 'pcr primer', 'protocol_top_k': 50})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_proto.call_args.kwargs.get('top_k'), 50)

    def test_illegal_values_fall_back_and_never_5xx(self):
        """类型不合法 / 非正数 ⇒ 回落默认 5；越界（类型合法）⇒ **夹到上限** 50（两种语义不同）。"""
        for bad in ['abc', '', 0, -1, None, [1]]:
            resp, mock_proto = self._post({'product_name': 'pcr primer', 'protocol_top_k': bad})
            self.assertEqual(resp.status_code, 200, f'非法值 {bad!r} 必须静默回落，不得 4xx/5xx')
            self.assertEqual(mock_proto.call_args.kwargs.get('top_k'), PROTOCOL_TOP_K_DEFAULT,
                             f'非法值 {bad!r} 应回落默认 5')
        for big in [PROTOCOL_TOP_K_MAX + 1, 999999]:
            resp, mock_proto = self._post({'product_name': 'pcr primer', 'protocol_top_k': big})
            self.assertEqual(resp.status_code, 200, f'越界值 {big!r} 必须夹到上限，不得 4xx/5xx')
            self.assertEqual(mock_proto.call_args.kwargs.get('top_k'), PROTOCOL_TOP_K_MAX,
                             f'越界值 {big!r} 应夹到上限 {PROTOCOL_TOP_K_MAX}（不是回落默认值）')
