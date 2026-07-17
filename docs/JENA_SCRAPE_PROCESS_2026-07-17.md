# Jena 数据爬虫生成过程记录（2026-07-17）

> 本文件记录**本次（2026-07-17）Jena Bioscience 全量爬虫从启动到上线部署的完整过程**，
> 供后续复盘与技能复用。爬虫脚本与可复用方法论见技能 `jena-scraper`（用户级技能）。
>
> 核心命题：爬虫的**唯一目的** = 为 **AI AUTO MATCH** 提供「可信、未变形」的 jena 身份数据
> （`catalog_no` / `cas` / `product_name` / `category_path`），使匹配准确可用。
> jena 数据永不落库成 Product（策略 B，本地索引常驻）。

---

## 1. 为什么全量重爬

旧数据源 `jena_products_v2.jsonl`（2098 条）是 2026-06-28 由策略 C（批次落库遗留）清出的，
经 2026-07-16 Phase 1~4 污染测绘发现**只满足「有值」不满足「值正确」**：

| 问题 | 实测 | 影响 |
|------|------|------|
| 身份字段污染 | 仅 91% 干净，9% 污染（catalog 与其它字段粘连 173 条等） | `catalog_no` 是 Bioz 硬锚点，污染即击穿整条 Bioz 链路 |
| 规格字段误抓 | 高覆盖率大量来自 scraper_v3.py 全页 fallback 正则误抓 | 值不可信 |
| name 歧义错配 | 双向子串匹配歧义率 43%（如 ATP→2'MeSe-ATP） | AUTO MATCH 用错 jena 记录 |

→ 结论：**需按根因（R1~R6）重爬**产出干净数据集。原则：字段和值只有正确才有价值，数据量本身没有价值。

---

## 2. 全量爬取过程（含多次静默死与自愈）

### 2.1 第一次全量（静默死 + 数据损坏）

- 启动 `scraper_v3.py` 五阶段全量。
- 现象：scrape 阶段后**进程静默死**；中间 SQLite DB 丢失；jsonl 未去重（4503 行 → 唯一 1322，且 schema 含应剔除的化学字段）。
- 处置：将损坏产物 `mv` 为 `*.BROKEN_unreassembled` 隔离，不污染后续。

### 2.2 第二次全量（建 venv + 持久化 DB）

- 在 `Desktop/jena_scraper` 建独立 venv（`requests 2.34.2` / `bs4 4.15.0` / `lxml`）。
- 关键修正：**DB 持久化**到 `v3/jena_v3.db`（`JENA_DB_PATH`），避免进程死即丢数据。
- 现象：再次**静默死**在 `discover → find-products` 交界处（discover 找到 4748 个 product URL）。

### 2.3 自愈续跑（resume_crawl.py）

- 写 `v3/resume_crawl.py` 断点续跑器：从持久化 DB 续跑 `find-products → scrape → applications → export`，
  幂等、复位卡在 `scraping` 的行、完成打印 `RESUME_WRAPPER_DONE`。
- 配合两层自动化兜底（根除「用户每 10 分钟唤醒」）：
  - **实时监听**：后台 Bash 每 30s 探进程死/卡死/完成，立即通知。
  - **定时自动化巡检**（HOURLY）：读真实日志/产物心跳，完成自动跑校验闸门收尾。
- 续跑越过 scrape（落 **4501** 条产品）→ applications → export 去重 → **1318 唯一条**。

### 2.4 双闸门校验

- `validate_full.py`：① 身份差异（变形 0）；② 真实 `JenaIndex` AUTO MATCH（变形 0）。
- 旧 `PASS` 阈值 `len(full)>=5000` 不符实际（1318/1998），已弃用。
- 结果：新 1318 条身份干净、质量闸门全 PASS，但 **1318 < 旧 2098**（会丢 707 条合法旧产品）。

---

## 3. 合并决策（新 1318 + 旧合法缺失）

- 用户决策：**合并新旧**（优先保全集）。
- `merge_products.py`：以新 1318 为主；旧条目入选条件 = `jena_catalog_no` 合法（CAT_RE，允许 1–6 位）
  **且** `product_name` 不在新数据（即新爬虫漏抓的真实产品）。
- 以 `catalog_no` 唯一、新优先，排除 27 个冲突 → **合并 1998 条**（新 1318 + 旧合法缺失 680）。
- 备份新 1318 → `jena_products_v3_1318.jsonl`；合并产物 → `jena_products_merged.jsonl`。

---

## 4. Bioz 文献覆盖统计

- `bioz_coverage.py`：独立统计脚本，本地 JSON 缓存 + 断点续跑 + 1.1s 限速 + 指数退避重试。
- Bioz widget API 对 catalog_no 返回两形态：`records`（有文献详情）/ `citation_distribution`（仅引用证据）/ `null`（无）。
- 双口径结果一致：**485 / 1998 = 24.3%** 可取得文献证据，`failed = 0`。
- 盲点未发生时即收尾（不强制补齐）。

---

## 5. 部署上线（数据 + matcher 一起）

- 用户指令：「认可合并产物，覆盖生产源，部署到线上服务器」。
- 前置核查：git 不干净（发现 4 个 matcher 改动未提交——正是 AUTO MATCH 干净所依赖）；SSH 可达；docker 正常。
- 用户决策：**数据 + matcher 一起部署**（确保线上 AUTO MATCH 干净）。
- 执行：
  1. 本地备份旧源 → `jena_products_v2.jsonl.bak_20260717-183810`
  2. 覆盖生产源为 1998 条
  3. `git add` 5 文件（数据 + 4 个 matcher 文件，不含 verification/）
  4. `commit a2be677` → `tag v2026.07.19` → `push`
  5. 服务器 `git fetch` + `checkout -B prod v2026.07.19` + `docker compose up -d --build backend`
  6. 验证：`manage.py shell` 跑 `JenaIndex().build(); print(JenaIndex().size())` → **1998** ✅
- **四地一致**：本地 = GitHub = 服务器 prod = 线上索引，均为 1998 条。
- 巡检自动化置 PAUSED。

---

## 6. 关键数字速查

| 项 | 值 |
|----|----|
| 新全量去重 | 1318 |
| 合并产物 | 1998（新 1318 + 旧合法缺失 680） |
| 生产源（部署后） | 1998 |
| AUTO MATCH 变形 | 0 |
| Bioz 覆盖率 | 485 / 1998 = 24.3%（双口径一致） |
| 部署 commit / tag | a2be677 / v2026.07.19 |
| 服务器 | 47.82.156.48（admin），docker compose 三容器 |

---

## 7. 沉淀的可复用资产

| 资产 | 位置 |
|------|------|
| 爬虫技能（方法论 + 脚本） | 用户级技能 `jena-scraper` |
| 过程记录 | 本文件 |
| 五阶段爬虫 | `scraper_v3.py` |
| 续跑器 | `resume_crawl.py` |
| 合并脚本 | `merge_products.py` |
| 质量闸门 | `validate_full.py` |
| Bioz 覆盖统计 | `bioz_coverage.py` |
| 字段级清洗校验 | `verify_jena_products.py` |

*记录日期：2026-07-17*
