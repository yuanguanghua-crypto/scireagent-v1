"""生成"给 Claude 的一个文件"：把任务规则 + 判据 + 输出格式 + 83 个方法定义
压成 READ_ME_FIRST.md，使每批只需上传 2 个文件（本文件 + 一个分片）。

为什么要合并：原本每批要传 6 个文档（TASK_SPEC / CRITERIA / OUTPUT_SCHEMA /
RUBRIC / METHOD_DEFS / gold_set），30 批就是 180 次上传，操作方是电脑小白，
必须把动作压到最少。
"""
import json
import os

BASE = 'docs/handoff'
OUT = os.path.join(BASE, 'READ_ME_FIRST.md')

crit = json.load(open(os.path.join(BASE, 'CRITERIA.json'), encoding='utf-8'))
defs = json.load(open(os.path.join(BASE, 'METHOD_DEFS.json'), encoding='utf-8'))

# ── 判据表：只保留 essence / must / exclude 三样，压掉注释 ──
crit_lines = []
for name, v in crit['methods'].items():
    crit_lines.append(f'### {name}')
    crit_lines.append(f'- **Essence**: {v["essence"]}')
    crit_lines.append(f'- **IS this method only if**: ' + ' / '.join(v['must']))
    crit_lines.append('- **Judge NOT this method when any applies**:')
    for e in v['exclude']:
        crit_lines.append(f'  - {e}')
    crit_lines.append('')
crit_block = '\n'.join(crit_lines)

# ── 方法定义表：83 条，逐行紧凑 ──
def_lines = []
for mid, d in sorted(defs.items(), key=lambda x: int(x[0])):
    flag = ' [common step]' if d['is_step_tag'] else ''
    def_lines.append(f'- `{mid}` **{d["name"]}**{flag} — {d["definition"]}')
def_block = '\n'.join(def_lines)

universal = '\n'.join(f'{i}. {r}' for i, r in enumerate(crit['universal_rules'], 1))

DOC = f"""# READ ME FIRST — 每次对话都要先上传这个文件

你（模型）的任务：判断「某条实验协议是否真的属于某个技术方法」，以及评审方法说明文字的质量。

本次只做**一件事**：Task A —— 逐条判断协议与方法之间的关联是否成立。

---

## 一、你会收到什么

1. **本文件**（READ_ME_FIRST.md）—— 规则、判据、输出格式、方法定义
2. **一个数据文件**（part_XX.jsonl）—— 500 条待判记录，一行一条（JSONL 格式）

数据行长这样（单条）：

```json
{{"task":"A","bridge_id":123,"method_id":47917,"criteria_key":"Sanger Sequencing",
 "protocol_id":456,"protocol_name":"...","protocol_objective":"...",
 "link_source":"manual_curated","link_status":"active"}}
```

⚠️ **注意：数据行里没有方法名和方法定义**。你需要用 `method_id` 到本文件末尾
的「方法定义表」里查。

---

## 二、怎么查方法

数据行的 `method_id`（例如 `47917`）→ 到本文末尾「附录：83 个方法定义」里找
对应条目 → 拿到方法的 name 和 definition。

- 查不到某个 `method_id` → 说明数据有问题，**在报告里指出，不要猜**。
- 标记 `[common step]` 的方法只是背景信息，**不改变判定规则**。

---

## 三、判定规则（核心）

对每一条记录，输出三选一：

| 判定 | 含义 |
|---|---|
| `on_topic` | 这条协议的**核心技术就是**这个方法 |
| `tangential` | 这个方法确实出现了，但只是次要步骤 |
| `wrong` | 这条协议跟这个方法没关系，或命中了排除条款 |

### 判定流程（按顺序做）

1. 看数据行的 `criteria_key`
2. 若**不是** `general` → 到下方「四、判据表」找同名条目，按 essence → must → exclude 逐条比对
3. 若是 `general` → 只用「五、通用规则」+ 该方法的 definition
4. **判据优先于你的直觉**：命中任何 exclude 条目就判 `wrong`，
   除非该方法仍是这条协议的核心产出

### 五条通用规则

{universal}

### 三条硬要求（违反即视为格式错误）

1. **判据压过直觉**。不许因为"我觉得它基本相关"就推翻排除条款。
2. **必须引用依据**。`criteria_hit` 不能为空，要写 `exclude#2` / `must#1` /
   `universal#3` / `definition` 之一。
3. **`tangential` 不能当保险档**。它只用于"确实有这个方法的一步，但不是主体"。
   **拿不准就判 `wrong` 并把 `confidence` 设成 `low`**，不要用 tangential 和稀泥。
   （我们实测过：tangential 是分歧最大的一档，一个方法 144 条里有 47 条卡在这）

---

## 四、判据表（20 个高分歧方法，其余方法用通用规则）

{crit_block}

---

## 五、输出格式

**一行一条 JSON**，字段如下（缺任何一个字段都会导致这条被退回）：

```json
{{"task":"A","method_id":47917,"protocol_id":456,
 "verdict":"on_topic|tangential|wrong",
 "criteria_hit":["exclude#2"],
 "confidence":"high|medium|low",
 "reason":"不超过25个英文单词，必须和你引用的判据一致"}}
```

要求：

- 严格保持输入顺序，**不许合并、去重、跳过任何一条**
- 输入多少条，就输出多少行
- 只输出 JSON，不要加解释文字、不要加代码块围栏

---

## 六、Task B（本次不做，后续另发）

如果你收到的数据行带 `"task":"B"`，那是另一件事（评审方法说明文字质量），
按当时给的说明做。本次只做 `"task":"A"`。

---

## 附录：83 个方法定义

按 `method_id` 查（升序）：

{def_block}
"""

open(OUT, 'w', encoding='utf-8', newline='\n').write(DOC)
print(f'READ_ME_FIRST.md 已生成：{os.path.getsize(OUT) / 1024:.0f} KB')
print(f'  含 {len(crit["methods"])} 个方法的详细判据 + {len(defs)} 个方法的定义')
