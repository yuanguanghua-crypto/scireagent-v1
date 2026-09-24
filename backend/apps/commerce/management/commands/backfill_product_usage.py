"""
backfill_product_usage — 第一版 §9 步骤2（docx 入库之 usage 灌入）。

读取 backend/docx_products.json（key=`catalog`=SCxxxx，`usage`=厂商声称用途），
按 Product.catalog_no == docx.catalog 匹配，将 usage 灌入对应 Product.usage。

契约（见 test_backfill_product_usage.py）：
- 仅填充已存在的、catalog 匹配的 Product（不创建新 Product）
- 空值安全：docx 条目 usage 为空/缺失则不覆盖（跳过）
- ★ **默认只填空值**（`Product.usage` 已有内容则**跳过，不覆盖**）——
  这是 2026-09-24 为 P2（研究员可在页面录入 usage）加的**保护**：
  原先本命令**无条件覆盖**，会把研究员手填的 usage 静默冲掉。
- ★ `--force`：显式允许覆盖，并**打印被覆盖的条数与样例**（可审计）。需要 docx 语料刷新时才用。
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
        parser.add_argument(
            '--force',
            action='store_true',
            help='允许覆盖已有 usage（默认**只填空值**，以保护人工录入/既有内容）',
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
        force = options['force']

        usage_map, skipped_empty = self._load_map(path)
        self.stdout.write(
            f"数据源：{path}\n"
            f"  有效 catalog→usage 条目：{len(usage_map)}（跳过空 usage：{skipped_empty}）\n"
            f"  模式：{'--force（允许覆盖）' if force else '默认（只填空值）'}"
        )

        matched = Product.objects.filter(catalog_no__in=usage_map.keys())
        matched_catalogs = set(matched.values_list('catalog_no', flat=True))
        self.stdout.write(f"  数据库中匹配 catalog 的 Product：{matched.count()}")

        filled = 0            # 空 → 有
        overwritten = 0       # 覆盖已有值（仅 --force）
        skipped_nonempty = 0  # 已有值，默认跳过
        samples = []          # 被跳过/覆盖的样例（审计用）

        for product in matched:
            target = usage_map[product.catalog_no]
            current = (product.usage or '').strip()
            if current == target:
                continue  # 幂等：同值跳过
            if current and not force:
                # ★ 保护：不覆盖已有内容（人工录入 / 既有 docx 值）
                skipped_nonempty += 1
                if len(samples) < 5:
                    samples.append((product.catalog_no, current[:40], target[:40]))
                continue
            if dry_run:
                overwritten += 1 if current else 0
                filled += 0 if current else 1
                continue
            product.usage = target
            product.save(update_fields=['usage'])
            if current:
                overwritten += 1
            else:
                filled += 1

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
            self.stdout.write(self.style.WARNING(
                f"[dry-run] 将填充 {filled} 条（空→有）、将覆盖 {overwritten} 条，未落库"))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"完成：填充 {filled} 条（空→有），覆盖 {overwritten} 条"))

        if skipped_nonempty:
            self.stdout.write(self.style.WARNING(
                f"跳过 {skipped_nonempty} 条（已有值，默认不覆盖；如需用 docx 刷新请加 --force）"))
            for cat, cur, tgt in samples:
                self.stdout.write(f"    例 {cat}：现值={cur!r} → docx={tgt!r}")
