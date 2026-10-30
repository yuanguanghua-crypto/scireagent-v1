"""
set_protocol_status 命令测试。

下架是**可逆**操作，但"改了哪些、原来什么状态"必须留痕，否则无法准确恢复。
这里重点测：拒非法状态值、dry-run 不写库、apply 先备份再改、幂等、--restore 能回滚。
"""
import contextlib
import io
import json
import os
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.knowledge.models import Protocol


def _mk(name, status='published'):
    return Protocol.objects.create(
        name=name, slug=name.lower().replace(' ', '-')[:200],
        version='1.0', status=status)


class SetProtocolStatusCommandTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='status_')
        self.ids_file = os.path.join(self.tmp, 'ids.txt')
        self.backup_dir = os.path.join(self.tmp, 'backup')

    def tearDown(self):
        for root, dirs, files in os.walk(self.tmp, topdown=False):
            for f in files:
                os.remove(os.path.join(root, f))
            for d in dirs:
                os.rmdir(os.path.join(root, d))

    def _write_ids(self, ids):
        with open(self.ids_file, 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(str(i) for i in ids))

    def _run(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            call_command('set_protocol_status', *args)
        return buf.getvalue()

    def test_rejects_invalid_status(self):
        p = _mk('A')
        self._write_ids([p.id])
        with self.assertRaises(CommandError) as ctx:
            self._run('--ids-file', self.ids_file, '--status', 'archive', '--apply')
        self.assertIn('必须是', str(ctx.exception))
        # 没有被改
        p.refresh_from_db()
        self.assertEqual(p.status, 'published')

    def test_dry_run_does_not_write_or_backup(self):
        p = _mk('B')
        self._write_ids([p.id])
        out = self._run('--ids-file', self.ids_file, '--status', 'archived',
                        '--backup-dir', self.backup_dir, '--dry-run')
        p.refresh_from_db()
        self.assertEqual(p.status, 'published')
        self.assertFalse(os.path.isdir(self.backup_dir) and os.listdir(self.backup_dir))
        self.assertIn('预演', out)

    def test_apply_changes_and_backs_up(self):
        p = _mk('C', status='published')
        keep = _mk('D', status='published')
        self._write_ids([p.id])
        self._run('--ids-file', self.ids_file, '--status', 'archived',
                  '--backup-dir', self.backup_dir, '--apply')
        p.refresh_from_db(); keep.refresh_from_db()
        self.assertEqual(p.status, 'archived')
        self.assertEqual(keep.status, 'published')

        files = os.listdir(self.backup_dir)
        self.assertEqual(len(files), 1)
        with open(os.path.join(self.backup_dir, files[0]), encoding='utf-8') as fh:
            data = json.load(fh)
        self.assertEqual(data['target_status'], 'archived')
        self.assertEqual(data['items'][0]['status'], 'published')  # 备份的是"改前"状态
        self.assertEqual(data['items'][0]['id'], p.id)

    def test_idempotent_second_run_does_not_backup(self):
        p = _mk('E', status='published')
        self._write_ids([p.id])
        self._run('--ids-file', self.ids_file, '--status', 'archived',
                  '--backup-dir', self.backup_dir, '--apply')
        first = len(os.listdir(self.backup_dir))
        self._run('--ids-file', self.ids_file, '--status', 'archived',
                  '--backup-dir', self.backup_dir, '--apply')
        self.assertEqual(len(os.listdir(self.backup_dir)), first)

    def test_restore_rolls_back(self):
        p = _mk('F', status='published')
        pid = p.id
        self._write_ids([pid])
        self._run('--ids-file', self.ids_file, '--status', 'archived',
                  '--backup-dir', self.backup_dir, '--apply')
        p.refresh_from_db()
        self.assertEqual(p.status, 'archived')

        path = os.path.join(self.backup_dir, os.listdir(self.backup_dir)[0])
        with contextlib.redirect_stdout(io.StringIO()):
            call_command('set_protocol_status', '--restore', path)
        p.refresh_from_db()
        self.assertEqual(p.status, 'published')

    def test_missing_ids_tolerated(self):
        p = _mk('G')
        self._write_ids([p.id, 999999])
        out = self._run('--ids-file', self.ids_file, '--status', 'archived',
                        '--backup-dir', self.backup_dir, '--apply')
        self.assertIn('库内不存在', out)

    def test_archived_disappears_from_public_list(self):
        """下架后必须从前台列表消失（apply_public_visibility 只放 published）。"""
        p = _mk('H', status='published')
        r1 = self.client.get('/api/v1/protocols/')
        ids1 = [x['id'] for x in r1.json()['data']]
        self.assertIn(p.id, ids1)

        self._write_ids([p.id])
        self._run('--ids-file', self.ids_file, '--status', 'archived',
                  '--backup-dir', self.backup_dir, '--apply')

        r2 = self.client.get('/api/v1/protocols/')
        ids2 = [x['id'] for x in r2.json()['data']]
        self.assertNotIn(p.id, ids2)
