"""知识实体批量发布命令 — publish_knowledge_entities。

缺口 X 决策 A（用户拍板 2026-09-01）：把非 fixture 的 draft RG/AP 批量置 ACTIVE，
让 T4 真实提取数据在公开面可见（RG/AP 列表、详情、收敛类成员、产品/协议/方法
详情页研究路径跳转）。数据真实（T4 验收 PASS），draft 仅是导入默认值
（import_topchain_extractions 未传 status，走模型默认 draft），非"审核未过"。

- 默认 dry-run：只统计不落库，输出完整影响面报告。
- --apply：真正把 status='draft' 且 is_test_fixture=False 的 RG/AP 置 ACTIVE。
  **范围守卫**：archived / deprecated / 已 ACTIVE / 任何 fixture 一律不动。
- --report <path>：报告 JSON 输出路径（缺省仅打印到 stdout）。
- --verify：apply 后做 ORM 级完整性核对（模拟公开过滤计数 + 无残留断言）。

用法：
  python manage.py publish_knowledge_entities
  python manage.py publish_knowledge_entities --apply
  python manage.py publish_knowledge_entities --apply --verify --report /tmp/publish_report.json
"""
import json
from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.knowledge.models import Application, ResearchGoal

MODELS = (ResearchGoal, Application)


class Command(BaseCommand):
    help = '批量发布非 fixture 的 draft 知识实体（RG/AP）为 ACTIVE（默认 dry-run）'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', default=False,
                            help='真正落库（缺省为 dry-run，只统计不写库）')
        parser.add_argument('--report', type=str, default='',
                            help='报告 JSON 输出路径（缺省仅打印到 stdout）')
        parser.add_argument('--verify', action='store_true', default=False,
                            help='apply 后做 ORM 级完整性核对（模拟公开过滤 + 无残留断言）')

    def handle(self, *args, **options):
        self.apply = options['apply']
        report_path = options['report']
        verify = options['verify']
        if verify and not self.apply:
            raise CommandError('--verify 仅在 --apply 模式下有意义')

        stats = {'mode': 'apply' if self.apply else 'dry-run'}
        for model in MODELS:
            label = model.__name__.lower()
            stats[label] = self._collect(model)

        self.stdout.write(self.style.SUCCESS(
            f'===== publish_knowledge_entities [{"APPLY" if self.apply else "DRY-RUN"}] ====='
        ))
        for model in MODELS:
            label = model.__name__.lower()
            s = stats[label]
            self.stdout.write(
                f'\n[{label}] total={s["total"]} '
                f'by_status={s["by_status"]} fixtures={s["fixtures"]} '
                f'draft_non_fixture={s["draft_non_fixture"]}'
            )

        if self.apply:
            for model in MODELS:
                label = model.__name__.lower()
                with transaction.atomic():
                    updated = model.objects.filter(
                        status=model.Status.DRAFT, is_test_fixture=False
                    ).update(status=model.Status.ACTIVE)
                stats[label]['published'] = updated
                self.stdout.write(self.style.SUCCESS(
                    f'[{label}] published draft→active: {updated}'
                ))
            if verify:
                self._verify(stats)

        if report_path:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2, default=str)
            self.stdout.write(f'报告已写入 {report_path}')

        if not self.apply:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN：未修改任何数据。确认影响面后加 --apply 真正发布。'
            ))

    # ------------------------------------------------------------------ #
    # 辅助
    # ------------------------------------------------------------------ #
    @staticmethod
    def _collect(model):
        """单模型影响面统计（只读）。"""
        by_status = dict(
            Counter(model.objects.values_list('status', flat=True))
        )
        return {
            'total': model.objects.count(),
            'by_status': by_status,
            'fixtures': model.objects.filter(is_test_fixture=True).count(),
            'draft_non_fixture': model.objects.filter(
                status=model.Status.DRAFT, is_test_fixture=False
            ).count(),
        }

    def _verify(self, stats):
        """apply 后 ORM 级完整性核对：模拟公开过滤计数 + 无残留断言。"""
        ok = True
        for model in MODELS:
            label = model.__name__.lower()
            draft_left = model.objects.filter(
                status=model.Status.DRAFT, is_test_fixture=False
            ).count()
            active_public = model.objects.filter(
                status=model.Status.ACTIVE, is_test_fixture=False
            ).count()
            fixtures_intact = model.objects.filter(
                is_test_fixture=True, status=model.Status.DRAFT
            ).count()
            stats[label]['verify_draft_left'] = draft_left
            stats[label]['verify_active_public'] = active_public
            stats[label]['verify_fixture_draft_intact'] = fixtures_intact
            self.stdout.write(
                f'[verify:{label}] draft_non_fixture_left={draft_left} '
                f'active_public={active_public} fixture_draft_intact={fixtures_intact}'
            )
            if draft_left != 0:
                self.stderr.write(self.style.ERROR(
                    f'[verify:{label}] 仍有 {draft_left} 条非 fixture draft 未发布！'
                ))
                ok = False
        if not ok:
            raise CommandError('完整性核对失败：存在未发布的非 fixture draft 实体')
        self.stdout.write(self.style.SUCCESS('完整性核对通过：无残留非 fixture draft'))
