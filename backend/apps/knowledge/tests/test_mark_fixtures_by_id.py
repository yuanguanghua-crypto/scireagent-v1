"""`mark_test_fixtures --model X --id N` 精确纠正模式。

## 背景（2026-10-30）

巡检发现 **19 个真实实体被误标为测试夹具**（`is_test_fixture=True`）：

| 实体 | id | 名字 | 后果 |
|---|---|---|---|
| ResearchGoal | 33 | RNA Analysis（挂 876 个应用 / 504 协议） | `/research-goals/33` **404** |
| ResearchGoal | 25 | Gene Expression Analysis（536 应用） | 同上，本站最高频的父级之一 |
| ResearchGoal | 30 | Pathogen Detection（119 应用） | 同上 |
| ResearchGoal | 23,24,26,27,28,29 | RNA Labeling、Genome Sequencing… | 同上 |
| Application | 30-37 | Fluorescent Labeling、PCR/qPCR、Sequencing、FISH… | **详情页全部 404**，列表搜不到 |
| Application | 45 | Other / Experimental Descriptions | 语料兜底类别 |
| Method | 36 | Random Primer Method（active） | 不在可见方法里 |

这 19 个误标正好解释了三个可见数字的**全部**差额：
RG 11,037−11,028=9、AP 28,566−28,558=8、Method 449−448=1。

原命令只能按**名称前缀**批量操作，无法按 id 精确纠正 ——
而 `--prefix ''`（空前缀）会 `name__startswith=''` 匹配**全部行**，
这极可能就是误标的来源。本文件锁住两件事：

1. 空前缀**必须被拒绝**（否则一次误跑就把全站打成夹具）
2. `--id` 模式**只动列出的行**，且缺 `--model` / 缺 `--id` 都要报错
"""
from django.core.management import call_command as _call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.knowledge.models import Application, Method, ResearchGoal
from apps.knowledge.tests.factories import (
    ApplicationFactory,
    MethodFactory,
    ResearchGoalFactory,
)

import io


def call_command(*args, **kwargs):
    """统一吞掉命令输出。

    直接 `call_command` 会把内容写进 sys.stdout，pytest 捕获后关闭流，
    Django 的 OutputWrapper 在 teardown 时 flush 会抛
    `ValueError: I/O operation on closed file`（不影响断言，但污染日志、
    在 CI 里会被误判为错误）。这里默认塞一个 StringIO。
    """
    kwargs.setdefault('stdout', io.StringIO())
    kwargs.setdefault('stderr', io.StringIO())
    return _call_command(*args, **kwargs)


class MarkFixturesByIdTest(TestCase):
    """精确 id 纠正 + 空前缀防护。"""

    def setUp(self):
        self.real = ResearchGoalFactory(name='RNA Analysis', status='active',
                                        is_test_fixture=True)
        self.other = ResearchGoalFactory(name='Cancer Biology', status='active',
                                         is_test_fixture=True)
        self.keep = ResearchGoalFactory(name='__e2e_goals_123__', status='draft',
                                        is_test_fixture=True)

    # ── 精确 id：只动列出的行 ───────────────────────────────
    def test_unmark_only_listed_ids(self):
        call_command('mark_test_fixtures', model='ResearchGoal',
                     id=[self.real.id], unmark=True)
        self.real.refresh_from_db()
        self.other.refresh_from_db()
        self.keep.refresh_from_db()
        self.assertFalse(self.real.is_test_fixture, '指定的 id 应被撤销标记')
        self.assertTrue(self.other.is_test_fixture, '未列出的真实实体不能被顺带改动')
        self.assertTrue(self.keep.is_test_fixture, '真夹具（__ 前缀）必须保持标记')

    def test_unmark_restores_public_visibility(self):
        """撤销后必须回到 public() 里 —— 这是「详情页 404 消失」的根因。"""
        self.assertNotIn(self.real, ResearchGoal.objects.public())
        call_command('mark_test_fixtures', model='ResearchGoal',
                     id=[self.real.id], unmark=True)
        self.assertIn(self.real, ResearchGoal.objects.public())

    def test_dry_run_writes_nothing(self):
        call_command('mark_test_fixtures', model='ResearchGoal',
                     id=[self.real.id], unmark=True, dry_run=True)
        self.real.refresh_from_db()
        self.assertTrue(self.real.is_test_fixture, '--dry-run 不得写库')

    def test_mark_by_id_also_works(self):
        """反向：把清理时漏网的一行补标（不带 --unmark）。"""
        stray = ResearchGoalFactory(name='__e2e_goals_999__', status='draft',
                                    is_test_fixture=False)
        call_command('mark_test_fixtures', model='ResearchGoal', id=[stray.id])
        stray.refresh_from_db()
        self.assertTrue(stray.is_test_fixture)

    # ── 参数守卫 ───────────────────────────────────────────
    def test_empty_prefix_is_rejected(self):
        """★ 空前缀会匹配全部行 —— 这是误标最可能的来源，必须拦住。"""
        with self.assertRaises(CommandError):
            call_command('mark_test_fixtures', prefix='', unmark=True)
        self.real.refresh_from_db()
        self.assertTrue(self.real.is_test_fixture, '被拒后不得有任何写入')

    def test_id_without_model_is_rejected(self):
        with self.assertRaises(CommandError):
            call_command('mark_test_fixtures', id=[self.real.id], unmark=True)

    def test_model_without_id_is_rejected(self):
        with self.assertRaises(CommandError):
            call_command('mark_test_fixtures', model='ResearchGoal', unmark=True)

    # ── 回归：原前缀用法不受影响 ────────────────────────────
    def test_prefix_mode_still_works(self):
        call_command('mark_test_fixtures', prefix='__', unmark=True)
        self.keep.refresh_from_db()
        self.real.refresh_from_db()
        self.assertFalse(self.keep.is_test_fixture, '前缀模式应把 __ 开头的撤销')
        self.assertTrue(self.real.is_test_fixture, '前缀模式不能波及普通名字')

    def test_zero_delete_invariant(self):
        """铁律：本命令只打标记，绝不删除数据。"""
        before = (ResearchGoal.objects.count(), Application.objects.count(),
                  Method.objects.count())
        call_command('mark_test_fixtures', model='ResearchGoal',
                     id=[self.real.id], unmark=True)
        after = (ResearchGoal.objects.count(), Application.objects.count(),
                 Method.objects.count())
        self.assertEqual(before, after)
