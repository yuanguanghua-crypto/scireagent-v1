"""S1 — 标记自动化测试残留的顶部知识实体（不删除任何数据）。

背景：e2e 用例（frontend/e2e/inventory-driven/workspace.spec.cjs）在运行时用
``__e2e_<entity>_<timestamp>__`` 创建临时实体并在结束时 cleanup。清理失败会留下
残骸，污染 staff 后台列表与 search 端点（后者根本没有 status 过滤）。

铁律①：数据源≠商品 —— 本命令**只打标记，绝不删除**。标记后所有对外读取面
（列表/详情/search/search-suggest/search-grouped/site-navigation/graph）
会自动排除这些行；staff 可用 ``?include_test_fixtures=1`` 逃生口查看并人工处理。

用法::

    python manage.py mark_test_fixtures --dry-run      # 只报告
    python manage.py mark_test_fixtures                # 按默认前缀 "__" 标记
    python manage.py mark_test_fixtures --prefix ZZ_   # 自定义前缀
    python manage.py mark_test_fixtures --unmark       # 回滚标记（仍不删数据）
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.knowledge.models import Application, Method, ResearchGoal

DEFAULT_PREFIX = '__'

TARGET_MODELS = (
    ('ResearchGoal', ResearchGoal),
    ('Application', Application),
    ('Method', Method),
)


class Command(BaseCommand):
    help = '按名称前缀标记测试夹具实体（is_test_fixture=True）。只打标记，不删除数据。'

    def add_arguments(self, parser):
        parser.add_argument(
            '--prefix', default=DEFAULT_PREFIX,
            help=f'名称前缀，默认 "{DEFAULT_PREFIX}"',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='只报告将要标记的行，不写库',
        )
        parser.add_argument(
            '--unmark', action='store_true',
            help='回滚：把匹配前缀的行 is_test_fixture 置回 False',
        )

    def handle(self, *args, **options):
        prefix = options['prefix']
        dry_run = options['dry_run']
        unmark = options['unmark']
        target_value = not unmark
        verb = '取消标记' if unmark else '标记'

        totals_before = {label: Model.objects.count() for label, Model in TARGET_MODELS}

        summary = []
        with transaction.atomic():
            for label, Model in TARGET_MODELS:
                qs = Model.objects.filter(name__startswith=prefix)
                pending = qs.exclude(is_test_fixture=target_value)
                names = list(pending.values_list('id', 'name')[:50])
                count = pending.count()

                if not dry_run and count:
                    pending.update(is_test_fixture=target_value)

                summary.append((label, count, qs.count(), names))

        # 铁律①硬校验：行数必须一字未变
        totals_after = {label: Model.objects.count() for label, Model in TARGET_MODELS}
        if totals_before != totals_after:
            raise RuntimeError(
                f'数据行数发生变化，违反零删除铁律: {totals_before} -> {totals_after}'
            )

        mode = '[DRY-RUN] ' if dry_run else ''
        self.stdout.write(f'{mode}前缀="{prefix}" 操作={verb}')
        for label, count, matched, names in summary:
            self.stdout.write(f'  {label}: 匹配 {matched} 行，本次{verb} {count} 行')
            for oid, name in names:
                self.stdout.write(f'      id={oid} {name}')
        self.stdout.write(
            f'{mode}行数校验通过（零删除）: '
            + ', '.join(f'{k}={v}' for k, v in totals_after.items())
        )
