"""S2 管理命令：按 v2 重挂表重挂真实 Method，并把整句伪 Method 重挂到隔离用
catch-all Application（F3 Option A：零删除，保留 Protocol/Product 桥接）。

用法：
    python manage.py remap_method_applications --dry-run   # 只报告
    python manage.py remap_method_applications             # 真正写入
"""
from django.core.management.base import BaseCommand
from apps.knowledge.services.method_remap import (
    apply_method_remap,
    REMAP_TABLE,
    PSEUDO_METHODS,
    PSEUDO_TARGET_APPLICATION,
)
from apps.knowledge.models import ResearchGoal


class Command(BaseCommand):
    help = 'S2: 重挂真实 Method→Application，并把伪 Method 重挂到 catch-all Application（零删除）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='只报告将要做的改动，不写入数据库',
        )
        parser.add_argument(
            '--skip-pseudo', action='store_true',
            help='只做真实 Method 重挂，完全跳过伪 Method 重挂（隔离用逃生口）',
        )

    def handle(self, *args, **options):
        # ★ 2026-10-30：B 方案（ApplicationMethod 桥）已取代这套建模。
        #   本命令会把方法重挂到 `Method.application` FK 并造出 draft 副本 ——
        #   跑一次就等于把刚清理干净的 47,835 行又造回来。硬停。
        from django.core.management.base import CommandError
        raise CommandError(
            "已废弃：`Method.application` 语义由 ApplicationMethod 桥取代。\n"
            "方法与应用的关系请用 `ApplicationMethod` 维护（M:N），"
            "不要再造 application FK 下的 draft 副本。\n"
            "如需迁移数据，用 `migrate_application_methods`。")
        dry_run = options['dry_run']
        skip_pseudo = options['skip_pseudo']
        self.stdout.write(f'{"[DRY-RUN] " if dry_run else ""}S2 Method 重挂开始...')
        if skip_pseudo:
            self.stdout.write(self.style.WARNING('  --skip-pseudo：伪 Method 处置已跳过'))

        pseudo_methods = [] if skip_pseudo else PSEUDO_METHODS
        report = apply_method_remap(
            REMAP_TABLE, pseudo_methods, PSEUDO_TARGET_APPLICATION, dry_run=dry_run
        )

        self.stdout.write(self.style.SUCCESS(
            f"重挂真实 Method : {len(report['remapped'])} 条"
        ))
        for m, a in report['remapped']:
            self.stdout.write(f"    - {m}  ->  {a}")

        self.stdout.write(self.style.SUCCESS(
            f"伪 Method 重挂  : {len(report['reparented_pseudo'])} 条  "
            f"->  {PSEUDO_TARGET_APPLICATION}"
        ))
        for m, a in report['reparented_pseudo']:
            self.stdout.write(f"    - {m[:60]}...")

        if report['created_catchall_app']:
            self.stdout.write(self.style.SUCCESS(
                f"已新建 catch-all Application: {PSEUDO_TARGET_APPLICATION} "
                f"(research_goal=None, 隔离出 RG 树)"
            ))

        if report['missing_apps']:
            self.stdout.write(self.style.WARNING(
                f"缺失 Application（未重挂）: {report['missing_apps']}"
            ))
        if report['missing_methods']:
            self.stdout.write(self.style.WARNING(
                f"缺失 Method（未找到）: {report['missing_methods']}"
            ))

        if not dry_run:
            nonzero_rg = (
                ResearchGoal.objects
                .filter(applications__methods__isnull=False)
                .distinct().count()
            )
            total_rg = ResearchGoal.objects.count()
            self.stdout.write(self.style.SUCCESS(
                f"验收快照: 非零 RG = {nonzero_rg} / {total_rg}"
            ))
