# 数据量级压测报告（2026-10-22）

> 对应 `FAILURE_MODES.md` 10.2「数据量 10 倍后崩」。
> 此前这条是 B 类，兜底写的是"数据增长后重跑 perf_gate 看趋势"——**但从来没有真跑过**。
> 本报告是第一次真的把数据放大 10 倍并测量。

## 1. 方法（为什么这样测才有意义）

**同一个库、同一台机器、只变数据量。** 这是唯一能得出"数据量影响"这个结论的设计：
- 若换库（dev sqlite → 新 PG），则测出的是"sqlite vs PG"的差异，不是数据量的影响
- 因此：新建 `scireagent_vol`（PG 17），先造 **1 倍**（≈当前生产/开发规模），测一遍；
  再补到 **10 倍**，测同一批端点。

```
scripts/seed_volume.py --apps 28600  --products 127     # 1x
scripts/seed_volume.py --apps 286000 --products 1270    # 10x（增量补到目标）
```

- 造数用 `bulk_create`（batch=5000）：1x 用 **5 秒**，10x 用 **37 秒** —— 成本远低于预期，
  所以"10 倍"不是够不着的目标，**随时可以重跑**。
- 安全：脚本**写死** `DB_NAME` 必须含 `vol`，否则直接退出（防误跑 dev/生产）。
- 用完 `DROP DATABASE scireagent_vol`，机器上不留垃圾。

## 2. 结果（p95，毫秒）

| 端点 | 1x (28.6k app) | 10x (286k app) | 恶化倍数 | 绝对上限 | 判定 |
|---|---|---|---|---|---|
| `/api/v1/products/` | 30.2 | 29.5 | **1.0x** | 2000 | ✅ 完全不受影响 |
| `/api/v1/search?q=a` | 13.8 | 124.5 | 9.0x | 2000 | ⚠️ 近线性 |
| **`/api/v1/search/grouped?q=a`** | **1203.1** | **7522.4** | 6.3x | 2000 | ❌ **超上限 3.8 倍** |
| `/api/v1/search/suggest?q=ab` | 2.2 | 2.2 | **1.0x** | 2000 | ✅ 完全不受影响 |
| `/api/v1/site/home` | 49.8 | 324.3 | 6.5x | 3000 | ⚠️ 未超但明显恶化 |
| `/api/v1/site/navigation` | 17.6 | 76.2 | 4.3x | 3000 | ⚠️ |
| **`/api/v1/sitemap.xml`** | **299.4** | **7630.5** | **25.5x** | 4000 | ❌ **超上限 + 响应 16.6MB** |

## 3. 归因（为什么是这四个不同的倍数）

**1.0x —— `products` / `search/suggest` 不受数据量影响**
说明它们**真的走了索引**（`product_cas_idx` / `product_name_trgm` 等），
查询成本与表大小基本无关。这是"索引正确"的正面证据。

**9.0x / 6.5x / 4.3x —— 近线性**
`search` / `site/home` / `site/navigation` 的成本大致随数据量线性增长。
`site/home` 我上一个任务优化过（GROUP BY 挡 LIMIT 已修），但**聚合本身仍是全量**，
所以 10 倍后仍从 50ms 涨到 324ms。**优化过 ≠ 不受规模影响。**

**6.3x —— `search/grouped` 亚线性但基数极高**
它 1x 时就已经 1203ms（dev 的 sqlite 只要 31ms，因为 sqlite 走 `icontains`）。
原因见 `search_grouped_views.py` 自己的 docstring：
> FTS 向量在**查询时**用 `SearchVector(...)` 现算，**不依赖预存的 `search_vector` 列**
> —— 那列在生产里是空的（迁移只建了列 + 索引，没有 trigger/backfill）

所以它每次查询都要对候选行**现场计算 tsvector**，索引完全用不上。
⇒ 它不是"随数据量崩"，而是"**从头就贵，且贵得很稳定**"。

**25.5x —— `sitemap.xml` 是超线性，且这不只是延迟问题**
25.5 倍远超数据量的 10 倍。原因不在 SQL（表变大 10 倍，扫描也就 10 倍），
而在**响应体**：1x 时 1.63MB → 10x 时 **16.6MB**。
序列化 + 传输 16.6MB 字符串的成本是超线性的（内存分配、gzip、socket 写）。

⚠️ **这是一个匿名可触发的 16.6MB 带宽放大点** —— 和之前修掉的
`site/navigation` 2.78MB 是同一类问题（那次是孤儿端点，这次是 `sitemap.xml`，**必须保留**，
但应该分片）。

## 4. 结论与建议

### 现在就该修的（按投入产出排序）

| # | 问题 | 修法 | 成本 |
|---|---|---|---|
| 1 | ~~**`sitemap.xml` 16.6MB**~~ | ✅ **已修（2026-10-22）**：改为 sitemap index + 按类型分片（每片 ≤45,000 URL）。见 §5 | 半天 |
| 2 | ~~**`search/grouped` 7.5s**~~ | ✅ **已修（2026-10-22）**：`0024_search_vector_triggers` 建 5 张表的 trigger + 回填 `search_vector`，查询改为查列。见 §6 | 半天 |

> 第 2 项尤其讽刺：schema 层面**早就准备好了**索引，但因为列从来没人填过，
> 代码只好每次现场算。这也是"迁移只建结构、没填数据"留下的债。

### 不用修的
- `products` / `search/suggest` 已验证不受规模影响
- `site/home` 324ms 在 3000ms 上限内；它的成本是"首页聚合"的固有代价，
  要再优化就得改数据模型（物化视图/缓存），**当前规模不值得**

### 这条 A 类到底"自动"了什么
10.2 的状态是 **A**，但要说清它 A 在哪：
- ✅ **有可复现的压测方法**（`seed_volume.py` + `perf_gate.py`，15 分钟能跑完）
- ✅ **有明确的超限信号**（跑出来 2 个端点 FAIL，不是我"感觉慢了"）
- ❌ **不是"已优化"**——两个瓶颈都还在，只是现在**被量化并归档**了

⇒ 后续任何"数据量要涨"的决策，都应该先按本文 §1 的方法重跑一次。

## 5. `sitemap.xml` 修复记录（2026-10-22）

### 动手前先测了一件事，它改变了优先级
不只是"10 倍才出问题"——**当前生产就已经逼近上限**：

| 指标 | 实测 |
|---|---|
| 当前 URL 数 | **42,779** |
| 协议上限（单文件） | **50,000 URL / 50MB** |
| 剩余余量 | **仅 17%** |

⇒ 数据再涨 17%，搜索引擎就会**拒收整个 sitemap**（不是变慢，是失效）。
所以这不是"优化"，是**带时间窗的缺陷**。

### 改法
`sitemap.xml` → `<sitemapindex>`，按类型分片：
- `/sitemap-static.xml`（6 个静态页）
- `/sitemap-applications-{n}.xml`
- `/sitemap-methods-{n}.xml`
- `/sitemap-protocols-{n}.xml`
- `/sitemap-products-{n}.xml`

每片 ≤ `SITEMAP_PAGE_SIZE = 45000`（留 10% 余量）。非法 kind / 越界页码 ⇒ **404**
（不用空 urlset —— 那会被搜索引擎当成"该片没内容"）。

### 验证：分片后不丢 URL
| 项 | 值 |
|---|---|
| 旧实现（理论） | 43,141（1 个静态页 + 43,140 实体） |
| 新实现（逐片累加实测） | **43,146**（6 个静态页 + 43,140 实体） |
| 差值 | **+5 = 新增的 5 个静态页**（`/products`、`/applications`、`/methods`、`/protocols`、`/research-goals`） |

> 旧 sitemap **只收录了首页**，漏掉了 5 个重要列表页 —— 顺带补上了。

单片最大 28,558 条 / 1.66MB（applications），距 45,000 还有 57% 余量；
即使数据涨 1 倍，applications 也只会分成 2 片、每片仍在限内。

### ⚠️ 过程中我违反了第 14 条铁律
改 sitemap 契约时，我只改了 `test_site_api.py`，**没有全仓 grep 谁在测 sitemap**
⇒ 漏了 `test_seo.py`（2 条）和 `test_seo_api.py`（1 条），跑全量才暴露。
正是「改/删/放开既有东西前，必全仓 grep 调用点」这条 —— **自己立的规矩自己没遵守**。

## 6. `search/grouped` 修复记录（2026-10-22）

### 先测了一件事，优先级被抬高
这个端点**真被前端使用**（`SearchPage.vue:64`），而且**生产实测 4.87 秒**
（普通 `/search` 只要 0.126 秒）。4.87 秒的搜索是用户能直接感知的慢。

### 根因：不是"数据变多"，是"索引建好了但从未有数据"
`search_grouped_views.py` 在**查询时**用 `SearchVector(...)` 现场算 tsvector ——
因为 `search_vector` 列虽然存在、GIN 索引也建好了，但**列里从来没填过值**
（`0008_*` 迁移只建结构，没有 trigger、没有 backfill）。⇒ 索引完全用不上。

### 为什么不用表达式索引
表达式索引要求查询表达式与索引表达式**逐字匹配**，而 Django 生成的表达式带
双重 `COALESCE((COALESCE(col,''))::text,'')`，手工对齐极脆弱。
**列和索引都已存在** ⇒ 只需填列 + trigger 维护，查询退化成最简单的
`filter(search_vector=...)`，没有匹配风险。

> 另外：`to_tsvector(text)` 单参数版本依赖会话变量 `default_text_search_config`，
> PG 判定它**不是 IMMUTABLE**，**拒绝为它建索引**。必须用两参数
> `to_tsvector('english', ...)`。这也是表达式索引路线的额外障碍。

### 实测（28,600 行 application）
| 方式 | 耗时 | 执行计划 |
|---|---|---|
| 现场算 `to_tsvector(...)` | **205.8ms** | Seq Scan + 每行算向量 |
| 查列（全命中，如 `nucleotide`） | **5.96ms** | Seq Scan（但不算向量） |
| 查列（选择性，如 `VOLAPP-000123`） | **0.059ms** | **Bitmap Index Scan on `application_search_gin`** |

### 端到端（`/api/v1/search/grouped`，28,600 app）
| 查询 | 修复前 | 修复后 |
|---|---|---|
| `q=a` | 1203ms | **364ms** |
| `q=nucleotide` | 1203ms | **130ms** |
| `q=Volume` | 1203ms | **58ms** |

### 实现要点
- `0024_search_vector_triggers`：5 张表（product/application/method/protocol/reference）
  各一个 trigger 函数 + trigger，**并在同一 migration 里回填**（28,600 行约 2 秒）
- **回填必须和 trigger 在同一 migration**：只建 trigger 不回填 ⇒ 新查询查空列
  ⇒ **搜索直接返回空**（比慢更糟）
- 回填后 `ANALYZE`（不更新统计，planner 可能不用索引）
- 只在 PostgreSQL 下执行（sqlite 无 `to_tsvector`）；sqlite 走 `icontains` 分支不受影响
- 回滚只摘 trigger/函数，**不清空 `search_vector` 列**（清空会让"回滚后仍跑新代码"的中间态搜索变空）
