"""重做分片：把重复的 method_definition 抽成查表文件，再按 500 条/片切分。

## 为什么重做（第一次切错了）

第一次按 800 条/片切，实测 part_01 是 **758KB / 948 字符单条**。
英文 + JSON 结构约 4 字符/token ⇒ 800 条 ≈ **190K token**，正好顶到模型
200K 窗口上限，输出空间为零 ⇒ 不可用。

## 两个优化

1. **抽掉重复字段**：`method_definition` 占单条体积 **38.1%**，而同一个方法
   平均被 180 条记录引用 ⇒ 同 260 字符重复 180 次。改为 `METHOD_DEFS.json`
   按 `method_id` 查表，单条从 948 → 约 620 字符（省 35%）。

2. **降到 500 条/片**：620 × 500 ≈ 310KB ≈ 78K token，留 120K 给输出。

结果：30 片，每片约 78K token。

## 产出

  docs/handoff/METHOD_DEFS.json        83 个方法的定义（查表用）
  docs/handoff/parts/part_01..30.jsonl 每片 500 条
  docs/handoff/input_task_a_parts.zip  打包（含所有配套文档）
  docs/handoff/PARTS_INDEX.md          清单
"""
import json
import os
import zipfile

BASE = 'docs/handoff'
SRC = '/tmp/handoff/input_task_a.jsonl'  # 由 scripts/export_handoff_input.py 生成
PARTS = os.path.join(BASE, 'parts')
SIZE = 500

os.makedirs(PARTS, exist_ok=True)
for f in os.listdir(PARTS):
    os.remove(os.path.join(PARTS, f))

rows = []
with open(SRC, encoding='utf-8') as fh:
    for line in fh:
        line = line.strip()
        if line:
            rows.append(json.loads(line))

# 抽 definition 为查表
defs = {}
for r in rows:
    mid = str(r['method_id'])
    if mid not in defs:
        defs[mid] = {
            'name': r['method_name'],
            'definition': r['method_definition'],
            'is_step_tag': r['method_is_step_tag'],
        }
with open(os.path.join(BASE, 'METHOD_DEFS.json'), 'w', encoding='utf-8') as fh:
    json.dump(defs, fh, ensure_ascii=False, indent=1)
print(f'METHOD_DEFS.json: {len(defs)} 个方法，{os.path.getsize(os.path.join(BASE, "METHOD_DEFS.json")) / 1024:.0f} KB')

# 瘦身记录：去掉 method_name / method_definition / method_is_step_tag（都能从查表拿）
SLIM = []
for r in rows:
    SLIM.append({
        'task': 'A',
        'bridge_id': r['bridge_id'],
        'method_id': r['method_id'],
        'criteria_key': r['criteria_key'],
        'protocol_id': r['protocol_id'],
        'protocol_name': r['protocol_name'],
        'protocol_objective': r['protocol_objective'],
        'link_source': r['link_source'],
        'link_status': r['link_status'],
    })

avg = sum(len(json.dumps(x, ensure_ascii=False)) for x in SLIM) / len(SLIM)
print(f'瘦身后单条平均 {avg:.0f} 字符（原 948）')

n_parts = (len(SLIM) + SIZE - 1) // SIZE
manifest = []
for i in range(n_parts):
    chunk = SLIM[i * SIZE:(i + 1) * SIZE]
    name = f'part_{i + 1:02d}.jsonl'
    path = os.path.join(PARTS, name)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        for r in chunk:
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    kb = os.path.getsize(path) / 1024
    mids = len({r['method_id'] for r in chunk})
    manifest.append((name, len(chunk), kb, mids, kb * 1024 / 4 / 1000))
    
zpath = os.path.join(BASE, 'input_task_a_parts.zip')
with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for f in sorted(os.listdir(PARTS)):
        z.write(os.path.join(PARTS, f), f)
    for extra in ('METHOD_DEFS.json', 'TASK_SPEC.md', 'CRITERIA.json',
                  'OUTPUT_SCHEMA.json', 'gold_set.jsonl', 'input_task_b.jsonl',
                  'RUBRIC.md', 'ACCEPTANCE.md', 'README.md', 'validate_output.py'):
        p = os.path.join(BASE, extra)
        if os.path.exists(p):
            z.write(p, extra)

print(f'\n共 {n_parts} 片｜{len(SLIM):,} 条')
print(f'  {"分片":<14} {"条数":>5} {"大小":>9} {"方法":>4} {"约token":>9}')
for name, n, kb, nm, tk in manifest:
    print(f'  {name:<14} {n:>5} {kb:>7.0f}KB {nm:>4} {tk:>8.0f}K')
print(f'\nzip: {zpath}  {os.path.getsize(zpath) / 1024 / 1024:.2f} MB')

lines = [
    '# Task A 分片清单（500 条/片，瘦身版）',
    '',
    f'总计 **{len(SLIM):,}** 条，切成 **{n_parts}** 片。',
    '',
    '## 为什么是 500 条不是 800',
    '',
    '第一版按 800 条切，实测单条 948 字符 ⇒ 758KB/片 ≈ **190K token**，',
    '正好顶到 200K 上下文窗口，没有输出空间，不可用。',
    '',
    '本版做了两件事：',
    '1. **抽掉重复字段**：`method_definition` 曾占单条 38.1%，同一方法平均重复 180 次。',
    '   现在改为查 `METHOD_DEFS.json`（按 `method_id`），单条降到约 620 字符。',
    '2. 片大小降到 500 条 ⇒ 每片约 **78K token**，留 120K 给输出。',
    '',
    '## 关键：输入行里没有 method_definition 了',
    '',
    '每行只有 `method_id`。**方法名与定义必须查 `METHOD_DEFS.json`**：',
    '',
    '```json',
    '{"123": {"name": "PCR", "definition": "...", "is_step_tag": false}}',
    '```',
    '',
    '提示词里要明确写：',
    '',
    '> 每条记录的 `method_id` 对应 `METHOD_DEFS.json` 的同名键，取其 `name` 与',
    '> `definition` 作为方法上下文；`is_step_tag` 仅作背景，不改变判定规则。',
    '',
    '## 分片明细',
    '',
    '| 分片 | 条数 | 大小 | 覆盖方法 | 约 token |',
    '|---|---|---|---|---|',
]
for name, n, kb, nm, tk in manifest:
    lines.append(f'| `{name}` | {n} | {kb:.0f} KB | {nm} | ~{tk:.0f}K |')
lines += [
    '',
    '## 合并结果',
    '',
    '```bash',
    'cat part_*.out.jsonl > result_task_a.jsonl',
    'wc -l result_task_a.jsonl   # 应为 14975',
    '```',
    '',
    '> 若平台不接受 `.jsonl` 后缀，改名 `.txt` 即可，内容格式不变。',
]
with open(os.path.join(BASE, 'PARTS_INDEX.md'), 'w', encoding='utf-8', newline='\n') as fh:
    fh.write('\n'.join(lines) + '\n')
print('清单已更新')
