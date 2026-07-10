# 数据源可靠性与健壮性方案

> ⚠️ **数据源的定义、接口、字段、传递校验已整合至 `FIVE_DATASOURCES.md`（2026-07-02 重写）**。本文档聚焦「生产可靠性」——缓存层、容错机制、降级链、可观测，是 `FIVE_DATASOURCES.md` §5.6 的深度展开。两文档互补，新人先读 `FIVE_DATASOURCES.md`。
>
> ---
>
> SciReAgent 平台 · 多数据源生产可靠性设计
>
> **文档定位**：`FIVE_DATASOURCES.md` 定义「数据源是什么、提供什么」；本文档定义「**这些数据源在生产中如何被可靠、健壮地使用**」——缓存、存储、容错、降级、可观测。
>
> **文档版本**：2026-07-02 更新待办状态 | 基于代码核查现状
>
> **核心命题**：随着数据源从 1 个增至 6 个（PubChem/ChEMBL/PubMed/BioProCorpus/jena/Bioz），长期生产使用的可靠性与健壮性必须由系统化的缓存层、容错机制和降级链保障，而非依赖外部 API 的实时可用性。

---

## 0. 文档阅读指南

| 你是 | 先看 |
|------|------|
| 设计缓存层 | §3（分层架构）、§5（缓存设计） |
| 处理 BioProCorpus 性能 | §2.B、§7 |
| 接入 jena 数据 | §2.C（撤销说明）、§8（索引策略） |
| 加固外部 API 调用 | §4（容错三件套） |
| 排查"接口慢/挂死" | §1（现状诊断）、§4 |
| 规划止血改造 | §11（优先级路径） |

---

## 1. 现状诊断：开发态可用，生产态必崩

经代码核查，当前数据源使用存在 **5 个生产级脆弱点**：

| # | 脆弱点 | 实证（文件:行号） | 生产后果 |
|---|--------|------------------|---------|
| 1 | **AI AUTO MATCH 结果全部即查即弃** | `pubchem_enhancer.py` / `literature_recommender.py` / `protocol_recommender.py` 无任何 cache 调用 | 同一产品反复查外部 API，每次 5-30 秒，负担随用户数线性增长 |
| 2 | **PubChem 调用无超时** | pubchempy 内部 `urlopen` 未传 timeout（`venv/.../pubchempy.py:380`） | PubChem 慢响应时 enrich 接口**挂死**，gunicorn worker 被占满 |
| 3 | **三套 PubChem 客户端各自为政** | `pubchem_fetcher.py:68`(15s) / `product_validator.py:52`(10s) / `pubchem_enhancer.py`(无超时) | 零共享限速，**PubChem 官方 5 req/s 完全未实现**，批量操作触发 503 |
| 4 | **全项目零重试** | tenacity/backoff 仅存于子项目 bioprocorpus，主代码无 | 一次网络抖动 = 数据缺失，无二次机会 |
| 5 | **django-redis 已装未接线** | `requirements.txt:29` 有 django-redis，`config/settings/` 无 CACHES 配置 | 退回 LocMemCache（等于无跨进程缓存） |

**一句话结论**：当前每次 AI AUTO MATCH 都是「裸奔重跑全部外部 API」，无缓存、无超时、无限速、无重试。开发期凑合能用，**上生产必崩**（接口挂死 + 被限速封禁 + 体验差）。

**唯一已落地的持久化缓存**：`PubChemCache` 模型（`documents/models.py:166`），但**仅 SDS 路径使用**（`workflow.py:127-143`），AI AUTO MATCH 的 PubChem 调用完全不复用它。

---

## 2. 三种数据放置策略 ⭐ 核心

不同数据源的特性不同，放进可靠性架构的**策略也不同**。必须区分三类，不能一概用"缓存"套所有数据。

### 2.A 外部 API 缓存（cache-aside）

**适用**：PubChem（化学属性）、PubMed（文献元数据）、Bioz（结构化文献）、ChEMBL（fallback）

| 维度 | 说明 |
|------|------|
| 数据位置 | 外部 API，本地存「查询结果的副本」 |
| 时效性 | 会变化（PubChem 数据更新、Bioz 文献增长）→ **需要 TTL** |
| 放进机制 | **cache-aside**：请求 → 查缓存 → miss 则调 API → 写缓存 → 返回 |
| 存储层级 | L1（DB，长期）+ L2（Redis，热数据） |
| 角色 | 加速层 + 离线兜底 |
| 失效策略 | TTL 过期 + 手动刷新 + 版本失效 |

```
请求(systematic_name)
   │
   ├─ L2 Redis 命中？ ──是──► 返回（~1ms）
   │     │否
   │     ▼
   ├─ L1 DB 命中且未过期？ ──是──► 回填 Redis + 返回
   │     │否
   │     ▼
   └─ 调外部 API（超时+重试+限速）
         │成功
         ▼
       写 L1 DB + L2 Redis + 返回
         │失败
         ▼
       L1 旧缓存兜底（即使过期，标记 stale）或降级
```

### 2.B 本地索引常驻（preload）—— BioProCorpus

**适用**：BioProCorpus 协议语料库（本地 JSON，~175MB）

| 维度 | 说明 |
|------|------|
| 数据位置 | 本地文件，静态快照 |
| 时效性 | 静态（重新下载才变）→ **不需要 TTL** |
| 放进机制 | **preload**：应用启动时构建索引一次 → 进程级单例常驻内存 |
| 当前问题 | `ProtocolRecommender.__init__` 每次 build() 重读全部 JSON；只有 `BioProCorpusLookup._retriever` 是类级单例，未推广 |
| 存储 | 进程内存（索引）+ Redis（检索结果，可选二次缓存） |
| 角色 | 索引常驻，避免每次请求重读大文件 |
| 失效策略 | 数据文件版本变更时重建（重启或手动触发） |

**关键区分**：BioProCorpus **不是缓存对象**——它本身就是数据源。要解决的是「索引不要每次重建」，而非「缓存原始响应」。索引是查询的结构化中间产物，应常驻。

### 2.C ~~批次导入落库（import）~~ —— 已撤销（jena 改归策略 B）

> **历史教训（2026-06-28 撤销）**：jena 曾被归为策略 C（批次导入落库），实现了 `jena_importer.py` + `import_jena_products` command 并落库 2098 条到 Product 表。该方向**已撤销**——jena 的最大价值是 systematic_name 锚点（撬动 Bioz 文献池），不在产品记录本身。研究员也不会从 jena 选择新建产品。代码已删除，2098 条已从 Product 表清除。
>
> **jena 正确归属是策略 B（本地索引常驻）**，与 BioProCorpus 同构。详见 §8。

### 2.D 两种本地数据策略对比（A 外部缓存 / B 本地索引常驻）

| 维度 | A 外部 API 缓存 | B 本地索引常驻 |
|------|----------------|---------------|
| 数据位置 | 外部 API | 本地文件 |
| 时效性 | 会变（需 TTL） | 静态快照 |
| 放进机制 | cache-aside | preload 单例 |
| 存储位置 | DB + Redis | 进程内存 + Redis(结果) |
| 角色 | 加速 + 兜底 | 索引常驻，AI AUTO MATCH 查询 |
| 落库成 Product 吗 | ❌ | ❌ |
| 失效方式 | TTL + 手动刷新 | 版本重建 |
| 适用数据源 | PubChem/PubMed/Bioz/ChEMBL | BioProCorpus · **jena** |

---

## 3. 分层架构（L0-L5）

```
┌─ L0 离线数据集（已有）─────────────────────────────────────────┐
│  jena jsonl（策略 B，AI AUTO MATCH 锚点源）· BioProCorpus 本地文件（策略 B）│
└────────────────────────────────────────────────────────────────┘
┌─ L1 持久化结果缓存（DB）──── 扩展 PubChemCache 为 DataSourceCache ┐
│  按源 + systematic_name 存原始 API 响应 · TTL 30天 · 可重建       │
│  PubChem 化学属性 · Bioz 文献池 · PubMed 元数据                  │
└────────────────────────────────────────────────────────────────┘
┌─ L2 内存缓存（Redis）─────────── 接已装的 django-redis ───────────┐
│  热数据短期缓存 · BioProCorpus 检索结果 · 限速窗口 · 熔断状态      │
└────────────────────────────────────────────────────────────────┘
┌─ L3 统一客户端 + 容错三件套 ───── 合并三套 PubChem 客户端 ────────┐
│  超时(必传) · 重试(tenacity 指数退避) · 限速(令牌桶)              │
└────────────────────────────────────────────────────────────────┘
┌─ L4 降级与兜底 ─────────────────────────────────────────────────┐
│  API 挂→L1 旧缓存兜底 · PubChem→ChEMBL · SDS 无 CAS→类别模板     │
└────────────────────────────────────────────────────────────────┘
┌─ L5 可观测 ─────────────────────────────────────────────────────┐
│  数据源健康端点 · 缓存命中率 · 错误率 · 限速状态                  │
└────────────────────────────────────────────────────────────────┘
```

---

## 4. 容错三件套（L3 核心）

### 4.1 超时（必传，消除挂死）

**现状致命缺口**：pubchempy 的 `urlopen` 无 timeout → 接口挂死。

**方案**：
- 自建客户端层**强制传 timeout**（PubChem 10s、ChEMBL 30s、PubMed 15s、Bioz 待测）
- 兜底：在 settings 配置全局 `socket.setdefaulttimeout(30)`，防止任何遗漏的裸调用挂死

### 4.2 重试（tenacity，针对瞬时故障）

**现状**：主代码零重试。

**方案**：用 `tenacity`（需加入主 `requirements.txt`），针对**瞬时故障**重试：
- 重试条件：网络异常、HTTP 429（限速）、503（ServerBusy）、504（GatewayTimeout）
- **不重试**：4xx（除 429）、空结果（非故障，走降级）
- 策略：指数退避（1s → 2s → 4s），最多 3 次
- 对 429/503：读取 `Retry-After` 头，按其值等待

### 4.3 限速（令牌桶，避免被封）

**现状**：只有 PubMed 实现了（`time.sleep` 阻塞式 0.35s）；PubChem 5 req/s 完全未实现。

**方案**：统一令牌桶限速器，按数据源配置：
- PubChem：5 req/s
- PubMed：3 req/s（无 Key）/ 10 req/s（有 Key）
- ChEMBL：保守 1-2 req/s（响应慢）
- Bioz：待实测后定

---

## 5. 缓存设计细节

### 5.1 缓存键统一用 systematic_name（与五数据源文档对齐）

```
缓存键 = (数据源, 查询类型, 标识符)
  主标识符优先级：systematic_name > CAS > product_name
```

**这和 `FIVE_DATASOURCES.md` 的「跨源锚点」完全统一**——查询层、缓存层、知识链层用同一个主键。一致性带来简单性。

### 5.2 TTL 按数据稳定性分级

| 数据 | 稳定性 | TTL |
|------|--------|-----|
| PubChem 化学属性 | 分子结构不变 | 30 天（可手动刷新） |
| Bioz 文献池 | 会增长 | 14 天 |
| PubMed 元数据 | 稳定 | 14 天 |
| ChEMBL 属性 | 稳定 | 30 天 |
| BioProCorpus 检索结果 | 依赖静态语料 | 7 天（L2 Redis） |

### 5.3 缓存 vs 落库边界（铁律）

| | 缓存（L1/L2） | 落库（Product/Reference） |
|---|---|---|
| 内容 | 原始 API 响应 | 研究员确认后的数据 |
| 可丢弃 | ✅ 可重建、可失效 | ❌ 不可丢 |
| 作用 | 加速 + 兜底 | 真实资产 |

**有缓存绝不意味着跳过人工确认**——呼应架构铁律「研究员是最终权威」。缓存只让「查」更快更稳，「存」仍需研究员拍板。

### 5.4 失效与刷新

- **TTL 自动过期**：按 §5.2 分级
- **手动刷新**：工作台提供「重新查询」按钮，强制 bypass 缓存
- **版本失效**：数据源 schema 变更时，management command 批量失效旧缓存
- **stale 兜底**：API 失败时，即使缓存过期也返回旧值，标记 `stale=True`

---

## 6. DataSourceCache 模型（L1 扩展）

扩展现有 `PubChemCache` 为通用 `DataSourceCache`：

| 字段 | 类型 | 说明 |
|------|------|------|
| `source` | CharField | 数据源标识：pubchem/chembl/pubmed/bioz |
| `query_key` | CharField | 查询键：systematic_name/CAS/product_name |
| `query_namespace` | CharField | 标识符类型：name/cas/smiles/inchi |
| `data_json` | TextField | 原始 API 响应 JSON |
| `fetched_at` | DateTimeField | 获取时间（用于 TTL 判断） |
| `expires_at` | DateTimeField | 过期时间（fetched_at + TTL） |
| `is_stale` | BooleanField | 是否为兜底返回的过期数据 |

**唯一性**：`(source, query_key, query_namespace)`
**索引**：`(source, query_key)`、`expires_at`（便于批量清理）

**写入点**：L3 统一客户端成功获取后写入。
**读取点**：所有外部 API 调用前先查 L1。

---

## 7. BioProCorpus 索引策略（策略 B 展开）

### 7.1 当前问题

`ProtocolRecommender.__init__`（`protocol_recommender.py`）每次 `new` 都 `indexer.build()` → 重读全部 JSON（~175MB）到内存。仅 `BioProCorpusLookup._retriever`（`product_validator.py:114`）是类级单例，未推广到 `ProductEnrichView`/`ProductRecommendProtocolsView` 路径。

### 7.2 方案：进程级单例索引 + AppConfig.ready 预加载

**两层**：

1. **索引层（进程常驻）**：
   - 在 `KnowledgeConfig.ready()`（`apps/knowledge/apps.py`，当前无 ready 方法）中触发索引构建
   - 索引存为模块级单例，全进程共享
   - 应用启动构建一次，后续请求复用

2. **检索结果层（Redis 缓存，可选）**：
   - 按 `查询词 hash` 缓存 top-K 检索结果（TTL 7 天）
   - 语料静态，相同查询结果稳定

### 7.3 失效

- 数据文件版本变更（重新下载）→ management command 重建索引 + 清 Redis 检索缓存
- 重启进程自动重建（ready 钩子）

---

## 8. jena 索引策略（策略 B 展开，与 §7 BioProCorpus 同构）

> **2026-06-28 修正**：本节原为「jena 数据导入策略（策略 C）」，描述批次落库。该方向已撤销（见 §2.C 历史教训）。jena 改为策略 B——本地索引常驻，AI AUTO MATCH 运行时查询，**永不落库成 Product**。

### 8.1 jena 的核心价值定位

jena 数据的最大价值**不是产品规格**（那是副产品），而是 **systematic_name 锚点**——它是驱动 Bioz 文献检索的唯一可靠钥匙（CAS 查不了 Bioz，product_name 命中率低）。1 个 systematic_name 撬动 1 个跨厂家文献池。

### 8.2 索引构建与查询（仿 BioProCorpus）

```
jena_products_v2.jsonl（2098 条，离线，项目外工作区）
   │
   ├─① 启动时/首次访问构建索引（进程级单例 get_shared_jena_index）
   │     · 按 catalog_no / cas_number / systematic_name / product_name 建查询索引
   │     · 清洗：concentration 语义分类、application_tags 去截断前缀（查询时按需）
   │
   └─② AI AUTO MATCH 运行时查询
         · 输入：研究员提供的 CAS / product_name / catalog_no
         · 匹配 jena 索引 → 取 systematic_name（核心锚点）+ 规格副产品
         · systematic_name → 驱动 Bioz 文献检索（知识资产链启动）
         · 规格字段（purity/storage）→ 顺手预填 Product 空字段
```

### 8.3 jena 永不落库成 Product

**关键**：jena 数据**不进 Product 表**，不需要 TTL，不会自动失效。它是 AI AUTO MATCH 的查询输入，不是产品记录。研究员通过文档导入或手动新建产品时，AI AUTO MATCH 才查询 jena 索引；研究员不会从 jena 选择新建产品。

### 8.4 实现要点（待建）

- 新建 `apps/commerce/services/jena_index.py`，仿 `protocol_recommender.py` 的 `get_shared_retriever` 模式
- 数据路径：默认项目内 `backend/data/jena/`，`JENA_DATA_DIR` 环境变量可指向项目外工作区
- AppConfig.ready 钩子可选预热（`JENA_PRELOAD=1`），默认惰性
- AI AUTO MATCH（`ProductEnrichView`）接入 jena 索引查询（较大改造，单独 plan）

### 8.5 与 SDS 降级链的关系（保留）

jena 的 category_path 仍可在 AI AUTO MATCH 预填时填入 Product.category_l1，后续 SDS 生成可据此走类别模板降级（见 COA_SDS.md）。

---

## 9. 降级与兜底链（L4）

### 9.1 现有降级链（保留）

| 链 | 状态 |
|----|------|
| PubChem → ChEMBL（化学属性） | ✅ 已实现（`pubchem_enhancer.py:256`） |
| name → substance → token（PubChem 内部） | ✅ 已实现 |
| CAS → name → SMILES → InChI（多字段） | ✅ 已实现（`ai_views.py:243`） |
| PubMed ESummary 失败 → pmid stub | ✅ 已实现 |

### 9.2 待补降级

| 链 | 方案 |
|----|------|
| **API 挂 → L1 旧缓存兜底** | 缓存即离线兜底；即使过期，标记 stale 返回（优于报错） |
| **SDS 无 CAS → 类别模板** | jena category_path 100% 覆盖驱动（见 COA_SDS.md） |
| **PubChem 全失败 → 仅返回文献/协议** | AI AUTO MATCH 三路独立 try/except（已部分实现），确保部分可用 |
| **熔断器**（远期） | 某源连续失败 N 次 → 短路 M 分钟，直接走降级，避免雪崩 |

---

## 10. 可观测（L5）

| 指标 | 实现 |
|------|------|
| 数据源健康端点 | `/api/v1/health/datasources/` 返回各源最近成功率、平均延迟、是否熔断 |
| 缓存命中率 | L1/L2 命中率，按数据源分（埋点计数） |
| 错误率 | 各源 4xx/5xx/超时计数 |
| 限速状态 | 当前令牌桶余量、是否触发退避 |

---

## 11. 优先级落地路径

> **进度（2026-07-02）**：P0-①②②' 已完成（全局 socket 超时 + Redis 接入 + PubChemEnhancer cache-aside）。P1-④⑤⑥⑦ 已完成（L3 容错层 + L1 DataSourceCache + PubChem/PubMed/ChEMBL 接入 L3 + BioProCorpus AppConfig.ready 单例）。P2-⑧⑨′ 已完成（Bioz 结果缓存 + jena 索引服务接入 AUTO MATCH，见 `FIVE_DATASOURCES.md` §4.5/§4.6）。P0-③ 合并客户端延后。全量测试 1197 passed / 10 skipped / 0 failed。

| 优先级 | 动作 | 工作量 | 收益 | 状态 |
|--------|------|--------|------|:----:|
| **P0 止血** | ① pubchempy 全局 socket 超时（`socket.setdefaulttimeout`） | 极小 | 消除挂死，**最高优先** | ✅ |
| **P0 止血** | ② 接 Redis（已装未用）+ AI AUTO MATCH 的 PubChem 走 cache-aside | 中 | 立竿见影降延迟 | ✅ |
| **P0 止血** | ③ 合并三套 PubChem 客户端为统一 service（超时/限速/异常统一） | 中 | 消除三套不一致 | ⏸ 延后 |
| **P1 健壮性** | ④ tenacity 重试（429/503 指数退避）+ 主 requirements 声明 | 中 | 避免瞬时故障丢数据 | ✅ |
| **P1 健壮性** | ⑤ PubChem 5req/s 令牌桶限速 | 中 | 避免被限速封禁 | ✅ |
| **P1 健壮性** | ⑥ 扩展 PubChemCache → DataSourceCache，AI AUTO MATCH 复用 | 中 | 跨路径共享 L1 | ✅ |
| **P1 健壮性** | ⑦ BioProCorpus AppConfig.ready 单例索引（消除重读 175MB） | 中 | 降 CPU/内存 | ✅ |
| **P2 Bioz 接入时** | ⑧ Bioz 结果缓存（systematic_name 键，TTL 14 天） | 中 | 新源自带缓存 | ✅ |
| **P2** | ⑨ ~~jena 导入 command（策略 C）~~ 已撤销 | — | jena 改策略 B（本地索引） | ⊘ 撤销 |
| **P2** | ⑨′ jena 索引服务 + AI AUTO MATCH 接入（策略 B） | 大 | jena 锚点驱动 Bioz | ✅ |
| **P3 远期** | ⑩ 熔断器 + 定时预热 management command + 健康端点 | 大 | 极端情况兜底 + 可观测 | ⬜ |

---

## 12. 技术栈约束

| 约束 | 说明 |
|------|------|
| **无 Celery**（CLAUDE.md 否决） | 缓存填充用同步 cache-aside；预热用 management command + 系统定时任务（cron），不用 Celery beat |
| **Redis 已装未用** | `requirements.txt:29` 有 django-redis，接上即用，无需新依赖 |
| **tenacity/backoff 需声明** | 当前仅子项目 bioprocorpus 有；主 requirements 需显式加入 tenacity |
| **requests 需显式声明** | 当前靠 pubchempy 间接安装（隐式依赖），需 pin 版本 |
| **研究员是最终权威** | 缓存不替代人工确认；所有落库仍需研究员审核 |

---

## 13. 配套文档

| 文档 | 关系 |
|------|------|
| `docs/FIVE_DATASOURCES.md` | 数据源定义（上游）：本文档的缓存对象定义于此 |
| `docs/AI_AUTO_MATCH.md` | AI AUTO MATCH 功能：本文档 P0 止血的主要改造对象 |
| `docs/COA_SDS.md` | COA/SDS：SDS 降级链（本文档 §9.2）的数据依赖 |
| `docs/jena_scraper_spec.md` | jena 数据规格：本文档 §8 索引策略的输入 |
| `CLAUDE.md` | 架构铁律、技术栈锁定 |

---

## 附录：现状引用清单

| 现状 | 引用 |
|------|------|
| PubChemCache 模型 | `documents/models.py:166-184` |
| PubChemCache 唯一读写（仅 SDS） | `documents/services/workflow.py:127-143` |
| 无 CACHES 配置 | `config/settings/base.py`（全文）、development.py、production.py |
| django-redis 未接线 | `requirements.txt:29`（有依赖，无配置） |
| AI AUTO MATCH 即查即弃 | `pubchem_enhancer.py:205`、`literature_recommender.py`、`protocol_recommender.py` |
| pubchempy 无超时 | `venv/.../pubchempy.py:380` |
| 三套 PubChem 客户端 | `pubchem_fetcher.py:68`、`product_validator.py:52,59,80`、`pubchem_enhancer.py` |
| ChEMBL fallback | `pubchem_enhancer.py:318,334,256` |
| PubMed 限速（唯一） | `pubmed_client.py:24-30` |
| BioProCorpus 每次重 build | `protocol_recommender.py:81-85,222-224` |
| BioProCorpus 单例（未推广） | `product_validator.py:114-120` |
| 各 AppConfig 无 ready | `apps/*/apps.py`（均无 ready 方法） |
| 主 requirements 缺 tenacity/requests | `backend/requirements.txt` |

---

*文档日期：2026-06-28 | 基于代码核查现状 | 数据源生产可靠性的设计与实施依据*
