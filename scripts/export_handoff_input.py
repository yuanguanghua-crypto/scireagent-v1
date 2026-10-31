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
"""
import json
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
django.setup()

from apps.bridges.models import MethodProtocol  # noqa: E402
from apps.knowledge.models import Method, Protocol  # noqa: E402

OUT = '/tmp/handoff'
os.makedirs(OUT, exist_ok=True)

CRIT_PATH = '/tmp/method_scope_criteria.json'
crit_names = set()
if os.path.exists(CRIT_PATH):
    crit_names = set(json.load(open(CRIT_PATH, encoding='utf-8'))['methods'].keys())


def clean(s, n):
    return ' '.join((s or '').split())[:n]


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
        'method_definition': clean(m.summary or m.purpose, 260),
        'method_is_step_tag': bool(m.is_step_tag),
        'criteria_key': m.name if m.name in crit_names else 'general',
        'protocol_id': p.id,
        'protocol_name': clean(p.name, 150),
        'protocol_objective': clean(p.objective, 300),
        'link_source': mp.evidence_source or 'legacy',
        'link_status': mp.status,
    })

with open(f'{OUT}/input_task_a.jsonl', 'w', encoding='utf-8') as fh:
    for r in rows_a:
        fh.write(json.dumps(r, ensure_ascii=False) + '\n')
print(f'Task A: {len(rows_a):,} 条 → {OUT}/input_task_a.jsonl')

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
            'method_definition': clean(m.summary, 260),
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
