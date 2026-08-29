"""generate_verified_drafts — Evidence Miner 批量草稿生成命令（C2）。

用法：
  python manage.py generate_verified_drafts                        # dry-run（默认，全 active 产品）
  python manage.py generate_verified_drafts --product-ids 23,27    # 指定产品
  python manage.py generate_verified_drafts --apply                # 执行落库
  python manage.py generate_verified_drafts --apply --report drafts_report.json

安全：默认 dry-run；--apply 才写库；幂等（同 PMID 已存在则跳过）；不自动 approve。
"""
import json

from django.core.management.base import BaseCommand

from apps.bridges.services.verified_drafts_generator import generate_verified_drafts
from apps.commerce.models import Product


class Command(BaseCommand):
    help = 'Evidence Miner 候选 → PMR(REVIEW) verified 草稿（两维度分离，relevance 级）'

    def add_arguments(self, parser):
        parser.add_argument('--product-ids', default='',
                            help='逗号分隔产品 id；默认全部 active 产品')
        parser.add_argument('--apply', action='store_true',
                            help='执行落库（默认 dry-run 仅规划）')
        parser.add_argument('--report', default='',
                            help='可选：把完整明细写入 JSON 报告文件')

    def handle(self, *args, **options):
        if options['product_ids']:
            ids = [int(x) for x in options['product_ids'].split(',') if x.strip()]
        else:
            ids = list(
                Product.objects.filter(status='active').values_list('id', flat=True))

        stats = generate_verified_drafts(ids, apply=options['apply'])

        mode = 'APPLY' if options['apply'] else 'DRY-RUN'
        self.stdout.write(f'=== generate_verified_drafts [{mode}] products={len(ids)} ===')
        self.stdout.write(
            f'planned={stats["planned"]} created={stats["created"]} '
            f'skip_dup={stats["skipped_dup"]} no_method={stats["no_method"]} '
            f'zero_candidate={stats["zero_candidate"]}'
        )
        for row in stats['rows']:
            self.stdout.write(
                f"  p={row['product_id']} {row['action']:<10} "
                f"pmid={row['pmid']} method={row['method'] or '—':<40} "
                f"{row['strength']}"
            )

        if options['report']:
            import os
            os.makedirs(os.path.dirname(os.path.abspath(options['report'])),
                        exist_ok=True)
            with open(options['report'], 'w', encoding='utf-8') as f:
                json.dump({'mode': mode, 'stats': {
                    k: v for k, v in stats.items() if k != 'rows'
                }, 'rows': stats['rows']}, f, ensure_ascii=False, indent=1)
            self.stdout.write(f'报告已写入 {options["report"]}')
