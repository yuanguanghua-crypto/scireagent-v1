"""打一个"给电脑小白"的交接包。

结构刻意做成 3 层，解压后一眼看懂：

  交接包_给小白.zip
  ├── 1_先看这个_操作手册.md
  ├── 2_上传给Claude/
  │   ├── READ_ME_FIRST.md          （每轮都要传）
  │   ├── part_01.jsonl … part_30.jsonl
  │   └── gold_set.jsonl            （只在考试那步用）
  └── 3_提示词.txt

刻意不放进来的：CRITERIA.json / OUTPUT_SCHEMA.json / RUBRIC.md /
ACCEPTANCE.md / validate_output.py / input_task_b.jsonl / METHOD_DEFS.json
—— 前 5 个是我们这边验收用的，小白用不上；METHOD_DEFS 已内嵌进 READ_ME_FIRST；
Task B 本次不做。放进越多，小白越容易传错文件。
"""
import os
import zipfile

BASE = 'docs/handoff'
PARTS = os.path.join(BASE, 'parts')
OUT = os.path.join(BASE, '交接包_给小白.zip')

items = []  # (磁盘路径, zip 内路径)

p = os.path.join(BASE, '1_先看这个_操作手册.md')
if os.path.exists(p):
    items.append((p, '1_先看这个_操作手册.md'))
else:
    raise SystemExit('缺少操作手册')

r = os.path.join(BASE, 'READ_ME_FIRST.md')
if os.path.exists(r):
    items.append((r, '2_上传给Claude/READ_ME_FIRST.md'))
else:
    raise SystemExit('缺少 READ_ME_FIRST.md')

g = os.path.join(BASE, 'gold_set.jsonl')
if os.path.exists(g):
    items.append((g, '2_上传给Claude/gold_set.jsonl'))

parts = sorted(f for f in os.listdir(PARTS) if f.endswith('.jsonl'))
for f in parts:
    items.append((os.path.join(PARTS, f), f'2_上传给Claude/{f}'))

t = os.path.join(BASE, '3_提示词.txt')
if os.path.exists(t):
    items.append((t, '3_提示词.txt'))

if os.path.exists(OUT):
    os.remove(OUT)

with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for src, arc in items:
        z.write(src, arc)

print(f'{OUT}')
print(f'  大小 {os.path.getsize(OUT) / 1024 / 1024:.2f} MB｜{len(items)} 个文件\n')
print('解压后结构：')
groups = {}
for _, arc in items:
    head = arc.split('/')[0] if '/' in arc else '(根目录)'
    groups.setdefault(head, []).append(arc)
for head in sorted(groups):
    print(f'  {head}')
    for arc in sorted(groups[head]):
        print(f'    - {arc}')

# 自检：分片数
print(f'\n分片数 {len(parts)}（应为 30）')
assert len(parts) == 30, '分片数不对'
# 自检：总行数
total = 0
for f in parts:
    with open(os.path.join(PARTS, f), encoding='utf-8') as fh:
        total += sum(1 for _ in fh)
print(f'总记录数 {total:,}（应为 14,975）')
assert total == 14975, f'总行数不对: {total}'
print('\n自检通过')
