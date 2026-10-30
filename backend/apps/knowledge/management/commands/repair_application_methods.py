"""
repair_application_methods — 补齐 `migrate-drafts` 漏建的「应用↔方法」桥。

## 为什么需要这个命令

`migrate_application_methods --step migrate-drafts` 的映射规则是：
「legacy Method（status != active，带 application）→ 同名唯一 canonical（active、application IS NULL）」。
它当时只跑了一遍，之后又有补救（把 archived 也纳入范围），但**没有重跑**。

后果（2026-10-30 首页走查实测，本地库）：
- 应建桥 63,589 条，实存 63,526 条 ⇒ **缺 63 条**；
- 落在 **20 个应用**上，且全是**顶层技术族**：Nucleic Acid Extraction(46)、
  Protein Extraction(47)、Metabolite Sample Preparation(48)、Enzymology(61)…
- 这些应用的详情页只显示 "Methods are being curated for this application."，
  而搜索 "Nucleic Acid Extraction" 的**第 1 条命中就是 AP 46** ⇒ 用户点进去看到空页。

`migrate-drafts --apply` 虽然幂等也能补，但它会重算全部 6 万行的 display_order，
改动面远大于实际缺口。本命令只补「同名唯一 canonical 存在、但桥缺失」的 pair，
不动任何现有行。

## 安全约束

- **默认 dry-run**，必须 `--apply` 才写库
- `ignore_conflicts=True` + `unique_together (application, method)` ⇒ 天然幂等，可反复跑
- 同名 canonical 不唯一（>1 个 active 同名）时**跳过**，遵循「宁 miss 不错配」
- `display_order` 接在「该应用现有最大 display_order」之后，按方法名字典序，保证可复现
- 写库前把「将要新增的 pair」落 JSON 备份到 `--backup-dir`

## 用法

    python manage.py repair_application_methods                    # 预演
    python manage.py repair_application_methods --apply            # 执行
    python manage.py repair_application_methods --apply --backup-dir /home/admin/scireagent_backups
"""
import json
import os
from collections import defaultdict
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Max

from apps.knowledge.models import ApplicationMethod, Method

BATCH = 2000
SOURCE = 'repair'


class Command(BaseCommand):
    help = '补齐 legacy Method → canonical 的 ApplicationMethod 桥（幂等，默认预演）'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='真正写库（默认只预演）')
        parser.add_argument('--backup-dir', default='/tmp/appmethod_bak',
                            help='新增 pair 的 JSON 备份目录')

    def handle(self, *args, **opts):
        apply_mode = opts['apply']

        # ── 1. canonical 池：只认 active 且无 application 归属的行 ──
        canon_pool = defaultdict(list)
        for row in Method.objects.filter(
            status='active', application__isnull=True
        ).values('id', 'name'):
            canon_pool[row['name']].append(row['id'])

        # ── 2. legacy 行：非 active 且带 application ──
        legacy = Method.objects.filter(
            application_id__isnull=False
        ).exclude(status='active').values('id', 'name', 'application_id', 'status')

        need = {}          # (app_id, canon_id) -> name
        skipped_ambiguous = 0
        skipped_name = []  # 名字映射不到唯一 canonical 的方法名（取样）
        for row in legacy:
            targets = canon_pool.get(row['name']) or []
            if len(targets) != 1:
                skipped_ambiguous += 1
                if len(skipped_name) < 10:
                    skipped_name.append(f"{row['name']} × {len(targets)}")
                continue
            need[(row['application_id'], targets[0])] = row['name']

        # ── 3. 现有桥 ──
        existing = set(
            ApplicationMethod.objects.values_list('application_id', 'method_id')
        )
        missing = {k: v for k, v in need.items() if k not in existing}

        self.stdout.write(f'canonical 方法名 {len(canon_pool)} 个')
        self.stdout.write(f'legacy 行（draft+archived，带 application） {legacy.count()} 行')
        self.stdout.write(f'可建桥 pair 总数 {len(need)}，已存在 {len(need) - len(missing)}')
        self.stdout.write(self.style.WARNING(f'★ 缺失待补 {len(missing)} 条'))
        self.stdout.write(f'名字映射不到唯一 canonical 而跳过 {skipped_ambiguous} 行')
        if skipped_name:
            self.stdout.write(f'  取样：{skipped_name}')

        if not missing:
            self.stdout.write(self.style.SUCCESS('无缺口，无需动作。'))
            return

        # 受影响的 AP 明细，便于人工核对
        per_app = defaultdict(list)
        for (app_id, canon_id), name in missing.items():
            per_app[app_id].append((name, canon_id))
        self.stdout.write(f'涉及应用 {len(per_app)} 个：')
        for app_id in sorted(per_app)[:40]:
            names = sorted(n for n, _ in per_app[app_id])
            self.stdout.write(f'  AP {app_id}: {names}')

        # ── 4. 备份将要新增的 pair ──
        backup_dir = opts['backup_dir']
        payload = {
            'generated_at': datetime.now().isoformat(timespec='seconds'),
            'source': SOURCE,
            'total': len(missing),
            'per_app': {
                str(aid): sorted([{'name': n, 'canonical_id': c} for n, c in items],
                                 key=lambda x: x['name'])
                for aid, items in per_app.items()
            },
        }
        try:
            os.makedirs(backup_dir, exist_ok=True)
            path = os.path.join(backup_dir, 'appmethod_repair_pairs.json')
            with open(path, 'w', encoding='utf-8') as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=1)
            self.stdout.write(f'待新增 pair 已备份：{path}')
        except OSError as exc:
            if apply_mode:
                raise
            self.stdout.write(self.style.WARNING(f'备份失败（预演可忽略）：{exc}'))

        if not apply_mode:
            self.stdout.write(self.style.WARNING('\n预演，未写库。加 --apply 执行。'))
            return

        # ── 5. 写库：display_order 接在现有最大值之后 ──
        max_order = {
            row['application_id']: row['max_order']
            for row in ApplicationMethod.objects
            .values('application_id')
            .annotate(max_order=Max('display_order'))
        }
        objs = []
        for app_id in sorted(per_app):
            base = max_order.get(app_id)
            start = 0 if base is None else base + 1
            for offset, (_name, canon_id) in enumerate(sorted(per_app[app_id])):
                objs.append(ApplicationMethod(
                    application_id=app_id,
                    method_id=canon_id,
                    display_order=start + offset,
                    source=SOURCE,
                ))

        created = 0
        with transaction.atomic():
            for i in range(0, len(objs), BATCH):
                chunk = objs[i:i + BATCH]
                created += len(ApplicationMethod.objects.bulk_create(
                    chunk, batch_size=BATCH, ignore_conflicts=True))

        self.stdout.write(self.style.SUCCESS(
            f'已写入桥 {created} 条（目标 {len(objs)}，差额为已存在的幂等跳过）'))

        # ── 6. 收尾核对 ──
        after = set(ApplicationMethod.objects.values_list('application_id', 'method_id'))
        still = [k for k in missing if k not in after]
        if still:
            self.stdout.write(self.style.ERROR(f'★ 仍有 {len(still)} 条未落库：{still[:10]}'))
        else:
            self.stdout.write(self.style.SUCCESS('核对通过：缺口已全部补齐。'))
