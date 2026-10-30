"""
purge_protocols — 定向清理"空协议"，**删除前强制备份**。

## 为什么需要这个命令

2026-10-30 全量诊断发现：全库 14,128 条协议里有 325 条既无步骤也无材料，
其中 318 条是 published（前台可见）。用户点击后只能看到一段摘要 + 5 个空 tab。
逐条查清成因后分为四类，只有后两类可删：

| 类别 | 条数 | 性质 | 处置 |
|---|---|---|---|
| RESCUE | 4 | 语料里**有**叶子步骤，是我们匹配漏了 | **修匹配，不删** |
| E2E | 7 | `__e2e_protocols_*` 测试残留 | 删 |
| SKELETON | 143 | 语料只有章节骨架无正文（Protocol-io 的 `protocol` 字段根本不存在） | 有 method 的保留，其余删 |
| NO_CORPUS | 171 | 三源按标题全查不到，早期手工录入 | 删 |

## 安全约束（删错了没法 Ctrl+Z）

1. **备份先行**：先把 protocol 全字段 + 4 张桥表的关联对写盘，
   备份文件行数与预期不符就中止，绝不在备份失败时继续删。
2. **默认 dry-run**：必须显式 `--apply`。
3. **只认显式 id 清单**：不做"自动判定并删除"——`--ids-file` 必填，
   避免某次判定逻辑改动后误删一大片。
4. **删除前二次核对**：清单里若有「有步骤」或「有材料」的协议，直接中止
   （那些不该出现在清理清单里，出现说明清单生成逻辑错了）。

## 用法

    # 1) 预演：打印将删什么、级联多少、备份写到哪
    python manage.py purge_protocols --ids-file /tmp/ids.txt --dry-run

    # 2) 执行（会先备份再删）
    python manage.py purge_protocols --ids-file /tmp/ids.txt --apply

    # 3) 恢复（如需）
    python manage.py purge_protocols --restore _corpus_backup/purged_xxx.json
"""
import json
import os
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count

from apps.knowledge.models import (
    Protocol, ProtocolStep, ProtocolMaterial,
)
from apps.bridges.models import MethodProtocol, ProductProtocol

BATCH = 500


class Command(BaseCommand):
    help = '定向删除"空协议"（先强制备份，默认 dry-run，只认显式 id 清单）'

    def add_arguments(self, parser):
        parser.add_argument('--ids-file', help='一行一个 protocol id 的文本文件')
        parser.add_argument('--ids', help='逗号分隔的 id 列表（与 --ids-file 二选一）')
        parser.add_argument('--backup-dir',
                            default=os.path.join(
                                os.path.dirname(os.path.dirname(os.path.dirname(
                                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))),
                                '_corpus_backup'),
                            help='备份目录（默认工作区 _corpus_backup）')
        parser.add_argument('--apply', action='store_true', help='真正删除；不加则预演')
        parser.add_argument('--dry-run', action='store_true', help='显式预演（默认行为）')
        parser.add_argument('--restore', help='从备份 JSON 恢复（与 --ids-file 互斥）')
        parser.add_argument('--allow-nonempty', action='store_true',
                            help='允许删除"有步骤或有材料"的协议（默认拒绝，防清单错）')

    # ---------- 入口 ----------

    def handle(self, *args, **opts):
        if opts['restore']:
            return self._restore(opts['restore'])

        ids = self._load_ids(opts)
        if not ids:
            raise CommandError('没有拿到任何 id（--ids-file / --ids 至少给一个）')

        # 二次核对：清单里不该出现有内容或有子行的协议
        protos = list(Protocol.objects.filter(id__in=ids).only(
            'id', 'name', 'status', 'corpus_source', 'corpus_id'))
        found = {p.id for p in protos}
        missing = sorted(set(ids) - found)
        steps = dict(ProtocolStep.objects.filter(protocol_id__in=found)
                     .values('protocol_id').annotate(n=Count('id'))
                     .values_list('protocol_id', 'n'))
        mats = dict(ProtocolMaterial.objects.filter(protocol_id__in=found)
                    .values('protocol_id').annotate(n=Count('id'))
                    .values_list('protocol_id', 'n'))
        nonempty = [p.id for p in protos if steps.get(p.id, 0) or mats.get(p.id, 0)]

        self.stdout.write(f'清单 id 数        {len(ids)}')
        self.stdout.write(f'库内存在          {len(found)}')
        self.stdout.write(f'库内不存在        {len(missing)}' + (f'  {missing[:10]}' if missing else ''))
        self.stdout.write(f'其中有步骤/有材料  {len(nonempty)}' + (f'  {nonempty[:10]}' if nonempty else ''))

        if nonempty and not opts['allow_nonempty']:
            raise CommandError(
                f'清单里有 {len(nonempty)} 条协议是有步骤或有材料的 —— 这些不该出现在清理清单里，'
                f'说明清单生成逻辑错了。已中止。如确需删除请加 --allow-nonempty。')

        # 级联影响面
        impact = {
            'protocol': len(found),
            'protocol_step': sum(steps.values()),
            'protocol_material': sum(mats.values()),
            'method_protocol': MethodProtocol.objects.filter(protocol_id__in=found).count(),
            'product_protocol': ProductProtocol.objects.filter(protocol_id__in=found).count(),
        }
        self.stdout.write('\n级联影响面：')
        for k, v in impact.items():
            self.stdout.write(f'  {k:<20} {v}')

        self.stdout.write('\n按 corpus_source：')
        from collections import Counter
        for k, v in Counter(p.corpus_source or '(空)' for p in protos).most_common():
            self.stdout.write(f'  {k:<18} {v}')
        self.stdout.write('\n按 status：')
        for k, v in Counter(p.status for p in protos).most_common():
            self.stdout.write(f'  {k:<18} {v}')

        self.stdout.write('\n前 5 条样本：')
        for p in protos[:5]:
            self.stdout.write(f'  id={p.id:<6} [{p.status}] {p.name[:60]}')

        if not opts['apply']:
            self.stdout.write(self.style.WARNING('\n这是预演，未备份也未删除。加 --apply 执行。'))
            return

        backup_path = self._backup(protos, opts['backup_dir'])
        self.stdout.write(self.style.SUCCESS(f'\n备份已写：{backup_path}'))

        deleted = 0
        with transaction.atomic():
            for i in range(0, len(found), BATCH):
                chunk = sorted(found)[i:i + BATCH]
                n, _ = Protocol.objects.filter(id__in=chunk).delete()
                deleted += n
        self.stdout.write(self.style.SUCCESS(f'\n已删除（含级联行）{deleted} 行'))
        left = Protocol.objects.count()
        self.stdout.write(f'剩余协议          {left}')

    # ---------- 输入 ----------

    def _load_ids(self, opts):
        ids = []
        if opts.get('ids_file'):
            with open(opts['ids_file'], encoding='utf-8') as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    try:
                        ids.append(int(line))
                    except ValueError:
                        raise CommandError(f'--ids-file 里有非整数行：{line!r}')
        if opts.get('ids'):
            ids += [int(x) for x in opts['ids'].split(',') if x.strip()]
        return sorted(set(ids))

    # ---------- 备份 / 恢复 ----------

    def _backup(self, protos, backup_dir):
        backup_dir = os.path.abspath(backup_dir)
        os.makedirs(backup_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        path = os.path.join(backup_dir, f'purged_{ts}.json')

        ids = sorted(p.id for p in protos)
        payload = {
            'created_at': datetime.now().isoformat(timespec='seconds'),
            'note': 'purge_protocols 备份：删前快照，可用 --restore 恢复',
            'protocols': list(Protocol.objects.filter(id__in=ids).values()),
            'protocol_step': list(ProtocolStep.objects.filter(protocol_id__in=ids).values()),
            'protocol_material': list(ProtocolMaterial.objects.filter(protocol_id__in=ids).values()),
            'method_protocol': list(MethodProtocol.objects.filter(protocol_id__in=ids)
                                    .values('method_id', 'protocol_id', 'featured', 'explicit', 'status')),
            'product_protocol': list(ProductProtocol.objects.filter(protocol_id__in=ids)
                                     .values()),
        }
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1, default=str)

        # 备份必须可读回且行数对得上，否则中止
        with open(path, encoding='utf-8') as fh:
            check = json.load(fh)
        if len(check['protocols']) != len(ids):
            raise CommandError(
                f'备份校验失败：期望 {len(ids)} 条，文件里 {len(check["protocols"])} 条。已中止，未删除。')
        return path

    def _restore(self, path):
        if not os.path.isfile(path):
            raise CommandError(f'备份文件不存在：{path}')
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)

        created = 0
        with transaction.atomic():
            for row in data.get('protocols', []):
                if Protocol.objects.filter(pk=row['id']).exists():
                    continue
                Protocol.objects.create(**{k: v for k, v in row.items() if k != 'id'},
                                        id=row['id'])
                created += 1
            for row in data.get('protocol_step', []):
                ProtocolStep.objects.get_or_create(
                    protocol_id=row['protocol_id'], step_no=row['step_no'],
                    defaults={k: v for k, v in row.items() if k not in ('id', 'protocol_id', 'step_no')})
            for row in data.get('protocol_material', []):
                ProtocolMaterial.objects.get_or_create(
                    protocol_id=row['protocol_id'], seq=row['seq'],
                    defaults={k: v for k, v in row.items() if k not in ('id', 'protocol_id', 'seq')})
        self.stdout.write(self.style.SUCCESS(f'已恢复 {created} 条协议'))
