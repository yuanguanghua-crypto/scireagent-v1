"""
import_method_definitions 命令的回归测试。

契约（本文件把这些钉死）：
- 默认 dry-run：不落库
- `--apply` 才写；按 (method, version) 幂等 upsert
- **先全量校验再统一写**：任一份不过 ⇒ 一份都不写（不许半灌）
- `--status active` 未加 `--allow-active` ⇒ 拒绝（active 须组织方单独点头）
- 方法定位：`--map` 优先；否则按 name 唯一匹配，**多个同名即拒绝**（宁停不猜）
- `exclude` 由 list[单键dict] 拍平为 dict；`layer_status` 写 NULL
- **不写 `Method.definition`**（已废弃列）
"""
import os
import tempfile

import yaml
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.knowledge.models import Method, MethodDefinition

CATS = ('upstream', 'downstream', 'variant', 'analogue', 'composite')


def valid_definition(method_name='SDS-PAGE', version='3.1'):
    return {
        'method': method_name,
        'version': version,
        'essence': 'A test method.',
        'must': ['step one'],
        'on_topic_requires': ['output one'],
        'common_but_not_required': ['nice to have'],
        'exclude': [{'E1': 'not this'}, {'E2': 'nor this'}],
        'category_definition': {c: 'def of %s' % c for c in CATS},
        'pos_examples': [{'text': 'p1', 'verdict': 'on_topic'},
                         {'text': 'p2', 'verdict': 'on_topic'}],
        'neg_examples': [{'text': 'n%d' % i, 'verdict': 'wrong',
                          'exclude_item': 'E1' if i % 2 else 'E2'} for i in range(5)],
        'edge_examples': [{'text': 'e-%s' % c, 'verdict': 'tangential',
                           'category': c, 'exclude_item': '', 'why': 'w'} for c in CATS],
        'author': '张三',
        'reviewed_by': '李四',
        'status': 'reviewed',
    }


class ImportMethodDefinitionsTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: None)          # 临时目录留给系统回收，避免误删用户文件

    def _write(self, name, data):
        p = os.path.join(self.tmp, name)
        with open(p, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        return p

    def _method(self, name, slug, **kw):
        return Method.objects.create(name=name, slug=slug, is_test_fixture=True,
                                     definition='', **kw)

    def test_dry_run_writes_nothing(self):
        m = self._method('SDS-PAGE', 'sds-page-test')
        p = self._write('a.yaml', valid_definition())
        call_command('import_method_definitions', p, '--map', 'SDS-PAGE=%s' % m.slug)
        self.assertEqual(MethodDefinition.objects.count(), 0)

    def test_apply_creates_row_with_expected_fields(self):
        m = self._method('SDS-PAGE', 'sds-page-test')
        p = self._write('a.yaml', valid_definition())
        call_command('import_method_definitions', p, '--map', 'SDS-PAGE=%s' % m.slug, '--apply')

        row = MethodDefinition.objects.get()
        self.assertEqual(row.method_id, m.id)
        self.assertEqual(row.version, '3.1')            # 文本，不是 float
        self.assertEqual(row.status, 'reviewed')
        self.assertEqual(row.verification, 'smoke_passed')
        self.assertIsNone(row.layer_status)
        self.assertIsInstance(row.exclude, dict)        # 已拍平
        self.assertEqual(sorted(row.exclude), ['E1', 'E2'])
        m.refresh_from_db()
        self.assertEqual(m.definition, '')              # 废弃列没被写

    def test_idempotent(self):
        m = self._method('SDS-PAGE', 'sds-page-test')
        p = self._write('a.yaml', valid_definition())
        args = ('import_method_definitions', p, '--map', 'SDS-PAGE=%s' % m.slug, '--apply')
        call_command(*args)
        call_command(*args)
        self.assertEqual(MethodDefinition.objects.count(), 1)

    def test_refuses_active_without_flag(self):
        m = self._method('SDS-PAGE', 'sds-page-test')
        p = self._write('a.yaml', valid_definition())
        with self.assertRaises(CommandError):
            call_command('import_method_definitions', p,
                         '--map', 'SDS-PAGE=%s' % m.slug, '--apply', '--status', 'active')
        self.assertEqual(MethodDefinition.objects.count(), 0)

    def test_refuses_ambiguous_name(self):
        self._method('SDS-PAGE', 'sds-page-a')
        self._method('SDS-PAGE', 'sds-page-b')
        p = self._write('a.yaml', valid_definition())
        with self.assertRaises(CommandError):
            call_command('import_method_definitions', p)
        self.assertEqual(MethodDefinition.objects.count(), 0)

    def test_invalid_definition_writes_nothing_at_all(self):
        """一份坏、一份好 ⇒ 一份都不写（全量校验优先，不许半灌）。"""
        good = self._method('SDS-PAGE', 'sds-page-test')
        pcr = self._method('PCR', 'pcr-test')
        p_ok = self._write('ok.yaml', valid_definition())
        bad = valid_definition('PCR', '0.1')
        bad['edge_examples'] = bad['edge_examples'][:2]     # 违反规则 5
        p_bad = self._write('bad.yaml', bad)

        with self.assertRaises(CommandError):
            call_command('import_method_definitions', p_ok, p_bad,
                         '--map', 'SDS-PAGE=%s' % good.slug,
                         '--map', 'PCR=%s' % pcr.slug, '--apply')
        self.assertEqual(MethodDefinition.objects.count(), 0)
