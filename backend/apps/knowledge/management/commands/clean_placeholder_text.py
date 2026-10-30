"""清掉被当成内容渲染的「占位字面量」脏值（如 `'{}'`、`'[]'`、`'None'`）。

## 背景（2026-10-30 知识实体走查）

用户点开协议详情，Troubleshooting tab 直接显示一个 `{}`。

根因：早期一批导入（id 113~200，88 条，76 条来自 protocol_io）把空的
dict 用 `str()` 塞进了 TextField，于是数据库里存的是**字面字符串 `"{}"`**
而不是空串。前端判空逻辑（`v-if="troubleshooting"`）对非空字符串为真
⇒ 原样渲染出来。

当前导入路径（`import_knowledge_graph.py` 的 `item.get('troubleshooting', '')`）
不会再产生这种值，所以这属于**历史一次性脏数据，清了不会复发**。

## 为什么做成通用命令

同样的形态在别的字段也可能出现（`'[]'`、`'None'`、`'null'`…）。
做成扫「一组目标字段 × 一组占位值」，将来发现新形态直接加进列表即可。

2026-10-30 首次全库扫描结果：**只有 `Protocol.troubleshooting='{}'` 88 条**，
其余字段（RG/AP/Method 的 name/summary/purpose/…、Protocol 的
objective/principle/materials/reagents/equipment/expected_results）全部干净。

## 安全约束

- **默认 dry-run**，必须 `--apply` 才写库
- 写库前把「id + 字段 + 原值」全量落 JSON 备份，`--restore` 可原样回滚
- 只匹配**整字段等于**占位值（不是包含）—— 避免误伤正文里合法出现的 `{}`
- 只动 `blank=True` 的文本字段（有 default='' 的那些）

## 用法

    python manage.py clean_placeholder_text                # 预演
    python manage.py clean_placeholder_text --apply        # 执行
    python manage.py clean_placeholder_text --restore <备份.json>
"""
import json
import os
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.knowledge.models import Application, Method, Protocol, ResearchGoal

# 被当成内容渲染的占位字面量
PLACEHOLDERS = ('{}', '[]', 'None', 'null', 'NULL', 'undefined', 'nan')

# (模型, 文本字段元组, 公开态)
TARGETS = (
    (Protocol,
     ('name', 'objective', 'principle', 'materials', 'reagents', 'equipment',
      'troubleshooting', 'expected_results', 'references'),
     'published'),
    (ResearchGoal, ('name', 'summary'), 'active'),
    (Application, ('name', 'summary'), 'active'),
    (Method, ('name', 'summary', 'purpose', 'advantages', 'limitations',
              'cost_band', 'timeline'), 'active'),
)


class Command(BaseCommand):
    help = '清掉被当成内容渲染的占位字面量脏值（默认预演，可 --restore 回滚）'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='真正写库（默认只预演）')
        parser.add_argument('--restore', default=None, metavar='JSON',
                            help='从备份文件恢复原值')
        parser.add_argument('--backup-dir', default='/tmp/placeholder_clean_bak')

    def handle(self, *args, **opts):
        if opts['restore']:
            return self._restore(opts['restore'])
        return self._clean(opts['apply'], opts['backup_dir'])

    # ---------- 扫描 ----------

    def _clean(self, apply_mode, backup_dir):
        hits = []          # [(model_label, id, field, value)]
        for model, fields, status in TARGETS:
            qs = model.objects.filter(status=status)
            for f in fields:
                for bad in PLACEHOLDERS:
                    rows = list(qs.filter(**{f: bad}).values_list('id', flat=True))
                    for rid in rows:
                        hits.append((model.__name__, rid, f, bad))

        self.stdout.write(f'占位值 {PLACEHOLDERS}')
        if not hits:
            self.stdout.write(self.style.SUCCESS('全库没有占位脏值，无需处理。'))
            return

        per_field = {}
        for label, _rid, f, bad in hits:
            per_field[f'{label}.{f}={bad!r}'] = per_field.get(f'{label}.{f}={bad!r}', 0) + 1
        self.stdout.write(f'命中 {len(hits)} 处：')
        for k, v in sorted(per_field.items()):
            self.stdout.write(f'  {k}: {v}')

        payload = {
            'generated_at': datetime.now().isoformat(timespec='seconds'),
            'count': len(hits),
            'items': [{'model': m, 'id': i, 'field': f, 'value': v} for m, i, f, v in hits],
        }
        os.makedirs(backup_dir, exist_ok=True)
        bpath = os.path.join(backup_dir, 'placeholder_before.json')
        with open(bpath, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
        self.stdout.write(f'原值已备份：{bpath}')

        if not apply_mode:
            self.stdout.write(self.style.WARNING(
                '\n预演，未写库。加 --apply 执行（--restore 可回滚）。'))
            return

        # 按 (model, field) 分组批量 update，减少事务开销
        grouped = {}
        for label, rid, f, _bad in hits:
            grouped.setdefault((label, f), []).append(rid)

        models = {m.__name__: m for m, _f, _s in TARGETS}
        total = 0
        with transaction.atomic():
            for (label, f), ids in grouped.items():
                total += models[label].objects.filter(id__in=ids).update(**{f: ''})
        self.stdout.write(self.style.SUCCESS(f'已清空 {total} 处。'))

        # 收尾核对
        remain = 0
        for model, fields, status in TARGETS:
            qs = model.objects.filter(status=status)
            for f in fields:
                for bad in PLACEHOLDERS:
                    remain += qs.filter(**{f: bad}).count()
        if remain:
            self.stdout.write(self.style.ERROR(f'★ 仍有 {remain} 处未清干净'))
        else:
            self.stdout.write(self.style.SUCCESS('核对通过：全库已无占位脏值。'))

    # ---------- 恢复 ----------

    def _restore(self, path):
        if not os.path.isfile(path):
            raise CommandError(f'备份文件不存在：{path}')
        with open(path, encoding='utf-8') as fh:
            payload = json.load(fh)

        models = {m.__name__: m for m, _f, _s in TARGETS}
        grouped = {}
        for item in payload.get('items', []):
            grouped.setdefault((item['model'], item['field'], item['value']), []).append(item['id'])

        total = 0
        with transaction.atomic():
            for (label, f, val), ids in grouped.items():
                total += models[label].objects.filter(id__in=ids).update(**{f: val})
        self.stdout.write(self.style.SUCCESS(
            f'已从 {path} 恢复 {total} 处（{payload.get("count")} 条记录）。'))
