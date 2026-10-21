# 迁移演练台账（migration drill ledger）

> **由 `scripts/migration_ledger.py` 自动生成，勿手改。** 重跑即重写。
> 演练器：`scripts/migration_drill.py`（在**独立临时 sqlite** 上跑，绝不碰项目 DB）。

## 0. 本次模式

> ✅ 本次是**完整演练**：每个 app 都在独立临时 sqlite 上跑了正向 → 造数 → 应用 → 幂等重放 → 反向回滚。

## 1. 结论

- 覆盖：**10 个 app / 74 个迁移**
- 迁移链路：**10/10 个 app 通过**（正向 → 应用 → 幂等重放 → 反向回滚）
- 存量数据覆盖：**5/10 个 app** 真的造出了存量数据；其余是**空库迁移**（链路有效，但不证明"有数据时也能迁"）
- 总耗时：113.4s（含每个 app 的实例创建/迁移/回滚）
- 生成时间：2026-10-21 15:20:44

## 2. 粒度与边界（读这张表前必看）

| 项 | 说明 |
|---|---|
| 粒度 | **一个 app 一行**：drill 会把该 app 的**全部迁移**跑完整链路（正向 → 造存量数据 → 应用 → 幂等重放 → 反向回滚）⇒ 74 个迁移都在这 10 条链路里 |
| **不是**什么 | **不是**"逐个迁移单独回滚"（那要 74×4 次实例创建，成本极高、收益低） |
| 造数覆盖 | **只有 documents / commerce / transactions** 造了"贴近生产形态"的存量数据；其余 app 的 seed 是空的 ⇒ 那些 app 的演练实际是**空库迁移**（表里"造数"列会标明） |
| 环境差异 | 独立**临时 sqlite**，与生产 PostgreSQL 有差异（如 `select_for_update` 在 sqlite 上是 no-op）⇒ 拦的是"迁移图/跨 app 依赖/可逆性"，**不替代生产演练** |

## 3. 逐 app 结果

| # | app | 迁移数 | 最新节点 | 迁移链路 | 存量数据 | 耗时 |
|---|---|---|---|---|---|---|
| 1 | `accounts` | 7 | `0007_organization_tax_exempt_id` | ✅ 正向/幂等/反向 均通过 | ⚠️ 空库（此刻迁移图里没有 commerce/documents） | 12.1s |
| 2 | `assets` | 1 | `0001_initial` | ✅ 正向/幂等/反向 均通过 | ⚠️ 空库（目标是首个迁移（无存量 schema）⇒ 不适用，跳过造数） | 8.4s |
| 3 | `bridges` | 7 | `0007_verified_draft_and_rejected` | ✅ 正向/幂等/反向 均通过 | ✅ 有存量数据：Product 4 / SdsRevision 8 / current_sds 已设 4（另有跳过：此刻 transactions 尚未纳入迁移图） | 12.9s |
| 4 | `commerce` | 15 | `0015_sku_export_controlled_sku_hs_code` | ✅ 正向/幂等/反向 均通过 | ✅ 有存量数据：Product 4 / SdsRevision 8 / current_sds 已设 4（另有跳过：此刻 transactions 尚未纳入迁移图） | 12.3s |
| 5 | `documents` | 6 | `0006_sdsrevision_status` | ✅ 正向/幂等/反向 均通过 | ✅ 有存量数据：Product 4 / SdsRevision 8 / current_sds 已设 0（此刻 commerce 尚未引入该字段，属正常）（另有跳过：此刻 transactions 尚未纳入迁移图） | 12.1s |
| 6 | `inventory` | 5 | `0005_inventory_ck_inv_available_nonneg_and_more` | ✅ 正向/幂等/反向 均通过 | ✅ 有存量数据：Product 4 / SdsRevision 8 / current_sds 已设 4 / Order 序号版 3 + uuid 版 3 | 13.3s |
| 7 | `knowledge` | 22 | `0022_search_trgm_indexes` | ✅ 正向/幂等/反向 均通过 | ⚠️ 空库（此刻迁移图里没有 commerce/documents） | 12.2s |
| 8 | `notifications` | 1 | `0001_initial` | ✅ 正向/幂等/反向 均通过 | ⚠️ 空库（目标是首个迁移（无存量 schema）⇒ 不适用，跳过造数） | 8.6s |
| 9 | `quotes` | 1 | `0001_initial` | ✅ 正向/幂等/反向 均通过 | ⚠️ 空库（目标是首个迁移（无存量 schema）⇒ 不适用，跳过造数） | 8.8s |
| 10 | `transactions` | 9 | `0009_ordersequence` | ✅ 正向/幂等/反向 均通过 | ✅ 有存量数据：Order 序号版 3 + uuid 版 3（另有跳过：此刻迁移图里没有 commerce/documents） | 12.7s |

## 4. 怎么复现 / 加新 app

```bash
python scripts/migration_ledger.py                # 全量重跑并重写本台账
python scripts/migration_ledger.py --audit-only   # 只做静态依赖审计（秒级）
python scripts/migration_drill.py --app documents --target 0006   # 单点复现
```

新增 app 不需要改本脚本（它扫 `backend/**/migrations/0*.py` 自动发现）；
但**建议同时给它的迁移补 seed**（在 `migration_drill.py` 的 SEED_SCRIPT 里），
否则该 app 的演练只是"空库能迁"，证明力有限。
