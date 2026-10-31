"""生成 GOLD_SET：给第三方模型做能力校准的已知答案样本。

来源与诚实边界：
  - 从 14,975 条既有判定里挑「判定理由明确」的样本（note 里能看出依据的）
  - 这些是**共识标准（consensus）**，不是绝对真值 —— 双模型一致率只有 80.5%
  - 另标注 tier="human" 的若干条，是我逐个读过协议原文确认的（更可靠）

用途：第三方模型先跑这批，命中率 <85% 就不能用它的结果。
"""
import json
import os
import re
from collections import defaultdict

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
django.setup()

from apps.knowledge.models import Method, Protocol  # noqa: E402

OUT = '/tmp/handoff/gold_set.jsonl'

# 我人工逐条读过原文确认的（2026-10-31 抽样 17 条里判对的部分 + 其他明确案例）
HUMAN_VERIFIED = {
    # (method_name, protocol_id): label —— 均已在原文层面核对过
    ('Pluripotent Stem Cell Culture', 9848): 'wrong',      # Plate Streaking 细菌划线
    ('Pluripotent Stem Cell Culture', 6420): 'wrong',      # 人施万细胞原代培养
    ('Pluripotent Stem Cell Culture', 7043): 'wrong',      # 泌尿生殖系统器官培养
    ('Genomic DNA Extraction', 1608): 'wrong',             # 脓毒症临床管理，无提取
    ('Bacterial/Microbial Culture', 4202): 'wrong',        # 葡萄果实培养
    ('Bacterial/Microbial Culture', 6347): 'wrong',        # 小麦种植
    ('Bacterial/Microbial Culture', 13359): 'wrong',       # HbA1c 酶法测定
    ('PCR', 9828): 'wrong',                                # 质粒扩增，无 PCR
    ('PCR', 9026): 'wrong',                                # NEBNext PCR-free 建库
    ('PCR', 11322): 'wrong',                               # RdRp 酶活测定
    ('PCR', 13297): 'wrong',                               # Ty1 逆转座频率测定
    ('Click Chemistry', 188): 'wrong',                     # Northern blot
    ('Click Chemistry', 217): 'wrong',                     # COVID 样本混检 RT-PCR
    ('Click Chemistry', 247): 'wrong',                     # 谷胱甘肽测定
    ('Click Chemistry', 220): 'wrong',                     # 短链脂肪酸 GC
    ('SDS-PAGE', 6600): 'wrong',                           # 图像处理
}

rows = []
for line in open('/tmp/mp_full_audit.jsonl', encoding='utf-8'):
    try:
        r = json.loads(line)
    except json.JSONDecodeError:
        continue
    rows.append(r)

msum = {m.id: m for m in Method.objects.filter(status='active', application_id__isnull=True)
        .only('id', 'name', 'summary')}
pids = {r['protocol_id'] for r in rows}
pinfo = {p.id: p for p in Protocol.objects.filter(id__in=list(pids)[:20000])
         .only('id', 'name', 'objective')}


def clean(s, n):
    return ' '.join((s or '').split())[:n]


gold = []
seen = set()

# ① 人工确认的
for (mname, pid), lab in HUMAN_VERIFIED.items():
    m = Method.objects.filter(name=mname).first()
    if not m:
        continue
    p = pinfo.get(pid)
    if not p:
        continue
    key = (m.id, pid)
    if key in seen:
        continue
    seen.add(key)
    gold.append({
        'gold_id': f'G{len(gold) + 1:03d}',
        'tier': 'human',
        'method_id': m.id, 'method_name': m.name,
        'method_definition': clean(m.summary, 260),
        'protocol_id': pid, 'protocol_name': clean(p.name, 150),
        'protocol_objective': clean(p.objective, 300),
        'expected_verdict': lab,
        'why': '人工阅读协议原文确认',
    })

# ② 共识样本：note 里能看出明确依据的
BAD_HINT = re.compile(r'unrelated|no |not |absent|unclear|none', re.I)
GOOD_HINT = re.compile(r'core|main|primary|direct|classic|standard', re.I)
by_label = defaultdict(list)
for r in rows:
    m = msum.get(r['method_id'])
    if not m or not r.get('note'):
        continue
    key = (r['method_id'], r['protocol_id'])
    if key in seen:
        continue
    lab = r.get('label')
    note = r['note']
    if lab == 'wrong' and BAD_HINT.search(note):
        by_label['wrong'].append((r, m, note))
    elif lab == 'on_topic' and GOOD_HINT.search(note):
        by_label['on_topic'].append((r, m, note))

import random  # noqa: E402
rng = random.Random(20261031)
for lab, want in (('wrong', 26), ('on_topic', 14)):
    pool = by_label.get(lab, [])
    rng.shuffle(pool)
    n = 0
    for r, m, note in pool:
        if n >= want:
            break
        key = (r['method_id'], r['protocol_id'])
        if key in seen:
            continue
        p = pinfo.get(r['protocol_id'])
        if not p:
            continue
        seen.add(key)
        n += 1
        gold.append({
            'gold_id': f'G{len(gold) + 1:03d}',
            'tier': 'consensus',
            'method_id': m.id, 'method_name': m.name,
            'method_definition': clean(m.summary, 260),
            'protocol_id': r['protocol_id'],
            'protocol_name': clean(p.name, 150),
            'protocol_objective': clean(p.objective, 300),
            'expected_verdict': lab,
            'why': f'既有判定理由：{note[:80]}',
        })

with open(OUT, 'w', encoding='utf-8') as fh:
    for g in gold:
        fh.write(json.dumps(g, ensure_ascii=False) + '\n')

from collections import Counter  # noqa: E402
print(f'gold_set: {len(gold)} 条 → {OUT}')
print(f'  tier 分布 {dict(Counter(g["tier"] for g in gold))}')
print(f'  verdict 分布 {dict(Counter(g["expected_verdict"] for g in gold))}')
print(f'  覆盖方法 {len({g["method_name"] for g in gold})} 个')
