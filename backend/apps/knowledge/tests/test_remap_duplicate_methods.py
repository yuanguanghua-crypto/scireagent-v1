"""
remap_duplicate_methods 命令测试。

修的是「协议→方法」94.5% 的 404 断链。测试重点是**不能修出新问题**：
- 重指向必须落在同名 active 上，不能凭空造 active
- 协议已关联同名 active 时必须跳过（否则撞 (method, protocol) 唯一约束）
- 源 Method 清空后归档，不能再被挂
- 找不到同名 active 的关联默认**报错拒绝执行**（宁可不修，不能删数据）
- dry-run 不写库、不备份
"""
import contextlib
import io
import json
import os
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.bridges.models import MethodProtocol
from apps.knowledge.models import Method, Protocol


def _mk_method(name, status, slug=None):
    return Method.objects.create(
        name=name, slug=slug or f'{name.lower().replace(" ", "-")}-{status}',
        status=status)


def _mk_protocol(name, status='published'):
    return Protocol.objects.create(
        name=name, slug=f'proto-{name.lower().replace(" ", "-")}',
        version='1.0', status=status)


class RemapDuplicateMethodsTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='remap_')

    def tearDown(self):
        for root, dirs, files in os.walk(self.tmp, topdown=False):
            for f in files:
                os.remove(os.path.join(root, f))
            for d in dirs:
                os.rmdir(os.path.join(root, d))

    def _run(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            call_command('remap_duplicate_methods', '--backup-dir', self.tmp, *args)
        return buf.getvalue()

    # ---------- 基本重指向 ----------

    def test_dry_run_does_not_write(self):
        active = _mk_method('PCR', 'active')
        draft = _mk_method('PCR', 'draft')
        p = _mk_protocol('P1')
        mp = MethodProtocol.objects.create(method=draft, protocol=p, status='active')
        out = self._run('--dry-run')
        mp.refresh_from_db()
        self.assertEqual(mp.method_id, draft.id)
        self.assertIn('预演', out)
        self.assertFalse(os.path.isdir(self.tmp) and os.listdir(self.tmp))

    def test_apply_remaps_to_same_name_active(self):
        active = _mk_method('PCR', 'active')
        draft = _mk_method('PCR', 'draft')
        p = _mk_protocol('P1')
        mp = MethodProtocol.objects.create(method=draft, protocol=p, status='active')
        self._run('--apply')
        mp.refresh_from_db()
        self.assertEqual(mp.method_id, active.id)

    def test_source_is_archived_after_emptied(self):
        active = _mk_method('PCR', 'active')
        draft = _mk_method('PCR', 'draft')
        p = _mk_protocol('P1')
        MethodProtocol.objects.create(method=draft, protocol=p, status='active')
        self._run('--apply')
        draft.refresh_from_db()
        self.assertEqual(draft.status, 'archived')

    def test_conflict_is_skipped_not_duplicated(self):
        """协议已关联同名 active 时，不能重复插 —— 否则撞 (method, protocol) 唯一约束。"""
        active = _mk_method('PCR', 'active')
        draft = _mk_method('PCR', 'draft')
        p = _mk_protocol('P1')
        MethodProtocol.objects.create(method=active, protocol=p, status='active')
        MethodProtocol.objects.create(method=draft, protocol=p, status='active')
        self._run('--apply')
        # 该协议对 active 的关联只能有一条
        self.assertEqual(
            MethodProtocol.objects.filter(method=active, protocol=p).count(), 1)
        # ★ 冲突那条不能留着 —— 留着 get_methods 仍返回它，用户点进去还是 404。
        #   它是冗余（同一协议已在同名 active 上），必须删掉，源才能清空并归档。
        self.assertEqual(MethodProtocol.objects.filter(method=draft).count(), 0)

    def test_multiple_protocols_all_moved(self):
        active = _mk_method('PCR', 'active')
        draft = _mk_method('PCR', 'draft')
        for i in range(5):
            MethodProtocol.objects.create(
                method=draft, protocol=_mk_protocol(f'P{i}'), status='active')
        self._run('--apply')
        self.assertEqual(MethodProtocol.objects.filter(method=active).count(), 5)
        self.assertEqual(MethodProtocol.objects.filter(method=draft).count(), 0)

    # ---------- 无主关联的安全闸门 ----------

    def test_orphan_blocks_apply_without_flag(self):
        """找不到同名 active 的关联，默认必须拒绝执行 —— 宁可不修，不能悄悄删数据。"""
        lonely = _mk_method('Administration of an AAV shuffled library', 'archived')
        p = _mk_protocol('P1')
        MethodProtocol.objects.create(method=lonely, protocol=p, status='active')
        with self.assertRaises(CommandError) as ctx:
            self._run('--apply')
        self.assertIn('drop-orphan-links', str(ctx.exception))
        # 没删
        self.assertEqual(MethodProtocol.objects.filter(method=lonely).count(), 1)

    def test_orphan_dropped_with_flag(self):
        lonely = _mk_method('Administration of an AAV shuffled library', 'archived')
        other = _mk_method('Real Method', 'active')
        p = _mk_protocol('P1')
        MethodProtocol.objects.create(method=lonely, protocol=p, status='active')
        MethodProtocol.objects.create(method=other, protocol=p, status='active')
        self._run('--apply', '--drop-orphan-links')
        self.assertEqual(MethodProtocol.objects.filter(method=lonely).count(), 0)
        # 协议仍保留另一个正确方法
        self.assertEqual(MethodProtocol.objects.filter(method=other).count(), 1)

    # ---------- 备份 ----------

    def test_backup_contains_full_method_protocol_table(self):
        active = _mk_method('PCR', 'active')
        draft = _mk_method('PCR', 'draft')
        MethodProtocol.objects.create(method=draft, protocol=_mk_protocol('P1'), status='active')
        MethodProtocol.objects.create(method=active, protocol=_mk_protocol('P2'), status='active')
        self._run('--apply')
        files = os.listdir(self.tmp)
        self.assertEqual(len(files), 1)
        with open(os.path.join(self.tmp, files[0]), encoding='utf-8') as fh:
            data = json.load(fh)
        # ★ 上次 purge 只备了"想到的"几张桥，漏了 facet 与 RG。
        #   这次 method_protocol 必须**全量**备，不只是受影响的行。
        self.assertEqual(len(data['method_protocol_all']), 2)
        self.assertIn('remap_plan', data)
        self.assertEqual(data['remap_plan'][0]['to'], active.id)

    # ---------- verify ----------

    def test_verify_reports_zero_broken(self):
        active = _mk_method('PCR', 'active')
        draft = _mk_method('PCR', 'draft')
        MethodProtocol.objects.create(method=draft, protocol=_mk_protocol('P1'), status='active')
        self._run('--apply')
        out = self._run('--verify')
        self.assertIn('断链归零', out)

    def test_verify_detects_broken(self):
        draft = _mk_method('OnlyDraft', 'draft')
        MethodProtocol.objects.create(method=draft, protocol=_mk_protocol('P1'), status='active')
        out = self._run('--verify')
        self.assertIn('0 才算修好', out)   # 有断链时会打这句
