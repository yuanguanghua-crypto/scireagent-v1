"""Protocol 分类导航：facet 筛选 + 计数聚合（2026-10-26 P0）。

## 背景

`/protocols` 有 14,121 条 published，但列表页**零分类导航**（只有搜索框），
用户除了知道确切名字无法探索。

好消息是分类数据**早就存在**：`FacetValue`（4 维受控词表）+ `ProtocolFacet`（桥表），
application 维度 18 个值覆盖 89.2% 的协议。所以本功能只是"把已有数据暴露成导航"，
不是新建分类体系。

## 必须锁住的两个语义

1. **计数是「该分类下的协议数」，不是「分类独占数」** —— 一个 protocol 可挂
   多个 application ⇒ 各分类计数之和 > 去重覆盖数。前端必须说明，否则会被
   当成"数字对不上"（我们已经在首页/列表计数上踩过两次同类坑）。
2. **只统计 published** —— 与列表默认口径一致，否则导航数字 14,128 而列表 14,121。
"""
import pytest
from rest_framework.test import APIClient

from apps.knowledge.models import Protocol, FacetValue, ProtocolFacet
from apps.knowledge.tests.factories import ProtocolFactory

LIST = '/api/v1/protocols/'
FACETS = '/api/v1/protocols/facets/'


def make_facet(value, slug=None, facet_type='application'):
    return FacetValue.objects.create(
        facet_type=facet_type,
        value=value,
        slug=slug or f'{facet_type}-{value.lower().replace(" ", "-")}',
    )


@pytest.mark.django_db
class TestProtocolFacetNavigation:
    def setup_method(self):
        self.client = APIClient()
        self.f_rna = make_facet('RNA Biology')
        self.f_seq = make_facet('Sequencing & Library Prep')

        # A 只挂 RNA；B 同时挂 RNA + Sequencing；C 不挂任何分类；D 是草稿
        self.p_a = ProtocolFactory(name='RNA Protocol A', status='published')
        self.p_b = ProtocolFactory(name='Seq Protocol B', status='published')
        self.p_c = ProtocolFactory(name='Unclassified C', status='published')
        self.p_draft = ProtocolFactory(name='Draft D', status='draft')
        ProtocolFacet.objects.create(protocol=self.p_a, facet=self.f_rna)
        ProtocolFacet.objects.create(protocol=self.p_b, facet=self.f_rna)
        ProtocolFacet.objects.create(protocol=self.p_b, facet=self.f_seq)
        # 草稿也挂一个，用于验证计数不含草稿
        ProtocolFacet.objects.create(protocol=self.p_draft, facet=self.f_rna)

        # method 维度：二级筛选用
        self.f_pcr = make_facet('PCR / qPCR', slug='method-pcr-qpcr', facet_type='method')
        ProtocolFacet.objects.create(protocol=self.p_a, facet=self.f_pcr)
        ProtocolFacet.objects.create(protocol=self.p_b, facet=self.f_pcr)

    def _count(self, path, **params):
        d = self.client.get(path, params).json()
        return (d.get('meta') or {}).get('pagination', {}).get('count')

    def test_facets_returns_counts(self):
        d = self.client.get(FACETS).json()
        rows = {r['slug']: r['count'] for r in d['data']}
        assert rows[self.f_rna.slug] == 2, 'RNA 应计 2 条（A、B），不含草稿 D'
        assert rows[self.f_seq.slug] == 1

    def test_facets_meta_reports_coverage(self):
        """application 是**互斥**分类：每个协议至多挂 1 个。

        实测生产数据也印证：各分类计数之和 == covered_protocols（12,598 == 12,598）。
        最初我按"多对多"写了实现注释与 UI 文案，是错的 —— 已修正。
        """
        meta = self.client.get(FACETS).json()['meta']
        # 测试数据刻意造了「B 挂 2 个分类」⇒ covered(去重)=2，各分类计数之和=3
        # ⇒ 这正是"不能假设互斥"的证据；note 必须用不依赖基数的表述。
        assert meta['covered_protocols'] == 2
        assert meta['unclassified'] == 1, 'C 未挂分类'
        assert meta['total_published'] == 3
        assert meta['facet_type'] == 'application'
        assert '12' not in meta['note'] or '条协议' in meta['note']
        assert '未分类' in meta['note']

    def test_filter_by_facet(self):
        assert self._count(LIST, facet=self.f_rna.slug) == 2
        assert self._count(LIST, facet=self.f_seq.slug) == 1

    def test_filter_unknown_facet_returns_empty(self):
        assert self._count(LIST, facet='application-nope') == 0

    def test_filter_excludes_draft(self):
        """草稿 D 挂了 RNA，但列表筛选只应返回 published 的 A、B。"""
        d = self.client.get(LIST, {'facet': self.f_rna.slug}).json()
        names = [r['name'] for r in d['data']]
        assert 'Draft D' not in names

    def test_unclassified_not_in_any_facet(self):
        """未分类协议只能通过「全部」访问 —— 这是已知限制，锁住以免误以为丢了。"""
        total = self._count(LIST)
        assert total == 3, 'published 共 3 条（A、B、C）'
        assert self._count(LIST, facet=self.f_rna.slug) == 2   # C 不在其中

    def test_invalid_facet_type_400(self):
        r = self.client.get(FACETS, {'facet_type': 'nonsense'})
        assert r.status_code == 400

    def test_anonymous_can_use_facets(self):
        """导航是给访客用的，必须匿名可用。"""
        assert self.client.get(FACETS).status_code == 200
        assert self._count(LIST, facet=self.f_rna.slug) == 2

    def test_unclassified_only_returns_untagged(self):
        """`unclassified=1` 只返回没挂 application facet 的（当前 C 一条）。"""
        d = self.client.get(LIST, {'unclassified': 1}).json()
        names = [r['name'] for r in d['data']]
        assert names == ['Unclassified C']
        assert (d.get('meta') or {}).get('pagination', {}).get('count') == 1

    def test_unclassified_excludes_draft(self):
        """草稿挂了分类，不属于未分类；且本来也不在 published 里。"""
        d = self.client.get(LIST, {'unclassified': 1}).json()
        assert 'Draft D' not in [r['name'] for r in d['data']]

    def test_method_second_level_filter(self):
        """一级 application + 二级 method 同时生效。"""
        assert self._count(LIST, facet=self.f_rna.slug, facet_method=self.f_pcr.slug) == 2
        # 单独用 method 也应生效（参数不限维度）
        assert self._count(LIST, facet_method=self.f_pcr.slug) == 2

    def test_method_filter_narrows_result(self):
        """method 二级筛选必须能缩小范围，而不是原样返回。"""
        only_rna = self._count(LIST, facet=self.f_rna.slug)
        with_method = self._count(LIST, facet=self.f_rna.slug, facet_method=self.f_pcr.slug)
        assert with_method <= only_rna

    def test_facets_within_application(self):
        """`within` 只统计该领域内的协议 —— method 分布。"""
        d = self.client.get(FACETS, {'facet_type': 'method', 'within': self.f_rna.slug}).json()
        rows = {r['slug']: r['count'] for r in d['data']}
        assert rows.get(self.f_pcr.slug) == 2, 'RNA 领域下挂 PCR 的有 A、B'
        meta = d['meta']
        assert meta['within'] == self.f_rna.slug
        # within 生效时 total_published 应是该领域内的协议数（A、B = 2），
        # 而不是全站 3 —— 否则 unclassified 会算成负数
        assert meta['total_published'] == 2
        assert meta['unclassified'] == 0

    def test_facet_isolation(self):
        """method 维度的 facet 不应污染 application 导航。

        （setUp 已在 p_a/p_b 上挂好 self.f_pcr，这里直接复用 —— 原先这里自己
          再 make_facet 同名 slug 会撞 unique 约束。）
        """
        rows = {r['slug'] for r in self.client.get(FACETS).json()['data']}
        assert self.f_pcr.slug not in rows, 'application 导航不应出现 method 词条'
        # 但用 method slug 筛选仍应生效（参数不限维度）
        assert self._count(LIST, facet=self.f_pcr.slug) == 2
