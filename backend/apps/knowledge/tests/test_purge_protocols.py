"""
purge_protocols 命令测试。

删错了没法 Ctrl+Z，所以这里重点测**安全闸门**而不是删除本身：
- 清单里有「有步骤/有材料」的协议 → 必须中止（说明清单生成逻辑错了）
- dry-run → 不备份、不删除
- apply → 先备份、备份行数与预期一致后才删
- 备份文件可用于 --restore
"""
import contextlib
import io
import json
import os
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.knowledge.models import Protocol, ProtocolStep


def _mk(name, **kw):
    return Protocol.objects.create(
        name=name, slug=kw.pop('slug', None) or name.lower().replace(' ', '-')[:200],
        version='1.0', **kw)


class PurgeProtocolsCommandTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='purge_')
        self.ids_file = os.path.join(self.tmp, 'ids.txt')
        self.backup_dir = os.path.join(self.tmp, 'backup')

    def tearDown(self):
        for root, dirs, files in os.walk(self.tmp, topdown=False):
            for f in files:
                os.remove(os.path.join(root, f))
            for d in dirs:
                os.rmdir(os.path.join(root, d))
        os.rmdir(self.tmp)

    def _write_ids(self, ids):
        with open(self.ids_file, 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(str(i) for i in ids))

    def _run(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            call_command('purge_protocols', *args)
        return buf.getvalue()

    def _dry(self, *extra):
        return self._run('--ids-file', self.ids_file, '--backup-dir', self.backup_dir,
                         '--dry-run', *extra)

    def _apply(self, *extra):
        return self._run('--ids-file', self.ids_file, '--backup-dir', self.backup_dir,
                         '--apply', *extra)

    # ---------- 安全闸门 ----------

    def test_refuses_when_list_contains_protocol_with_steps(self):
        p = _mk('Has Steps')
        ProtocolStep.objects.create(protocol=p, step_no=1, title='t', body='b')
        self._write_ids([p.id])
        with self.assertRaises(CommandError) as ctx:
            self._apply()
        self.assertIn('不该出现在清理清单里', str(ctx.exception))
        # 没有删掉
        self.assertTrue(Protocol.objects.filter(pk=p.id).exists())

    def test_allow_nonempty_override(self):
        p = _mk('Has Steps Override')
        ProtocolStep.objects.create(protocol=p, step_no=1, title='t', body='b')
        self._write_ids([p.id])
        self._apply('--allow-nonempty')
        self.assertFalse(Protocol.objects.filter(pk=p.id).exists())

    def test_raises_without_ids(self):
        with self.assertRaises(CommandError):
            self._run('--dry-run')

    def test_raises_on_non_integer_line(self):
        with open(self.ids_file, 'w', encoding='utf-8') as fh:
            fh.write('1\nabc\n')
        with self.assertRaises(CommandError):
            self._dry()

    # ---------- dry-run ----------

    def test_dry_run_does_not_delete_or_backup(self):
        p = _mk('Empty One')
        self._write_ids([p.id])
        out = self._dry()
        self.assertTrue(Protocol.objects.filter(pk=p.id).exists())
        self.assertFalse(os.path.isdir(self.backup_dir) and os.listdir(self.backup_dir))
        self.assertIn('预演', out)

    def test_dry_run_reports_cascade_impact(self):
        p = _mk('Empty Two')
        self._write_ids([p.id])
        out = self._dry()
        self.assertIn('protocol', out)
        self.assertIn('级联影响面', out)

    # ---------- apply ----------

    def test_apply_backs_up_then_deletes(self):
        p = _mk('Empty Three', objective='some abstract')
        keep = _mk('Not In List')
        self._write_ids([p.id])
        self._apply()
        self.assertFalse(Protocol.objects.filter(pk=p.id).exists())
        self.assertTrue(Protocol.objects.filter(pk=keep.id).exists())

        files = os.listdir(self.backup_dir)
        self.assertEqual(len(files), 1)
        with open(os.path.join(self.backup_dir, files[0]), encoding='utf-8') as fh:
            data = json.load(fh)
        self.assertEqual(len(data['protocols']), 1)
        self.assertEqual(data['protocols'][0]['name'], 'Empty Three')
        self.assertEqual(data['protocols'][0]['objective'], 'some abstract')

    def test_missing_ids_are_tolerated(self):
        p = _mk('Empty Four')
        self._write_ids([p.id, 999999])
        out = self._apply()
        self.assertIn('库内不存在', out)
        self.assertFalse(Protocol.objects.filter(pk=p.id).exists())

    # ---------- restore ----------

    def test_restore_brings_back(self):
        p = _mk('To Restore', objective='abstract text')
        pid = p.id
        self._write_ids([pid])
        self._apply()
        self.assertFalse(Protocol.objects.filter(pk=pid).exists())

        path = os.path.join(self.backup_dir, os.listdir(self.backup_dir)[0])
        with contextlib.redirect_stdout(io.StringIO()):
            call_command('purge_protocols', '--restore', path)
        back = Protocol.objects.filter(pk=pid).first()
        self.assertIsNotNone(back)
        self.assertEqual(back.name, 'To Restore')
        self.assertEqual(back.objective, 'abstract text')

    def test_restore_missing_file_raises(self):
        with self.assertRaises(CommandError):
            call_command('purge_protocols', '--restore', os.path.join(self.tmp, 'nope.json'))
