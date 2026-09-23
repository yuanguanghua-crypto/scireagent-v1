"""purge_verified_orphans 管理命令最小单测。

验收（与命令的默认 dry-run 纪律对齐）：
- 默认（不加 --apply）绝不删行；
- --apply 只删命中的 rejected 行，active 行不受影响；
- 无任何显式选择器时拒绝执行（CommandError）。
"""
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.bridges.models import ProductMethodRelation
from apps.bridges.tests.factories import ProductMethodRelationFactory
from apps.commerce.tests.factories import ProductFactory
from apps.knowledge.tests.factories import MethodFactory


class PurgeVerifiedOrphansTests(TestCase):
    def setUp(self):
        self.product = ProductFactory(name='P', catalog_no='SC-PURGE')
        self.orphan = ProductMethodRelationFactory(
            product=self.product, method=MethodFactory(name='M1'),
            status='rejected', evidence_note='purge-cmd-selftest orphan')
        self.active = ProductMethodRelationFactory(
            product=self.product, method=MethodFactory(name='M2'),
            status='active', evidence_type='pubmed',
            evidence_reference=[{'type': 'PMID', 'value': '1'}],
            evidence_strength='high', curator='curator')

    def _run(self, *args):
        out = StringIO()
        call_command('purge_verified_orphans', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_does_not_delete(self):
        self._run('--all-rejected')
        self.assertTrue(
            ProductMethodRelation.objects.filter(id=self.orphan.id).exists())
        self.assertTrue(
            ProductMethodRelation.objects.filter(id=self.active.id).exists())

    def test_apply_deletes_only_targeted_rejected(self):
        self._run('--note-like', 'purge-cmd-selftest', '--apply')
        self.assertFalse(
            ProductMethodRelation.objects.filter(id=self.orphan.id).exists())
        self.assertTrue(
            ProductMethodRelation.objects.filter(id=self.active.id).exists())

    def test_no_selector_refuses(self):
        with self.assertRaises(CommandError):
            self._run()
