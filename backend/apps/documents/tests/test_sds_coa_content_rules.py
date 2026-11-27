"""SDS §11 与 COA Verdict 的内容规则（A-053 / A-055 / A-210，2026-11-27）。

这两条 QA 报告的共同病根：**模板把"没有数据"渲染成了肯定结论**。
- A-053：§2/§3 说 H315/H319，§11 却写死 "Not classified."
- A-055/210：COA 的 Verdict 只要填了结果就印 PASS（无规格也 PASS、不达标也 PASS）

本文件只钉**纯函数**（`_derive_section11` / `_verdict`）与默认模板的一致性，
不跑 PDF 渲染（那层由 e2e 的 H2/H5 覆盖）。
"""
import pytest

from apps.documents.services.coa_generator import _verdict
from apps.documents.services.pubchem_fetcher import (
    _GHS_FALLBACK,
    _derive_section11,
)


class TestSdsSection11DerivedFromHazardCodes:
    """A-053：§11 必须与 §2 的 H 码一致。"""

    def test_h315_h319_produce_classified_text(self):
        d = _derive_section11(['H302', 'H315', 'H319', 'H335'])
        assert 'H315' in d['skin_irritation']
        assert 'Category 2' in d['skin_irritation']
        assert 'H319' in d['eye_irritation']
        assert 'Category 2A' in d['eye_irritation']
        assert 'H335' in d['stot_single']
        # 关键：**不能**再出现"未分类"，那正是与 §2 打架的那句话
        for v in d.values():
            assert 'Not classified as' not in v

    def test_no_codes_means_not_classified_and_no_h_code_claim(self):
        d = _derive_section11([])
        assert 'no H315' in d['skin_irritation']
        assert 'no H319' in d['eye_irritation']
        # 未提供码时不得凭空写出 Category
        for v in d.values():
            assert 'Category' not in v

    def test_case_and_spacing_tolerant(self):
        d = _derive_section11([' h315 ', 'H319'])
        assert 'Category 2 (H315)' in d['skin_irritation']
        assert 'Category 2A (H319)' in d['eye_irritation']

    def test_default_template_section11_matches_section2_codes(self):
        """默认模板里 §2 与 §11 必须出自同一套码 —— 这是本条的回归闸门。"""
        codes = _GHS_FALLBACK['hazard_codes']
        derived = _derive_section11(codes)
        # 模板中 §11 用的就是同一组码派生出来的文本
        assert 'H315' in derived['skin_irritation']
        if 'H315' in codes:
            assert 'Not classified as a skin irritant' not in derived['skin_irritation']


class TestCoaVerdict:
    """A-055 / A-210：Verdict 必须真判定，判不了就 '—'。"""

    @pytest.mark.parametrize('spec,result,expected', [
        # 单侧下限
        ('≥98.0%', '99.1%', 'PASS'),
        ('≥98.0%', '85%', 'FAIL'),
        ('>=98', '98', 'PASS'),
        ('>90', '90', 'FAIL'),
        # 单侧上限
        ('≤0.5%', '0.3%', 'PASS'),
        ('≤0.5%', '0.9%', 'FAIL'),
        ('<5', '4.9', 'PASS'),
        # 区间（含连字符不能被读成负数 —— 实测踩过）
        ('98-102%', '100', 'PASS'),
        ('98-102%', '97', 'FAIL'),
        ('98.0 – 102.0', '101', 'PASS'),
        # 文本一致性
        ('Conforms', 'Conforms (pass)', 'PASS'),
        ('Conforms', 'Opaque liquid', 'FAIL'),
    ])
    def test_real_comparison(self, spec, result, expected):
        assert _verdict(spec, result) == expected

    @pytest.mark.parametrize('spec,result', [
        ('', '95%'),              # 无规格 ⇒ 判不了
        ('', 'Not tested'),
        ('MW: 523.4', '523.4'),   # 规格不是判定条件
        ('Visual', 'White powder'),
        ('≥98.0%', 'not numeric'),  # 结果不是数字
    ])
    def test_not_evaluated_instead_of_pass(self, spec, result):
        """★ 这条就是 QA 报的核心：改前一律 PASS。"""
        assert _verdict(spec, result) == '—'

    def test_empty_result_gives_empty_verdict(self):
        assert _verdict('≥98.0%', '') == ''
        assert _verdict('', '') == ''

    def test_no_fail_path_is_gone(self):
        """回归：改前的实现里没有任何 FAIL 分支，这里必须能产出 FAIL。"""
        assert _verdict('≤0.5%', '9%') == 'FAIL'
