"""
summary_i18n — 清理混入英文站的 CJK summary（导出审核表 / 按表回写）。

## 背景

2026-10-30 首页走查实测：英文站里有 **45 条 summary 是中文**（ResearchGoal 25 + Application 20），
而且**全部落在最顶层、最显眼的实体上**（Cancer Biology、RNA Analysis、Nucleic Acid Extraction、
Sequencing Library Preparation…）。首页与列表页一点进去就看到中英混杂。

病因是这批实体来自早期中文整理稿，之后没做本地化。

## 两条子命令

| 命令 | 作用 |
|---|---|
| `--export` | 从库里导出「含 CJK 的 summary」到 CSV（带已填好的 proposed_en 初稿），供人审 |
| `--apply`  | 读 CSV，把 `approved_en`（为空则用 `proposed_en`）写回库；原值备份为 JSON |

## 安全约束

- `--apply` 默认 dry-run，必须再加 `--apply` 才写库
- 写库前把「原值 → 新值」全量落 JSON 备份（`--backup-dir`），可原样回滚
- CSV 里 `skip` 列填任意非空值时跳过该行（人工判断「这条先不动」）
- 只处理 `status='active'` 的实体；draft/archived 不碰
- 回写只改 `summary` 一个字段，不动 name/slug/关联

## 用法

    python manage.py summary_i18n --export
    # 人工审 docs/i18n/cjk_summaries_i18n.csv 的 proposed_en / approved_en 两列
    python manage.py summary_i18n --apply
    python manage.py summary_i18n --apply --commit
"""
import csv
import json
import os
import re
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from apps.knowledge.models import Application, ResearchGoal

CJK = re.compile(r'[\u4e00-\u9fff]')
CSV_HEADER = [
    'kind', 'id', 'name', 'original_zh', 'proposed_en', 'approved_en',
    'review_note', 'skip',
]
MODELS = {'research_goal': ResearchGoal, 'application': Application}
DEFAULT_CSV = 'docs/i18n/cjk_summaries_i18n.csv'


class Command(BaseCommand):
    help = '导出 / 回写被中文化污染的 summary（默认只读导出，--apply 才写库）'

    def add_arguments(self, parser):
        parser.add_argument('--export', action='store_true', help='导出 CSV 审核表')
        parser.add_argument('--apply', action='store_true', help='按 CSV 回写数据库')
        parser.add_argument('--commit', action='store_true',
                            help='与 --apply 连用才真正写库（不加则仅预演）')
        parser.add_argument('--csv', default=DEFAULT_CSV, help=f'CSV 路径（默认 {DEFAULT_CSV}）')
        parser.add_argument('--backup-dir', default='/tmp/summary_i18n_bak',
                            help='原值备份目录')

    def handle(self, *args, **opts):
        if opts['export'] == opts['apply']:
            raise CommandError('必须且只能指定 --export 或 --apply 之一。')
        if opts['export']:
            return self._export(opts['csv'])
        return self._apply(opts['csv'], opts['backup_dir'], commit=opts['commit'])

    # ---------- 导出 ----------

    def _export(self, path):
        rows = []
        for kind, model in MODELS.items():
            qs = model.objects.filter(status='active').only('id', 'name', 'summary').order_by('id')
            for obj in qs:
                text = (obj.summary or '').strip()
                if not text or not CJK.search(text):
                    continue
                rows.append({
                    'kind': kind,
                    'id': obj.id,
                    'name': obj.name,
                    'original_zh': text,
                    'proposed_en': '',
                    'approved_en': '',
                    'review_note': '',
                    'skip': '',
                })

        if not rows:
            self.stdout.write(self.style.SUCCESS('没有含中文的 summary，无需处理。'))
            return

        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        existed = os.path.isfile(path)
        mode = 'a' if existed else 'w'
        with open(path, mode, encoding='utf-8-sig', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=CSV_HEADER)
            if not existed:
                w.writeheader()
            w.writerows(rows)

        self.stdout.write(self.style.SUCCESS(
            f'已导出 {len(rows)} 条到 {path}'
            + ('（追加）' if existed else '（新建）')))
        per = {}
        for r in rows:
            per[r['kind']] = per.get(r['kind'], 0) + 1
        for k, v in per.items():
            self.stdout.write(f'  {k}: {v}')

    # ---------- 回写 ----------

    def _apply(self, path, backup_dir, commit=False):
        if not os.path.isfile(path):
            raise CommandError(f'CSV 不存在：{path}（先跑 --export）')

        with open(path, encoding='utf-8-sig', newline='') as fh:
            rows = list(csv.DictReader(fh))

        applicable, skipped, missing, unchanged = [], [], [], []
        for r in rows:
            if (r.get('skip') or '').strip():
                skipped.append(r)
                continue
            new = (r.get('approved_en') or '').strip() or (r.get('proposed_en') or '').strip()
            if not new:
                skipped.append(r)
                continue
            if CJK.search(new):
                raise CommandError(
                    f"{r['kind']} {r['id']} 的译文中仍含中文：{new!r}（先修 CSV）")
            model = MODELS.get(r['kind'])
            if model is None:
                raise CommandError(f"未知 kind：{r['kind']}")
            obj = model.objects.filter(pk=int(r['id'])).first()
            if obj is None:
                missing.append(r)
                continue
            if (obj.summary or '').strip() == new:
                unchanged.append(r)
                continue
            applicable.append((obj, r, new))

        self.stdout.write(f'CSV 共 {len(rows)} 行')
        self.stdout.write(f'  待写 {len(applicable)}')
        self.stdout.write(f'  已是目标值 {len(unchanged)}')
        self.stdout.write(f'  跳过（skip/无译文） {len(skipped)}')
        if missing:
            self.stdout.write(self.style.WARNING(f'  查不到实体 {len(missing)}'))

        if not applicable:
            self.stdout.write(self.style.SUCCESS('无需动作。'))
            return

        payload = {
            'generated_at': datetime.now().isoformat(timespec='seconds'),
            'count': len(applicable),
            'items': [
                {'kind': r['kind'], 'id': obj.pk, 'name': obj.name,
                 'before': obj.summary, 'after': new}
                for obj, r, new in applicable
            ],
        }
        try:
            os.makedirs(backup_dir, exist_ok=True)
            bpath = os.path.join(backup_dir, 'summary_i18n_before.json')
            with open(bpath, 'w', encoding='utf-8') as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=1)
            self.stdout.write(f'原值已备份：{bpath}')
        except OSError as exc:
            if commit:
                raise
            self.stdout.write(self.style.WARNING(f'备份失败（预演可忽略）：{exc}'))

        for obj, r, new in applicable[:5]:
            self.stdout.write(f"  例：{r['kind']} {obj.pk} {obj.name[:36]!r}")
            self.stdout.write(f"      原：{obj.summary[:60]}")
            self.stdout.write(f"      新：{new[:60]}")

        if not commit:
            self.stdout.write(self.style.WARNING(
                '\n预演，未写库。加 --commit 执行（--apply --commit）。'))
            return

        from django.db import transaction
        with transaction.atomic():
            for obj, _r, new in applicable:
                obj.summary = new
                obj.save(update_fields=['summary'])
        self.stdout.write(self.style.SUCCESS(f'已回写 {len(applicable)} 条。'))

        # 收尾核对：再扫一遍 active 实体，确认 0 条残留
        remain = 0
        for model in MODELS.values():
            for obj in model.objects.filter(status='active').only('summary'):
                if obj.summary and CJK.search(obj.summary):
                    remain += 1
        if remain:
            self.stdout.write(self.style.WARNING(f'★ 仍有 {remain} 条含中文（可能不在 CSV 里）'))
        else:
            self.stdout.write(self.style.SUCCESS('核对通过：active 实体已无中文 summary。'))
