"""
TDD RED: backfill_protocol_steps 命令 + protocol_steps_parser 解析器（P2 协议富化回填）。

背景：生产 13,971 条 source='bioprocorpus' 的 Protocol 是空壳（仅 name/slug/source），
steps 空置率 99.3%。源数据 hierarchical_protocol 其实是完整层级步骤树，只是没被解析入库。
本次纯程序化解析、零 LLM 调用。

GREEN 后契约：
- 解析器 parse_hierarchical_protocol(hp) -> list[{'step_no','title','body'}]
  * dict 值 = 章节（只含 title，不是可执行步骤）；str 值 = 叶子步骤正文
  * 自然排序：'1.2' 必须排在 '1.10' 前（按数字分段排序，不能字符串排序）
  * title 继承最近的父级章节 title（'1.1.1' 继承 '1.1'，无则继承 '1'，都没有则空）
  * 空 / 纯空白 body 跳过
  * 超长 title 截断到 255
  * 空 dict / None / 非预期类型不崩
- 命令 backfill_protocol_steps
  * --corpus-dir（默认 /app/backend/data/bioprocorpus）、--apply、--verify、--limit N、--checkpoint-file
  * 默认 dry-run：统计匹配数 / 将建步骤数 / 平均步骤数 / 跳过数 + 打印样本
  * --apply 用 bulk_create 分批建 ProtocolStep（只新增，绝不删改已有数据）
  * 幂等：已有 steps 的协议（含 94 条 curated 及重复运行）跳过
  * 不覆盖 curated：source != bioprocorpus 的协议一条都不许动
  * --limit N 只处理前 N 条
  * title 匹配不到时跳过并记录（不模糊凑数）

本地测试造 fixture 语料（临时目录），不依赖 514MB 真实语料。
"""
import json
import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.knowledge.models import Protocol, ProtocolStep


# ---------------------------------------------------------------------------
# 解析器单元测试
# ---------------------------------------------------------------------------

class ParseHierarchicalProtocolTest(TestCase):
    def _hp(self):
        return {
            '1':     {'title': 'Bacterial Growth'},
            '1.1':   {'title': 'Plate Preparation'},
            '1.1.1': 'Spread a fresh H1 minimal medium.',
            '1.1.2': 'Incubate at the appropriate temperature and time.',
            '1.2':   {'title': 'Overnight Culture'},
            '1.2.1': 'Start a fresh 3mL overnight culture.',
            '2':     {'title': 'Second Section'},
            '2.1':   'Do the thing.',
            '10.1':  'Tenth section step.',
            # 自然排序边界
            '1.10':  'Tenth subsection leaf.',
        }

    def test_module_importable(self):
        from apps.knowledge.services import protocol_steps_parser  # noqa: F401

    def test_only_str_leaves_become_steps(self):
        from apps.knowledge.services.protocol_steps_parser import parse_hierarchical_protocol
        steps = parse_hierarchical_protocol(self._hp())
        # 9 个 str 叶子：1.1.1,1.1.2,1.2.1,2.1,10.1,1.10 -> 6 个
        bodies = [s['body'] for s in steps]
        self.assertEqual(len(steps), 6)
        self.assertIn('Spread a fresh H1 minimal medium.', bodies)
        # dict 章节（'1','1.1','1.2','2'）绝不能成为步骤
        for s in steps:
            self.assertNotIn('Bacterial Growth', s['body'])
            self.assertNotIn('Plate Preparation', s['body'])

    def test_natural_order_1_2_before_1_10(self):
        from apps.knowledge.services.protocol_steps_parser import parse_hierarchical_protocol
        steps = parse_hierarchical_protocol(self._hp())
        bodies = [s['body'] for s in steps]
        i_12 = bodies.index('Start a fresh 3mL overnight culture.')   # 1.2.1
        i_110 = bodies.index('Tenth subsection leaf.')                  # 1.10
        self.assertLess(i_12, i_110, "'1.2' 必须排在 '1.10' 之前（自然排序）")

    def test_step_no_sequential_from_one(self):
        from apps.knowledge.services.protocol_steps_parser import parse_hierarchical_protocol
        steps = parse_hierarchical_protocol(self._hp())
        self.assertEqual([s['step_no'] for s in steps], list(range(1, len(steps) + 1)))

    def test_title_inherits_nearest_parent_section(self):
        from apps.knowledge.services.protocol_steps_parser import parse_hierarchical_protocol
        steps = {s['body']: s['title'] for s in parse_hierarchical_protocol(self._hp())}
        self.assertEqual(steps['Spread a fresh H1 minimal medium.'], 'Plate Preparation')  # 1.1.1 <- 1.1
        self.assertEqual(steps['Start a fresh 3mL overnight culture.'], 'Overnight Culture')  # 1.2.1 <- 1.2
        self.assertEqual(steps['Do the thing.'], 'Second Section')  # 2.1 <- 2

    def test_title_inherits_grandparent_when_parent_missing(self):
        from apps.knowledge.services.protocol_steps_parser import parse_hierarchical_protocol
        hp = {
            '1': {'title': 'Top'},
            '1.1': 'leaf under section without its own title dict? no',  # str -> leaf, inherits '1'
        }
        steps = parse_hierarchical_protocol(hp)
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]['title'], 'Top')

    def test_title_empty_when_no_ancestor_has_title(self):
        from apps.knowledge.services.protocol_steps_parser import parse_hierarchical_protocol
        hp = {
            '3': {},          # 章节但无 title
            '3.1': 'leaf with no ancestor title',
        }
        steps = parse_hierarchical_protocol(hp)
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]['title'], '')

    def test_skips_empty_or_whitespace_body(self):
        from apps.knowledge.services.protocol_steps_parser import parse_hierarchical_protocol
        hp = {
            '1': {'title': 'S'},
            '1.1': '   ',
            '1.2': '',
            '1.3': 'real step',
        }
        steps = parse_hierarchical_protocol(hp)
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]['body'], 'real step')

    def test_overlong_title_truncated_to_255(self):
        from apps.knowledge.services.protocol_steps_parser import parse_hierarchical_protocol
        hp = {
            '1': {'title': 'A' * 300},
            '1.1': 'body',
        }
        steps = parse_hierarchical_protocol(hp)
        self.assertEqual(len(steps[0]['title']), 255)
        self.assertEqual(steps[0]['title'], 'A' * 255)

    def test_robust_against_empty_none_and_unexpected_types(self):
        from apps.knowledge.services.protocol_steps_parser import parse_hierarchical_protocol
        # 这些都不应崩溃，且不应产生步骤
        self.assertEqual(parse_hierarchical_protocol(None), [])
        self.assertEqual(parse_hierarchical_protocol('not a dict'), [])
        self.assertEqual(parse_hierarchical_protocol(123), [])
        self.assertEqual(parse_hierarchical_protocol({}), [])
        # 非预期值类型（list / None 值 / 无 title 的 dict）不崩
        hp = {
            '1': [1, 2, 3],                 # list 值 -> 跳过
            '2': None,                      # None 值 -> 跳过
            '3': {'foo': 1},               # dict 无 title -> 章节，无 title
            '3.1': 'leaf under untitled section',
            '4': {'title': 'X'},           # 纯章节无叶子
        }
        steps = parse_hierarchical_protocol(hp)
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]['body'], 'leaf under untitled section')
        self.assertEqual(steps[0]['title'], '')

    def test_natural_key_sort_function(self):
        from apps.knowledge.services.protocol_steps_parser import natural_key
        keys = ['1.10', '1.2', '10.1', '2.1', '1.1']
        self.assertEqual(sorted(keys, key=natural_key),
                         ['1.1', '1.2', '1.10', '2.1', '10.1'])


# ---------------------------------------------------------------------------
# 命令集成测试（造 fixture 语料）
# ---------------------------------------------------------------------------

def _write_corpus(directory, filename, records):
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, filename), 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False)


def _hp_record(title, items):
    """构造一条带 hierarchical_protocol 的源记录。

    items: list[tuple]
      ('sec',  key, title) -> 章节（dict，只含 title，不是步骤）
      ('leaf', key, body)  -> 叶子步骤（str 正文）
    """
    hp = {}
    for kind, key, val in items:
        if kind == 'sec':
            hp[key] = {'title': val}
        else:
            hp[key] = val
    return {'id': abs(hash(title)) % 10**9, 'title': title, 'hierarchical_protocol': hp}


class BackfillProtocolStepsCommandTest(TestCase):
    def setUp(self):
        self.src_dir = tempfile.mkdtemp(prefix='bps_src_')

    def _make_proto(self, name, source=Protocol.Source.BIOPROCORPUS, with_step=False):
        p = Protocol.objects.create(name=name, slug=name.lower().replace(' ', '-'), source=source)
        if with_step:
            ProtocolStep.objects.create(protocol=p, step_no=1, title='existing', body='existing body')
        return p

    def test_command_module_importable(self):
        from apps.knowledge.management.commands import backfill_protocol_steps  # noqa: F401

    def test_dry_run_does_not_persist(self):
        _write_corpus(self.src_dir, 'Bio-protocol.json', [
            _hp_record('Proto A', [('leaf', '1.1', 'Mix reagents.'), ('leaf', '1.2', 'Heat to 95C.')]),
        ])
        self._make_proto('Proto A')
        out = StringIO()
        call_command('backfill_protocol_steps', '--corpus-dir', self.src_dir, stdout=out)
        self.assertEqual(ProtocolStep.objects.count(), 0)
        self.assertIn('dry-run', out.getvalue().lower())

    def test_apply_persists_and_count_correct(self):
        _write_corpus(self.src_dir, 'Bio-protocol.json', [
            _hp_record('Proto A', [
                ('sec', '1', 'Prep'),
                ('leaf', '1.1', 'Mix reagents.'),
                ('leaf', '1.2', 'Heat to 95C.'),
                ('sec', '2', 'Run'),
                ('leaf', '2.1', 'Load gel.'),
            ]),
        ])
        p = self._make_proto('Proto A')
        call_command('backfill_protocol_steps', '--corpus-dir', self.src_dir, '--apply')
        steps = list(ProtocolStep.objects.filter(protocol=p).order_by('step_no'))
        self.assertEqual(len(steps), 3)
        self.assertEqual(steps[0].body, 'Mix reagents.')
        self.assertEqual(steps[0].title, 'Prep')
        self.assertEqual(steps[1].body, 'Heat to 95C.')
        self.assertEqual(steps[2].body, 'Load gel.')
        self.assertEqual(steps[2].title, 'Run')

    def test_idempotent_no_duplicate_on_reapply(self):
        _write_corpus(self.src_dir, 'Bio-protocol.json', [
            _hp_record('Proto A', [('leaf','1.1','a'),('leaf','1.2','b')]),
        ])
        p = self._make_proto('Proto A')
        call_command('backfill_protocol_steps', '--corpus-dir', self.src_dir, '--apply')
        call_command('backfill_protocol_steps', '--corpus-dir', self.src_dir, '--apply')
        self.assertEqual(ProtocolStep.objects.filter(protocol=p).count(), 2)

    def test_skips_protocols_already_having_steps(self):
        """已有 steps 的 bioprocorpus 协议（如重复运行或历史残留）必须跳过，一条都不加。"""
        _write_corpus(self.src_dir, 'Bio-protocol.json', [
            _hp_record('Has Steps', [('leaf','1.1','a'),('leaf','1.2','b'),('leaf','1.3','c')]),
        ])
        p = self._make_proto('Has Steps', with_step=True)  # 已有 1 条 step
        call_command('backfill_protocol_steps', '--corpus-dir', self.src_dir, '--apply')
        self.assertEqual(ProtocolStep.objects.filter(protocol=p).count(), 1)

    def test_never_touches_curated_protocols(self):
        _write_corpus(self.src_dir, 'Bio-protocol.json', [
            _hp_record('Curated X', [('leaf','1.1','should not be written')]),
        ])
        p = self._make_proto('Curated X', source=Protocol.Source.CURATED)
        call_command('backfill_protocol_steps', '--corpus-dir', self.src_dir, '--apply')
        self.assertEqual(ProtocolStep.objects.filter(protocol=p).count(), 0)

    def test_limit_processes_only_first_n(self):
        _write_corpus(self.src_dir, 'Bio-protocol.json', [
            _hp_record('Proto A', [('leaf','1.1','a')]),
            _hp_record('Proto B', [('leaf','1.1','b')]),
            _hp_record('Proto C', [('leaf','1.1','c')]),
        ])
        self._make_proto('Proto A')
        self._make_proto('Proto B')
        self._make_proto('Proto C')
        call_command('backfill_protocol_steps', '--corpus-dir', self.src_dir, '--apply', '--limit', '2')
        self.assertEqual(ProtocolStep.objects.count(), 2)

    def test_unmatched_title_skipped_and_recorded(self):
        _write_corpus(self.src_dir, 'Bio-protocol.json', [
            _hp_record('Different Title', [('leaf','1.1','a')]),
        ])
        self._make_proto('No Match Title')
        out = StringIO()
        call_command('backfill_protocol_steps', '--corpus-dir', self.src_dir, '--apply', stdout=out)
        self.assertEqual(ProtocolStep.objects.count(), 0)
        self.assertIn('未匹配', out.getvalue())

    def test_ignores_non_protocol_corpus_files(self):
        """ERR/GEN/ORD/PQA 等非协议文件无 hierarchical_protocol，不应崩溃或建步骤。"""
        _write_corpus(self.src_dir, 'GEN.json', [
            {'system_prompt': 'x', 'instruction': 'y', 'output': 'z', 'id': 1},
        ])
        _write_corpus(self.src_dir, 'Bio-protocol.json', [
            _hp_record('Proto A', [('leaf','1.1','a')]),
        ])
        self._make_proto('Proto A')
        call_command('backfill_protocol_steps', '--corpus-dir', self.src_dir, '--apply')
        self.assertEqual(ProtocolStep.objects.filter(protocol__name='Proto A').count(), 1)

    def test_dry_run_prints_samples(self):
        _write_corpus(self.src_dir, 'Bio-protocol.json', [
            _hp_record('Proto A', [('leaf','1.1','Mix reagents carefully.'),('leaf','1.2','Heat.')]),
        ])
        self._make_proto('Proto A')
        out = StringIO()
        call_command('backfill_protocol_steps', '--corpus-dir', self.src_dir, stdout=out)
        text = out.getvalue()
        self.assertIn('Proto A', text)
        self.assertIn('Mix reagents carefully.', text)
