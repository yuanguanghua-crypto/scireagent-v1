"""
TDD RED: backfill_protocol_objective 命令（任务2 — BioProCorpus 协议正文回填）。

背景：#400 导入 13971 条 source='bioprocorpus' 的 Protocol 时只写了 name/slug/source，
正文字段全空。轴A(`_protocol_q_text`) 与轴C(`_protocol_embedding`) 都拼接 objective，
故协议侧文本实际只有标题 → 相关性排序退化为"标题匹配"。

本命令从本地 BioProCorpus 源目录（backend/data/bioprocorpus/*.json）读取
`title` → `abstract`，按 Protocol.name.strip() == title.strip() 回填 objective。

运行时应 FAIL（命令模块尚不存在）。

GREEN 后契约：
- 数据源默认 settings.BASE_DIR/data/bioprocorpus，可用 --path 覆盖目录
- 只扫描含 title+abstract 的记录；缺字段的文件/记录静默跳过（ERR/GEN/ORD/PQA 等）
- 仅回填 source='bioprocorpus' 的 Protocol；curated 人工策展库绝不改动
- 空值安全：abstract 为空 → 跳过，不写空串
- 不覆盖：objective 已非空 → 跳过（除非 --force）
- 幂等：重复运行结果一致
- --dry-run 只报告不落库
"""
import json
import os

from django.core.management import call_command
from django.test import TestCase

from apps.knowledge.models import Protocol


def _write_source(tmpdir, filename, records):
    os.makedirs(tmpdir, exist_ok=True)
    with open(os.path.join(tmpdir, filename), 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False)


class BackfillProtocolObjectiveCommandTest(TestCase):
    def setUp(self):
        import tempfile
        self.src_dir = tempfile.mkdtemp(prefix='bpc_src_')

    def test_command_module_importable(self):
        from apps.knowledge.management.commands import (  # noqa: F401
            backfill_protocol_objective,
        )

    def test_fills_objective_from_abstract(self):
        _write_source(self.src_dir, 'Bio-protocol.json', [
            {'id': 1, 'title': 'CuAAC RNA Labeling', 'abstract': 'Click chemistry labeling of RNA.'},
        ])
        p = Protocol.objects.create(
            name='CuAAC RNA Labeling', slug='cuaac-rna-labeling',
            source=Protocol.Source.BIOPROCORPUS, objective='',
        )
        call_command('backfill_protocol_objective', '--path', self.src_dir)
        p.refresh_from_db()
        self.assertEqual(p.objective, 'Click chemistry labeling of RNA.')

    def test_matches_on_stripped_title(self):
        """源标题带首尾空白也应命中（#400 入库时做过 strip）。"""
        _write_source(self.src_dir, 'Protocol-io.json', [
            {'title': '  Western Blot  ', 'abstract': 'Detect proteins by immunoblotting.'},
        ])
        p = Protocol.objects.create(
            name='Western Blot', slug='western-blot',
            source=Protocol.Source.BIOPROCORPUS, objective='',
        )
        call_command('backfill_protocol_objective', '--path', self.src_dir)
        p.refresh_from_db()
        self.assertEqual(p.objective, 'Detect proteins by immunoblotting.')

    def test_never_touches_curated_protocols(self):
        _write_source(self.src_dir, 'Bio-protocol.json', [
            {'title': 'Curated Only', 'abstract': 'SHOULD NOT BE WRITTEN'},
        ])
        p = Protocol.objects.create(
            name='Curated Only', slug='curated-only',
            source=Protocol.Source.CURATED, objective='',
        )
        call_command('backfill_protocol_objective', '--path', self.src_dir)
        p.refresh_from_db()
        self.assertEqual(p.objective, '', '人工策展库协议不得被 BioProCorpus 正文覆盖')

    def test_skips_empty_abstract(self):
        _write_source(self.src_dir, 'Bio-protocol.json', [
            {'title': 'No Abstract Here', 'abstract': '   '},
            {'title': 'Missing Abstract Key'},
        ])
        a = Protocol.objects.create(
            name='No Abstract Here', slug='no-abstract-here',
            source=Protocol.Source.BIOPROCORPUS, objective='',
        )
        b = Protocol.objects.create(
            name='Missing Abstract Key', slug='missing-abstract-key',
            source=Protocol.Source.BIOPROCORPUS, objective='',
        )
        call_command('backfill_protocol_objective', '--path', self.src_dir)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(a.objective, '')
        self.assertEqual(b.objective, '')

    def test_does_not_overwrite_existing_objective(self):
        _write_source(self.src_dir, 'Bio-protocol.json', [
            {'title': 'Already Filled', 'abstract': 'NEW TEXT'},
        ])
        p = Protocol.objects.create(
            name='Already Filled', slug='already-filled',
            source=Protocol.Source.BIOPROCORPUS, objective='OLD TEXT',
        )
        call_command('backfill_protocol_objective', '--path', self.src_dir)
        p.refresh_from_db()
        self.assertEqual(p.objective, 'OLD TEXT')

    def test_force_overwrites_existing_objective(self):
        _write_source(self.src_dir, 'Bio-protocol.json', [
            {'title': 'Already Filled', 'abstract': 'NEW TEXT'},
        ])
        p = Protocol.objects.create(
            name='Already Filled', slug='already-filled',
            source=Protocol.Source.BIOPROCORPUS, objective='OLD TEXT',
        )
        call_command('backfill_protocol_objective', '--path', self.src_dir, '--force')
        p.refresh_from_db()
        self.assertEqual(p.objective, 'NEW TEXT')

    def test_dry_run_does_not_persist(self):
        _write_source(self.src_dir, 'Bio-protocol.json', [
            {'title': 'Dry Run Target', 'abstract': 'Some abstract.'},
        ])
        p = Protocol.objects.create(
            name='Dry Run Target', slug='dry-run-target',
            source=Protocol.Source.BIOPROCORPUS, objective='',
        )
        call_command('backfill_protocol_objective', '--path', self.src_dir, '--dry-run')
        p.refresh_from_db()
        self.assertEqual(p.objective, '')

    def test_idempotent(self):
        _write_source(self.src_dir, 'Bio-protocol.json', [
            {'title': 'Run Twice', 'abstract': 'Stable abstract.'},
        ])
        p = Protocol.objects.create(
            name='Run Twice', slug='run-twice',
            source=Protocol.Source.BIOPROCORPUS, objective='',
        )
        call_command('backfill_protocol_objective', '--path', self.src_dir)
        call_command('backfill_protocol_objective', '--path', self.src_dir)
        p.refresh_from_db()
        self.assertEqual(p.objective, 'Stable abstract.')

    def test_ignores_files_without_title_abstract(self):
        """ERR/GEN/ORD/PQA 等非协议文件不应导致崩溃。"""
        _write_source(self.src_dir, 'GEN.json', [
            {'system_prompt': 'x', 'instruction': 'y', 'output': 'z', 'id': 1},
        ])
        _write_source(self.src_dir, 'Bio-protocol.json', [
            {'title': 'Mixed Dir', 'abstract': 'Real abstract.'},
        ])
        p = Protocol.objects.create(
            name='Mixed Dir', slug='mixed-dir',
            source=Protocol.Source.BIOPROCORPUS, objective='',
        )
        call_command('backfill_protocol_objective', '--path', self.src_dir)
        p.refresh_from_db()
        self.assertEqual(p.objective, 'Real abstract.')

    # ---- 扩展字段来源（B 类改进③）：abstract 为空时回退其他正文字段 ----

    def test_falls_back_to_protocol_field_when_abstract_empty(self):
        """源记录 abstract 为空但 protocol 字段有内容 → 用 protocol 回填。"""
        _write_source(self.src_dir, 'Bio-protocol.json', [
            {'id': 1, 'title': 'RNA Extraction',
             'protocol': 'Lyse cells, add TRIzol, centrifuge.'},
        ])
        p = Protocol.objects.create(
            name='RNA Extraction', slug='rna-extraction',
            source=Protocol.Source.BIOPROCORPUS, objective='',
        )
        call_command('backfill_protocol_objective', '--path', self.src_dir)
        p.refresh_from_db()
        self.assertEqual(p.objective, 'Lyse cells, add TRIzol, centrifuge.')

    def test_falls_back_through_priority_order(self):
        """abstract 空时按 protocol>description>method>hierarchical_protocol 优先级取首个非空。"""
        _write_source(self.src_dir, 'Bio-protocol.json', [
            {'id': 1, 'title': 'X',
             'description': 'Desc only', 'method': 'Method text'},
        ])
        p = Protocol.objects.create(
            name='X', slug='x', source=Protocol.Source.BIOPROCORPUS, objective='',
        )
        call_command('backfill_protocol_objective', '--path', self.src_dir)
        p.refresh_from_db()
        self.assertEqual(p.objective, 'Desc only')

    def test_abstract_preferred_over_longer_protocol(self):
        """abstract 非空时优先用 abstract（即便 protocol 更长）。"""
        _write_source(self.src_dir, 'Bio-protocol.json', [
            {'id': 1, 'title': 'Y',
             'abstract': 'Short abstract',
             'protocol': 'Very long protocol body ' * 50},
        ])
        p = Protocol.objects.create(
            name='Y', slug='y', source=Protocol.Source.BIOPROCORPUS, objective='',
        )
        call_command('backfill_protocol_objective', '--path', self.src_dir)
        p.refresh_from_db()
        self.assertEqual(p.objective, 'Short abstract')

    # ---- 保守模糊匹配（B 类改进④）：默认关闭，--fuzzy 启用，高相似度唯一候选才写 ----

    def test_fuzzy_match_normalized_case_punct(self):
        """--fuzzy：源标题与 DB name 仅大小写/标点差异 → 归一化精确命中。"""
        _write_source(self.src_dir, 'Bio-protocol.json', [
            {'id': 1, 'title': 'RNA Extraction (Protocol)', 'abstract': 'Abstract text.'},
        ])
        p = Protocol.objects.create(
            name='rna extraction protocol', slug='re',
            source=Protocol.Source.BIOPROCORPUS, objective='',
        )
        call_command('backfill_protocol_objective', '--path', self.src_dir, '--fuzzy')
        p.refresh_from_db()
        self.assertEqual(p.objective, 'Abstract text.')

    def test_fuzzy_off_by_default(self):
        """默认（无 --fuzzy）不启用模糊匹配，差异标题应保持未命中（不写空/不误写）。"""
        _write_source(self.src_dir, 'Bio-protocol.json', [
            {'id': 1, 'title': 'RNA Extraction (Protocol)', 'abstract': 'Abstract text.'},
        ])
        p = Protocol.objects.create(
            name='rna extraction protocol', slug='re2',
            source=Protocol.Source.BIOPROCORPUS, objective='',
        )
        call_command('backfill_protocol_objective', '--path', self.src_dir)
        p.refresh_from_db()
        self.assertEqual(p.objective, '')

    def test_fuzzy_requires_high_similarity(self):
        """--fuzzy 高相似度门槛：不相关标题不得误匹配（宁 miss 不错配）。"""
        _write_source(self.src_dir, 'Bio-protocol.json', [
            {'id': 1, 'title': 'Completely Different Title About Yeast', 'abstract': 'A.'},
        ])
        p = Protocol.objects.create(
            name='RNA extraction from mammalian cells', slug='re3',
            source=Protocol.Source.BIOPROCORPUS, objective='',
        )
        call_command('backfill_protocol_objective', '--path', self.src_dir, '--fuzzy')
        p.refresh_from_db()
        self.assertEqual(p.objective, '', '高相似度门槛：不相关标题不得误匹配')

    def test_structured_field_dict_is_stringified(self):
        """hierarchical_protocol 等为 dict/list 等结构化字段应安全拼接为文本（不崩溃）。"""
        _write_source(self.src_dir, 'Bio-protocol.json', [
            {'id': 1, 'title': 'Struct Proto',
             'abstract': '',
             'hierarchical_protocol': {'step_1': 'Lyse', 'step_2': 'Centrifuge'}},
        ])
        p = Protocol.objects.create(
            name='Struct Proto', slug='struct-proto',
            source=Protocol.Source.BIOPROCORPUS, objective='',
        )
        call_command('backfill_protocol_objective', '--path', self.src_dir)
        p.refresh_from_db()
        self.assertIn('Lyse', p.objective)
        self.assertIn('Centrifuge', p.objective)
