"""导出交接给第三方模型的输入数据。

两个任务：
  Task A —— 关联相关性判定：每条 MethodProtocol 桥，判断协议是否真属于该方法
  Task B —— adv/lim 质量评审：83 个方法的 advantages/limitations 是否符合标准

输出（JSONL，一行一条，自包含）：
  /tmp/handoff/input_task_a.jsonl   约 14,975 行
  /tmp/handoff/input_task_b.jsonl   约 166 行

设计要点：
  - 每条必须自包含：模型拿到一行就能判，不需要另外查库
  - criteria_key 指向 CRITERIA.json 里的判据组；无判据的方法标 general
  - 刻意不把「我们自己的判定结果」放进输入，避免给模型答案

## 2026-11-01 修：protocol_objective 被硬截断在 300 字符

实测影响面（对已发出的 30 片输入）：恰好 300 字符 10,645 条（71.1%），
无一超过 300，>250 且结尾无标点 10,459 条（69.8%）。
⇒ 上一版 `clean(p.objective, 300)` 把 71% 的协议目标切在半句上，
   直接毁掉「以 objective 陈述的主目的为准」这类判据（Step 3）。
   同期 `clean(p.name, 150)` 同样有风险。

修法（本文件）：
  1. 默认**不截断** objective；`--objective-cap N` 可显式限制（仅作应急回退）
  2. 导出前先打印长度分布 + **预估分片体积**，超阈值直接拒绝写出
  3. 若体积超预算，提示改用 `--part-size` 降条数，而不是悄悄截断

用法:
  python scripts/export_handoff_input.py                    # 完整导出 + 体检
  python scripts/export_handoff_input.py --dry-run           # 只体检不写文件
  python scripts/export_handoff_input.py --objective-cap 600 # 应急回退
"""
import argparse
import json
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
django.setup()

from apps.bridges.models import MethodProtocol  # noqa: E402
from apps.knowledge.models import Method, Protocol  # noqa: E402

# 每片 token 预算：实测英文+JSON 约 4 字符/token；模型窗口 200K，留 120K 给输出
TOKEN_PER_CHAR = 4
PART_TOKEN_BUDGET = 80_000      # 单片输入 token 上限
PART_SIZE_DEFAULT = 500

_ap = argparse.ArgumentParser()
_ap.add_argument('--objective-cap', type=int, default=0,
                 help='0=不截断（默认）。设正整数则截断，仅作应急回退')
_ap.add_argument('--name-cap', type=int, default=150, help='protocol_name 截断长度')
_ap.add_argument('--part-size', type=int, default=PART_SIZE_DEFAULT)
_ap.add_argument('--dry-run', action='store_true', help='只做体检，不写文件')
ARGS = _ap.parse_args()

OUT = '/tmp/handoff'
os.makedirs(OUT, exist_ok=True)


def _cap(s):
    return ARGS.objective_cap if ARGS.objective_cap and ARGS.objective_cap > 0 else None


def clean(s, n=None):
    """归一空白；n>0 才截断。默认不截断。"""
    t = ' '.join((s or '').split())
    return t[:n] if (n and n > 0) else t


def report_len(label, lengths):
    lengths = sorted(lengths)
    if not lengths:
        print(f'  {label}: 无数据')
        return
    n = len(lengths)
    q = lambda p: lengths[min(n - 1, int(n * p))]
    print(f'  {label}: n={n:,}  min={lengths[0]}  p50={q(.5)}  p90={q(.9)} '
          f'p99={q(.99)}  max={lengths[-1]}  均值={sum(lengths)/n:.0f}')


CRIT_PATH = '/tmp/method_scope_criteria.json'
crit_names = set()
if os.path.exists(CRIT_PATH):
    crit_names = set(json.load(open(CRIT_PATH, encoding='utf-8'))['methods'].keys())


# ── Task A ─────────────────────────────────────────────────────
methods = {m.id: m for m in Method.objects.filter(
    status='active', application_id__isnull=True)
    .only('id', 'name', 'summary', 'purpose', 'is_step_tag')}

rows_a = []
for mp in MethodProtocol.objects.select_related('protocol').iterator(chunk_size=2000):
    m = methods.get(mp.method_id)
    p = mp.protocol
    if not m or not p:
        continue
    rows_a.append({
        'task': 'A',
        'bridge_id': mp.id,
        'method_id': m.id,
        'method_name': m.name,
        # ★ 2026-10-31 修：原为 clean(..., 260) 硬截断，导致 71/83 个定义在单词
        #   中间断掉（PCR 停在 "diver"、Flow Cytometry 停在 "uptake an"）。
        #   实测完整长度 min 222 / 中位 298 / max 437，全量仅 24KB ⇒ 无需截断。
        'method_definition': ' '.join((m.summary or m.purpose or '').split()),
        'method_is_step_tag': bool(m.is_step_tag),
        'criteria_key': m.name if m.name in crit_names else 'general',
        'protocol_id': p.id,
        'protocol_name': clean(p.name, ARGS.name_cap),
        # ★ 2026-11-01 修：原为 clean(p.objective, 300)，实测 71.1% 记录被切在
        #   半句上（恰好 300 字符 10,645 条，无一超过），毁掉"以主目的为准"类判据。
        #   默认不截断；--objective-cap N 仅作应急回退。
        'protocol_objective': clean(p.objective, _cap(p.objective)),
        'link_source': mp.evidence_source or 'legacy',
        'link_status': mp.status,
    })

# ── 体检：长度分布 + 分片体积预估（写文件之前先拦）──────────────
obj_len = [len(r['protocol_objective']) for r in rows_a]
name_len = [len(r['protocol_name']) for r in rows_a]
print('\n=== 长度体检（决定分片体积）===')
report_len('protocol_objective', obj_len)
report_len('protocol_name     ', name_len)
_capval = _cap(None)
_capdesc = '无截断' if _capval is None else f'{_capval} 字符'
print(f'  截断策略: objective={_capdesc}, name={ARGS.name_cap} 字符')

line_bytes = [len(json.dumps(r, ensure_ascii=False).encode('utf-8')) for r in rows_a]
tot_mb = sum(line_bytes) / 1024 / 1024
per_part = sum(line_bytes) / max(1, -(-len(rows_a) // ARGS.part_size))
per_part_tok = per_part / TOKEN_PER_CHAR / 1000
print(f'  总字节 {tot_mb:.2f} MB｜每片约 {per_part/1024:.0f} KB ≈ {per_part_tok:.0f}K token '
      f'(预算 {PART_TOKEN_BUDGET//1000}K)')
if per_part_tok > PART_TOKEN_BUDGET / 1000:
    print(f'  ❌ 超预算！不要截断 objective，请改用 --part-size 降条数。')
    print(f'     满足预算的建议条数: {int(ARGS.part_size * PART_TOKEN_BUDGET/1000 / per_part_tok)}')
    if not ARGS.dry_run:
        raise SystemExit('拒绝写出：分片体积超预算（避免再次产出被截断/超窗口的输入）')
else:
    print('  ✅ 体积在预算内')

if ARGS.dry_run:
    print('\n[dry-run] 未写任何文件')
    raise SystemExit(0)

with open(f'{OUT}/input_task_a.jsonl', 'w', encoding='utf-8') as fh:
    for r in rows_a:
        fh.write(json.dumps(r, ensure_ascii=False) + '\n')
print(f'\nTask A: {len(rows_a):,} 条 → {OUT}/input_task_a.jsonl')

# ── Task B ─────────────────────────────────────────────────────
rows_b = []
for m in Method.objects.filter(status='active', application_id__isnull=True) \
        .only('id', 'name', 'summary', 'advantages', 'limitations', 'timeline'):
    for field, label in (('advantages', 'advantages'), ('limitations', 'limitations')):
        text = getattr(m, field) or ''
        if not text.strip():
            continue
        rows_b.append({
            'task': 'B',
            'method_id': m.id,
            'method_name': m.name,
            'method_definition': ' '.join((m.summary or '').split()),
            'timeline': m.timeline or '',
            'field': label,
            'lines': [ln.strip() for ln in text.split('\n') if ln.strip()],
        })

with open(f'{OUT}/input_task_b.jsonl', 'w', encoding='utf-8') as fh:
    for r in rows_b:
        fh.write(json.dumps(r, ensure_ascii=False) + '\n')
print(f'Task B: {len(rows_b):,} 条 → {OUT}/input_task_b.jsonl')

# ── 统计 ───────────────────────────────────────────────────────
from collections import Counter  # noqa: E402
c = Counter(r['criteria_key'] for r in rows_a)
with_crit = sum(v for k, v in c.items() if k != 'general')
print(f'\n有专门判据的桥 {with_crit:,}｜只有通用规则的 {c.get("general", 0):,}')
print(f'判据覆盖方法数 {len([k for k in c if k != "general"])} / {len(methods)}')
