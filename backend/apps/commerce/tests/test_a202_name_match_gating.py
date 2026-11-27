"""名字匹配收紧（A-202，2026-11-27）—— "瞎编一个名字也给候选"的三处漏洞。

## 实测复现（本地真跑，不是推测）
`_fallback_search_by_tokens('TEST-NON-EXIST-20261110')` 返回的正是 QA 报的那 4 个 CID
（54680032 / 54682465 / 170915471 / 176473205）。逐 token 定位：

    TEST  → 那 4 个香豆素/噻唑类化合物（PubChem 的 name 端点是模糊匹配）
    NON   → decanoic acid 等
    EXIST → 空

根因有三层，本文件逐层钉住：
① 降级搜索拿**英文通用词**当化学名去搜；
② 名字回验用**同一批 token** 做子串匹配 ⇒ 自证恒真（`non` 命中 `nonanoate`）；
③ ChEMBL 的 `?q=` 是全文检索，对任意字符串都给 5 条 ⇒ 又绕回来了。
"""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.commerce.services.validators.pubchem_enhancer import PubChemEnhancer


def _compound(name='', synonyms=None, formula=''):
    return SimpleNamespace(
        iupac_name=name,
        synonyms=synonyms or [],
        molecular_formula=formula,
    )


class SignificantTokenTest(SimpleTestCase):
    """① 片段必须像化学名。"""

    def test_nonsense_name_has_no_significant_token(self):
        assert PubChemEnhancer._significant_tokens('TEST-NON-EXIST-20261110') == []

    def test_common_words_only_are_rejected(self):
        for name in ('sample batch', 'unknown product', 'demo item', 'new grade'):
            assert PubChemEnhancer._significant_tokens(name) == [], name

    def test_real_chemical_tokens_survive(self):
        # 'Biotin' 属化学通用片段（母核名），必须让位给有辨识度的 'ddUTP'
        assert PubChemEnhancer._significant_tokens('Biotin-16-ddUTP') == ['ddUTP']
        assert PubChemEnhancer._significant_tokens('SC8001') == ['SC8001']
        assert PubChemEnhancer._significant_tokens('Aspirin') == ['Aspirin']

    def test_pure_digits_rejected(self):
        assert PubChemEnhancer._significant_tokens('20261110') == []

    def test_lowercase_long_word_with_digit_passes(self):
        # 含数字的片段一律算"像化学名"（SC8001 / 16-ddUTP 这类）
        assert PubChemEnhancer._is_chemistry_like_token('abc123') is True

    def test_short_lowercase_word_rejected(self):
        assert PubChemEnhancer._is_chemistry_like_token('acid') is False

    def test_real_chemical_name_in_normal_case_passes(self):
        """★ 回归：'Aspirin' 全小写、无数字 —— 第一版把这类**真名**误杀了。"""
        assert PubChemEnhancer._is_chemistry_like_token('Aspirin') is True
        assert PubChemEnhancer._is_chemistry_like_token('Ibuprofen') is True


class MoietyWordSplitTest(SimpleTestCase):
    """化学母核词在「搜索」与「回验」里要求相反 —— 两套表不能合并。

    合并会二选一地出错：
      · 当成通用词禁掉 ⇒ "CTP labeling kit" 这种真名回验失败（实测既有用例红）；
      · 当成有效片段 ⇒ "Biotin" 抢在 "ddUTP" 前被搜，结果全是 biotin 衍生物。
    """

    def test_search_excludes_moieties(self):
        assert PubChemEnhancer._significant_tokens('Biotin-16-ddUTP') == ['ddUTP']

    def test_reverse_check_keeps_moieties(self):
        toks = PubChemEnhancer._significant_tokens('CTP labeling kit', allow_moieties=True)
        assert 'CTP' in toks

    def test_moiety_is_still_not_an_english_filler_word(self):
        # 'biotin' 只是母核词，不是填充词 —— 回验时必须可用
        assert PubChemEnhancer._is_chemistry_like_token('biotin', allow_moieties=True) is True
        assert PubChemEnhancer._is_chemistry_like_token('biotin') is False
        # 而真·填充词两边都不算
        assert PubChemEnhancer._is_chemistry_like_token('test', allow_moieties=True) is False


class FallbackSearchGateTest(SimpleTestCase):
    """① 的落地：没有显著片段时**不许发请求**。"""

    def test_no_api_call_when_name_looks_unchemical(self):
        e = PubChemEnhancer()
        with patch.object(e, '_search_by_namespace') as m:
            assert e._fallback_search_by_tokens('TEST-NON-EXIST-20261110') == []
            m.assert_not_called()

    def test_api_called_with_the_significant_token(self):
        e = PubChemEnhancer()
        with patch.object(e, '_search_by_namespace', return_value=[object()]) as m:
            out = e._fallback_search_by_tokens('Biotin-16-ddUTP')
            assert out
            assert any(c.args[0] == 'ddUTP' for c in m.call_args_list), (
                f'应当拿 ddUTP 去搜，实际调用 {m.call_args_list}')


class NameReverseCheckTest(SimpleTestCase):
    """② 回验必须整词匹配，且不吃通用词。"""

    def test_common_word_only_identifier_fails(self):
        e = PubChemEnhancer()
        c = _compound(name='Nonanoic acid', synonyms=['nonanoic acid'], formula='C9H18O2')
        assert e._name_reverse_check('TEST-NON-EXIST-20261110', c) is False, (
            '★ 旧实现用子串匹配，`non` 会命中 nonanoic/nonanoate ⇒ 自证通过'
        )

    def test_substring_is_not_enough(self):
        e = PubChemEnhancer()
        c = _compound(name='Nonanoic acid', synonyms=['nonanoic acid'])
        # 'non' 是 nonanoic 的子串，但不是整词
        assert e._name_reverse_check('non', c) is False

    def test_whole_token_hit_passes(self):
        e = PubChemEnhancer()
        c = _compound(name='Uridine triphosphate', synonyms=['UTP', 'ddUTP'])
        assert e._name_reverse_check('Biotin-16-ddUTP', c) is True

    def test_chinese_name_cannot_be_verified_so_passes(self):
        """中文名没有 ASCII 片段 ⇒ 无从回验，沿用旧口径放行（下游仍 requires_review）。"""
        e = PubChemEnhancer()
        c = _compound(name='Any compound', synonyms=['whatever'])
        assert e._name_reverse_check('尿苷三磷酸', c) is True

    def test_no_synonyms_passes(self):
        e = PubChemEnhancer()
        assert e._name_reverse_check('whatever', _compound(synonyms=[])) is True


class ChemblGateTest(SimpleTestCase):
    """③ ChEMBL 全文检索也要过闸。"""

    def test_nonsense_name_never_hits_chembl(self):
        e = PubChemEnhancer()
        with patch('apps.commerce.services.validators.pubchem_enhancer.request_with_resilience') as m:
            out = e._chembl_search('TEST-NON-EXIST-20261110', namespace='name')
            assert out['found'] is False
            assert out['candidates'] == []
            assert 'does not look like a chemical name' in (out.get('search_hint') or '')
            m.assert_not_called()

    def test_hits_without_name_match_are_dropped(self):
        e = PubChemEnhancer()
        fake = SimpleNamespace(
            ok=True,
            json=lambda: {'molecules': [
                {'molecule_chembl_id': 'CHEMBL1', 'pref_name': 'UNRELATED THING',
                 'molecule_properties': {}, 'molecule_structures': {}},
            ]},
        )
        with patch('apps.commerce.services.validators.pubchem_enhancer.request_with_resilience',
                   return_value=fake):
            out = e._chembl_search('ddUTP', namespace='name')
        assert out['found'] is False, '名字对不上的 ChEMBL 命中必须丢掉'

    def test_smiles_namespace_not_gated_by_name_rules(self):
        """smiles/inchi 这类标识符本来就不像单词，不能被名字闸门挡住。"""
        e = PubChemEnhancer()
        fake = SimpleNamespace(ok=True, json=lambda: {'molecules': [
            {'molecule_chembl_id': 'CHEMBL2', 'pref_name': 'Something',
             'molecule_properties': {}, 'molecule_structures': {}},
        ]})
        with patch('apps.commerce.services.validators.pubchem_enhancer.request_with_resilience',
                   return_value=fake):
            out = e._chembl_search('CC(=O)O', namespace='smiles')
        assert out['found'] is True
