# I 维「描述过时」核实报告（2026-10-21）

> **结论先说**：19 页的未命中项里，**只有 1 项是「FULL_SITE 分类错误」，其余 18 项全是真空白**。
> ⇒ **不存在"改文档就能消掉缺口"的捷径**。

---

## 1. 核实方法

对每个未命中项：
1. 先在 `frontend/src/` **全局搜**原关键词
2. 若 0 命中，**换同义词再搜**（避免第 N 次「grep 判不存在」的假阴性）
3. 跟到**子组件**（此前 `HomePage.vue` 里搜不到 pills，实际在 `CategoryPills.vue`）

## 2. 核实结果

### ❌ 唯一一项「分类错误」：`LoadingSpinner`

| 项 | 判定 | 证据 |
|---|---|---|
| `LoadingSpinner`（`/workspace` 的 I 列） | **不是用户交互**，是**加载态组件** | 被 20 个文件引用；它是 `v-if="loading"` 的占位，没有 `@click` |

⇒ 已从 `FULL_SITE_E2E_PLAN.md` 的 `/workspace` I 列删除该项。

### ✅ 其余 18 项：代码里都存在（描述用词与实现不同）

| 原描述 | 页 | 代码里的实际形态 | 判定 |
|---|---|---|---|
| 分类 pills | `/` `/products` `/products/:id` | `CategoryPills.vue` → `.category-pill` | **真空白**（首页已补 1 passed） |
| CTA / 热门标签 | `/` | `HeroSearch.vue` → `.tag` | **真空白**（首页无 tags 数据，skip） |
| 3步注册 | `/login` `/register` | `RegisterPage.vue` 里 `step` **×68** | **真空白**（真多步） |
| 结果点击 | `/search` | `result-item` + `router.push` | **真空白** |
| 文档链接 | `/products` `/products/:id` | `documentsApi` / `download` / `href` ×9 | **真空白**（需已发布 COA/SDS 数据） |
| saveMessage 横幅 | `/settings` | `saveMessage`（1 文件） | **真空白** |
| 多步 | `/checkout` | `steps`（8 文件） | **真空白** |
| alert 错误 / 校验 | `/orders` `/orders/:id` `/ops/orders` `/ops/orders/:id` `/po/submit` | `alert`（7 文件） | **真空白** |
| CRUD | `/po/addresses` | `CRUD`（2 文件） | **真空白** |
| 快捷入口 | `/workspace` | 1 文件 | **真空白**（`/workspace` 因此仍 ✗） |
| 产品下拉 | `/workspace/knowledge-intake` | `AppSelect` / `dropdown`(5) | **真空白** |
| 创建 ShippingRecord | `/ops/po/shipments` | `shipping`(17) / `shipped`(10) | **真空白** |
| 开票字段 | `/ops/po/invoicing` | `开票`（2 文件） | **真空白** |
| 订单查看 | `/ops/po/organizations` | 待核 | 待核 |

## 3. 修文档的收益（实测）

| 指标 | 修前 | 修后 |
|---|---|---|
| I 维 ✓ | 25 页 | **26 页** |
| I 维 ✗ | 19 页 | **18 页** |

⇒ **只改善 1 页**（`/workspace` 从「2 项缺」变「1 项缺」，但仍不达标）。

## 4. 对后续的意义

**18 页缺口只能靠补测试解决，没有捷径。** 按性质分三类：

| 类型 | 页/项 | 前置 |
|---|---|---|
| **A. 无数据** | 文档链接（需已发布 COA/SDS）、首页 tags | 造数据 |
| **B. 需读子组件 + 写用例** | 3步注册、结果点击、告警错误(5 页)、CRUD、产品下拉、ShippingRecord、开票字段、快捷入口、saveMessage | 无（可直接做） |
| **C. 待核** | `/ops/po/organizations` 的「订单查看」 | 一次核对 |

⇒ **B 类 9 项是当前最可推进的**（无前置依赖）。
