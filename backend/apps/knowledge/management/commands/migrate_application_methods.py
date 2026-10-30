"""
migrate_application_methods — 把「应用↔方法」从 1:N 修正为 M:N（B 方案）。

## 背景

`Method.application` 这个 FK 假设「一个方法只属于一个应用」，与领域事实矛盾
（PCR 同时服务基因分型 / 病原检测 / 克隆）。历史实现的后果：给 22,213 个应用
各存了一份方法清单（47,761 行 draft），再靠 `canonical_by_name()` 在运行时
翻译回 83 个全局方法。

## 四步（顺序有依赖，不能颠倒）

| step | 做什么 | 为什么必须在这个位置 |
|---|---|---|
| `baseline` | 把「每个应用现在看到哪几个方法」固化成 JSON | 后面 `verify` 唯一的对照依据 |
| `merge-active` | 合并 10 个「有 application 的 active」到同名 canonical | 这 10 个**全部**与 canonical 重名；不先合并，后面建桥会让 `/methods` 出现 10 组同名重复 |
| `rescue-bridges` | 把 159 PMR + 39 MRC + 3 ProductMethod 重指向 canonical | 它们的载体名字**全部**在 canonical 池里；不救就随 archived 一起级联删除。救完反而从「指向 archived 不可见」变成「指向 active 可见」 |
| `migrate-drafts` | 47,761 行 draft → `ApplicationMethod` 桥 | 建桥前必须先有 canonical（前两步保证） |

## 安全约束

- 默认 dry-run，必须 `--apply`
- 每步前备份受影响数据到 `--backup-dir`
- `merge-active` 走 `NOT EXISTS` 防 `method_protocol` 唯一约束冲突
- `migrate-drafts` 用 `ignore_conflicts=True`，靠 `unique_together` 去重
- `verify` 逐应用比对基线，**任一不一致即 exit 1**

## 用法

    python manage.py migrate_application_methods --step baseline --apply
    python manage.py migrate_application_methods --step merge-active --dry-run
    python manage.py migrate_application_methods --step all --apply
    python manage.py migrate_application_methods --step verify
"""
import json
import os
from collections import Counter, defaultdict
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.bridges.models import (
    MethodProtocol, MethodReagentClass, ProductMethod, ProductMethodRelation,
)
from apps.knowledge.models import Application, ApplicationMethod, Method
from apps.knowledge.services.canonical_methods import canonical_by_name

BATCH = 2000


class Command(BaseCommand):
    help = '把「应用↔方法」从 1:N 修正为 M:N（baseline/merge-active/rescue-bridges/migrate-drafts/verify）'

    def add_arguments(self, parser):
        parser.add_argument('--step', required=True,
                            choices=['baseline', 'merge-active', 'rescue-bridges',
                                     'migrate-drafts', 'all', 'verify'])
        parser.add_argument('--apply', action='store_true', help='真正写库（baseline/verify 不需要）')
        parser.add_argument('--dry-run', action='store_true', help='显式预演（默认）')
        parser.add_argument('--backup-dir', default='/tmp/appmethod_bak')
        parser.add_argument('--baseline-file', default=None,
                            help='基线 JSON 路径（默认 <backup-dir>/baseline_app_methods.json）')

    # ---------- 入口 ----------

    def handle(self, *args, **opts):
        self.apply_mode = opts['apply']
        self.backup_dir = opts['backup_dir']
        self.baseline_file = opts['baseline_file'] or os.path.join(
            self.backup_dir, 'baseline_app_methods.json')
        step = opts['step']

        if step == 'verify':
            return self._verify()
        if step == 'baseline':
            return self._baseline()

        os.makedirs(self.backup_dir, exist_ok=True)
        # ★ 顺序不能颠倒：rescue 必须先在 merge 之前。
        #   原因：`ProductMethodRelation.method` 是 PROTECT（不是 CASCADE），
        #   若先 merge 删 Method，会被 PMR 挡住（实测 ProtectedError）。
        #   先 rescue 把 PMR/MRC/ProductMethod 重指向 canonical，merge 才能删。
        steps = ['rescue-bridges', 'merge-active', 'migrate-drafts'] if step == 'all' else [step]
        for s in steps:
            if s == 'merge-active':
                self._merge_active()
            elif s == 'rescue-bridges':
                self._rescue_bridges()
            elif s == 'migrate-drafts':
                self._migrate_drafts()
        if step == 'all' and self.apply_mode:
            self._verify()

    # ---------- step: baseline ----------

    def _baseline(self):
        """固化「每个应用现在看到哪几个方法」（canonical 名字集合）。"""
        # ★ 用与前台 \`ApplicationDetailSerializer.get_methods\` 完全相同的函数算基线。
        #   原先我用 \`canonical_by_name()\` 自己算，漏了两个分支：
        #   ① active 方法「直接输出」（不论有无 application）
        #   ② archived 也走 canonical 映射
        #   结果 verify 报 30 个应用不一致（少 20 个、多 1 个）。必须单一实现。
        # ★ baseline 必须用 **legacy 语义**算（读 Method.application FK），
        #   不能用当前读路径 —— 它固化的是「改造前用户看到什么」。
        #   若用桥算，在桥还没建/或已被改过的情况下会得到错误基线，verify 变成空转。
        from apps.knowledge.services.application_methods import resolve_from_legacy_fk
        out = {}
        apps = Application.objects.only('id').iterator(chunk_size=5000)
        for a in apps:
            names = sorted({m['name'] for m in resolve_from_legacy_fk(a)})
            if names:
                out[str(a.id)] = names
        os.makedirs(self.backup_dir, exist_ok=True)
        with open(self.baseline_file, 'w', encoding='utf-8') as fh:
            json.dump(out, fh, ensure_ascii=False, indent=0)
        total_pairs = sum(len(v) for v in out.values())
        self.stdout.write(self.style.SUCCESS(
            f'基线已写：{self.baseline_file}'))
        self.stdout.write(f'  有方法的应用 {len(out)}｜(应用, 方法名) 对 {total_pairs}')
        dist = Counter(len(v) for v in out.values())
        self.stdout.write(f'  每应用方法数分布：{sorted(dist.items())}')

    # ---------- step: merge-active ----------

    def _merge_active(self):
        """合并「有 application 的 active Method」到同名 canonical。

        这 10 个**全部**与 canonical 重名（实测 10/10）。不合并的话，后面建桥会
        让 /methods 出现同名重复条目。
        """
        rows = list(Method.objects.filter(status='active', application_id__isnull=False)
                    .values('id', 'name', 'application_id'))
        canons = Method.objects.filter(status='active', application_id__isnull=True)
        canon_by_name = {}
        for m in canons.values('id', 'name'):
            canon_by_name.setdefault(m['name'], []).append(m['id'])

        plan, promote, no_canon = [], [], []
        for r in rows:
            targets = canon_by_name.get(r['name']) or []
            if len(targets) == 1:
                plan.append((r['id'], r['name'], r['application_id'], targets[0]))
            elif len(targets) == 0:
                # ★ 实测会有 1 个（id=36 "Random Primer Method"）：active 但带 application，
                #   而 canonical 池里没有同名。它不是重复品，而是「唯一一个还没转正的方法」。
                #   正确处理是把它自己转成 canonical（清空 application FK + 写桥），
                #   而不是跳过 —— 跳过会让它的 3 条 method_protocol 关联悬空。
                promote.append((r['id'], r['name'], r['application_id']))
            else:
                no_canon.append((r['id'], r['name'], r['application_id'], targets))

        self.stdout.write(f'带 application 的 active Method   {len(rows)}')
        self.stdout.write(f'  可合并（唯一同名 canonical）   {len(plan)}')
        self.stdout.write(f'  自身转 canonical（无同名）     {len(promote)}')
        for x in promote[:10]:
            self.stdout.write(f'    id={x[0]} {x[1][:40]}  → 清空 application={x[2]}，转 canonical')
        self.stdout.write(f'  无法处理（多个同名）           {len(no_canon)}')
        for x in no_canon[:10]:
            self.stdout.write(self.style.WARNING(f'    id={x[0]} {x[1][:40]} 候选={x[3]}'))

        moved = conflict = bridged = 0
        for sid, name, app_id, tid in plan:
            mp_total = MethodProtocol.objects.filter(method_id=sid).count()
            dup = MethodProtocol.objects.filter(method_id=sid).filter(
                protocol_id__in=MethodProtocol.objects.filter(method_id=tid)
                .values('protocol_id')).count()
            moved += mp_total - dup
            conflict += dup
            bridged += 1

        self.stdout.write(f'\n将重指向 method_protocol   {moved} 条')
        self.stdout.write(f'将删除冲突（已存在同名）    {conflict} 条')
        self.stdout.write(f'将写桥（合并 + 转正）       {bridged + len(promote)} 条')
        self.stdout.write(f'将删除 Method              {len(plan)} 行（promote 的不删）')

        if not self.apply_mode:
            self.stdout.write(self.style.WARNING('\n预演，未写库。加 --apply 执行。'))
            return
        if no_canon:
            raise CommandError(
                f'有 {len(no_canon)} 个 active 找不到唯一同名 canonical，需人工指定后再跑。')

        self._dump('merge_active_snapshot.json', {
            'methods': list(Method.objects.filter(id__in=[p[0] for p in plan])
                            .values('id', 'name', 'status', 'application_id')),
            'method_protocol': list(MethodProtocol.objects
                                    .filter(method_id__in=[p[0] for p in plan])
                                    .values('id', 'method_id', 'protocol_id', 'status')),
        })

        # 删除前的硬闸门：确认待删的 Method 已无任何桥指向
        # （PMR/MRC/ProductMethod 都是 PROTECT，留着会被数据库挡住）
        doomed = [p[0] for p in plan]
        # 只查 PROTECT 的三张桥（PMR/MRC/ProductMethod）。
        # `MethodProtocol` 刻意**不算**：它由本步骤在事务内自己重指向，
        # 算进来会导致本步永远无法通过闸门。
        leftover = {
            'ProductMethodRelation': ProductMethodRelation.objects.filter(method_id__in=doomed).count(),
            'MethodReagentClass': MethodReagentClass.objects.filter(method_id__in=doomed).count(),
            'ProductMethod': ProductMethod.objects.filter(method_id__in=doomed).count(),
        }
        blocking = {k: v for k, v in leftover.items() if v}
        if blocking:
            raise CommandError(
                f'待删的 {len(doomed)} 个 Method 仍被这些 PROTECT 桥引用：{blocking}。'
                f'先跑 --step rescue-bridges 重指向它们。已中止，未删除。')

        with transaction.atomic():
            # 先处理「自身转 canonical」：清 FK + 写桥，保留 Method 行
            for sid, name, app_id in promote:
                Method.objects.filter(id=sid).update(application_id=None)
                ApplicationMethod.objects.get_or_create(
                    application_id=app_id, method_id=sid,
                    defaults={'source': 'migrated_active',
                              'display_order': self._order_for(app_id, name)})
            for sid, name, app_id, tid in plan:
                # 1) method_protocol 重指向（防重）
                dup_pids = set(MethodProtocol.objects.filter(method_id=tid)
                               .values_list('protocol_id', flat=True))
                for mp in MethodProtocol.objects.filter(method_id=sid):
                    if mp.protocol_id in dup_pids:
                        mp.delete()
                    else:
                        mp.method_id = tid
                        mp.save(update_fields=['method_id'])
                # 2) 写桥
                ApplicationMethod.objects.get_or_create(
                    application_id=app_id, method_id=tid,
                    defaults={'source': 'migrated_active',
                              'display_order': self._order_for(app_id, name)})
            # 3) 删除被合并的 active 行
            Method.objects.filter(id__in=[p[0] for p in plan]).delete()
        self.stdout.write(self.style.SUCCESS(
            f'已合并 {len(plan)} 个｜转 canonical {len(promote)} 个｜'
            f'重指向 {moved} 条｜删冲突 {conflict} 条'))

    # ---------- step: rescue-bridges ----------

    def _rescue_bridges(self):
        """把 PMR/MRC/ProductMethod 里指向非 canonical 的，重指向同名 canonical。

        实测：PMR 159 条载体名字 3/3、MRC 39 条 14/14 都在 canonical 池里。
        不救就随 archived 一起 CASCADE 删除；救完从「指向 archived 不可见」
        变成「指向 active 可见」—— 是净收益。
        """
        specs = [
            ('ProductMethodRelation', ProductMethodRelation),
            ('MethodReagentClass', MethodReagentClass),
            ('ProductMethod', ProductMethod),
        ]
        canon_pool = {}
        for m in Method.objects.filter(status='active', application_id__isnull=True).values('id', 'name'):
            canon_pool.setdefault(m['name'], []).append(m['id'])

        grand = []
        for label, model in specs:
            rows = list(model.objects.select_related('method')
                        .values('id', 'method_id', 'method__name', 'method__status'))
            plan, unmapped = [], []
            for r in rows:
                targets = canon_pool.get(r['method__name']) or []
                if len(targets) == 1 and targets[0] != r['method_id']:
                    plan.append((r['id'], r['method_id'], targets[0], r['method__name'],
                                 r['method__status']))
                elif not targets:
                    unmapped.append((r['id'], r['method__name'], r['method__status']))
            grand.append((label, model, plan, unmapped))
            self.stdout.write(f'{label}: 总 {len(rows)}｜可救 {len(plan)}｜无处可去 {len(unmapped)}')
            for u in unmapped[:5]:
                self.stdout.write(self.style.WARNING(f'    id={u[0]} {u[1][:40]} [{u[2]}]'))

        if not self.apply_mode:
            self.stdout.write(self.style.WARNING('\n预演，未写库。加 --apply 执行。'))
            return

        self._dump('rescue_snapshot.json', {
            label: list(model.objects.filter(id__in=[p[0] for p in plan])
                        .values('id', 'method_id'))
            for label, model, plan, _ in grand
        })
        with transaction.atomic():
            for label, model, plan, _ in grand:
                for rid, old, new, _name, _st in plan:
                    model.objects.filter(id=rid).update(method_id=new)
        self.stdout.write(self.style.SUCCESS(
            '已重指向：' + '｜'.join(f'{l} {len(p)}' for l, _m, p, _u in grand)))

    # ---------- step: migrate-drafts ----------

    def _migrate_drafts(self):
        """47,761 行 draft Method → ApplicationMethod 桥。"""
        # ★ 覆盖范围必须是「所有非 active 且带 application 的行」：
        #   原先只查 status='draft'，漏了 archived（实测本地 30 个应用的关联来自
        #   archived Method，基线里有、桥里没有 ⇒ verify 报缺）。
        #   archived 在 get_methods 里也走 canonical 映射，所以必须一起迁。
        drafts = list(Method.objects.filter(application_id__isnull=False)
                      .exclude(status='active')
                      .values('id', 'name', 'application_id', 'status'))
        canon_pool = {}
        for m in Method.objects.filter(status='active', application_id__isnull=True).values('id', 'name'):
            canon_pool.setdefault(m['name'], []).append(m['id'])

        stats = Counter()
        pairs = {}            # (app_id, canon_id) -> name（用于 display_order）
        for r in drafts:
            if r['application_id'] is None:
                stats['无 application（无法建桥）'] += 1
                continue
            targets = canon_pool.get(r['name']) or []
            if len(targets) != 1:
                stats['名字无法映射到 canonical'] += 1
                continue
            pairs[(r['application_id'], targets[0])] = r['name']
            stats['可建桥'] += 1
        stats['去重后桥行数'] = len(pairs)

        self.stdout.write(f'待迁 Method（draft+archived） {len(drafts)}')
        for k, v in stats.items():
            self.stdout.write(f'  {k:<26} {v}')

        if not self.apply_mode:
            self.stdout.write(self.style.WARNING('\n预演，未写库。加 --apply 执行。'))
            return

        # display_order 按 (app, name) 字典序，保证顺序稳定可复现
        per_app = defaultdict(list)
        for (app_id, canon_id), name in pairs.items():
            per_app[app_id].append((name, canon_id))
        objs = []
        for app_id, items in per_app.items():
            for i, (_name, canon_id) in enumerate(sorted(items)):
                objs.append(ApplicationMethod(
                    application_id=app_id, method_id=canon_id,
                    display_order=i, source='migrated_t2'))

        created = 0
        with transaction.atomic():
            for i in range(0, len(objs), BATCH):
                chunk = objs[i:i + BATCH]
                created += len(ApplicationMethod.objects.bulk_create(
                    chunk, batch_size=BATCH, ignore_conflicts=True))
        self.stdout.write(self.style.SUCCESS(
            f'已写入桥 {created} 条（目标 {len(objs)}，差额为已存在的幂等跳过）'))

    # ---------- step: verify ----------

    def _verify(self):
        if not os.path.isfile(self.baseline_file):
            raise CommandError(f'基线文件不存在：{self.baseline_file}（先跑 --step baseline）')
        with open(self.baseline_file, encoding='utf-8') as fh:
            base = json.load(fh)

        by_app = defaultdict(set)
        for row in ApplicationMethod.objects.values('application_id', 'method__name'):
            by_app[row['application_id']].add(row['method__name'])

        mismatch = []
        for app_id_str, names in base.items():
            aid = int(app_id_str)
            now = by_app.get(aid, set())
            if now != set(names):
                mismatch.append((aid, set(names) - now, now - set(names)))

        self.stdout.write(f'基线应用数            {len(base)}')
        self.stdout.write(f'桥覆盖应用数          {len(by_app)}')
        self.stdout.write(f'ApplicationMethod 行  {ApplicationMethod.objects.count()}')
        self.stdout.write(f'不一致应用            {len(mismatch)}'
                          + ('  (OK，与基线完全一致)' if not mismatch else '  ← 必须为 0'))
        for aid, missing, extra in mismatch[:10]:
            self.stdout.write(self.style.WARNING(
                f'  app={aid} 缺 {sorted(missing)[:3]} 多 {sorted(extra)[:3]}'))
        if mismatch:
            raise CommandError(f'{len(mismatch)} 个应用与基线不一致，检查映射逻辑。')

    # ---------- 工具 ----------

    def _order_for(self, app_id, name):
        """给合并来的 active 方法一个稳定 display_order。"""
        existing = list(ApplicationMethod.objects.filter(application_id=app_id)
                        .values_list('method__name', flat=True))
        names = sorted(existing + [name])
        return names.index(name)

    def _dump(self, filename, payload):
        os.makedirs(self.backup_dir, exist_ok=True)
        path = os.path.join(self.backup_dir, filename)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1, default=str)
        self.stdout.write(f'备份：{path}')
