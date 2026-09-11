"""TDD RED→GREEN：化学特异性读端静默置顶（chem-specific silent re-rank）。

覆盖 chem_specificity 服务的三个纯函数 + relevance 排序键/集成：
- keywords_for_product：S6 标签 → 受控词表关键词展开（无条目标签被过滤）
- is_chem_specific：基于 name/objective/principle 子串命中（含 U+2010 归一化）
- protocol_link_sort_key：chem 键插入后，chem 行静默置顶、weak 恒沉底
- build_protocol_links：行携带 chem_specific 且零新增查询

硬约束回放：本改造绝不删除链接、不改 relevance_score/tier/link_source、零 migration。
"""
from types import SimpleNamespace

import pytest

from apps.bridges.services.chem_specificity import (
    load_lexicon,
    keywords_for_product,
    is_chem_specific,
)
from apps.bridges.services.relevance import (
    protocol_link_sort_key,
    build_protocol_links,
)


def _product(tags):
    return SimpleNamespace(substructure_tags=tags)


def _protocol(**kw):
    # 默认补齐 scope_fields，避免 None 干扰子串判定
    return SimpleNamespace(
        name=kw.get('name', ''),
        objective=kw.get('objective', ''),
        principle=kw.get('principle', ''),
    )


# ---------------------------------------------------------------------------
# keywords_for_product
# ---------------------------------------------------------------------------
class TestKeywordsForProduct:
    def test_expands_propargyl_keywords_and_filters_unmapped_labels(self):
        p = _product({'parsed': True, 'labels': ['U', 'deoxy', 'NTP', 'Propargyl']})
        kws = keywords_for_product(p)
        # 没有词表条目的标签（U/deoxy/NTP）自然被过滤
        assert 'u' not in kws
        assert 'deoxy' not in kws
        assert 'ntp' not in kws
        # Propargyl 系列关键词完整展开
        for kw in ('propargyl', 'alkyn', 'ethynyl', 'click', 'cuaac', 'dbco', 'spaac', 'tetrazine'):
            assert kw in kws, f"缺失 Propargyl 关键词 {kw}"

    def test_none_tags_returns_empty(self):
        assert keywords_for_product(_product(None)) == set()

    def test_non_dict_tags_returns_empty(self):
        # substructure_tags 不是 dict（例如旧字符串/列表）→ 空
        assert keywords_for_product(_product(['U', 'Propargyl'])) == set()

    def test_parsed_false_returns_empty(self):
        assert keywords_for_product(_product({'parsed': False, 'labels': ['Biotin']})) == set()

    def test_load_lexicon_is_cached_and_non_empty(self):
        lex = load_lexicon()
        assert 'labels' in lex
        assert 'Propargyl' in lex['labels']
        assert load_lexicon() is lex  # 模块级缓存


# ---------------------------------------------------------------------------
# is_chem_specific
# ---------------------------------------------------------------------------
class TestIsChemSpecific:
    def test_biotin_positive(self):
        p = _product({'parsed': True, 'labels': ['Biotin']})
        proto = _protocol(name='x', objective='Cell surface protein biotinylation', principle='')
        assert is_chem_specific(p, proto) is True

    def test_2f_fluoro_negative(self):
        # 防回退：2'-F 标签绝不能用裸词 fluoro 误配 immunofluorescence
        p = _product({'parsed': True, 'labels': ["2'-F"]})
        proto = _protocol(
            name='x',
            objective='Human Islet Microvasculature Immunofluorescence in Optically Cleared Tissue',
            principle='',
        )
        assert is_chem_specific(p, proto) is False

    def test_no_chem_labels_false_even_with_click_text(self):
        p = _product({'parsed': True, 'labels': []})
        proto = _protocol(name='Click chemistry conjugation', objective='', principle='')
        assert is_chem_specific(p, proto) is False

    def test_no_product_keywords_short_circuits_false(self):
        # substructure_tags=None → 关键词为空 → 直接 False，不读协议文本
        p = _product(None)
        proto = _protocol(name='CuAAC click chemistry', objective='', principle='')
        assert is_chem_specific(p, proto) is False

    def test_normalization_propargyl_u2010(self):
        # U+2010 连字符（5‑Propargylamino‑dUTP 真实品名）必须被归一化命中
        p = _product({'parsed': True, 'labels': ['Propargyl']})
        name = '5\u2010Propargylamino\u2010dUTP labeling'
        proto = _protocol(name=name, objective='', principle='')
        assert is_chem_specific(p, proto) is True

    def test_normalization_principle_scope_field(self):
        # 命中也可发生在 principle 字段上
        p = _product({'parsed': True, 'labels': ['Propargyl']})
        proto = _protocol(name='Unrelated title', objective='', principle='CuAAC click cycloaddition of the alkyne')
        assert is_chem_specific(p, proto) is True


# ---------------------------------------------------------------------------
# protocol_link_sort_key
# ---------------------------------------------------------------------------
class TestSortKey:
    def test_chem_document_ranks_before_nonchem_literature(self):
        a = {'tier': 'document', 'chem_specific': True, 'relevance_score': 0.2, 'score_c': 0.0, 'id': 1}
        b = {'tier': 'literature', 'chem_specific': False, 'relevance_score': 0.9, 'score_c': 0.0, 'id': 2}
        rows = [b, a]
        rows.sort(key=protocol_link_sort_key)
        assert [r['id'] for r in rows] == [1, 2]

    def test_weak_still_sinks_below_any_non_weak(self):
        weak = {'tier': 'weak', 'chem_specific': True, 'relevance_score': 0.99, 'score_c': 0.0, 'id': 1}
        normal = {'tier': 'document', 'chem_specific': False, 'relevance_score': 0.1, 'score_c': 0.0, 'id': 2}
        rows = [normal, weak]
        rows.sort(key=protocol_link_sort_key)
        assert [r['id'] for r in rows] == [2, 1]

    def test_all_weak_chem_does_not_lift(self):
        # weak 行即便 chem_specific=True，也仍按 weak 沉底，不被顶起
        weak_chem = {'tier': 'weak', 'chem_specific': True, 'relevance_score': 0.99, 'score_c': 0.0, 'id': 1}
        weak_plain = {'tier': 'weak', 'chem_specific': False, 'relevance_score': 0.3, 'score_c': 0.0, 'id': 2}
        rows = [weak_chem, weak_plain]
        rows.sort(key=protocol_link_sort_key)
        # 仍是 weak 桶内比较（relevance 降序），weak_chem 不会跳到非 weak 之前
        assert [r['id'] for r in rows] == [1, 2]


# ---------------------------------------------------------------------------
# build_protocol_links 集成
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestBuildProtocolLinksIntegration:
    def _make(self, tags, proto_kwargs, pp_kwargs=None):
        from apps.bridges.tests.factories import ProductProtocolFactory
        from apps.commerce.tests.factories import ProductFactory
        from apps.knowledge.tests.factories import ProtocolFactory

        p = ProductFactory(substructure_tags=tags)
        proto = ProtocolFactory(status='published', **proto_kwargs)
        pp_kwargs = pp_kwargs or {}
        ProductProtocolFactory(product=p, protocol=proto, tier='document', relevance_score=0.5, **pp_kwargs)
        return p, proto

    def test_chem_specific_true_for_matching_protocol(self):
        p, _ = self._make(
            {'parsed': True, 'labels': ['Biotin'], 'axes': {}},
            {'name': 'Biotinylation assay', 'objective': 'Label surface proteins'},
        )
        rows = build_protocol_links(p)
        assert len(rows) == 1
        assert rows[0]['chem_specific'] is True

    def test_chem_specific_false_for_nonmatching_protocol(self):
        p, _ = self._make(
            {'parsed': True, 'labels': ['Biotin'], 'axes': {}},
            {'name': 'Generic PCR protocol', 'objective': 'Amplify template DNA'},
        )
        rows = build_protocol_links(p)
        assert rows[0]['chem_specific'] is False

    def test_no_extra_db_queries_for_chem_check(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        p, _ = self._make(
            {'parsed': True, 'labels': ['Propargyl'], 'axes': {}},
            {'name': 'CuAAC click labeling', 'objective': 'Conjugate alkyne modified nucleotide'},
        )
        with CaptureQueriesContext(connection) as ctx:
            rows = build_protocol_links(p)
        assert rows[0]['chem_specific'] is True
        # 仅 1 条查询（PP 主源 select_related('protocol')）；is_chem_specific 纯内存、零新增
        assert len(ctx.captured_queries) == 1, (
            f"预期 1 条查询，实际 {len(ctx.captured_queries)}:\n"
            + "\n".join(q['sql'] for q in ctx.captured_queries)
        )
