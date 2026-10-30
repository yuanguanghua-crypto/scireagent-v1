"""
协议溯源四件套（doi / source_url / corpus_id / corpus_source）测试。

覆盖三条红线（对应 docs/PROTOCOL_MATERIALIZATION_PLAN.md §3.3）：
1. 字段默认空、序列化器只暴露 doi/source_url，**不暴露**内部 corpus_* 字段；
2. json-ld 输出 identifier(DOI) 与 isBasedOn(原文链接)；
3. backfill 命令：dry-run 绝不写库、apply 写四字段、**二次运行幂等**、
   标题不完全相等一律不写（宁 miss 不错配）、跨源同名且 DOI 冲突必须跳过。
"""
from django.core.management import call_command
from django.test import TestCase
import contextlib
import io
import json
import os
import tempfile

from apps.knowledge.models import Protocol


def _mk_protocol(name, **kw):
    return Protocol.objects.create(
        name=name,
        slug=name.lower().replace(' ', '-')[:200],
        version=kw.pop('version', '1.0'),
        **kw,
    )


class ProtocolProvenanceFieldTest(TestCase):
    def test_fields_default_to_empty(self):
        p = _mk_protocol('Untouched Protocol')
        self.assertEqual(p.doi, '')
        self.assertEqual(p.source_url, '')
        self.assertEqual(p.corpus_id, '')
        self.assertEqual(p.corpus_source, '')

    def test_detail_serializer_exposes_doi_and_url_only(self):
        p = _mk_protocol(
            'Provenance Visible',
            doi='10.21769/BioProtoc.1234',
            source_url='https://doi.org/10.21769/BioProtoc.1234',
            corpus_id='Bio-protocol-9999',
            corpus_source='bioprotocol',
        )
        from apps.knowledge.api.v1.serializers import ProtocolDetailSerializer
        data = ProtocolDetailSerializer(p, context={'request': None}).data
        self.assertEqual(data['doi'], '10.21769/BioProtoc.1234')
        self.assertEqual(data['source_url'], 'https://doi.org/10.21769/BioProtoc.1234')
        # 内部溯源字段刻意不对外
        self.assertNotIn('corpus_id', data)
        self.assertNotIn('corpus_source', data)

    def test_jsonld_carries_doi_and_basedon(self):
        p = _mk_protocol(
            'Jsonld Provenance',
            doi='10.1038/protex.2015.115',
            source_url='https://doi.org/10.1038/protex.2015.115',
        )
        from core.jsonld import build_protocol_jsonld
        data = build_protocol_jsonld(p, [], None)
        self.assertEqual(data['identifier']['propertyID'], 'DOI')
        self.assertEqual(data['identifier']['value'], '10.1038/protex.2015.115')
        self.assertEqual(data['isBasedOn'], 'https://doi.org/10.1038/protex.2015.115')

    def test_jsonld_omits_keys_when_absent(self):
        p = _mk_protocol('Jsonld No Provenance')
        from core.jsonld import build_protocol_jsonld
        data = build_protocol_jsonld(p, [], None)
        self.assertNotIn('identifier', data)
        self.assertNotIn('isBasedOn', data)


class BackfillProvenanceCommandTest(TestCase):
    """命令级测试：真实写临时语料 JSON，再跑命令。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='corpus_')
        self.corpus_dir = self.tmp

    def tearDown(self):
        for fn in os.listdir(self.tmp):
            os.remove(os.path.join(self.tmp, fn))
        os.rmdir(self.tmp)

    def _write_corpus(self, rows, filename='Bio-protocol.json'):
        with open(os.path.join(self.corpus_dir, filename), 'w', encoding='utf-8') as fh:
            json.dump(rows, fh, ensure_ascii=False)

    def _run(self, *args):
        # 用 redirect_stdout 而不是 call_command(stdout=...)：
        # 后者会让 Django 的 OutputWrapper 在测试销毁时仍持有已关闭的 StringIO，
        # 触发「I/O operation on closed file」噪音。
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            call_command('backfill_protocol_provenance',
                         '--corpus-dir', self.corpus_dir, *args)
        return buf.getvalue()

    def test_dry_run_never_writes(self):
        self._write_corpus([{
            'id': 'Bio-protocol-1', 'title': 'Alpha Protocol',
            'url': 'https://doi.org/10.21769/BioProtoc.5130',
        }])
        p = _mk_protocol('Alpha Protocol')
        self._run('--dry-run')
        p.refresh_from_db()
        self.assertEqual(p.doi, '')
        self.assertEqual(p.corpus_id, '')

    def test_apply_writes_four_fields(self):
        self._write_corpus([{
            'id': 'Bio-protocol-2290',
            'title': 'Nab Escaping AAV Mutants Isolated from Mouse Muscles',
            'url': 'https://doi.org/10.21769/BioProtoc.2841',
        }])
        p = _mk_protocol('Nab Escaping AAV Mutants Isolated from Mouse Muscles')
        self._run('--apply')
        p.refresh_from_db()
        self.assertEqual(p.doi, '10.21769/BioProtoc.2841')
        self.assertEqual(p.source_url, 'https://doi.org/10.21769/BioProtoc.2841')
        self.assertEqual(p.corpus_id, 'Bio-protocol-2290')
        self.assertEqual(p.corpus_source, 'bioprotocol')

    def test_second_run_is_idempotent(self):
        self._write_corpus([{
            'id': 'Bio-protocol-1', 'title': 'Alpha Protocol',
            'url': 'https://doi.org/10.21769/BioProtoc.5130',
        }])
        p = _mk_protocol('Alpha Protocol')
        self._run('--apply')
        first = Protocol.objects.get(pk=p.pk)
        self._run('--apply')
        second = Protocol.objects.get(pk=p.pk)
        self.assertEqual(first.doi, second.doi)
        self.assertEqual(first.corpus_id, second.corpus_id)

    def test_title_mismatch_is_not_written(self):
        """宁 miss 不错配：标题差一个词就不认。"""
        self._write_corpus([{
            'id': 'Bio-protocol-1', 'title': 'Alpha Protocol Detailed Version',
            'url': 'https://doi.org/10.21769/BioProtoc.5130',
        }])
        p = _mk_protocol('Alpha Protocol')
        self._run('--apply')
        p.refresh_from_db()
        self.assertEqual(p.doi, '')

    def test_punctuation_and_case_are_normalized(self):
        """归一化允许大小写与标点差异（实测语料标题与库名存在这类差异）。"""
        self._write_corpus([{
            'id': 'Protocol.io-1', 'title': 'Cell Viability: Protocol (using ATP)',
            'url': 'https://www.protocols.io/view/cell-viability-abc123',
        }], filename='Protocol-io.json')
        p = _mk_protocol('cell viability - protocol (using ATP)')
        self._run('--apply')
        p.refresh_from_db()
        self.assertEqual(p.corpus_id, 'Protocol.io-1')
        self.assertEqual(p.corpus_source, 'protocol_io')
        self.assertEqual(p.doi, '')  # protocols.io 无 DOI
        self.assertTrue(p.source_url.startswith('https://www.protocols.io/'))

    def test_conflicting_duplicates_are_skipped(self):
        """同一归一化标题在语料里指向两个不同 DOI ⇒ 跳过，不猜。"""
        self._write_corpus([
            {'id': 'A-1', 'title': 'Same Title', 'url': 'https://doi.org/10.1/aaa'},
            {'id': 'A-2', 'title': 'Same   Title', 'url': 'https://doi.org/10.1/bbb'},
        ])
        p = _mk_protocol('Same Title')
        self._run('--apply')
        p.refresh_from_db()
        self.assertEqual(p.corpus_id, '')

    def test_force_overwrites_existing(self):
        self._write_corpus([{
            'id': 'Bio-protocol-7', 'title': 'Force Me',
            'url': 'https://doi.org/10.21769/BioProtoc.7777',
        }])
        p = _mk_protocol('Force Me', corpus_id='OLD-ID', corpus_source='manual')
        self._run('--apply')            # 默认跳过已回填
        p.refresh_from_db()
        self.assertEqual(p.corpus_id, 'OLD-ID')
        self._run('--apply', '--force')  # 显式覆盖
        p.refresh_from_db()
        self.assertEqual(p.corpus_id, 'Bio-protocol-7')

    def test_verify_mode_reports_counts(self):
        _mk_protocol('X', doi='10.1/x', source_url='https://doi.org/10.1/x',
                     corpus_id='X-1', corpus_source='bioprotocol')
        out = self._run('--verify')
        self.assertIn('doi 非空', out)
