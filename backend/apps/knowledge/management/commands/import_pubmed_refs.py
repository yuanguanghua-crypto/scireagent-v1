"""管理命令：从扫描报告导入 PubMed 文献到 Reference + ProductReference"""
import json
import sys
from datetime import datetime
from django.core.management.base import BaseCommand
from apps.knowledge.models import Reference
from apps.commerce.models import Product
from apps.bridges.models import ProductReference


class Command(BaseCommand):
    help = '从 scan_report.json 导入 PubMed 文献'

    def add_arguments(self, parser):
        parser.add_argument('--report', type=str,
                            default=r'E:\scireagent-tencent\backend\data\scan_report.json')

    def handle(self, *args, **options):
        report_path = options['report']
        with open(report_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        results = data['results']
        stats = {'created_refs': 0, 'skipped_refs': 0, 'created_links': 0, 'errors': 0}

        for row in results:
            if not row.get('refs'):
                continue
            try:
                product = Product.objects.get(id=row['id'])
            except Product.DoesNotExist:
                continue

            for ref_data in row['refs']:
                pmid = ref_data.get('pmid')
                title = ref_data.get('title', '')
                if not pmid:
                    continue

                # 查重
                existing = Reference.objects.filter(pmid=pmid).first()
                if existing:
                    ref = existing
                    stats['skipped_refs'] += 1
                else:
                    # 从 PMID 号推断年份
                    year = None
                    try:
                        pmid_int = int(pmid)
                        # PMID 年份无法直接推断，设为 None
                        pass
                    except ValueError:
                        pass

                    doi = ref_data.get('doi') or ref_data.get('elocationid', '')
                    if doi and not doi.startswith('10.'):
                        doi = ''
                    ref = Reference.objects.create(
                        title=title or f'PubMed article {pmid}',
                        pmid=pmid,
                        doi=doi or None,
                        journal='',
                        year=year,
                        source_type='journal',
                    )
                    stats['created_refs'] += 1

                # 关联产品（去重）
                link_exists = ProductReference.objects.filter(
                    product=product, reference=ref
                ).exists()
                if not link_exists:
                    ProductReference.objects.create(
                        product=product,
                        reference=ref,
                        citation_role='supporting',
                    )
                    stats['created_links'] += 1

        self.stdout.write(self.style.SUCCESS(
            f'导入完成: 新建 {stats["created_refs"]} 条参考文献, '
            f'跳过 {stats["skipped_refs"]} 条已有, '
            f'新建 {stats["created_links"]} 条产品关联, '
            f'错误 {stats["errors"]}'
        ))
