"""`summary_i18n` 命令的 scope 隔离与安全闸门。

## 为什么要有这个文件

第一批（scope=summary）清掉了 45 条中文 summary，第二批（scope=protocol）
处理了协议 name/objective。两个 scope 共用同一套导出/回写逻辑，
最容易出的事故是**scope 串味** —— 跑 protocol 时顺手把 RG/AP 的 summary 也改了。
这里把隔离性钉死。

同时钉住两条安全边界：
- CSV 里 `skip` 非空 ⇒ 该行绝不能被写（允许人工判定「这条先不动」）
- 译文本身含中文 ⇒ 直接报错，不允许把中文再写回去
"""
import csv
import io
import tempfile
from pathlib import Path

from django.core.management import call_command as _call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.knowledge.models import Application, Protocol, ResearchGoal
from apps.knowledge.tests.factories import (
    ApplicationFactory,
    ProtocolFactory,
    ResearchGoalFactory,
)


def call_command(*args, **kwargs):
    """统一吞掉命令输出（避免 pytest 关流后 Django flush 抛 ValueError）。"""
    kwargs.setdefault('stdout', io.StringIO())
    kwargs.setdefault('stderr', io.StringIO())
    return _call_command(*args, **kwargs)

HEADER = ['kind', 'id', 'field', 'name', 'original_zh', 'proposed_en',
          'approved_en', 'review_note', 'skip']


class SummaryI18nScopeTest(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.csv = self.tmp / 'x.csv'
        self.bak = self.tmp / 'bak'

        self.goal = ResearchGoalFactory(
            name='Cancer Biology', status='active', summary='癌症发生发展与转移机制研究')
        self.app = ApplicationFactory(
            name='Nucleic Acid Extraction', status='active',
            summary='从生物样本提取纯化核酸的技术族')
        self.proto = ProtocolFactory(
            name='反转录cDNA', status='published', objective='混匀，37°C，1h')

    def _write(self, rows):
        with open(self.csv, 'w', encoding='utf-8-sig', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=HEADER)
            w.writeheader()
            w.writerows(rows)

    def _row(self, kind, pk, field, en, skip=''):
        return {'kind': kind, 'id': str(pk), 'field': field, 'name': '',
                'original_zh': '', 'proposed_en': en, 'approved_en': '',
                'review_note': '', 'skip': skip}

    # ── scope 隔离 ─────────────────────────────────────────
    def test_protocol_scope_does_not_touch_summaries(self):
        """跑 protocol 时，RG/AP 的 summary 必须原封不动。

        ★ 关键是 CSV 里**故意混入** RG / AP 行 —— 只有这样才能证伪
        「scope 过滤失效」。若 CSV 只放 protocol 行，改坏 scope 检查也测不出来
        （这一点在 `verify_fix_gates.py` 的 ⑦ 号闸门里被真实抓到过一次）。
        """
        self._write([
            self._row('protocol', self.proto.pk, 'name', 'Reverse Transcription'),
            self._row('protocol', self.proto.pk, 'objective', 'Mix, 37 °C, 1 h'),
            # 混入：这两行属于 summary scope，跑 protocol 时必须被跳过
            self._row('research_goal', self.goal.pk, 'summary', 'Mechanisms of cancer.'),
            self._row('application', self.app.pk, 'summary', 'Technique family for extraction.'),
        ])
        call_command('summary_i18n', apply=True, commit=True, scope='protocol',
                     csv=str(self.csv), backup_dir=str(self.bak))
        self.proto.refresh_from_db()
        self.goal.refresh_from_db()
        self.app.refresh_from_db()
        self.assertEqual(self.proto.name, 'Reverse Transcription')
        self.assertEqual(self.goal.summary, '癌症发生发展与转移机制研究',
                         'scope=protocol 不得波及 ResearchGoal.summary')
        self.assertEqual(self.app.summary, '从生物样本提取纯化核酸的技术族',
                         'scope=protocol 不得波及 Application.summary')

    def test_summary_scope_ignores_protocol_rows(self):
        """反向：跑 summary 时，CSV 里的 protocol 行要被跳过。"""
        self._write([
            self._row('research_goal', self.goal.pk, 'summary', 'Mechanisms of cancer.'),
            self._row('protocol', self.proto.pk, 'name', 'Reverse Transcription'),
        ])
        call_command('summary_i18n', apply=True, commit=True, scope='summary',
                     csv=str(self.csv), backup_dir=str(self.bak))
        self.goal.refresh_from_db()
        self.proto.refresh_from_db()
        self.assertEqual(self.goal.summary, 'Mechanisms of cancer.')
        self.assertEqual(self.proto.name, '反转录cDNA', 'scope=summary 不得改协议名')

    # ── 安全闸门 ───────────────────────────────────────────
    def test_skip_column_is_respected(self):
        self._write([
            self._row('research_goal', self.goal.pk, 'summary', 'Mechanisms of cancer.',
                      skip='1'),
        ])
        call_command('summary_i18n', apply=True, commit=True, scope='summary',
                     csv=str(self.csv), backup_dir=str(self.bak))
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.summary, '癌症发生发展与转移机制研究',
                         'skip 非空的行绝不能被写')

    def test_chinese_in_translation_is_rejected(self):
        """不允许把中文再写回去 —— 否则本地化原地打转。"""
        self._write([
            self._row('research_goal', self.goal.pk, 'summary', '癌症机制'),
        ])
        with self.assertRaises(CommandError):
            call_command('summary_i18n', apply=True, commit=True, scope='summary',
                         csv=str(self.csv), backup_dir=str(self.bak))
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.summary, '癌症发生发展与转移机制研究')

    def test_approved_en_overrides_proposed(self):
        row = self._row('research_goal', self.goal.pk, 'summary', 'draft translation')
        row['approved_en'] = 'Mechanisms of cancer initiation and metastasis.'
        self._write([row])
        call_command('summary_i18n', apply=True, commit=True, scope='summary',
                     csv=str(self.csv), backup_dir=str(self.bak))
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.summary,
                         'Mechanisms of cancer initiation and metastasis.')

    def test_export_finds_cjk_only(self):
        """导出只收含 CJK 的行，纯英文实体不进表。"""
        ResearchGoalFactory(name='Pure English', status='active',
                            summary='All English summary.')
        call_command('summary_i18n', export=True, scope='summary', csv=str(self.csv))
        with open(self.csv, encoding='utf-8-sig', newline='') as fh:
            rows = list(csv.DictReader(fh))
        ids = {int(r['id']) for r in rows}
        self.assertIn(self.goal.id, ids)
        self.assertIn(self.app.id, ids)
        self.assertEqual(len(rows), 2, '纯英文 summary 不应被导出')

    def test_backup_is_written_before_commit(self):
        self._write([
            self._row('research_goal', self.goal.pk, 'summary', 'Mechanisms of cancer.'),
        ])
        call_command('summary_i18n', apply=True, commit=True, scope='summary',
                     csv=str(self.csv), backup_dir=str(self.bak))
        files = list(self.bak.glob('*.json'))
        self.assertTrue(files, '写库前必须落原值备份')
