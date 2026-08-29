"""Evidence Miner v0 生产版单测（移植 pilot 14 例 + Method 匹配）。

FakeClient 模拟 PubMed，零网络。覆盖：语法/空输入/大小写/全名变体/低覆盖率拒绝/
U+2011 归一化/零命中/信号映射/上限/并集去重/Method 标题匹配。
"""
import unittest

from apps.bridges.services.evidence_miner import (
    build_terms, build_query, count_signals, match_methods_in_title,
    mine_product, _norm_text,
)


class FakeClient:
    """模拟 PubMed：esearch 逐项返回 idlist，esummary 返回 docs。"""

    def __init__(self, idlist=None, docs=None, count=0, by_term=None):
        self.idlist = idlist or []
        self.docs = docs or {}
        self.count = count
        self.by_term = by_term

    def esearch(self, term, retmax=5):
        if self.by_term is not None:
            hit = self.by_term.get(term)
            if hit is None:
                return {'count': '0', 'idlist': []}
            return {'count': str(hit.get('count', len(hit['idlist']))),
                    'idlist': hit['idlist']}
        return {'count': str(self.count), 'idlist': self.idlist}

    def esummary(self, ids):
        return {'uids': ids, **{str(i): self.docs.get(int(i)) for i in ids}}

    def efetch_one(self, pmid):
        doc = self.docs.get(int(pmid)) or {}
        return doc.get('abstract', '')


PROD = {'id': 1, 'name': 'Fluorescein-12-UTP',
        'synonyms': ['12-Fluorescein-UTP'], 'cas': '134367-01-4'}


class NormTextTests(unittest.TestCase):
    def test_nonbreaking_hyphen_normalized(self):
        self.assertEqual(_norm_text('5\u2011Propargylamino\u2011CTP'),
                         '5-propargylamino-ctp')

    def test_prime_variants_normalized(self):
        self.assertEqual(_norm_text("5-iodo-2\u2032-deoxyuridine"),
                         "5-iodo-2'-deoxyuridine")


class BuildTermsTests(unittest.TestCase):
    def test_terms_cover_name_synonyms_cas(self):
        terms = build_terms('Fluorescein-12-UTP', ['12-Fluorescein-UTP'],
                            '134367-01-4')
        self.assertEqual(terms, ['"fluorescein-12-utp"',
                                 '"12-fluorescein-utp"', '"134367-01-4"'])

    def test_empty_terms_when_no_identifiers(self):
        self.assertEqual(build_terms('', [], ''), [])

    def test_query_joins_terms(self):
        q = build_query('Fluorescein-12-UTP', [], '134367-01-4')
        self.assertIn('"fluorescein-12-utp"', q)
        self.assertIn('"134367-01-4"', q)
        self.assertEqual(q, ' OR '.join(build_terms('Fluorescein-12-UTP', [],
                                                    '134367-01-4')))


class CountSignalsTests(unittest.TestCase):
    def test_both_signals(self):
        names, cas = count_signals(
            'Synthesis of 134367-01-4 and Fluorescein-12-UTP derivatives',
            'Fluorescein-12-UTP', ['12-Fluorescein-UTP'], '134367-01-4')
        self.assertTrue(names and cas)

    def test_name_only(self):
        names, cas = count_signals(
            'Fluorescein-12-UTP for RNA labeling',
            'Fluorescein-12-UTP', [], '999-99-9')
        self.assertTrue(names)
        self.assertFalse(cas)

    def test_case_insensitive(self):
        names, cas = count_signals(
            'fluorescein-12-utp and CAS 134367-01-4',
            'Fluorescein-12-UTP', [], '134367-01-4')
        self.assertTrue(names and cas)

    def test_fullname_variant_with_spaces(self):
        # 全名「5-iodo-2'-deoxyuridine 5'-triphosphate」空格/撇号变体 → 词元覆盖命中
        names, cas = count_signals(
            "5-iodo-2'-deoxyuridine 5'-triphosphate, an allosteric inhibitor",
            '5-Iodo-dUTP', ["5-Iodo-2'-deoxyuridine-5'-Triphosphate"], '3731-55-3')
        self.assertTrue(names)

    def test_low_coverage_is_rejected(self):
        names, cas = count_signals('Methoxy derivatives in kinase research',
                                   '5-Methoxy-UTP', [], '999-99-9')
        self.assertFalse(names and cas)


class MatchMethodsTests(unittest.TestCase):
    METHODS = [
        {'id': 1, 'name': 'DNA Polymerase', 'slug': 'dna-polymerase'},
        {'id': 2, 'name': 'Nanopore Sequencing', 'slug': 'nanopore-sequencing'},
        {'id': 3, 'name': 'Reverse Transcription', 'slug': 'reverse-transcription'},
    ]

    def test_title_mentions_method_matches(self):
        hits = match_methods_in_title(
            'Nanopore sequencing of modified RNA', self.METHODS)
        self.assertEqual([h['id'] for h in hits], [2])

    def test_no_method_in_title_returns_empty(self):
        hits = match_methods_in_title('Synthesis of thiouridine triphosphate',
                                      self.METHODS)
        self.assertEqual(hits, [])

    def test_multiple_methods_sorted_by_coverage(self):
        hits = match_methods_in_title(
            'DNA polymerase and reverse transcription assay', self.METHODS)
        self.assertGreaterEqual(len(hits), 2)
        # 降序：第一个覆盖率最高
        self.assertTrue(hits[0]['coverage'] >= hits[-1]['coverage'])


class MineProductTests(unittest.TestCase):
    def test_zero_hits_returns_empty(self):
        r = mine_product(FakeClient(idlist=[], count=0), PROD)
        self.assertEqual(r['candidates'], [])

    def test_name_signal_maps_to_medium(self):
        client = FakeClient(
            idlist=['111'], count=1,
            docs={111: {'title': 'Use of Fluorescein-12-UTP in situ',
                        'source': 'Methods Mol Biol', 'pubdate': '2020'}})
        r = mine_product(client, PROD)
        self.assertEqual(len(r['candidates']), 1)
        self.assertEqual(r['candidates'][0]['strength'], 'medium')

    def test_name_plus_cas_maps_to_high(self):
        client = FakeClient(
            idlist=['222'], count=1,
            docs={222: {'title': '134367-01-4 (Fluorescein-12-UTP) probe',
                        'source': 'Biochemistry', 'pubdate': '2019'}})
        r = mine_product(client, PROD)
        self.assertEqual(r['candidates'][0]['strength'], 'high')

    def test_no_title_signal_is_excluded(self):
        client = FakeClient(
            idlist=['333'], count=1,
            docs={333: {'title': 'Unrelated kinase assay',
                        'source': 'Nature', 'pubdate': '2018'}})
        r = mine_product(client, PROD)
        self.assertEqual(r['candidates'], [])
        self.assertEqual(len(r['excluded']), 1)

    def test_candidates_capped_at_three(self):
        docs = {i: {'title': f'Fluorescein-12-UTP study {i}',
                    'source': 'J', 'pubdate': '2021'} for i in range(1, 6)}
        r = mine_product(FakeClient(idlist=[str(i) for i in range(1, 6)],
                                    count=5, docs=docs), PROD)
        self.assertLessEqual(len(r['candidates']), 3)

    def test_per_term_search_unions_and_dedupes(self):
        t1, t2 = '"fluorescein-12-utp"', '"12-fluorescein-utp"'
        docs = {101: {'title': 'Fluorescein-12-UTP for labeling',
                      'source': 'J', 'pubdate': '2020'},
                102: {'title': 'unrelated', 'source': 'J', 'pubdate': '2020'},
                103: {'title': 'Fluorescein-12-UTP assay', 'source': 'J',
                      'pubdate': '2021'}}
        client = FakeClient(
            by_term={t1: {'idlist': ['101', '102'], 'count': 2},
                     t2: {'idlist': ['101', '103'], 'count': 2}},
            docs=docs)
        r = mine_product(client, PROD)
        self.assertEqual(r['esearch_count'], 3)
        self.assertEqual(len(r['candidates']), 2)

    def test_candidates_enriched_with_abstract(self):
        """v0.2：候选附 record_text（标题+摘要），供方法级匹配提召回。"""
        docs = {111: {'title': 'Fluorescein-12-UTP modified nucleotide study',
                      'source': 'J', 'pubdate': '2020',
                      'abstract': 'We used Fluorescein-12-UTP with DNA polymerase '
                                  'in reverse transcription experiments.'}}
        client = FakeClient(
            by_term={'"fluorescein-12-utp"': {'idlist': ['111'], 'count': 1},
                     '"12-fluorescein-utp"': {'idlist': [], 'count': 0}},
            docs=docs)
        r = mine_product(client, PROD)
        self.assertEqual(len(r['candidates']), 1)
        cand = r['candidates'][0]
        self.assertIn('DNA polymerase', cand['record_text'])
        self.assertIn('reverse transcription', cand['record_text'])


if __name__ == '__main__':
    unittest.main()
