"""
remap_duplicate_methods — 把「协议→方法」的断链重指向到同名 active Method。

## 问题（2026-10-30 实测）

协议页会显示方法名，但点进去 **404**：

    protocol 124 页面显示 3 个方法名
    点击其中 method id=65  →  404

根因是两个过滤条件不一致：
- `get_methods()` 取 `MethodProtocol.status='active'`（13,408 条）—— 不看 Method 自己的状态
- `/methods/{id}` 与 `/methods` 走 `apply_public_visibility`，只放 `Method.status='active'`

结果：**12,682 条关联（94.5%）指向 draft Method，点进去全 404**。

## 数据真相（不是「升 active」能解决的）

| 事实 | 数字 |
|---|---|
| Method 总行数 | 47,935 |
| **真正被协议引用的** | **84**（其余 47,851 是孤儿） |
| 被引用的 84 个里，能在 active 里找到同名的 | **83** |
| 只有 1 个找不到同名（id=45，名字是一整句协议标题） | 1 |

也就是说：**93 个 active Method 是收敛好的版本，被引用的 84 个是未收敛的重复版本**。
所以正确做法不是「把 draft 升 active」（会造成同名重复条目），而是
**把协议关联重指向到同名 active Method**，然后清空并归档那些重复版本。

## 本命令做三件事

1. **重指向**：`MethodProtocol.method_id` 从「重复的非 active Method」改成「同名 active Method」
   （重指向前会检冲突：若该协议已关联同名 active，跳过并计数）
2. **清理无主关联**：既非 active、又找不到同名 active 的 Method（实测只有 id=45，79 条），
   其关联全部删除 —— 前置已验证这 79 条协议**每条都还有其他方法关联**，删掉不会让协议失去方法
3. **归档源**：被清空的重复 Method 标为 `archived`，避免将来又被误挂

## 安全约束

- 默认 dry-run，必须 `--apply`
- 先备份 `method_protocol` 全表 + 受影响 Method 的 id/name/status
- 重指向强制走 `NOT EXISTS` 防重，绝不产生 `(method, protocol)` 唯一约束冲突
- 无主关联只在 `--drop-orphan-links` 显式给出时才删（默认只报告）

## 用法

    python manage.py remap_duplicate_methods --dry-run
    python manage.py remap_duplicate_methods --apply --drop-orphan-links
    python manage.py remap_duplicate_methods --verify
"""
import json
import os
from collections import Counter
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count

from apps.bridges.models import MethodProtocol
from apps.knowledge.models import Method

BATCH = 1000


class Command(BaseCommand):
    help = '把「协议→方法」断链重指向到同名 active Method（默认 dry-run）'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='真正写库')
        parser.add_argument('--dry-run', action='store_true', help='显式预演（默认）')
        parser.add_argument('--backup-dir', default=None)
        parser.add_argument('--drop-orphan-links', action='store_true',
                            help='删除「找不到同名 active」的 Method 上的关联（实测仅 id=45 的 79 条）')
        parser.add_argument('--verify', action='store_true', help='落库后核查断链是否归零')

    # ---------- 入口 ----------

    def handle(self, *args, **opts):
        if opts['verify']:
            return self._verify()

        # 1) 被引用的 Method（不管状态）
        used = (Method.objects
                .filter(id__in=MethodProtocol.objects.values('method_id'))
                .values('id', 'name', 'status'))
        used = list(used)
        active_by_name = {}
        for m in Method.objects.filter(status='active').values('id', 'name'):
            active_by_name.setdefault(m['name'], []).append(m['id'])

        remap = []          # (source_id, source_name, source_status, target_id, links)
        orphan = []         # (source_id, name, status, links)
        ambiguous = []      # 同名 active 有多个，不敢自动选

        link_counts = dict(
            MethodProtocol.objects.values('method_id').annotate(n=Count('id'))
            .values_list('method_id', 'n'))

        for m in used:
            if m['status'] == 'active':
                continue
            targets = active_by_name.get(m['name']) or []
            n = link_counts.get(m['id'], 0)
            if len(targets) == 1:
                remap.append((m['id'], m['name'], m['status'], targets[0], n))
            elif len(targets) > 1:
                ambiguous.append((m['id'], m['name'], m['status'], targets, n))
            else:
                orphan.append((m['id'], m['name'], m['status'], n))

        total_remap_links = sum(r[4] for r in remap)
        total_orphan_links = sum(o[3] for o in orphan)

        self.stdout.write(f'被引用的 Method 总数          {len(used)}')
        self.stdout.write(f'  可重指向（唯一同名 active） {len(remap)} 个，涉及关联 {total_remap_links} 条')
        self.stdout.write(f'  同名 active 有多个（跳过）  {len(ambiguous)}')
        self.stdout.write(f'  找不到同名 active           {len(orphan)} 个，涉及关联 {total_orphan_links} 条')

        if ambiguous:
            self.stdout.write('\n⚠️ 同名 active 多个，需人工指定：')
            for sid, name, st, targets, n in ambiguous[:10]:
                self.stdout.write(f'  id={sid} [{st}] {name[:44]} → 候选 {targets}（{n} 条关联）')

        if orphan:
            self.stdout.write('\n⚠️ 找不到同名 active（关联会 404）：')
            for sid, name, st, n in orphan[:10]:
                self.stdout.write(f'  id={sid} [{st}] {name[:50]}（{n} 条关联）')

        # 冲突预检
        conflict = 0
        for sid, name, st, tid, _n in remap:
            conflict += (MethodProtocol.objects
                         .filter(method_id=sid)
                         .filter(protocol_id__in=MethodProtocol.objects
                                 .filter(method_id=tid).values('protocol_id'))
                         .count())
        self.stdout.write(f'\n冲突预检（协议已关联同名 active）：{conflict} 条将跳过')

        # 重指向前受影响协议的方法数
        affected_protocols = (MethodProtocol.objects.filter(method_id__in=[r[0] for r in remap])
                              .values('protocol_id').distinct().count())
        self.stdout.write(f'受影响协议数                  {affected_protocols}')

        if not opts['apply']:
            self.stdout.write(self.style.WARNING(
                f'\n预演结束。加 --apply 执行'
                + ('（含删除 %d 条无主关联，需 --drop-orphan-links）' % total_orphan_links
                   if orphan and not opts['drop_orphan_links'] else '')))
            return

        if orphan and not opts['drop_orphan_links']:
            raise CommandError(
                f'存在 {len(orphan)} 个无主 Method（{total_orphan_links} 条关联），'
                f'重指向无法覆盖它们，这些协议点进去仍会 404。'
                f'确认后加 --drop-orphan-links 一并清理。')

        path = self._backup(remap, orphan, opts['backup_dir'])
        self.stdout.write(self.style.SUCCESS(f'\n备份已写：{path}'))

        moved = skipped = 0
        archived = 0
        with transaction.atomic():
            for sid, name, st, tid, _n in remap:
                # 逐条按 protocol 过滤，天然避开唯一约束冲突
                src_qs = MethodProtocol.objects.filter(method_id=sid)
                dup_protocols = set(MethodProtocol.objects
                                    .filter(method_id=tid).values_list('protocol_id', flat=True))
                to_move = list(src_qs.values_list('id', 'protocol_id'))
                ids_move = [pk for pk, pid in to_move if pid not in dup_protocols]
                # ★ 冲突行不能「原样留着」—— 留着它，get_methods 仍会返回它，
                #   用户点进去照样 404。它其实是冗余（同一协议已在同名 active 上有关联），
                #   所以直接删，源方法才能被清空并归档。
                ids_dup = [pk for pk, pid in to_move if pid in dup_protocols]
                if ids_dup:
                    for i in range(0, len(ids_dup), BATCH):
                        MethodProtocol.objects.filter(id__in=ids_dup[i:i + BATCH]).delete()
                    skipped += len(ids_dup)
                if ids_move:
                    for i in range(0, len(ids_move), BATCH):
                        moved += MethodProtocol.objects.filter(
                            id__in=ids_move[i:i + BATCH]).update(method_id=tid)
                # 源清空后归档
                if not MethodProtocol.objects.filter(method_id=sid).exists():
                    # Method 用 StatusMixin，合法值: active / archived / draft
                    Method.objects.filter(id=sid).update(status='archived')
                    archived += 1

            dropped = 0
            if orphan and opts['drop_orphan_links']:
                oids = [o[0] for o in orphan]
                dropped = MethodProtocol.objects.filter(method_id__in=oids).delete()[0]

        self.stdout.write(self.style.SUCCESS(
            f'\n重指向 {moved} 条｜冲突冗余删除 {skipped} 条｜归档源 Method {archived} 个'
            + (f'｜删除无主关联 {dropped} 行' if dropped else '')))
        self._verify()

    # ---------- 备份 ----------

    def _backup(self, remap, orphan, backup_dir):
        if not backup_dir:
            # ★ 默认写 /tmp 而不是「往上找 5 层的 _corpus_backup」：
            #   容器里往上找会得到 /app/_corpus_backup，写在镜像层里 ——
            #   容器一重建备份就没了，等于没有备份。默认 /tmp 至少能用 docker cp 取出来。
            backup_dir = '/tmp/corpus_backup'
        os.makedirs(backup_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        path = os.path.join(backup_dir, f'method_remap_{ts}.json')

        source_ids = [r[0] for r in remap] + [o[0] for o in orphan]
        payload = {
            'created_at': datetime.now().isoformat(timespec='seconds'),
            'note': 'remap_duplicate_methods 备份：method_protocol 全表 + 受影响 Method 状态',
            # ★ 这次把 method_protocol 全量备了（上次 purge 只备了想到的几张桥，漏了 facet 与 RG）
            'method_protocol_all': list(
                MethodProtocol.objects.values(
                    'id', 'method_id', 'protocol_id', 'featured', 'explicit', 'status')),
            'methods_touched': list(
                Method.objects.filter(id__in=source_ids).values('id', 'name', 'status')),
            'remap_plan': [{'from': r[0], 'to': r[3], 'name': r[1]} for r in remap],
            'orphan_plan': [{'id': o[0], 'name': o[1], 'links': o[3]} for o in orphan],
        }
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1, default=str)
        with open(path, encoding='utf-8') as fh:
            check = json.load(fh)
        if len(check['method_protocol_all']) < 1:
            raise CommandError('备份校验失败：method_protocol 为空，已中止')
        return path

    # ---------- 核查 ----------

    def _verify(self):
        total = MethodProtocol.objects.count()
        broken = 0
        active_pairs = MethodProtocol.objects.filter(status='active').values_list(
            'method_id', flat=True)
        active_ids = set(Method.objects.filter(status='active').values_list('id', flat=True))
        for mid in set(active_pairs):
            if mid not in active_ids:
                broken += MethodProtocol.objects.filter(method_id=mid, status='active').count()

        self.stdout.write('\n=== 核查 ===')
        self.stdout.write(f'method_protocol 总行        {total}')
        self.stdout.write(f'指向非 active Method 的关联  {broken}'
                          + ('  ← 0 才算修好' if broken else '  (OK，断链归零)'))

        linked_methods = Method.objects.filter(
            status='active',
            id__in=MethodProtocol.objects.values('method_id')).count()
        active_total = Method.objects.filter(status='active').count()
        self.stdout.write(f'active Method 中有协议的      {linked_methods} / {active_total}')
        pc = MethodProtocol.objects.filter(status='active').values('protocol_id').distinct().count()
        self.stdout.write(f'有方法关联的协议              {pc}')
