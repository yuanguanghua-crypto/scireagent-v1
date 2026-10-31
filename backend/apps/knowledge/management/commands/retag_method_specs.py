"""retag_method_specs — 应用决策 1B（通用步骤标记）+ 2C（timeline 重分档）。

## 决策 1B：is_step_tag

判据是「协议共享度」= 该方法的协议中同时挂在其他方法下的比例。
实测 83 个方法里 69 个共享度 <50%，≥85% 的只有 9 个。其中：

| 共享高 + 分歧低（真错挂） | 处置 |
|---|---|
| Click Chemistry 97%错/1%分歧、Streptavidin 100%/0%、T7 53%/7%、qPCR 77%/14% |
| Illumina Sequencing 34%/17% | 清数据即可，**不标**本字段 |

| 共享高 + 分歧高（定义不清） | 处置 |
|---|---|
| Sanger Sequencing 34%错/**47%分歧** | 标 is_step_tag=True |
| Enzymatic Labeling 27%/39% | 同上 |
| Random Primer Method 33%/33% | 同上 |
| End Labeling 74%/21% | 同上 |

理由：这 4 个方法 100%/95%/100%/96% 的协议都属于别的实验，不存在
「我要做一次 Sanger 测序实验」这种独立需求。

## 决策 2C：timeline 重分档

**不再让 LLM 判档**，纯测量：算每个方法的协议耗时中位数，按 4h/10h/20h 切档。
这从根上消除「LLM 违反枚举区间」的问题（原来 4 条 DISAGREE 全是 LLM 越界）。

原档位实测分布：minutes 0 / hours 18 / days 65 / weeks 0（78% 挤在 days，
内部跨度 23 倍）。新档位预期：lt_4h 18 / h4_10 28 / h10_20 20 / gt_20h 17。

## 用法

    python manage.py retag_method_specs --dry-run
    python manage.py retag_method_specs --apply
    python manage.py retag_method_specs --verify
"""
import json
import os
import re
from datetime import datetime

from django.core.management.base import BaseCommand

from apps.bridges.models import MethodProtocol
from apps.knowledge.models import Method, ProtocolStep

# 与 generate_method_specs.py 同源的耗时解析（改一处必须同步另一处）
NUM = r'\d+(?:\.\d+)?'
UNITS = (r'(?:s|secs?|seconds?|min|mins?|minutes?|h|hr|hrs|hours?|'
         r'd|days?|wks?|weeks?)')
TIME_HIT = re.compile(
    r'(?:' + NUM + r'[ \t]*(?:-|~|to|–)[ \t]*)?(' + NUM + r')[ \t]*(' + UNITS + r')\b'
    r'|\b(overnight)\b', re.I)
SPEC_RX = re.compile(
    r'\b(?:aged?|age of|weeks?[ \t]*(?:of[ \t]*)?old|old[ \t]*|at[ \t]+the[ \t]+age)\b', re.I)
BRACKET_SPEC = re.compile(
    r'[\(\[]\s*(?:' + NUM + r'[ \t]*(?:-|~|to|–)[ \t]*)?' + NUM + r'[ \t]*'
    r'(?:weeks?|days?|months?)\s*[,;\)\]]', re.I)
STORE_RX = re.compile(
    r'stor(?:e|ed|age|ing)|can[ \t]+be[ \t]+kept|stable[ \t]+for|shelf[ \t]*life|'
    r'keep[ \t]+at|use[ \t]+within|discard[ \t]+after|expir', re.I)
ACTION_RX = re.compile(
    r'incubat|wait|leave|stand|settle|shake|rock|rotat|centrifug|spin|heat|bake|dry|'
    r'wash|rinse|run|electrophor|block|stain|rest|grow|cultur|adapt|fix|permeabil|'
    r'hybridi|digest|lyse|lysis|autoradiograph|expos|develop|overnight|at[ \t]+\d+\s*°?C',
    re.I)

# 决策 1B 的 4 个方法（共享度≥85% 且双模型分歧≥20%）
STEP_TAG_METHODS = [
    'Sanger Sequencing',
    'Enzymatic Labeling',
    'Random Primer Method',
    'End Labeling',
]

# 决策 2C 的新切点（小时）
CUTS = (4.0, 10.0, 20.0)
NEW_BANDS = ('lt_4h', 'h4_10', 'h10_20', 'gt_20h')
OLD_BANDS = ('minutes', 'hours', 'days', 'weeks')


def _scale(u):
    u = u.lower().rstrip('s')
    if u.startswith('sec') or u == 's':
        return 1
    if u.startswith('min'):
        return 60
    if u.startswith('h'):
        return 3600
    if u.startswith('d'):
        return 86400
    if u.startswith('w'):
        return 604800
    return 1


def parse_step(text):
    out = []
    for m in TIME_HIT.finditer(text):
        i, j = max(0, m.start() - 60), min(len(text), m.end() + 60)
        ctx = text[i:j].replace('\n', ' ')
        if not ACTION_RX.search(ctx):
            continue
        if BRACKET_SPEC.search(ctx) or SPEC_RX.search(ctx) or STORE_RX.search(ctx):
            continue
        if m.group(3):
            out.append(8 * 3600)
            continue
        out.append(float(m.group(1)) * _scale(m.group(2)))
    return out


def new_band(sec):
    h = sec / 3600
    if h < CUTS[0]:
        return NEW_BANDS[0]
    if h < CUTS[1]:
        return NEW_BANDS[1]
    if h < CUTS[2]:
        return NEW_BANDS[2]
    return NEW_BANDS[3]


class Command(BaseCommand):
    help = '按决策 1B/2C 标记通用步骤方法并重算 timeline 分档（默认 dry-run）'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--verify', action='store_true')
        parser.add_argument('--only', default='both',
                            choices=['both', 'step', 'timeline'])
        parser.add_argument('--backup-dir', default='/tmp')

    def handle(self, *args, **opts):
        if opts['verify']:
            return self._verify()

        methods = list(Method.objects.filter(status='active', application_id__isnull=True)
                       .only('id', 'name', 'timeline', 'is_step_tag'))

        # ── 决策 1B ────────────────────────────────────────────
        step_rows = []
        if opts['only'] in ('both', 'step'):
            print('=' * 78)
            print('决策 1B：标记通用步骤方法')
            print('=' * 78)
            for name in STEP_TAG_METHODS:
                m = Method.objects.filter(name=name, status='active').first()
                if not m:
                    print(f'  !! 未找到方法 {name}')
                    continue
                pids = list(MethodProtocol.objects.filter(method=m)
                            .values_list('protocol_id', flat=True))
                proto_methods_set = {}
                for pid in pids:
                    proto_methods_set[pid] = MethodProtocol.objects.filter(
                        protocol_id=pid).count()
                shared = sum(1 for pid in pids if proto_methods_set.get(pid, 0) > 1)
                ratio = shared * 100 / len(pids) if pids else 0
                step_rows.append((m.id, name, len(pids), ratio,
                                  m.is_step_tag))
                print(f'  {name[:34]:<36} 协议 {len(pids):>4}｜共享度 {ratio:>4.0f}%｜'
                      f'当前 is_step_tag={m.is_step_tag}')

        # ── 决策 2C ────────────────────────────────────────────
        tl_rows = []
        if opts['only'] in ('both', 'timeline'):
            print()
            print('=' * 78)
            print('决策 2C：timeline 重分档（纯测量，不经 LLM）')
            print('=' * 78)
            for m in methods:
                pids = list(MethodProtocol.objects.filter(method=m)
                            .values_list('protocol_id', flat=True))
                per = {}
                for st in ProtocolStep.objects.filter(protocol_id__in=pids) \
                        .only('protocol_id', 'body').iterator(chunk_size=2000):
                    s = parse_step(st.body or '')
                    if s:
                        per[st.protocol_id] = per.get(st.protocol_id, 0) + sum(s)
                if per:
                    v = sorted(per.values())
                    med = v[len(v) // 2]
                    nb = new_band(med)
                    note = f'中位 {med / 3600:.1f}h'
                else:
                    nb, note = '', '无可用耗时'
                tl_rows.append((m.id, m.name, m.timeline or '', nb, note))

            from collections import Counter
            old_c = Counter(r[2] for r in tl_rows if r[2])
            new_c = Counter(r[3] for r in tl_rows if r[3])
            print(f'  旧档位分布 {dict(old_c)}')
            print(f'  新档位分布 {dict(new_c)}')
            changed = [r for r in tl_rows if r[2] != r[3]]
            print(f'  会变档 {len(changed)} 个 / {len(tl_rows)}')
            print()
            print(f'  {"方法":<38} {"旧":>8} {"新":>8}  依据')
            for mid, name, old, nb, note in changed[:22]:
                print(f'  {name[:36]:<38} {old or "(空)":>8} {nb or "(空)":>8}  {note}')

        if not opts['apply']:
            print()
            print(self.style.WARNING('预演，未写库。加 --apply 执行。'))
            return

        # ── 备份 ───────────────────────────────────────────────
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        bpath = os.path.join(opts['backup_dir'], f'retag_methods_{ts}.json')
        payload = {'created_at': ts, 'step': step_rows, 'timeline': tl_rows}
        try:
            os.makedirs(opts['backup_dir'], exist_ok=True)
            with open(bpath, 'w', encoding='utf-8') as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=1)
            print(f'备份：{bpath}')
        except OSError as exc:
            print(self.style.WARNING(f'备份失败（不影响写库）：{exc}'))

        # ── 写库 ───────────────────────────────────────────────
        n_step = n_tl = 0
        if step_rows:
            for mid, name, _n, _r, cur in step_rows:
                if not cur:
                    n_step += Method.objects.filter(id=mid).update(is_step_tag=True)
        if tl_rows:
            for mid, name, old, nb, note in tl_rows:
                if nb and nb != old:
                    n_tl += Method.objects.filter(id=mid).update(timeline=nb)
        print(self.style.SUCCESS(
            f'\n已标记 is_step_tag {n_step} 个｜timeline 改写 {n_tl} 个'))
        self._verify()

    def _verify(self):
        qs = Method.objects.filter(status='active', application_id__isnull=True)
        total = qs.count()
        print()
        print('=== 核查 ===')
        print(f'canonical 方法     {total}')
        print(f'  is_step_tag=True {qs.filter(is_step_tag=True).count()}')
        print(f'  有 timeline      {qs.exclude(timeline="").count()}')
        from collections import Counter
        c = Counter(qs.values_list('timeline', flat=True))
        for k in NEW_BANDS:
            print(f'    {k:<9} {c.get(k, 0)}')
        bad = sum(v for k, v in c.items() if k and k not in NEW_BANDS)
        print(f'  非法 timeline 值  {bad}' + (' ← 必须为 0' if bad else ''))
        if bad:
            print(self.style.ERROR('  仍有旧枚举值（minutes/hours/days/weeks），需重跑 --apply'))
