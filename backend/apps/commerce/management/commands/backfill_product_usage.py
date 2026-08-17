"""
backfill_product_usage — 第一版 §9 步骤2（docx 入库之 usage 灌入）。

读取 backend/docx_products.json（key=`catalog`=SCxxxx，`usage`=厂商声称用途），
按 Product.catalog_no == docx.catalog 匹配，将 usage 灌入对应 Product.usage。

契约（见 test_backfill_product_usage.py）：
- 仅填充已存在的、catalog 匹配的 Product（不创建新 Product）
- 空值安全：docx 条目 usage 为空/缺失则不覆盖（跳过）
- 幂等：重复运行结果一致（同值写入）
- 默认数据源 = settings.BASE_DIR/docx_products.json，可用 --path 覆盖
- --dry-run 只报告不落库
"""
import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.commerce.models import Product


class Command(BaseCommand):
    help = "将 docx_products.json 的厂商声称用途(usage) 按 catalog 灌入已存在的 Product。"

    def add_arguments(self, parser):
        parser.add_argument(
            '--path',
            default=None,
            help='docx_products.json 路径（默认 settings.BASE_DIR/docx_products.json）',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='只报告匹配/将要更新的数量，不落库',
        )

    def _load_map(self, path):
        """返回 {catalog(去空格): usage}；仅含 usage 非空的条目（空值安全）。"""
        if not os.path.exists(path):
            raise CommandError(f"找不到 docx_products.json：{path}")
        with open(path, encoding='utf-8') as f:
            records = json.load(f)

        usage_map = {}
        skipped_empty = 0
        for rec in records:
            catalog = (rec.get('catalog') or '').strip()
            usage = (rec.get('usage') or '').strip()
            if not catalog:
                continue
            if not usage:
                skipped_empty += 1
                continue
            usage_map[catalog] = usage
        return usage_map, skipped_empty

    def handle(self, *args, **options):
        path = options['path'] or os.path.join(settings.BASE_DIR, 'docx_products.json')
        dry_run = options['dry_run']

        usage_map, skipped_empty = self._load_map(path)
        self.stdout.write(
            f"数据源：{path}\n"
            f"  有效 catalog→usage 条目：{len(usage_map)}（跳过空 usage：{skipped_empty}）"
        )

        matched = Product.objects.filter(catalog_no__in=usage_map.keys())
        matched_catalogs = set(matched.values_list('catalog_no', flat=True))
        self.stdout.write(f"  数据库中匹配 catalog 的 Product：{matched.count()}")

        updated = 0
        for product in matched:
            target = usage_map[product.catalog_no]
            if product.usage == target:
                continue  # 幂等：同值跳过
            if dry_run:
                updated += 1
                continue
            product.usage = target
            product.save(update_fields=['usage'])
            updated += 1

        # 报告未匹配到的 docx catalog（便于核对数据缺口）
        unmatched = sorted(set(usage_map.keys()) - matched_catalogs)
        if unmatched:
            self.stdout.write(
                self.style.WARNING(
                    f"  docx 中有 {len(unmatched)} 个 catalog 在 Product 表无匹配"
                    f"（前 10：{unmatched[:10]}）"
                )
            )

        if dry_run:
            self.stdout.write(self.style.WARNING(f"[dry-run] 将要更新 {updated} 条，未落库"))
        else:
            self.stdout.write(self.style.SUCCESS(f"完成：更新 {updated} 条 Product.usage"))
