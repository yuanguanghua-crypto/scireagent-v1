"""
Build ProductClass category tree (v1 authority) and link products.

v1 权威分类表：3 个 L1（采纳 jena 产品线）共 21 个 L2，L3 待研究员后续细化。
分类树以 ProductClass 表为唯一权威，本命令负责建树 + 回填 product_class_id +
清理 v1 之外的孤立 ProductClass。

Usage: python manage.py setup_categories
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.commerce.models import ProductClass, Product


# v1 权威分类表：L1 slug → {label, children: {L2_name: [L3_name, ...]}}
# 来源：jena 产品线采纳 3 个（Nucleotides / Click Chemistry / Molecular Biology），
# L2 清洗规整自 jena category_path，L3 暂留空待研究员细化。
CATEGORY_TREE = {
    'nucleotides_nucleosides': {
        'label': 'Nucleotides & Nucleosides',
        'children': {
            'Fluorescent Nucleotides': [],
            'Nucleotides labeled with Functional Groups': [],
            'Important Structure Motifs': [],
            'Cyclic Nucleotides': [],
            'Nucleotide Trove': [],
            'Non-hydrolyzable Nucleotides': [],
            'Unmodified Nucleotides': [],
            'Analogs and Derivatives': [],
            'Unprotected Nucleosides': [],
        },
    },
    'click_chemistry': {
        'label': 'Click Chemistry',
        'children': {
            'Click Reagents by Chemistry': [],
            'Click Reagents by Application': [],
        },
    },
    'molecular_biology': {
        'label': 'Molecular Biology',
        'children': {
            'Reverse Transcription & RT-PCR': [],
            'Enzymes & Protein Markers': [],
            'Real-Time PCR': [],
            'RNA/DNA Preparation & Cleanup': [],
            'Single Components': [],
            'PCR Classics': [],
            'Buffers and Reagents': [],
            'Contamination & Controls': [],
            'Isothermal Amplification & LAMP': [],
            'Cloning and Mutagenesis': [],
        },
    },
}

# v1 保留的 L1 slug 集合（用于清理孤立节点）
V1_L1_SLUGS = set(CATEGORY_TREE.keys())


class Command(BaseCommand):
    help = 'Build v1 ProductClass category tree, link products, prune orphan categories'

    def handle(self, *args, **options):
        # Clear existing test categories
        deleted, _ = ProductClass.objects.filter(slug__startswith='test-').delete()
        self.stdout.write(f'Cleared {deleted} test categories')

        created_count = 0
        sort_order = 0

        # 保留的 slug 集合（v1 树中出现的所有 L1/L2/L3 slug）
        kept_slugs = set()

        for l1_key, l1_data in CATEGORY_TREE.items():
            sort_order += 1
            l1_name = l1_data['label']
            l1_slug = slugify(l1_key)
            kept_slugs.add(l1_slug)

            l1_obj, created = ProductClass.objects.update_or_create(
                slug=l1_slug,
                defaults={
                    'name': l1_name,
                    'parent': None,
                    'sort_order': sort_order,
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f'  L1: {l1_name}')
            else:
                self.stdout.write(f'  L1: {l1_name} (exists)')

            # L2 children
            l2_sort = 0
            for l2_name, l3_list in l1_data['children'].items():
                l2_sort += 1
                l2_slug = slugify(f'{l1_key}-{l2_name}')
                kept_slugs.add(l2_slug)

                l2_obj, created = ProductClass.objects.update_or_create(
                    slug=l2_slug,
                    defaults={
                        'name': l2_name,
                        'parent': l1_obj,
                        'sort_order': l2_sort,
                    }
                )
                if created:
                    created_count += 1
                    self.stdout.write(f'    L2: {l2_name}')

                # L3 children (if any)
                l3_sort = 0
                for l3_name in l3_list:
                    l3_sort += 1
                    l3_slug = slugify(f'{l1_key}-{l2_name}-{l3_name}')
                    kept_slugs.add(l3_slug)

                    _, created = ProductClass.objects.update_or_create(
                        slug=l3_slug,
                        defaults={
                            'name': l3_name,
                            'parent': l2_obj,
                            'sort_order': l3_sort,
                        }
                    )
                    if created:
                        created_count += 1

        self.stdout.write(self.style.SUCCESS(f'\nCreated/updated {created_count} categories'))

        # 回填 product_class_id：按 category_l1 slug 匹配 L1，
        # 若 category_l2 name 能匹配该 L1 下某 L2 则挂到 L2，否则挂 L1。
        linked_l1 = 0
        linked_l2 = 0
        skipped = 0
        for product in Product.objects.all():
            l1_slug = product.category_l1
            if not l1_slug:
                skipped += 1
                continue
            try:
                l1_pc = ProductClass.objects.get(slug=slugify(l1_slug), parent__isnull=True)
            except ProductClass.DoesNotExist:
                self.stdout.write(f'  WARN: No L1 ProductClass for category_l1={l1_slug!r} (product {product.id})')
                skipped += 1
                continue

            # 尝试按 category_l2 name 匹配 L2
            target_pc = l1_pc
            cat_l2_raw = (product.category_l2 or '').strip()
            # 旧 category_l2 可能存 "L2 | L3" 拼接，取第一段
            cat_l2_name = cat_l2_raw.split('|')[0].strip() if cat_l2_raw else ''
            if cat_l2_name:
                l2_pc = ProductClass.objects.filter(
                    parent=l1_pc, name=cat_l2_name
                ).first()
                if l2_pc:
                    target_pc = l2_pc
                    linked_l2 += 1
                else:
                    linked_l1 += 1
            else:
                linked_l1 += 1

            product.product_class = target_pc
            product.save(update_fields=['product_class'])

        self.stdout.write(self.style.SUCCESS(
            f'Linked products: {linked_l1} to L1, {linked_l2} to L2, {skipped} skipped (no category_l1)'
        ))

        # 清理孤立 ProductClass：不在 v1 树中且无产品引用的节点
        orphans = ProductClass.objects.exclude(slug__in=kept_slugs)
        # 只删除没有产品引用的孤儿
        deletable = [pc for pc in orphans if not pc.products.exists()]
        deleted_count = 0
        # 自底向上删除（先删子节点避免 ON DELETE CASCADE 阻塞）
        for pc in sorted(deletable, key=lambda x: x.parent_id is not None, reverse=True):
            if not pc.products.exists():
                pc.delete()
                deleted_count += 1
        if deleted_count:
            self.stdout.write(self.style.WARNING(
                f'Pruned {deleted_count} orphan ProductClass nodes not in v1 tree'
            ))

        # 报告仍有产品引用的废弃节点（不能删）
        still_referenced = orphans.filter(products__isnull=False).distinct()
        if still_referenced.exists():
            self.stdout.write(self.style.WARNING(
                f'  {still_referenced.count()} non-v1 ProductClass still referenced by products (kept)'
            ))
