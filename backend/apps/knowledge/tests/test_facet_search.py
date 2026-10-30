"""
搜索接入 facet 标签的测试（2026-10-30）。

修的 bug：搜索只看 `name` + `objective`，完全不看 facet 受控词表。
实测「搜 DNA extraction 只回 10 条协议，而 facet 里 `DNA Extraction & Purification`
实际标了 325 条」—— 差 32 倍。facet 是全库唯一收敛干净的分类层（121 个值），
搜索不用它等于把整理好的数据白放着。

两条硬约束：
1. 名称命中必须排在「仅 facet 命中」之前（否则 325 条 facet 结果会把真正匹配挤下去）
2. `meta.count`（返回条数）与 `meta.matched`（真实匹配总数）必须分开，
   前端才能说"共 N 条，显示前 10"
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.knowledge.models import FacetValue, Protocol, ProtocolFacet


def _kv(type_, value, slug, kind=''):
    return FacetValue.objects.create(facet_type=type_, value=value, slug=slug, kind=kind)


def _protocol(name, objective='', status='published'):
    return Protocol.objects.create(
        name=name, slug=f'p-{name.lower().replace(" ", "-")[:60]}',
        version='1.0', status=status, objective=objective)


class FacetSearchTest(TestCase):
    def setUp(self):
        self.c = APIClient()

    def _search(self, q):
        r = self.c.get('/api/v1/search', {'q': q})
        self.assertEqual(r.status_code, 200, r.content[:300])
        return r.json()

    def _grouped(self, q):
        r = self.c.get('/api/v1/search/grouped', {'q': q})
        self.assertEqual(r.status_code, 200)
        return r.json()

    def _facet_on(self, protocol, value, slug, type_='application'):
        fv = _kv(type_, value, slug)
        ProtocolFacet.objects.create(protocol=protocol, facet=fv, source='test')

    # ---------- 核心：facet 命中的协议要能被搜到 ----------

    def test_facet_only_match_is_found(self):
        """协议名字和 objective 都不含关键词，只靠 facet 标签命中 —— 必须能搜到。"""
        p = _protocol('Totally Unrelated Name', objective='nothing here')
        self._facet_on(p, 'DNA Extraction & Purification', 'dna-extraction-purification')

        data = self._search('DNA extraction')
        ids = [x['id'] for x in data['data'] if x['type'] == 'protocol']
        self.assertIn(p.id, ids)

    def test_protocol_without_facet_and_without_keyword_not_found(self):
        p = _protocol('Something Else', objective='unrelated')
        data = self._search('DNA extraction')
        ids = [x['id'] for x in data['data'] if x['type'] == 'protocol']
        self.assertNotIn(p.id, ids)

    # ---------- 排序：名称命中优先 ----------

    def test_name_match_ranks_above_facet_only_match(self):
        name_hit = _protocol('DNA extraction kit protocol')
        facet_hit = _protocol('Zzz Unrelated')
        self._facet_on(facet_hit, 'DNA Extraction & Purification', 'dna-extraction-purification')

        data = self._search('DNA extraction')
        ids = [x['id'] for x in data['data'] if x['type'] == 'protocol']
        self.assertIn(name_hit.id, ids)
        self.assertIn(facet_hit.id, ids)
        self.assertLess(ids.index(name_hit.id), ids.index(facet_hit.id),
                        '名称命中必须排在仅 facet 命中之前')

    # ---------- matched vs count ----------

    def test_meta_matched_exceeds_returned_count(self):
        """matched 是真实总数，count 是返回条数 —— 两者必须分开。"""
        # facet_value 有 (facet_type, kind, value) 唯一约束 ⇒ 复用一个值，挂多条协议
        fv = _kv('application', 'DNA Extraction & Purification', 'dna-extraction-purification')
        for i in range(12):
            p = _protocol(f'DNA extraction variant {i}')
            ProtocolFacet.objects.create(protocol=p, facet=fv, source='test')
        data = self._search('DNA extraction')
        proto_returned = len([x for x in data['data'] if x['type'] == 'protocol'])
        self.assertLessEqual(proto_returned, 10)
        self.assertGreaterEqual(data['meta']['matched']['protocols'], 12)

    def test_grouped_also_returns_matched(self):
        p = _protocol('Unrelated', objective='')
        self._facet_on(p, 'DNA Extraction & Purification', 'dna-extraction-purification')
        data = self._grouped('DNA extraction')
        self.assertGreaterEqual(data['meta']['matched']['protocols'], 1)
        self.assertIn(p.id, [x['id'] for x in data['data']['protocols']])

    # ---------- 列表页 ?search= 同口径 ----------

    def test_list_search_hits_facet(self):
        """从搜索页点「查看全部」跳到列表页时，?search= 也必须能命中 facet，
        否则用户会看到一个空列表。"""
        p = _protocol('Unrelated Name', objective='')
        self._facet_on(p, 'DNA Extraction & Purification', 'dna-extraction-purification')
        r = self.c.get('/api/v1/protocols/', {'search': 'DNA extraction'})
        self.assertEqual(r.status_code, 200)
        ids = [x['id'] for x in r.json()['data']]
        self.assertIn(p.id, ids)

    def test_list_search_still_hits_name(self):
        p = _protocol('DNA extraction by phenol')
        r = self.c.get('/api/v1/protocols/', {'search': 'DNA extraction'})
        self.assertIn(p.id, [x['id'] for x in r.json()['data']])

    # ---------- 不回归：搜不到无关词 ----------

    def test_unrelated_query_returns_nothing(self):
        p = _protocol('DNA extraction by phenol')
        self._facet_on(p, 'DNA Extraction & Purification', 'dna-extraction-purification')
        r = self.c.get('/api/v1/protocols/', {'search': 'zzzz-nonexistent-term'})
        self.assertEqual(r.json()['meta']['pagination']['count'], 0)

    # ---------- 公开可见性不被绕过 ----------

    def test_archived_protocol_not_returned_even_if_facet_matches(self):
        p = _protocol('Archived One', status='archived')
        self._facet_on(p, 'DNA Extraction & Purification', 'dna-extraction-purification')
        data = self._search('DNA extraction')
        ids = [x['id'] for x in data['data'] if x['type'] == 'protocol']
        self.assertNotIn(p.id, ids)
