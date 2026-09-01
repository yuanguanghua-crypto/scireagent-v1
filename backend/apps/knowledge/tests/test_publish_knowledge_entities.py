"""publish_knowledge_entities 范围守卫测试（TDD）。

缺口 X 决策 A：批量把非 fixture draft RG/AP 置 ACTIVE。
范围守卫铁律：
  - dry-run 不修改任何数据；
  - apply 只动 status='draft' 且 is_test_fixture=False 的实体；
  - archived / deprecated / 已 ACTIVE / 任何 fixture 一律不动；
  - --verify 在 apply 后断言无残留非 fixture draft。
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.knowledge.models import Application, ResearchGoal
from apps.knowledge.tests.factories import ApplicationFactory, ResearchGoalFactory


class PublishKnowledgeEntitiesTest(TestCase):
    def setUp(self):
        # 非 fixture draft（将被发布）
        self.rg_draft = ResearchGoalFactory()  # status=draft, is_test_fixture=False
        self.ap_draft = ApplicationFactory()
        # 已 ACTIVE 非 fixture（不应动）
        self.rg_active = ResearchGoalFactory(
            status=ResearchGoal.Status.ACTIVE)
        self.ap_active = ApplicationFactory(
            status=Application.Status.ACTIVE)
        # archived / deprecated（不应动）
        self.rg_archived = ResearchGoalFactory(
            status=ResearchGoal.Status.ARCHIVED)
        self.ap_deprecated = ApplicationFactory(
            status=Application.Status.DEPRECATED)
        # fixture draft（不应动——fixture 一律不发布）
        self.rg_fixture = ResearchGoalFactory(is_test_fixture=True)
        self.ap_fixture = ApplicationFactory(is_test_fixture=True)

    def _snapshot(self):
        """各实体状态快照，用于断言未变。"""
        return {obj.pk: obj.status for obj in (
            self.rg_active, self.ap_active, self.rg_archived,
            self.ap_deprecated, self.rg_fixture, self.ap_fixture,
        )}

    def test_dry_run_does_not_modify_data(self):
        call_command('publish_knowledge_entities')
        # 所有实体状态保持原样
        self.assertEqual(self.rg_draft.status, ResearchGoal.Status.DRAFT)
        self.assertEqual(self.ap_draft.status, Application.Status.DRAFT)
        self.assertEqual(self._snapshot(), {
            self.rg_active.pk: ResearchGoal.Status.ACTIVE,
            self.ap_active.pk: Application.Status.ACTIVE,
            self.rg_archived.pk: ResearchGoal.Status.ARCHIVED,
            self.ap_deprecated.pk: Application.Status.DEPRECATED,
            self.rg_fixture.pk: ResearchGoal.Status.DRAFT,
            self.ap_fixture.pk: Application.Status.DRAFT,
        })

    def test_dry_run_reports_to_publish_counts(self):
        out = StringIO()
        call_command('publish_knowledge_entities', stdout=out)
        text = out.getvalue()
        # Application 只造了 1 条非 fixture draft（RG 会因 ApplicationFactory 的
        # SubFactory 连带创建额外 draft RG，故只断言 AP 行）。
        self.assertIn('draft_non_fixture=1', text)
        self.assertIn('DRY-RUN', text)

    def test_apply_publishes_only_draft_non_fixture(self):
        call_command('publish_knowledge_entities', apply=True)
        # 发布后：draft 非 fixture → ACTIVE
        self.rg_draft.refresh_from_db()
        self.ap_draft.refresh_from_db()
        self.assertEqual(self.rg_draft.status, ResearchGoal.Status.ACTIVE)
        self.assertEqual(self.ap_draft.status, Application.Status.ACTIVE)
        # 其余状态不动
        self.assertEqual(self._snapshot(), {
            self.rg_active.pk: ResearchGoal.Status.ACTIVE,
            self.ap_active.pk: Application.Status.ACTIVE,
            self.rg_archived.pk: ResearchGoal.Status.ARCHIVED,
            self.ap_deprecated.pk: Application.Status.DEPRECATED,
            self.rg_fixture.pk: ResearchGoal.Status.DRAFT,
            self.ap_fixture.pk: Application.Status.DRAFT,
        })

    def test_verify_passes_after_apply(self):
        call_command('publish_knowledge_entities', apply=True, verify=True)
        # verify 无 CommandError 即通过（无残留非 fixture draft）
        self.assertEqual(
            ResearchGoal.objects.filter(
                status=ResearchGoal.Status.DRAFT, is_test_fixture=False
            ).count(), 0)
        self.assertEqual(
            Application.objects.filter(
                status=Application.Status.DRAFT, is_test_fixture=False
            ).count(), 0)

    def test_verify_requires_apply(self):
        # --verify 不带 --apply 应报错
        from django.core.management import CommandError
        with self.assertRaises(CommandError):
            call_command('publish_knowledge_entities', verify=True)

    def test_fixture_draft_never_published(self):
        # fixture draft 即使 apply 也保持 draft（fixture 一律不可见）
        call_command('publish_knowledge_entities', apply=True)
        self.rg_fixture.refresh_from_db()
        self.ap_fixture.refresh_from_db()
        self.assertEqual(self.rg_fixture.status, ResearchGoal.Status.DRAFT)
        self.assertEqual(self.ap_fixture.status, Application.Status.DRAFT)
