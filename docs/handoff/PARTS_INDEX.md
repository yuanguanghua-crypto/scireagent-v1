# Task A 分片清单（500 条/片，瘦身版）

总计 **14,975** 条，切成 **30** 片。

## 为什么是 500 条不是 800

第一版按 800 条切，实测单条 948 字符 ⇒ 758KB/片 ≈ **190K token**，
正好顶到 200K 上下文窗口，没有输出空间，不可用。

本版做了两件事：
1. **抽掉重复字段**：`method_definition` 曾占单条 38.1%，同一方法平均重复 180 次。
   现在改为查 `METHOD_DEFS.json`（按 `method_id`），单条降到约 620 字符。
2. 片大小降到 500 条 ⇒ 每片约 **78K token**，留 120K 给输出。

## 关键：输入行里没有 method_definition 了

每行只有 `method_id`。**方法名与定义必须查 `METHOD_DEFS.json`**：

```json
{"123": {"name": "PCR", "definition": "...", "is_step_tag": false}}
```

提示词里要明确写：

> 每条记录的 `method_id` 对应 `METHOD_DEFS.json` 的同名键，取其 `name` 与
> `definition` 作为方法上下文；`is_step_tag` 仅作背景，不改变判定规则。

## 分片明细

| 分片 | 条数 | 大小 | 覆盖方法 | 约 token |
|---|---|---|---|---|
| `part_01.jsonl` | 500 | 289 KB | 69 | ~74K |
| `part_02.jsonl` | 500 | 291 KB | 64 | ~75K |
| `part_03.jsonl` | 500 | 287 KB | 69 | ~74K |
| `part_04.jsonl` | 500 | 290 KB | 63 | ~74K |
| `part_05.jsonl` | 500 | 288 KB | 66 | ~74K |
| `part_06.jsonl` | 500 | 284 KB | 64 | ~73K |
| `part_07.jsonl` | 500 | 283 KB | 63 | ~72K |
| `part_08.jsonl` | 500 | 286 KB | 70 | ~73K |
| `part_09.jsonl` | 500 | 288 KB | 67 | ~74K |
| `part_10.jsonl` | 500 | 286 KB | 73 | ~73K |
| `part_11.jsonl` | 500 | 279 KB | 72 | ~71K |
| `part_12.jsonl` | 500 | 248 KB | 76 | ~64K |
| `part_13.jsonl` | 500 | 243 KB | 67 | ~62K |
| `part_14.jsonl` | 500 | 257 KB | 64 | ~66K |
| `part_15.jsonl` | 500 | 247 KB | 68 | ~63K |
| `part_16.jsonl` | 500 | 251 KB | 67 | ~64K |
| `part_17.jsonl` | 500 | 249 KB | 69 | ~64K |
| `part_18.jsonl` | 500 | 250 KB | 67 | ~64K |
| `part_19.jsonl` | 500 | 246 KB | 62 | ~63K |
| `part_20.jsonl` | 500 | 238 KB | 72 | ~61K |
| `part_21.jsonl` | 500 | 195 KB | 72 | ~50K |
| `part_22.jsonl` | 500 | 253 KB | 68 | ~65K |
| `part_23.jsonl` | 500 | 238 KB | 67 | ~61K |
| `part_24.jsonl` | 500 | 246 KB | 69 | ~63K |
| `part_25.jsonl` | 500 | 236 KB | 67 | ~60K |
| `part_26.jsonl` | 500 | 241 KB | 68 | ~62K |
| `part_27.jsonl` | 500 | 244 KB | 72 | ~63K |
| `part_28.jsonl` | 500 | 242 KB | 67 | ~62K |
| `part_29.jsonl` | 500 | 241 KB | 67 | ~62K |
| `part_30.jsonl` | 475 | 240 KB | 71 | ~61K |

## 合并结果

```bash
cat part_*.out.jsonl > result_task_a.jsonl
wc -l result_task_a.jsonl   # 应为 14975
```

> 若平台不接受 `.jsonl` 后缀，改名 `.txt` 即可，内容格式不变。
