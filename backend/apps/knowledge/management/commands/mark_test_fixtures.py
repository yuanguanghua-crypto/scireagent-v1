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

    # ★ 按 id 精确操作（2026-10-30 加）：只影响列出的行，用于纠正误标。
    #   必须配 --model（id 在不同实体间会重复，例如 RG 33 与 AP 33 是两回事）
    python manage.py mark_test_fixtures --model ResearchGoal --id 23 --id 33 --dry-run
    python manage.py mark_test_fixtures --model ResearchGoal --id 23 --id 33 --unmark
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.knowledge.models import Application, Method, Reference, ResearchGoal

DEFAULT_PREFIX = '__'

# (label, Model, 名称字段) —— Reference 的名字字段是 title 不是 name
TARGET_MODELS = (
    ('ResearchGoal', ResearchGoal, 'name'),
    ('Application', Application, 'name'),
    ('Method', Method, 'name'),
    ('Reference', Reference, 'title'),
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
        parser.add_argument(
            '--model', choices=[label for label, _m, _f in TARGET_MODELS],
            help='配合 --id 使用：限定要操作的实体类型',
        )
        parser.add_argument(
            '--id', action='append', type=int, default=[],
            help='按主键精确操作，可重复；必须同时给 --model',
        )

    def handle(self, *args, **options):
        prefix = options['prefix']
        dry_run = options['dry_run']
        unmark = options['unmark']
        by_id = options['id'] or []
        only_model = options['model']

        if by_id and not only_model:
            raise CommandError('--id 必须配合 --model 使用（id 在不同实体间会重复）。')
        if only_model and not by_id:
            raise CommandError('--model 只在按 id 精确操作时使用，请同时给 --id。')
        # ★ 2026-10-30 加：空前缀会 `name__startswith=''` 匹配**全部行**。
        #   这是最可能的误标来源 —— 一次误跑就把真实实体（RNA Analysis、
        #   Cancer Biology…）全打成夹具，而它们本该出现在前台。
        #   纠正时发现 18 个真实实体被误标（9 RG + 9 AP + 1 Method），
        #   其中一个挂着 876 个应用。宁可报错，也不允许空前缀跑批量标记。
        if not by_id and not prefix.strip():
            raise CommandError(
                '空前缀会匹配全部实体（name__startswith=""），拒绝执行。'
                '若要精确纠正误标，请用 --model + --id。')

        target_value = not unmark
        verb = '取消标记' if unmark else '标记'
        scope = f'id={sorted(set(by_id))} @ {only_model}' if by_id else f'前缀="{prefix}"'

        totals_before = {label: Model.objects.count() for label, Model, _f in TARGET_MODELS}

        summary = []
        with transaction.atomic():
            for label, Model, name_field in TARGET_MODELS:
                if by_id:
                    if label != only_model:
                        continue
                    qs = Model.objects.filter(pk__in=by_id)
                else:
                    qs = Model.objects.filter(**{f'{name_field}__startswith': prefix})
                pending = qs.exclude(is_test_fixture=target_value)
                names = list(pending.values_list('id', name_field)[:50])
                count = pending.count()

                if not dry_run and count:
                    pending.update(is_test_fixture=target_value)

                summary.append((label, count, qs.count(), names))

            # id 模式下逐个核对「请求的 id 是否都真的存在」，防止静默漏改
            not_found = []
            if by_id:
                Model = {lbl: m for lbl, m, _f in TARGET_MODELS}[only_model]
                found = set(Model.objects.filter(pk__in=by_id).values_list('id', flat=True))
                not_found = sorted(set(by_id) - found)

        # 铁律①硬校验：行数必须一字未变
        totals_after = {label: Model.objects.count() for label, Model, _f in TARGET_MODELS}
        if totals_before != totals_after:
            raise RuntimeError(
                f'数据行数发生变化，违反零删除铁律: {totals_before} -> {totals_after}'
            )

        mode = '[DRY-RUN] ' if dry_run else ''
        self.stdout.write(f'{mode}范围={scope} 操作={verb}')
        for label, count, matched, names in summary:
            self.stdout.write(f'  {label}: 匹配 {matched} 行，本次{verb} {count} 行')
            for oid, name in names:
                self.stdout.write(f'      id={oid} {name}')
        if not_found:
            self.stdout.write(self.style.WARNING(
                f'★ 以下 id 在 {only_model} 中不存在：{not_found}'))
        self.stdout.write(
            f'{mode}行数校验通过（零删除）: '
            + ', '.join(f'{k}={v}' for k, v in totals_after.items())
        )
