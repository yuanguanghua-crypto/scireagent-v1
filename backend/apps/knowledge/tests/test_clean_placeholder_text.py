"""`clean_placeholder_text` 命令：占位脏值清理与回滚。

## 背景

2026-10-30 知识实体走查发现：协议详情页的 Troubleshooting tab 直接显示一个 `{}`。
根因是早期一批导入（id 113~200，88 条）把空 dict 用 `str()` 塞进了 TextField
⇒ 数据库里是**字面字符串 `"{}"`**，前端 `v-if="troubleshooting"` 判为真就原样渲染。

全库扫描确认只有这一种形态（`Protocol.troubleshooting='{}'` 88 条），
RG/AP/Method 的 name/summary/purpose 等字段全部干净。

本文件锁三件事：
1. 只匹配**整字段等于**占位值 —— 不能误伤正文里合法出现的 `{}`（比如 JSON 示例）
2. 默认 dry-run，不写库
3. `--restore` 能从备份原样回滚
"""
import json
import tempfile
from pathlib import Path

from django.core.management import call_command as _call_command
from django.test import TestCase

from apps.knowledge.models import Method, Protocol
from apps.knowledge.tests.factories import MethodFactory, ProtocolFactory

import io


def call_command(*args, **kwargs):
    kwargs.setdefault('stdout', io.StringIO())
    kwargs.setdefault('stderr', io.StringIO())
    return _call_command(*args, **kwargs)


class CleanPlaceholderTextTest(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.dirty = ProtocolFactory(status='published', troubleshooting='{}')
        self.dirty2 = ProtocolFactory(status='published', troubleshooting='[]')
        self.clean = ProtocolFactory(status='published', troubleshooting='')
        self.real = ProtocolFactory(
            status='published',
            troubleshooting='If buffer is {} then check pH.',  # 正文里合法出现 {}
        )

    def _run(self, **kw):
        kw.setdefault('backup_dir', str(self.tmp))
        return call_command('clean_placeholder_text', **kw)

    def test_dry_run_does_not_write(self):
        self._run()
        for p in (self.dirty, self.dirty2):
            p.refresh_from_db()
        self.assertEqual(self.dirty.troubleshooting, '{}', '--dry-run 不得写库')
        self.assertEqual(self.dirty2.troubleshooting, '[]')

    def test_apply_clears_only_exact_placeholder(self):
        self._run(apply=True)
        self.dirty.refresh_from_db()
        self.dirty2.refresh_from_db()
        self.clean.refresh_from_db()
        self.real.refresh_from_db()
        self.assertEqual(self.dirty.troubleshooting, '')
        self.assertEqual(self.dirty2.troubleshooting, '')
        self.assertEqual(self.clean.troubleshooting, '')
        self.assertEqual(
            self.real.troubleshooting, 'If buffer is {} then check pH.',
            '★ 正文里合法包含 {} 的不能被误清 —— 只匹配整字段等于',
        )

    def test_backup_written(self):
        self._run(apply=True)
        files = list(self.tmp.glob('*.json'))
        self.assertTrue(files, '写库前必须落备份')
        payload = json.loads(files[0].read_text(encoding='utf-8'))
        self.assertEqual(payload['count'], 2)
        self.assertEqual({i['value'] for i in payload['items']}, {'{}', '[]'})

    def test_restore_brings_values_back(self):
        self._run(apply=True)
        self.dirty.refresh_from_db()
        self.assertEqual(self.dirty.troubleshooting, '')

        backup = next(self.tmp.glob('*.json'))
        call_command('clean_placeholder_text', restore=str(backup))

        self.dirty.refresh_from_db()
        self.dirty2.refresh_from_db()
        self.assertEqual(self.dirty.troubleshooting, '{}', '--restore 必须原样恢复')
        self.assertEqual(self.dirty2.troubleshooting, '[]')

    def test_second_run_is_noop(self):
        """清完再跑应报「无需处理」，且不产生新改动。"""
        self._run(apply=True)
        out = io.StringIO()
        call_command('clean_placeholder_text', apply=True,
                     backup_dir=str(self.tmp), stdout=out)
        self.assertIn('没有占位脏值', out.getvalue())
