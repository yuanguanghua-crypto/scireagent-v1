# 知识实体审核交接包

把「需要人工判断」的部分交给第三方模型，同时保证结果可被程序化接收。

---

## 一、这个包里有什么

| 文件 | 给谁看 | 用途 |
|---|---|---|
| `README.md` | **你** | 本文件：怎么用、怎么交代 |
| `TASK_SPEC.md` | 模型 | 任务说明书（英文，避免歧义） |
| `CRITERIA.json` | 模型 | 20 个高分歧方法的判定规则 + 5 条通用规则 |
| `OUTPUT_SCHEMA.json` | 模型 / 校验器 | 输出契约 |
| `RUBRIC.md` | 模型 | Task B（adv/lim 质量评审）的 7 条规则 |
| `ACCEPTANCE.md` | 你 / 模型 | 五道验收闸门与阈值 |
| `gold_set.jsonl` | 模型 | 56 条校准样本（16 人工确认 + 40 共识） |
| `input_task_a.jsonl.gz` | 模型 | **Task A**：14,975 条协议↔方法关联，待判对错 |
| `input_task_b.jsonl` | 模型 | **Task B**：166 段 advantages/limitations，待评审 |
| `validate_output.py` | 你 | 接收校验工具（格式 / 校准 / 三方交叉） |

**两个任务的性质不同**：

- **Task A** 是客观题——协议是否真的属于该方法，有判据可依
- **Task B** 是主观题——写得好不好，只能按清单勾选

---

## 二、怎么用（三步）

### 步骤 1：本地准备（5 分钟）

```bash
cd docs/handoff
gunzip -k input_task_a.jsonl.gz          # 解压出 input_task_a.jsonl（约 7MB）
```

确认行数：

```bash
wc -l input_task_a.jsonl input_task_b.jsonl gold_set.jsonl
# 应分别得到 14975 / 166 / 56
```

### 步骤 2：交接给模型（见第三节）

### 步骤 3：接收与校验（模型返回后）

```bash
# ① 格式与覆盖率（Gate 1）
python validate_output.py --check --input result_task_a.jsonl --expect 14975

# ② 金标准校准（Gate 2，模型先单独跑 gold_set 的产物）
python validate_output.py --calibrate --input result_gold.jsonl --gold gold_set.jsonl

# ③ 三方交叉（Gate 3，需要我们既有的两份判定）
python validate_output.py --cross --input result_task_a.jsonl \
    --flash flash_verdicts.jsonl --pro pro_verdicts.jsonl
```

三道全过 → 才轮到 `ACCEPTANCE.md` 的 Gate 4（人工抽 5%）和 Gate 5（写库前的安全校验）。

---

## 三、怎么交代给 Claude

### 3.1 先说清楚一件事

**不要一次把 14,975 条全丢给 Claude。** 上下文装不下（约 7MB 文本 ≈ 200 万 token）。
必须分批，每批 **400–600 条**（约 50–70K token，留足输出空间）。

### 3.2 第一批要做的事（校准，不是干活）

新建一个 Claude 会话，**依次上传**这 4 个文件：

```
TASK_SPEC.md
CRITERIA.json
OUTPUT_SCHEMA.json
gold_set.jsonl
```

然后发这段话（可直接复制）：

> 读 `TASK_SPEC.md`，理解 Task A 的判定规则。
> 先不要处理全量数据。用 `gold_set.jsonl` 做校准：按 `TASK_SPEC.md` 的规则给每条判
> `on_topic` / `tangential` / `wrong`，然后和 `expected_verdict` 对比。
>
> 输出一份校准报告：总体准确率、按 `tier`（human / consensus）分层的准确率、
> 混淆矩阵。格式按 `OUTPUT_SCHEMA.json` 里的 `calibrationReport`。
>
> 如果总体准确率低于 85%，直接告诉我，不要继续。

**为什么要这样起步**：我们的两个人模型在同一个校准集上只有 80.5% 的一致率，
所以"模型觉得自己判得对"没有意义——必须先用已知答案测出它的真实水平。

### 3.3 校准通过后，分批跑全量

每次上传 400–600 条（可以把 `input_task_a.jsonl` 按行切分成多个小文件），然后说：

> 这批是 Task A 的第 N/25 批，共 XXX 条。按 `TASK_SPEC.md` 的判定流程逐条判，
> 输出 JSONL，字段严格按 `OUTPUT_SCHEMA.json` 的 `taskARecord`。
> 保持输入顺序，不要合并或跳过任何一条。
> `criteria_hit` 必须引用具体条目（如 `exclude#2`），不能留空。
> 不确定的标 `confidence: "low"`，不要用 `tangential` 当保险。

### 3.4 每条指令都要重复的三件事

Claude 跨批次会漂移，所以**每一批都重申**：

1. **判据优先于你的直觉** —— 命中 `exclude` 就是 `wrong`，不接受"基本相关"这种理由
2. **`tangential` 不是保险档** —— 实测它是分歧最大来源（某方法 144 条里 47 条卡在这）
3. **保持顺序、不许合并** —— 否则我们无法按 `(method_id, protocol_id)` 回填

### 3.5 Task B 单独一轮

Task B 只有 166 条，一次就能跑完。上传 `RUBRIC.md` + `input_task_b.jsonl`：

> 读 `RUBRIC.md`，按 R1–R7 逐行评审 `input_task_b.jsonl` 里的每段文字。
> 每条输出 `findings`，**一行一个 finding**，`line_index` 从 0 开始，不能漏行。
> `pass=false` 时必须给出违反的规则编号；只有机械可改的才给 `suggested_rewrite`。
> 输出按 `OUTPUT_SCHEMA.json` 的 `taskBRecord`。

### 3.6 回来后先验格式，再看内容

**顺序不能反。** 拿到结果先跑 `validate_output.py --check`：

- 有缺行 / 重复 / `criteria_hit` 为空 → **整批退回重跑**，不要手工补
- 格式全过再看校准分数和内容

理由：我们此前吃过一次亏——`--evidence 4` 参数因为循环缺 break 实际灌进 16 条，
当时只看输出"像不像"没发现，直到后续对比才暴露。**格式是第一道可信度闸门。**

---

## 四、四个必须知道的前提

1. **这个包不能解决"谁对"的问题。** 它只能给出第三票。三个模型都同意也可能是共同偏见——
   我们没有客观真值，只有"更多独立判断收敛到同一处"。

2. **判据只覆盖 20 个方法（2,428 条），其余 63 个方法（12,547 条）只有通用规则。**
   这 20 个是双模型分歧 >25% 的——即定义本身不清楚的。剩下的分歧小，通用规则够用。

3. **Task B 没有金标准。** `RUBRIC.md` 末尾写了替代校准法：先评 20 段我们已经人工
   看过的好样本，如果 rejected > 2 段，说明阈值太严，先调阈值再跑全量。

4. **`human` 那一档只有 16 条。** 够做校准，不够做统计。真要更强的金标准，需要我们再
   读一批协议原文——这件事模型替不了。

---

## 五、我们这边接收后做什么

| 结果 | 动作 |
|---|---|
| `wrong` + `high` + 三方一致 | 标 `status='review'`（对公开读路径隐藏），**可回滚** |
| `wrong` 但 2/3 一致或 `medium` | 进人工仲裁队列 |
| `tangential` | 保留可见，降展示优先级 |
| 任何 `low` confidence | 一律人工，不自动处理 |

**不会直接删除任何数据。** 3,807 条协议目前只有一条（错的）关联，删了会变孤儿——
这些单独走重新归类队列。
