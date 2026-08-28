"""
normalize_product_status — Product 非法状态清洗（A2 数据卫生，P0-5）。

背景：Product 状态机（core StatusMixin）= draft/active/deprecated/archived，
但历史遗留数据存在枚举外状态（如实测 dev 库 13 条 status='published'，全部
archived=True 的 docx 导入品）。

清洗映射（宁缺毋滥）：
  非法状态 + archived=True  → 'archived'（归档标志优先，绝不复活已归档产品）
  非法状态 + archived=False → 'draft'（不得自动上站，需人工定夺）

用法：
  python manage.py normalize_product_status            # dry-run，仅打印待清洗清单
  python manage.py normalize_product_status --apply    # 执行清洗

幂等：清洗后非法状态集为空，二次运行报 0 条。
合法枚举外的 Protocol/COA published 不在范围（它们是合法枚举）。
"""
from django.core.management.base import BaseCommand

from apps.commerce.models import Product

LEGAL_STATUSES = ('draft', 'active', 'deprecated', 'archived')


class Command(BaseCommand):
    help = '清洗 Product 枚举外状态：archived=True→archived，否则→draft'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='执行清洗（默认 dry-run 仅打印）',
        )

    def handle(self, *args, **options):
        apply_mode = options['apply']
        illegal = Product.objects.exclude(status__in=LEGAL_STATUSES)
        count = illegal.count()

        if count == 0:
            self.stdout.write('待清洗 0 条：全部 Product 状态合法。')
            return

        self.stdout.write(f'待清洗 {count} 条（{"APPLY" if apply_mode else "DRY-RUN"}）：')
        changed = 0
        for p in illegal.iterator():
            target = 'archived' if p.archived else 'draft'
            self.stdout.write(
                f'  id={p.id} catalog_no={p.catalog_no} name={p.name[:40]!r} '
                f'{p.status!r} -> {target!r} (archived={p.archived})'
            )
            if apply_mode:
                p.status = target
                # archived 映射时保持 archived 标志一致；draft 映射不动 archived
                p.save(update_fields=['status'])
                changed += 1

        if apply_mode:
            self.stdout.write(self.style.SUCCESS(
                f'完成：清洗 {changed} 条；剩余枚举外 '
                f'{Product.objects.exclude(status__in=LEGAL_STATUSES).count()} 条。'))
        else:
            self.stdout.write('DRY-RUN 结束（未写库）。确认后加 --apply 执行。')
