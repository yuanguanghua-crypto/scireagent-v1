"""detect_substructures —— 对全库带 SMILES 的商品跑四轴子结构判定（S6 覆盖测量 + 治理落库）。

用法：
    python manage.py detect_substructures [--json out.json]
    python manage.py detect_substructures --write        # 把四轴判定写入 Product.substructure_tags

默认：纯只读、零写入、零删除（仅输出统计 + 数据质量标记）。
--write：把 build_substructure_payload 的结果写入 Product.substructure_tags（离线填充、用户不可写），
         数据质量告警（名称宣称糖环类型 vs SMARTS 判定）照常打印但**不阻断**写入。

依赖 RDKit（独立 py3.12 venv，由 S6_RDKIT_VENV / settings.S6_RDKIT_VENV_PATH 指定）。
"""
import json

from django.core.management.base import BaseCommand, CommandError

from apps.bridges.services.substructure_backend import (
    build_substructure_payload,
    s6_rdkit_venv_path,
    _rdkit,
)

# 名称宣称的糖环类型（用于数据质量对照）
_DEOXY_HINTS = ('dutp', 'datp', 'dctp', 'dgtp', 'dntp', "2'-f", "2'-azido",
                "2'-fluoro", "2'-nh2", "2'-amino")
_RIBOSE_HINTS = ('utp', 'atp', 'ctp', 'gtp', 'ntp')


class Command(BaseCommand):
    help = "Run four-axis SMARTS substructure detection over all products with SMILES."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json", default=None,
            help="Optional output JSON path for the full stats dict.",
        )
        parser.add_argument(
            "--write", action="store_true",
            help="Write the four-axis payload into Product.substructure_tags (offline enrichment; "
                 "data-quality warnings still printed but never block the write).",
        )

    def handle(self, *args, **opts):
        try:
            _rdkit()
        except Exception as e:
            raise CommandError(
                f"RDKit 不可用（venv={s6_rdkit_venv_path()}）：{e}\n"
                f"请在独立 py3.12 venv 安装 rdkit 并设置 S6_RDKIT_VENV。"
            )

        from apps.commerce.models import Product

        qs = Product.objects.exclude(smiles__isnull=True).exclude(smiles='')
        total = qs.count()
        written = 0
        stats = {
            'total_with_smiles': total,
            'parsed': 0,
            'unparsed': 0,
            'base': {},
            'sugar_sub': {},
            'sugar_type': {},
            'base_mod': {},
            'biotin_label': 0,
            'ntp': 0,
            'propargyl': 0,
            'data_quality': [],
        }

        for p in qs.iterator():
            payload = build_substructure_payload(p.smiles)
            # qs 已排除空 SMILES，payload 不应为 None；防御性兜底
            if payload is None:
                stats['unparsed'] += 1
                continue

            d = payload['axes']
            if payload['parsed'] and d is not None:
                stats['parsed'] += 1
                for k in ('base', 'sugar_sub', 'sugar_type', 'base_mod'):
                    v = d[k]
                    if v:
                        stats[k][v] = stats[k].get(v, 0) + 1
                stats['biotin_label'] += int(bool(d['biotin_label']))
                stats['ntp'] += int(bool(d['ntp']))
                stats['propargyl'] += int(bool(d['propargyl']))

                # 数据质量：名称宣称糖环类型 vs SMARTS 判定
                name = (p.name or '').lower()
                claimed = None
                if any(h in name for h in _DEOXY_HINTS):
                    claimed = 'deoxy'
                elif any(h in name for h in _RIBOSE_HINTS):
                    claimed = 'ribose'
                if claimed and d['sugar_type'] != claimed:
                    stats['data_quality'].append({
                        'catalog_no': p.catalog_no,
                        'name': p.name,
                        'claimed': claimed,
                        'detected': d['sugar_type'],
                    })
            else:
                stats['unparsed'] += 1

            if opts.get('write'):
                p.substructure_tags = payload
                p.save(update_fields=['substructure_tags'])
                written += 1

        if opts.get('json'):
            with open(opts['json'], 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
            self.stdout.write(f"wrote {opts['json']}")

        summary = {k: v for k, v in stats.items() if k != 'data_quality'}
        if opts.get('write'):
            summary['written_substructure_tags'] = written
        self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2))
        if stats['data_quality']:
            self.stdout.write("=== 数据质量：名称宣称与 SMARTS 判定不一致 ===")
            for d in stats['data_quality']:
                self.stdout.write(
                    f"  {d['catalog_no']} {d['name']} | 名称={d['claimed']} 判定={d['detected']}"
                )
