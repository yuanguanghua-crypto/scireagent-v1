"""
Biotium → Product 受控毕业导入（Biotium × AI AUTO MATCH 集成方案 步骤5）。

将 datasource_eval 沙箱清洗产物（biotium_supplier_formal.jsonl）导入为 Product
实体（status=draft，绝不自动激活）。140 零误差黄金集的结构图（PubChem PNG base64）
写入 Product.structure_image（原样保存，前端 <img> 渲染）。

纪律：
  - 全部 draft，不激活（激活须人工审核 Import）；
  - 不自动落库到其他表；SKU 留空（无定价数据），激活时再补；
  - 不猜测/补全任何缺失字段；仅搬运沙箱中已验证的数据。

用法：
  python manage.py import_biotium [--file PATH] [--limit N] [--dry-run] [--clear]

  --dry-run  仅统计与打印，不写库（默认推荐先跑一次验证映射）
  --clear    导入前先删除 catalog_no 在本次文件集合内的已有 Biotium 产品（幂等重导）
  --limit N  仅导入前 N 条（调试用）

说明（数据落点）：
  - cas / formula / molecular_weight 来自记录（formula 取 extras.formula 或 pubchem_formula）
  - structure_image 仅 140 黄金集有（PubChem PNG，加 data:image/png;base64, 前缀）
  - ex_em（荧光试剂核心光谱）Product 无专用列，暂存入 overview 文本，供检索可见；
    后续如需持久化结构化光谱，须扩 Product 模型字段。
  - product_type / cas_source 属 matcher 层元数据，已在 data/suppliers/biotium.jsonl
    候选源中保留，不重复落 Product。
  - product_class 留空：Biotium 荧光/生物制品不在平台已采纳的 3 个 L1 内，避免错分。
"""
import json
import os

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.commerce.models import Product

# 默认读 backend/data/suppliers/biotium.jsonl（即已注册的候选源文件，生产/本地一致）。
# 沙箱清洗产物 biotium_supplier_formal.jsonl 需先复制/软链到该路径（或由 --file 指定）。
DEFAULT_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))),
    "data", "suppliers", "biotium.jsonl",
)


class Command(BaseCommand):
    help = 'Import Biotium products (draft) from biotium_supplier_formal.jsonl'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, default=DEFAULT_FILE,
                            help='Path to biotium_supplier_formal.jsonl')
        parser.add_argument('--limit', type=int, default=0,
                            help='Only import first N records (0 = all)')
        parser.add_argument('--dry-run', action='store_true',
                            help='Count and print only, no DB writes')
        parser.add_argument('--clear', action='store_true',
                            help='Delete existing Biotium products whose catalog_no is in this file')

    def handle(self, *args, **options):
        file_path = options['file']
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'File not found: {file_path}'))
            return

        with open(file_path, 'r', encoding='utf-8') as f:
            records = [json.loads(l) for l in f if l.strip()]

        limit = options['limit'] or len(records)
        records = records[:limit]
        self.stdout.write(f'Loaded {len(records)} records from {file_path}')

        # 收集 catalog_no 集合（供 --clear 与去重）
        catalog_nos = [r.get('catalog_no', '').strip() for r in records if r.get('catalog_no')]
        catalog_nos = [c for c in catalog_nos if c]

        if options['clear'] and not options['dry_run']:
            deleted = Product.objects.filter(catalog_no__in=catalog_nos).delete()[0]
            self.stdout.write(self.style.WARNING(f'Cleared {deleted} existing Biotium products'))

        created = skipped = updated = 0
        with_structure = 0

        for r in records:
            catalog_no = (r.get('catalog_no') or '').strip()
            name = (r.get('product_name') or '').strip()
            if not catalog_no or not name:
                skipped += 1
                continue

            extras = r.get('extras') or {}

            # 唯一 slug（基于 catalog_no，避免中文名 slugify 为空）
            base_slug = slugify(f"biotium-{catalog_no}")[:240] or f"biotium-{catalog_no}"[:240]
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"[:250]
                counter += 1

            # 结构图（140 黄金集，PubChem PNG base64 → data URL）
            structure_image = ''
            b64 = extras.get('structure_image_b64')
            if b64:
                structure_image = f"data:image/png;base64,{b64}"
                with_structure += 1

            # Ex/Em 光谱（Product 无专用列，暂入 overview 文本，保留可见性）
            overview = (r.get('description') or '').strip()
            ex_em = (r.get('ex_em') or '').strip()
            if ex_em:
                ex_line = f"Ex/Em: {ex_em}"
                overview = f"{ex_line}\n{overview}".strip() if overview else ex_line

            # 分子量与分子式
            mw_raw = extras.get('mw')
            molecular_weight = None
            if mw_raw not in (None, ''):
                try:
                    molecular_weight = float(mw_raw)
                except (TypeError, ValueError):
                    molecular_weight = None
            formula = extras.get('formula') or extras.get('pubchem_formula') or ''

            exists = Product.objects.filter(catalog_no=catalog_no).first()

            if options['dry_run']:
                if exists:
                    updated += 1
                else:
                    created += 1
                continue

            if exists:
                # 幂等：仅补结构图（若此前缺失），不覆盖既有字段
                if not exists.structure_image and structure_image:
                    exists.structure_image = structure_image
                    exists.save(update_fields=['structure_image'])
                    updated += 1
                else:
                    skipped += 1
                continue

            Product.objects.create(
                catalog_no=catalog_no,
                name=name,
                slug=slug,
                cas=(r.get('cas_number') or '').strip(),
                formula=formula,
                molecular_weight=molecular_weight,
                structure_image=structure_image,
                overview=overview,
                status='draft',
                research_use_only=True,
                # product_class 留空（Biotium 不在已采纳 L1）；SKU 留空（无定价）
            )
            created += 1

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('[DRY-RUN] 未写入数据库'))
        self.stdout.write(self.style.SUCCESS(
            f'\nDone! created={created} updated={updated} skipped={skipped} '
            f'with_structure_image={with_structure} (total scanned={len(records)})'
        ))
