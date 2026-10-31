"""生成「独立判断版」READ_ME_FIRST.md。

## 与上一版的根本区别

上一版把「我怎么判」也交给了模型：20 个方法的 exclude 清单、五条通用规则、
"tangential 不能当保险档"这类纪律。结果是模型只能复现我的判断 ——
它判得和我一致，只说明它像我，不说明它判得对。

这一版**只给三样东西**：
  1. 任务是什么
  2. 方法是怎么定义的（83 条，不含任何判定倾向）
  3. 输出格式（这是解析契约，不是判据）

刻意**不给**：
  - 20 个方法的 exclude 条款
  - 「区分实验主体/上游制备/下游分析」这类方法论
  - 「tangential 是保险档」这类纪律
  - 任何"你该怎么想"的提示

目的是让它的判断不受我的框架影响，两边分歧才是真实分歧。
"""
import json
import os

BASE = 'docs/handoff'
OUT = os.path.join(BASE, 'READ_ME_FIRST.md')
defs = json.load(open(os.path.join(BASE, 'METHOD_DEFS.json'), encoding='utf-8'))

def_lines = []
for mid, d in sorted(defs.items(), key=lambda x: int(x[0])):
    flag = (' *(often a supporting step rather than a standalone technique)*'
            if d['is_step_tag'] else '')
    def_lines.append(f'- `{mid}` — **{d["name"]}**{flag}\n  {d["definition"]}')
def_block = '\n'.join(def_lines)

DOC = """# READ ME FIRST

## What you are doing

Below you will receive batches of records. Each record links one laboratory **protocol**
to one canonical **method** (a technique category). For each record, decide whether that
link is correct — that is, whether the protocol genuinely uses that method.

You are judging **one record at a time**, independently. There is no answer key and no
prior labelling to match. Use your own domain knowledge and the method definitions in the
appendix at the bottom of this file.

---

## What you receive

1. **This file** — the task, the label definitions, the output format, and the definitions
   of all 83 methods.
2. **One batch file** (`part_XX.jsonl`) — a few hundred records, one JSON object per line.

Each record looks like this:

```json
{"task":"A","bridge_id":123,"method_id":47917,"criteria_key":"Sanger Sequencing",
 "protocol_id":456,"protocol_name":"...","protocol_objective":"...",
 "link_source":"manual_curated","link_status":"active"}
```

Notes:

- `protocol_name` and `protocol_objective` describe the protocol. `protocol_objective` may
  be empty; when it is, judge from the title alone and lower your confidence accordingly.
- **The record does not carry the method's name or definition.** Look those up by
  `method_id` in the appendix at the bottom of this file.
- `criteria_key`, `link_source` and `link_status` are metadata about how the link was
  originally produced. They are **not** evidence about whether it is correct — ignore them
  for judging.
- If a `method_id` is missing from the appendix, report it. Do not guess.

---

## Three labels

Pick exactly one per record:

| Label | Meaning |
|---|---|
| `on_topic` | The protocol's **core technique is** this method. |
| `tangential` | The method genuinely appears in the protocol, but only as a secondary or incidental step — not what the protocol is fundamentally about. |
| `wrong` | The protocol does not meaningfully involve this method. |

There is no preference ordering among these labels and no expectation about how often
each should appear. Call it as you see it.

---

## Output format

One JSON object per line, in the **same order as the input**. If the batch has 500 records,
output exactly 500 lines.

Required fields:

| Field | Type | Notes |
|---|---|---|
| `task` | string | always `"A"` |
| `method_id` | integer | copy from the input record |
| `protocol_id` | integer | copy from the input record |
| `verdict` | string | `on_topic` / `tangential` / `wrong` |
| `confidence` | string | `high` / `medium` / `low` |
| `reason` | string | <= 25 words, in English, stating why you chose this label |

Example of a single line:

```json
{"task":"A","method_id":47917,"protocol_id":456,"verdict":"wrong","confidence":"high","reason":"Protocol describes bacterial plate streaking; no sequencing performed."}
```

Rules for the output:

- **No** commentary, preamble, summary, or markdown fences. JSON lines only.
- Do not merge, split, deduplicate, or reorder records.
- If output is truncated, you will be asked to continue from where you stopped.
- `reason` should say what the protocol actually does and why that does or does not match
  the method — not restate the method's definition.

---

## Appendix — definitions of all 83 methods

Look up by `method_id`. The italic note marks methods that are typically supporting steps
inside other workflows rather than standalone techniques; that note is descriptive context
only and carries no judging instruction.

""" + def_block + "\n"

open(OUT, 'w', encoding='utf-8', newline='\n').write(DOC)
print(f'READ_ME_FIRST.md（独立判断版）已生成：{os.path.getsize(OUT) / 1024:.0f} KB')
print('  含：任务说明 + 三档定义 + 输出格式 + 83 个方法定义')
print('  不含：20 个方法的 exclude 判据、五条通用规则、任何判定倾向提示')
