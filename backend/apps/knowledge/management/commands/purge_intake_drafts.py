"""清理过期的知识录入草稿（A-070 方案 A 的配套清理策略）。

## 为什么要单独一个命令，而不是在请求里顺手删
用户可能正开着 Intake 页面在填。若在别的请求里按时间删草稿，正好删掉他手上那份
⇒ 又是一次"静默丢数据"。所以清理只由人工/cron 触发，不在请求路径里做。

## 用法
```
# 看会删哪些（不真删）
python manage.py purge_intake_drafts --days 30 --dry-run

# 真删（保留期默认 30 天）
python manage.py purge_intake_drafts
```

## 保留期的口径
按 `updated_at`（最后一次保存时间），不是 `created_at` —— 用户反复修改的草稿不该因为
"第一次填是很久以前"被清掉。
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.knowledge.models import KnowledgeIntakeDraft


class Command(BaseCommand):
    help = '删除超过保留期的知识录入草稿（默认 30 天，按 updated_at 判定）'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30,
                            help='保留天数（默认 30）')
        parser.add_argument('--dry-run', action='store_true',
                            help='只统计不删除')

    def handle(self, *args, **options):
        days = options['days']
        dry = options['dry_run']
        if days < 1:
            self.stderr.write('--days 必须 ≥ 1')
            return
        cutoff = timezone.now() - timedelta(days=days)
        qs = KnowledgeIntakeDraft.objects.filter(updated_at__lt=cutoff)
        n = qs.count()
        if dry:
            self.stdout.write(f'[dry-run] 将删除 {n} 条 updated_at < {cutoff.isoformat()} 的草稿')
            for row in qs.values('id', 'product_id', 'updated_at')[:20]:
                self.stdout.write(f"  - id={row['id']} product={row['product_id']} "
                                  f"updated_at={row['updated_at'].isoformat()}")
            return
        deleted, _ = qs.delete()
        self.stdout.write(self.style.SUCCESS(
            f'已删除 {deleted} 条过期草稿（保留 {days} 天，cutoff={cutoff.isoformat()}）'))
