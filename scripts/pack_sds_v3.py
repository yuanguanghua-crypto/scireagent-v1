#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""pack_sds_v3.py — 组 SDS-PAGE v3 重验的两个盲测包（诸葛亮 / 郭畅）

## 为什么要单独一个打包器

`scripts/pack_p0.py` 是 2026-11-02 那批（1b/2b/3b）的打包器，**已交付、不能再动**。
本脚本独立，复用同一套"确定性打包"做法（固定时间戳 + 固定顺序），保证同内容同字节。

## 包里放什么（自包含，收件人不需要任何外部文件）

| 包内文件 | 内容 |
|---|---|
| `00_TASK.md` | 任务说明（判什么、怎么判、交什么） |
| `01_DEFINITION_v3.yaml` | **曹操采纳版**定义（status: adopted-by-author） |
| `02_SPEC_v3.4.md` | 方法定义规范 v3.4 全文 |
| `03_SAMPLES_33.json` | 样本 33 条（**探针已混入、不标记**） |
| `04_OUTPUT_FORMAT.md` | 输出格式 + 一条示例 + 校验命令 |
| `05_verify_sample_len.py` | 输入侧校验（防查看器截断） |
| `06_verify_annotator_output.py` | 输出侧校验（字段/编号/英文） |
| `MD5.txt` | 包内文件 md5 |

## 绝不放（forbid，硬断言）

κ 结果 / 上一轮判定 / 探针 meta / 方案草案 / 任何他人输出。
包里出现其一即中止打包。

## 包内文件名用 ASCII

zip 里带中文名在 Windows 解压会乱码（前几轮踩过）⇒ 包内全 ASCII，中文说明写在 `00_TASK.md` 正文里。
"""
from __future__ import annotations

import hashlib
import io
import os
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXED_DT = (2026, 11, 2, 0, 0, 0)
OUT_DIR = os.path.join(REPO, 'dist', '_released_20261102', 'SDS-PAGE-v3重验')

DEFINITION = os.path.join(REPO, 'work', 'p0_sds_page_definition_v3_曹操采纳_20261102.yaml')
BATCH = os.path.join(REPO, 'work', '_sds_v3_batch_20261102.json')
SAMPLELEN = os.path.join(REPO, 'scripts', 'verify_sample_len.py')
OUTCHK = os.path.join(REPO, 'scripts', 'verify_annotator_output.py')

# 绝不许出现在包里的内容特征（**只禁"结果值"与"探针身份"，不禁 κ 这个字本身**）
# 规范正文里必然出现 κ / Po 阈值 —— 那是验收标准；禁的是**已算出的结果**与**谁是谁的探针**。
FORBID_CONTENT = ('0.813', '_batch_meta', 'probe_positions', 'probe_bridge_ids')

# 样本文件的结构契约：字段必须恰好是这 8 个（多一个都可能泄漏分层/探针信息）
SAMPLE_KEYS = {'bridge_id', 'protocol_id', 'protocol_name', 'objective',
               'steps', 'objective_len', 'n_steps', 'steps_len'}

TASK_MD = """# 任务说明 · SDS-PAGE 判定（33 条）

> 本包**自包含**：判定所需的东西都在包里，不需要查库、不需要问人。

## 一、你要做什么

对 `03_SAMPLES_33.json` 里的 **33 条协议**，逐条判断：
**这个协议是否属于「SDS-PAGE」这个方法**，并按下面的三档给出结论与英文理由。

## 二、判定依据只有两处

1. `objective`（协议的目标陈述）
2. 每条样本给出的**前 6 步**步骤正文

> **仅"协议标题里出现 SDS-PAGE"不构成依据。**
> 允许认的词形（全称、缩写、连写、带连字符）：`SDS-PAGE` / `SDS PAGE` /
> `sodium dodecyl sulfate` / `SDS-polyacrylamide` / `Laemmli`。

**`objective` 为空不代表方法没执行** —— 那就按步骤判；
若步骤里也没有方法证据，按"拿不准往低判"处理（见第三节第 3 档）。

## 三、三档结论

| verdict | 什么时候用 |
|---|---|
| `on_topic` | 方法的**全部 must 条件**满足，**且**产出就是 SDS-PAGE 胶带图样本身 |
| `tangential` | must 条件满足，但**产出不是胶带图样**（如转膜后免疫检测、纯度检查、质谱前处理） |
| `wrong` | 至少一条 must 条件不满足（材料不是蛋白/肽；没有 SDS 变性；没有上胶跑电泳）；或证据不足、拿不准 |

**完整判定标准在 `01_DEFINITION_v3.yaml`**（`must` / `on_topic_requires` / `exclude` / 例子）。
**拿不准时以定义文件为准，不要凭印象。**

### 关于证据不足

若 `objective` 为空、前 6 步也没陈述方法证据 → 判 `wrong`，并在 `why` 里**明确写**
`insufficient detail` 这两个词。

## 四、交什么

一个 JSONL 文件（**每行一个 JSON 对象**，**33 行**），字段**只允许三个**：

```json
{"bridge_id": 12345, "verdict": "on_topic", "why": "One sentence in English."}
```

| 字段 | 要求 |
|---|---|
| `bridge_id` | 照抄样本里的 `bridge_id`，**33 条都要有，一条不多一条不少** |
| `verdict` | 只能是 `on_topic` / `tangential` / `wrong` |
| `why` | **英文**、非空、一到两句话说明依据（引用定义里的哪条） |

更多示例见 `04_OUTPUT_FORMAT.md`。

## 五、交之前自检（两条命令）

```bash
# ① 先确认你没被查看器截断（输入侧）
python 05_verify_sample_len.py --batch 03_SAMPLES_33.json

# ② 再确认输出格式对（输出侧）
python 06_verify_annotator_output.py --batch 03_SAMPLES_33.json --mine 你的输出.jsonl
```

两条都 exit 0 才算交得出手。

## 六、纪律

1. **独立完成**：不要和任何人讨论这 33 条，不要对答案
2. **不要查库/搜原文**：判定只依据包里给的内容 —— 这是为了保持可复现
3. **不要用查看器粗略浏览长文本**：本批最长 objective 1,544 字符、最长 steps 合计 3,436 字符，
   用 `05_verify_sample_len.py` 确认你看到的是完整的
4. **不要改样本文件**
"""

JUDGING_MD = """# 判读要点（本文件是摘要，**判定标准以 01_DEFINITION_v3.yaml 为准**）

> 本包**不附方法定义规范全文**。规范是组织方内部文档，含与本轮判定无关的内容；
> 你判定所需的全部标准都在 `01_DEFINITION_v3.yaml` 里（must / on_topic_requires / exclude / 例子 / scope_note）。
> 本文件只把最容易搞错的四件事拎出来。

## 一、三档怎么落

| 条件 | verdict |
|---|---|
| 有任何一条 `must` 不满足 | `wrong` |
| `must` 全满足，且 `on_topic_requires` 全满足 | `on_topic` |
| `must` 全满足，但至少一条 `on_topic_requires` 不满足 | `tangential` |

**`must` 与 `on_topic_requires` 是两件事**：前者问"这个方法有没有被执行"，后者问"产出是不是这个方法本身的产出"。
不要把"没写产出"当成"没执行"。

## 二、证据只看两处

1. `objective`
2. 每条样本给的前 6 步步骤正文

**仅协议标题出现方法名，不构成证据。** 认词形：全称 / 缩写 / 连写 / 带连字符。

## 三、`objective` 为空怎么办

- `objective` 空，但前 6 步陈述了方法证据 → **按步骤正常判**
- `objective` 空，前 6 步也没证据 → 判 `wrong`，且 `why` 里写明 `insufficient detail`

**不要因为"没写目标"就判 `wrong`。** 空 ≠ 没执行。

## 四、`scope_note` 怎么用（重要）

定义里的 `scope_note` 只**声明本方法范围不含哪些东西**，它**不参与判定**：

- **不能用它当依据去判 `wrong`**（它不是 exclude 条目）
- 它只是告诉你"这些边界情况存在"，**不回答落在边界上的协议该怎么判**

若某条协议正好落在 `scope_note` 提到的范围里，**按 `must` / `on_topic_requires` 正常走一遍**，
不要因为"它提到了某个范围外的词"就直接判 `wrong`。

## 五、拿不准时

按"往低判"处理：能判 `wrong` 就判 `wrong`，并在 `why` 里说明缺哪条证据。
不要为了"看起来合理"硬判 `on_topic`。
"""

OUTPUT_FORMAT_MD = """# 输出格式 · 示例与常见错

## 一、必须是 JSONL（每行一个对象，不是 JSON 数组）

**对：**
```
{"bridge_id": 12345, "verdict": "on_topic", "why": "The sample is boiled in Laemmli buffer, run on a 10% polyacrylamide gel, and the Coomassie-stained band pattern is the stated readout."}
{"bridge_id": 12346, "verdict": "tangential", "why": "SDS-PAGE is run, but the stated readout is immunodetection on a membrane rather than the gel band pattern."}
{"bridge_id": 12347, "verdict": "wrong", "why": "The analyte is DNA separated on an agarose gel; no SDS-polyacrylamide separation of protein is performed."}
```

**错（整份写成数组）：**
```
[ {"bridge_id": ...}, {"bridge_id": ...} ]
```

## 二、字段只允许三个

`bridge_id` / `verdict` / `why`。**多一个字段都会被校验脚本拒掉**（包括 `category`、`notes`、`confidence`）。

## 三、`why` 必须是英文

校验脚本会查中日韩字符。**不要写中文**，也不要中英混写。

## 四、拿不准时的写法

```json
{"bridge_id": 12348, "verdict": "wrong", "why": "The objective is empty and none of the first six steps states the method; judged wrong under the lower-when-unsure rule with insufficient detail flagged."}
```

要点：`verdict` 判 `wrong`，`why` 里出现 `insufficient detail`。

## 五、自检命令

```bash
python 06_verify_annotator_output.py --batch 03_SAMPLES_33.json --mine 你的输出.jsonl
```

它检查六项：JSON 合法 / 行数等于批条数 / 只有三个字段 / bridge_id 逐条对得上 / verdict 合法 / why 英文非空。
"""


def _md5(b):
    return hashlib.md5(b).hexdigest()


def build(annotator: str, tag: str) -> str:
    files = {
        '00_TASK.md': TASK_MD.encode(),
        '01_DEFINITION_v3.yaml': open(DEFINITION, 'rb').read(),
        '02_JUDGING_RULES.md': JUDGING_MD.encode(),
        '03_SAMPLES_33.json': open(BATCH, 'rb').read(),
        '04_OUTPUT_FORMAT.md': OUTPUT_FORMAT_MD.encode(),
        '05_verify_sample_len.py': open(SAMPLELEN, 'rb').read(),
        '06_verify_annotator_output.py': open(OUTCHK, 'rb').read(),
    }

    # ── forbid 第一层：内容特征 ──
    for name, data in files.items():
        t = data.decode('utf-8', 'replace')
        for kw in FORBID_CONTENT:
            if kw in t:
                raise SystemExit(f'❌ forbid 命中：{name} 含 {kw!r}，中止打包')

    # ── forbid 第二层：样本结构（字段集合必须精确，多一个就中止）──
    import json as _json
    recs = _json.loads(files['03_SAMPLES_33.json'].decode())
    for i, r in enumerate(recs, 1):
        extra = set(r) - SAMPLE_KEYS
        miss = SAMPLE_KEYS - set(r)
        if extra or miss:
            raise SystemExit(f'❌ 样本第 {i} 条字段不合契约：多余 {sorted(extra)} 缺 {sorted(miss)}')
    if len(recs) != 33:
        raise SystemExit(f'❌ 样本条数 {len(recs)} ≠ 33')
    # 探针身份不得以任何形式出现（meta 里的 bridge 号不得出现在任务/输出说明中）
    for nm in ('00_TASK.md', '02_JUDGING_RULES.md', '04_OUTPUT_FORMAT.md'):
        t = files[nm].decode()
        for bad in ('探针', 'probe', '内部标记'):
            if bad in t:
                raise SystemExit(f'❌ {nm} 含 {bad!r}（不得向标注员透露探针存在）')

    md5txt = '\n'.join(f'{_md5(v)}  {k}' for k, v in files.items()) + '\n'
    files['MD5.txt'] = md5txt.encode()

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f'SDS-PAGE-v3_{tag}.zip')
    with zipfile.ZipFile(out, 'w') as z:
        for name in sorted(files):
            zi = zipfile.ZipInfo(f'SDS-PAGE-v3_{tag}/{name}', date_time=FIXED_DT)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, files[name])
    b = open(out, 'rb').read()
    print(f'✅ {annotator} 包 → {os.path.relpath(out, REPO)}  {len(b)} B  md5 {_md5(b)}')
    return out


def main() -> int:
    outs = [build('诸葛亮', '诸葛亮'), build('郭畅', '郭畅')]
    for p in outs:
        z = zipfile.ZipFile(p)
        bad = z.testzip()
        print(f'   {os.path.basename(p)}: CRC {"OK" if not bad else bad}, {len(z.namelist())} 条目')
    return 0


if __name__ == '__main__':
    sys.exit(main())
