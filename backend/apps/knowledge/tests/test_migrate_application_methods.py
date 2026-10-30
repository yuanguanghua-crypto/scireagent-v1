"""
migrate_application_methods 测试（B 方案：应用↔方法 1:N → M:N）。

用最小但**结构真实**的场景验证：draft 副本 + 同名 active + archived 混合，
这正是生产库的形态（47,761 行 draft 副本、10 个带 application 的 active、
81 个 archived）。

必须验证的三件事：
1. `--step all` 之后 `--step verify` **不抛异常**（逐应用与基线一致）
2. 桥的内容正确：同 app 多条同名 draft 只写一条；active 带 application 的
   要合并到 canonical 且写桥
3. archived 也要迁（它在 get_methods 里走 canonical 映射，漏了 verify 会报缺）
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
from apps.knowledge.models import (
    Application, ApplicationMethod, Method, Protocol,
)


def _app(name):
    return Application.objects.create(name=name, slug=name.lower().replace(' ', '-')[:60])


def _method(name, status='active', app=None, slug=None):
    # slug 必须唯一（模型 unique）；同一 name+status 会在场景里出现多次
    import uuid
    return Method.objects.create(
        name=name, status=status, application=app,
        slug=slug or f'{name.lower().replace(" ", "-")[:40]}-{status}-{uuid.uuid4().hex[:8]}',
    )


def _protocol(name):
    return Protocol.objects.create(
        name=name, slug=f'p-{name.lower().replace(" ", "-")[:50]}',
        version='1.0', status='published')


class MigrateApplicationMethodsTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='am_')
        self.bak = os.path.join(self.tmp, 'bak')

    def tearDown(self):
        for root, dirs, files in os.walk(self.tmp, topdown=False):
            for f in files:
                os.remove(os.path.join(root, f))
            for d in dirs:
                os.rmdir(os.path.join(root, d))

    def _run(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            call_command('migrate_application_methods', '--backup-dir', self.bak, *args)
        return buf.getvalue()

    def _build_scene(self):
        """构造生产同构的场景。"""
        a1, a2 = _app('App One'), _app('App Two')
        # canonical 池：active 且无 application
        pcr = _method('PCR', 'active', None)
        wb = _method('Western Blot', 'active', None)
        # a1 的 draft 副本：同名 PCR 三行（模拟每个应用各存一份）
        d1 = _method('PCR', 'draft', a1)
        d2 = _method('PCR', 'draft', a1)
        d3 = _method('Western Blot', 'draft', a1)
        # a2 的 draft 副本 + archived 副本（archived 也走 canonical 映射，必须迁）
        d4 = _method('PCR', 'draft', a2)
        d5 = _method('Western Blot', 'archived', a2)
        # 带 application 的 active（与 canonical 重名）—— 应被合并
        act_dup = _method('PCR', 'active', a1)
        # 噪音名（无 canonical）—— 应被丢弃
        noisy = _method('__e2e_methods_1__', 'draft', a1)
        # 给 act_dup 挂一条 method_protocol，验证重指向
        proto = _protocol('Proto A')
        MethodProtocol.objects.create(method=act_dup, protocol=proto, status='active')
        return dict(a1=a1, a2=a2, pcr=pcr, wb=wb, act_dup=act_dup, proto=proto)

    # ---------- 完整流程 ----------

    def test_full_flow_then_verify_passes(self):
        self._build_scene()
        self._run('--step', 'baseline')
        self.assertTrue(os.path.isfile(os.path.join(self.bak, 'baseline_app_methods.json')))
        self._run('--step', 'all', '--apply')
        # verify 不抛异常即通过
        out = self._run('--step', 'verify')
        self.assertIn('OK', out)

    def test_bridge_content_correct(self):
        s = self._build_scene()
        self._run('--step', 'baseline')
        self._run('--step', 'all', '--apply')

        # a1 应有 PCR + Western Blot 两个方法；a2 应有 PCR + Western Blot
        a1_names = sorted(ApplicationMethod.objects.filter(application=s['a1'])
                          .values_list('method__name', flat=True))
        a2_names = sorted(ApplicationMethod.objects.filter(application=s['a2'])
                          .values_list('method__name', flat=True))
        self.assertEqual(a1_names, ['PCR', 'Western Blot'])
        self.assertEqual(a2_names, ['PCR', 'Western Blot'])

        # 桥必须指向 canonical（无 application 的 active 行）
        for row in ApplicationMethod.objects.select_related('method'):
            self.assertIsNone(row.method.application_id,
                              '桥必须指向 canonical（application 为空的 active）')
            self.assertEqual(row.method.status, 'active')

    def test_duplicate_drafts_collapse_to_one(self):
        s = self._build_scene()
        self._run('--step', 'baseline')
        self._run('--step', 'all', '--apply')
        # a1 有 3 条同名 PCR 的 draft，桥里只能有 1 条
        qty = ApplicationMethod.objects.filter(
            application=s['a1'], method__name='PCR').count()
        self.assertEqual(qty, 1)

    def test_archived_is_migrated(self):
        """archived 在 get_methods 里走 canonical 映射，漏迁会让 verify 报缺。"""
        s = self._build_scene()
        self._run('--step', 'baseline')
        self._run('--step', 'all', '--apply')
        names = set(ApplicationMethod.objects.filter(application=s['a2'])
                    .values_list('method__name', flat=True))
        self.assertIn('Western Blot', names)   # 它的来源是 archived 副本

    def test_active_with_application_is_merged(self):
        s = self._build_scene()
        self._run('--step', 'baseline')
        self._run('--step', 'all', '--apply')
        # 同名 active 被删，其 method_protocol 重指向 canonical
        self.assertFalse(Method.objects.filter(id=s['act_dup'].id).exists())
        self.assertTrue(MethodProtocol.objects.filter(
            method_id=s['pcr'].id, protocol_id=s['proto'].id).exists())

    def test_noisy_name_is_dropped(self):
        self._build_scene()
        self._run('--step', 'baseline')
        self._run('--step', 'all', '--apply')
        names = set(ApplicationMethod.objects.values_list('method__name', flat=True))
        self.assertFalse(any(n.startswith('__e2e') for n in names))

    # ---------- 安全闸门 ----------

    def test_dry_run_writes_nothing(self):
        self._build_scene()
        self._run('--step', 'baseline')
        self._run('--step', 'all', '--dry-run')
        self.assertEqual(ApplicationMethod.objects.count(), 0)

    def test_verify_without_baseline_raises(self):
        with self.assertRaises(CommandError):
            self._run('--step', 'verify')

    def test_verify_detects_missing_bridge(self):
        s = self._build_scene()
        self._run('--step', 'baseline')
        self._run('--step', 'all', '--apply')
        # 人为删掉一条桥，verify 必须报错
        ApplicationMethod.objects.filter(application=s['a1'], method__name='PCR').delete()
        with self.assertRaises(CommandError) as ctx:
            self._run('--step', 'verify')
        self.assertIn('不一致', str(ctx.exception))

    def test_guard_blocks_when_bridge_left(self):
        """待删的 active 若仍被桥引用，merge 必须中止而不是静默级联删。

        用 ProductMethod 构造（CASCADE，删 Method 不会抛 ProtectedError，
        但会静默丢数据）—— 闸门正是为了拦住这种静默丢失。
        PMR 走的是 PROTECT（数据库自己会挡），行为已被 SQL 保证，不在此重复构造
        （它还有 `ck_pmr_relation_discriminator` 的复杂约束）。
        """
        s = self._build_scene()
        from apps.bridges.models import ProductMethod
        from apps.commerce.models import Product
        prod = Product.objects.create(
            name='Fake Product', slug='fake-product', catalog_no='FAKE-1')
        ProductMethod.objects.create(product=prod, method=s['act_dup'], role='reagent')
        self._run('--step', 'baseline')
        with self.assertRaises(CommandError) as ctx:
            self._run('--step', 'merge-active', '--apply')
        self.assertIn('PROTECT', str(ctx.exception))
        # 没删
        self.assertTrue(Method.objects.filter(id=s['act_dup'].id).exists())
