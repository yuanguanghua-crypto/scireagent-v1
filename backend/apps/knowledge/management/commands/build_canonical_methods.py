"""build_canonical_methods —— P1-1 canonical Method 收敛命令。

背景：生产 47,834 行 Method 是 T2 补链产生的 draft（application=X, status='draft'），
P0（apply_public_visibility）把它们挡在展示面外，导致方法可见性覆盖率骤降。

本命令把「高频 draft 方法名」建成 canonical Method 实体（status='active',
application=None），供展示层「名字 → canonical」解析使用。

铁律：绝不删除 / 修改任何已存在的 draft 行（最大化数据、不删链）。

幂等：已存在同名 active 且 application=None 的 canonical 实体则跳过不建；
      slug 唯一，冲突由 Method.save() 自动加后缀。

用法：
  python manage.py build_canonical_methods            # dry-run（默认），只统计+列样本，不落库
  python manage.py build_canonical_methods --apply    # 实际建 canonical
  python manage.py build_canonical_methods --verify   # 核对 eligible 名是否已全部有 canonical
  python manage.py build_canonical_methods --min-count 20   # 只建出现 >=20 次的名字（默认 10）
"""
from django.core.management.base import BaseCommand

from apps.knowledge.models import Method, OriginChoices
from apps.knowledge.services.canonical_methods import (
    canonical_by_name,
    draft_name_counts,
)

_SAMPLE_LIMIT = 10


class Command(BaseCommand):
    help = '把高频 draft 方法名建成 canonical（active, application=None）Method 实体（默认 dry-run）'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', default=False,
                            help='实际建 canonical（缺省为 dry-run，只统计不落库）')
        parser.add_argument('--verify', action='store_true', default=False,
                            help='核对 eligible 名字是否已全部有 canonical（不落库）')
        parser.add_argument('--min-count', type=int, default=10,
                            help='只把 draft 中出现 >=N 次的名字建成 canonical（默认 10）')

    def handle(self, *args, **options):
        apply = options['apply']
        verify = options['verify']
        min_count = options['min_count']

        self.stdout.write('=' * 64)
        self.stdout.write('build_canonical_methods：canonical Method 收敛（P1-1）')
        mode = ('--apply（实际建 canonical）' if apply
                else '--verify（核对）' if verify
                else '[DRY-RUN]（默认，不修改数据）')
        self.stdout.write(f'模式：{mode}    min-count={min_count}')
        self.stdout.write('=' * 64)

        counts = draft_name_counts(min_count=min_count)
        counts_by_name = {r['name']: r['cnt'] for r in counts}
        total_draft = sum(counts_by_name.values())
        eligible_names = list(counts_by_name)
        existing = canonical_by_name(eligible_names)
        to_create = [name for name in eligible_names if name not in existing]

        self.stdout.write(f'draft 方法总行数（>=min-count 名字累计）：{total_draft}')
        self.stdout.write(f'唯一 draft 方法名（>=min-count）：{len(eligible_names)}')
        self.stdout.write(f'已存在 canonical（同名 active & application=None）：{len(existing)}')
        self.stdout.write(f'本次将建 canonical：{len(to_create)}')

        sample = counts[:_SAMPLE_LIMIT]
        if sample:
            self.stdout.write('样例（名字: 出现次数）：')
            for r in sample:
                tag = ' [已存在canonical]' if r['name'] in existing else ''
                self.stdout.write(f"  - {r['name']}: {r['cnt']}{tag}")

        if apply:
            created = 0
            for name in to_create:
                Method.objects.create(
                    name=name,
                    status=Method.Status.ACTIVE,
                    application=None,
                    origin=OriginChoices.AI_EXTRACTED,
                    origin_detail=f'canonical build from {counts_by_name[name]} draft methods (P1-1)',
                )
                created += 1
            self.stdout.write(f'完成：新建 canonical {created} 个，'
                              f'现有 canonical（active & application=None）'
                              f'{Method.objects.filter(status="active", application__isnull=True).count()} 个。')
            return

        if verify:
            missing = [name for name in eligible_names
                       if not Method.objects.filter(
                           name=name, status='active', application__isnull=True).exists()]
            self.stdout.write(f'核对：eligible {len(eligible_names)} 个名字中，'
                              f'仍缺 canonical 的：{len(missing)} 个')
            for name in missing[:_SAMPLE_LIMIT]:
                self.stdout.write(f'  - 缺：{name}')
            if not missing:
                self.stdout.write('核对通过：所有 eligible 名字均已存在 canonical。')
            return

        self.stdout.write('[DRY-RUN] 未修改任何数据。加 --apply 实际建 canonical，'
                          '或 --verify 核对。')
