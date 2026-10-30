"""
set_protocol_status — 批量改协议发布状态（下架 / 恢复上架）。

## 为什么单独做一个命令而不是直接 UPDATE

下架是**可逆**的，但"改了哪些、原来是什么状态"必须留痕，否则将来无法准确恢复。
这个命令把「备份原状态 → 校验 → 批量改 → 回报」固定成一条路径，
避免下次又写一遍裸 SQL。

同时它带一条防呆：**只接受 published/draft/archived/superseded 四个合法值**，
不接受任意字符串（否则写错一个字就让协议在前台永久消失且没有任何报错）。

## 用法

    # 预演：打印将改多少条、原状态分布
    python manage.py set_protocol_status --ids-file /tmp/ids.txt --status archived --dry-run

    # 执行
    python manage.py set_protocol_status --ids-file /tmp/ids.txt --status archived --apply

    # 恢复（把备份里的原状态改回去）
    python manage.py set_protocol_status --restore _corpus_backup/status_xxx.json
"""
import json
import os
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.knowledge.models import Protocol

VALID = {c for c, _ in Protocol.PublicationStatus.choices}


class Command(BaseCommand):
    help = '批量改协议发布状态（默认 dry-run；先备份原状态再改）'

    def add_arguments(self, parser):
        parser.add_argument('--ids-file', help='一行一个 protocol id')
        parser.add_argument('--ids', help='逗号分隔 id 列表')
        parser.add_argument('--status', help='目标状态：' + ' / '.join(sorted(VALID)))
        parser.add_argument('--backup-dir', default=None, help='备份目录（默认工作区 _corpus_backup）')
        parser.add_argument('--apply', action='store_true', help='真正写库')
        parser.add_argument('--dry-run', action='store_true', help='显式预演（默认）')
        parser.add_argument('--restore', help='从备份 JSON 恢复原状态')

    def handle(self, *args, **opts):
        if opts['restore']:
            return self._restore(opts['restore'])

        target = (opts.get('status') or '').strip()
        if target not in VALID:
            raise CommandError(f'--status 必须是 {sorted(VALID)} 之一，收到 {target!r}')

        ids = self._load_ids(opts)
        if not ids:
            raise CommandError('没有拿到任何 id')

        qs = Protocol.objects.filter(id__in=ids).only('id', 'name', 'status')
        rows = list(qs)
        found = {p.id for p in rows}
        missing = sorted(set(ids) - found)
        # 已经是目标状态的单独列出（幂等：重复跑不会重复备份）
        already = [p.id for p in rows if p.status == target]
        change = [p for p in rows if p.status != target]

        from collections import Counter
        self.stdout.write(f'清单 id 数        {len(ids)}')
        self.stdout.write(f'库内存在          {len(found)}')
        self.stdout.write(f'库内不存在        {len(missing)}' + (f'  {missing[:10]}' if missing else ''))
        self.stdout.write(f'已是目标状态      {len(already)}')
        self.stdout.write(f'将变更            {len(change)}')
        self.stdout.write(f'\n原状态分布：')
        for k, v in Counter(p.status for p in rows).most_common():
            self.stdout.write(f'  {k:<14} {v}')
        self.stdout.write(f'\n目标状态          {target}')

        if not opts['apply']:
            self.stdout.write(self.style.WARNING('\n这是预演，未备份也未写库。加 --apply 执行。'))
            return
        if not change:
            self.stdout.write(self.style.SUCCESS('\n没有需要变更的记录，未备份。'))
            return

        path = self._backup(change, target, opts['backup_dir'])
        self.stdout.write(self.style.SUCCESS(f'备份已写：{path}'))

        with transaction.atomic():
            n = Protocol.objects.filter(id__in=[p.id for p in change]).update(status=target)
        self.stdout.write(self.style.SUCCESS(f'\n已改 {n} 条 → {target}'))
        for st in ('published', 'draft', 'archived', 'superseded'):
            c = Protocol.objects.filter(status=st).count()
            self.stdout.write(f'  全库 {st:<12} {c}')

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
                        raise CommandError(f'--ids-file 有非整数行：{line!r}')
        if opts.get('ids'):
            ids += [int(x) for x in opts['ids'].split(',') if x.strip()]
        return sorted(set(ids))

    def _backup(self, rows, target, backup_dir):
        if not backup_dir:
            backup_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))),
                '_corpus_backup')
        os.makedirs(backup_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        path = os.path.join(backup_dir, f'status_{target}_{ts}.json')
        payload = {
            'created_at': datetime.now().isoformat(timespec='seconds'),
            'target_status': target,
            'note': 'set_protocol_status 备份：记录改前的 status，可用 --restore 恢复',
            'items': [{'id': p.id, 'name': p.name, 'status': p.status} for p in rows],
        }
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
        with open(path, encoding='utf-8') as fh:
            if len(json.load(fh)['items']) != len(rows):
                raise CommandError('备份校验失败，已中止')
        return path

    def _restore(self, path):
        if not os.path.isfile(path):
            raise CommandError(f'备份文件不存在：{path}')
        with open(path, encoding='utf-8') as fh:
            items = json.load(fh)['items']
        n = 0
        with transaction.atomic():
            for it in items:
                n += Protocol.objects.filter(id=it['id']).update(status=it['status'])
        self.stdout.write(self.style.SUCCESS(f'已按备份恢复 {n} 条状态'))
