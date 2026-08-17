# Jena Auto Match · 使用链路修复设计方案（层 B）

> 状态：**方案文档，未改动任何代码**。供用户过目确认后再决定是否落地。
> 依赖前序：① jena 数据测绘 ② 身份字段准确性审计（91% 干净）③ 使用链路审计（本报告修复对象）。
> 目标：消除"双向子串 + 取首条"导致的错配，让 auto match 在通用名查询下也精准、可信、可复核。
> 原则：治标（算法层）不依赖修爬虫即可生效；与层 A 数据闸门、层 C 呈现层协同。

---

## 0. 当前代码事实（已读确认的坐标）

| 位置 | 现状 | 问题 |
|---|---|---|
| `jena_index.find_by_name` (174-187) | `exact + partial[:limit]`，返回 `list[JenaRecord]` | 不暴露 exact/partial 区分；partial 按文件顺序 |
| `jena_matcher._match_jena_no_cache` (51-105) | `match_key` ∈ {cas, name, synonym:xxx}；返回 dict 无置信档 | 不区分"精确名"vs"子串名" |
| `jena_matcher.match_jena` (108-164) | L1 缓存 TTL 30天，按 identifier 分桶；`MAPPER_VERSION="2"` | 缓存键未含 match_type（修复后需递增版本） |
| `ai_views.enrich` (356-444) | 原样返回 `jena` + `bioz` 到 response | 无"高/低置信"分流，低置信也当成可用草案 |
| `bioz_pipeline.fetch_bioz_evidence` (24-89) | 已返回 `catalog_no` / `equivalence` / `needs_review` / `disclaimer` | **锚点已透传**，但缺"锚点可信度"标注；错误 catalog 仍查得文献 |

**关键修正（相对上一轮报告）**：bioz 的 `catalog_no` 锚点**已经存在**，故 B-4 不是"新增锚点字段"，而是**给锚点加可信度标注**（`match_confidence`），并在低置信匹配时明确化"文献基于可能不准确的锚点"。

---

## 1. B-1：`match_key` 细化四档 + 新增 `confidence`

**坐标**：`jena_index.find_by_name` (174-187) → `jena_matcher._match_jena_no_cache` (51-105)。

**改动**：
1. `find_by_name` 暴露 exact/partial 区分（返回 `(record, is_exact)` 元组，或给 JenaRecord 加临时 `match_type` 属性）。
2. matcher 据 `is_exact` 与命中路径，设四档之一：

```python
# 伪代码（jena_matcher._match_jena_no_cache 内）
if record is not None:
    if match_key == "cas":
        match_type, confidence = "cas", "high"
    elif is_exact:                      # find_by_name 命中 exact 集合
        match_type, confidence = "exact_name", "high"
    else:                               # find_by_name 命中 partial（子串）
        match_type, confidence = "substring_name", "low"
    # synonym 路径保持 low
    if match_key.startswith("synonym:"):
        match_type, confidence = "synonym", "low"

return {
    "matched": True,
    "match_key": match_key,        # 保留原三档（向后兼容前端）
    "match_type": match_type,       # 新增：四档精确值
    "confidence": confidence,       # 新增：high / low
    "catalog_no": record.catalog_no,
    # ... 其余字段不变
}
```

**注意**：`find_by_name` 当前被 `lookup()` (205-207) 用 `results[0]` 取首条。改为元组返回后，`lookup` 同步改为 `results[0][0]` 并保留 `is_exact`（供 matcher 判断）。

---

## 2. B-2：子串命中 / 多候选 → 返回候选列表而非单条首条

**坐标**：`jena_index.find_by_name` (174-187) + `jena_matcher._match_jena_no_cache` (66-73 synonym 循环)。

**改动**：当 `match_type == "substring_name"` 或候选数 > 1，matcher 收集候选列表返回，而非只取首条。

```python
# 伪代码（name 路径）
records = index.find_by_name(identifier, limit=5)   # 返回 (record, is_exact) 列表
exact_recs = [r for r, ex in records if ex]
partial_recs = [r for r, ex in records if not ex]

if exact_recs:
    record = exact_recs[0]; is_exact = True
else:
    # 子串命中：保留全部候选，供前端/操作员挑选
    record = partial_recs[0]; is_exact = False
    candidates = [r.catalog_no for r in partial_recs]   # 候选 catalog 列表

# 返回 dict 增加：
"candidates": candidates if (not is_exact and len(records) > 1) else [],
```

**效果**：`ATP` 查询不再只返回 `2'MeSe-ATP`，而是返回候选列表 `[2'MeSe-ATP, ATPγS, N6-Benzyl-ATPγS, ...]` + `confidence=low`，由操作员/前端决策。

---

## 3. B-3：view 按置信分流（不自动采纳低置信）

**坐标**：`ai_views.enrich` (356-444)，返回结构 `{chemical, literature, protocols, jena, bioz}`。

**改动**：在 response 中显式标注置信，并区分"可自动预填"与"待人工复核"。

```python
# 伪代码（ai_views.enrich 组装 jena 段）
jena = match_jena(...)
jena_block = {
    **jena,
    "auto_fill": jena.get("confidence") == "high",   # 高置信才自动预填
    "needs_human_review": jena.get("confidence") == "low",
}
# 低置信时不进入"已采纳草案"，而是进入工作台"待复核队列"
# （前端据此渲染：高置信=绿色自动带入；低置信=amber 待确认 + 候选列表）
return self.success_response({
    "chemical": chemical,
    "literature": literature,
    "protocols": protocols,
    "jena": jena_block,
    "bioz": bioz,
})
```

**数据流约束**：后端只"标注"，不替研究员决策（遵循 FIVE_DATASOURCES.md §5.4 铁律：草案供确认，不直接落库）。落库仍由研究员在 `/workspace` 显式确认。

---

## 4. B-4：bioz 锚点可信度标注

**坐标**：`jena_matcher`（透传 match_type）→ `bioz_pipeline.fetch_bioz_evidence` (24-89)。

**改动**：matcher 把 `match_type` / `confidence` 透传给 bioz；bioz 在返回里加 `match_confidence`，并在 substring 匹配时明确化"证据基于低可信锚点"。

```python
# 伪代码（fetch_bioz_evidence 签名 + 返回）
def fetch_bioz_evidence(jena_result, platform_cas="", vendor="Jena Bioscience",
                        max_results=10, match_confidence=None):
    # ... 现有逻辑 ...
    # 接收来自 matcher 的可信度（若调用方已给，用调用方的；否则从 jena_result 取）
    conf = match_confidence or jena_result.get("confidence", "low")
    return {
        "queried": True,
        "vendor": vendor,
        "catalog_no": catalog_no,            # 已有锚点字段
        "match_confidence": conf,            # 新增：锚点可信度
        "equivalence": equiv.get("equivalence", "weak"),
        "needs_review": equiv.get("needs_review", True) or (conf == "low"),
        "disclaimer": DISCLAIMER,
        "total": len(clean),
        "references": clean,
    }
```

**语义**：当 `match_confidence == "low"`（substring 命中），即使 `equivalence` 算出 strong，也强制 `needs_review=True`，且前端可明示"该文献基于子串匹配锚点 `{catalog_no}`，锚点可能不准确"。

---

## 5. 影响面（落地时需同步变更）

| 文件 | 变更 | 风险 |
|---|---|---|
| `jena_index.py` | `find_by_name` 返回结构变（元组/属性）；`lookup()` 同步 | 中：调用方需适配 |
| `jena_matcher.py` | `_match_jena_no_cache` 构造 match_type/confidence/candidates；`match_jena` 缓存键 | 中：需递增 `MAPPER_VERSION` 使旧 30天缓存失效 |
| `ai_views.py` | enrich 返回加 auto_fill/needs_human_review | 低：仅增字段，向后兼容 |
| `bioz_pipeline.py` | 加 match_confidence 参数 + 返回字段 | 低：仅增字段 |
| 前端工作台 | 匹配依据卡 / 候选列表 / 来源标签 / amber 色（层 C） | 中：前端另一仓库，需协同 |
| `test_jena_index.py` / `test_jena_matcher.py` / `test_ai_views.py` | 更新期望（match_type/confidence/candidates） | 低：测试同步 |

**缓存兼容性**：`MAPPER_VERSION` 当前 `"2"`，修复后改为 `"3"`，旧缓存自动失效重查（已有机制，见 jena_matcher.py:19-22, 145）。

**回归基准**：`verification/jena_match_ambiguity.py` 可作修复后回归——修复后 `ATP`/`UTP`/`Salt` 等查询应返回 `candidates[]` + `confidence=low`，**不再错误返回单条首条**。

---

## 6. 与层 A（数据闸门）协同

- 层 A 保证 `catalog_no` 真实存在（修 173 条粘连）→ bioz 查询能真正命中正确 catalog。
- 层 B 保证"即使查询词是通用名"，也不会错配采纳 → 错误 catalog 根本不会进入 bioz 锚点。
- 二者正交：层 A 治"数据脏"，层 B 治"算法松"；任一成立都提升精准度，二者齐备链条才完全可靠。

---

## 7. 未决 / 待你确认

1. **子类匹配是否要加词边界/相似度阈值**（更激进的治本）：如在 `find_by_name` 中要求 `name_lower == pn` 或 `(name_lower in pn and len(name_lower) >= 0.7*len(pn))`，可减少"短词命中长名"误中。还是仅用"exact 优先 + 子串降为低置信 + 返候选"的保守方案？
2. **候选列表上限**：limit 取 5 还是 10？
3. **层 C 前端**是否在此次一并规划（当前方案仅列影响，代码在另一仓库）？
4. 是否同意先递增 `MAPPER_VERSION` 清缓存？

> 以上确认后，再进入"动代码"阶段。本文件为方案，未执行任何修改。
