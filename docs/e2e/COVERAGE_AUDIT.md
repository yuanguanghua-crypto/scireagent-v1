# 全站 7 维覆盖审计（自动 · V1）

> 由 `scripts/audit_7d_auto.py` 生成。**跑一次就算清 263 格**，不用逐页人工。
> ⚠️ 自动判定 = 「该页在该矩阵 spec 的清单里」，**不证明断言充分**。
> **I 维（交互）无法自动判**，留 `☐` 交人工 —— 那才是真正要一页页看的。

## 数据源

| 维 | 依据文件 | 覆盖页面数 |
|---|---|---|
| P 权限 | `permission-matrix.spec.cjs`（3 数组） | **28** |
| S 状态 | `state-matrix.spec.cjs` | 0 |
| R 响应式 | `responsive.spec.cjs` | **11** |
| V 视觉 | `visual-tokens.spec.cjs` | 5 |
| A 可访问 | `a11y.spec.cjs` | 5 |
| B 浏览器 | `package.json` npm script | **只 chromium** |
| I 交互 | — | **不可自动判** |

## 逐页审计

| # | 路由 | 页面 | 优先级 | I | P | S | R | V | A | B | 已覆盖 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `/` | HomePage | P0 | ☐ | — | — | ✓ | ✓ | ✓ | ✗ | **3/7** |
| 2 | `/login` | Login/Register | P0 | ☐ | ✓ | — | ✓ | ✗ | ✗ | ✗ | **2/7** |
| 3 | `/register` | Login/Register | P0 | ☐ | ✗ | — | ✓ | ✗ | ✗ | ✗ | **1/7** |
| 4 | `/search` | SearchPage | P0 | ☐ | — | — | ✓ | ✗ | ✗ | ✗ | **1/7** |
| 5 | `/applications` | AppIndex/Detail | P0 | ☐ | — | — | ✗ | ✗ | ✗ | ✗ | **0/7** |
| 6 | `/applications/:id` | AppIndex/Detail | P0 | ☐ | — | — | ✗ | ✗ | ✗ | ✗ | **0/7** |
| 7 | `/methods` | MethodIndex/Detail | P0 | ☐ | — | — | ✗ | ✗ | ✗ | ✗ | **0/7** |
| 8 | `/methods/:id` | MethodIndex/Detail | P0 | ☐ | — | — | ✗ | ✗ | ✗ | ✗ | **0/7** |
| 9 | `/protocols` | ProtocolIndex/Detail | P0 | ☐ | — | — | ✗ | ✗ | ✗ | ✗ | **0/7** |
| 10 | `/protocols/:id` | ProtocolIndex/Detail | P0 | ☐ | — | — | ✗ | ✗ | ✗ | ✗ | **0/7** |
| 11 | `/products` | ProductIndex/Detail | P0 | ☐ | — | ✗ | ✓ | ✓ | ✓ | ✗ | **3/7** |
| 12 | `/products/:id` | ProductIndex/Detail | P0 | ☐ | — | ✗ | ✓ | ✓ | ✓ | ✗ | **3/7** |
| 13 | `/research-goals` | RGIndex/Detail | P0 | ☐ | — | — | ✗ | ✗ | ✗ | ✗ | **0/7** |
| 14 | `/research-goals/:id` | RGIndex/Detail | P0 | ☐ | — | — | ✗ | ✗ | ✗ | ✗ | **0/7** |
| 15 | `/quote-request` | QuoteRequestPage | P1 | ☐ | — | — | ✓ | ✗ | ✗ | ✗ | **1/7** |
| 16 | `/cart` | CartPage | P1 | ☐ | — | — | ✗ | ✗ | ✗ | ✗ | **0/7** |
| 17 | `/:pathMatch` | NotFound | P0 | ☐ | — | — | ✓ | ✓ | ✓ | ✗ | **3/7** |
| 18 | `/settings` | SettingsPage | P1 | ☐ | ✓ | — | ✗ | ✗ | ✗ | ✗ | **1/7** |
| 19 | `/checkout` | CheckoutPage | P1 | ☐ | ✓ | — | ✗ | ✗ | ✗ | ✗ | **1/7** |
| 20 | `/orders` | OrderList/Detail | P1 | ☐ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | **1/7** |
| 21 | `/orders/:id` | OrderList/Detail | P1 | ☐ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | **1/7** |
| 22 | `/po/submit` | PoSubmit | P1 | ☐ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | **1/7** |
| 23 | `/po/orders` | PoOrderList/Detail | P1 | ☐ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | **1/7** |
| 24 | `/po/:id` | PoOrderList/Detail | P1 | ☐ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | **1/7** |
| 25 | `/po/addresses` | PoAddressList | P1 | ☐ | ✓ | — | ✗ | ✗ | ✗ | ✗ | **1/7** |
| 26 | `/po/reorder` | PoReorder | P2 | ☐ | ✓ | — | ✗ | ✗ | ✗ | ✗ | **1/7** |
| 27 | `/po/downloads` | PoDownloadCenter | P2 | ☐ | ✓ | — | ✗ | ✗ | ✗ | ✗ | **1/7** |
| 28 | `/workspace` | DashboardPage | P1 | ☐ | ✓ | — | ✓ | ✓ | ✓ | ✗ | **4/7** |
| 29 | `/workspace/products` | ProductsPage | P1 | ☐ | ✓ | — | ✓ | ✗ | ✗ | ✗ | **2/7** |
| 30 | `/workspace/products/new` | ProductEditPage | P0 | ☐ | ✓ | ✗ | ✓ | ✗ | ✗ | ✗ | **2/7** |
| 31 | `/workspace/products/:id/edit` | ProductEditPage | P0 | ☐ | ✓ | ✗ | ✓ | ✗ | ✗ | ✗ | **2/7** |
| 32 | `/workspace/goals` | 各管理页 | P1 | ☐ | ✓ | — | ✗ | ✗ | ✗ | ✗ | **1/7** |
| 33 | `/applications` | 各管理页 | P1 | ☐ | ✗ | — | ✗ | ✗ | ✗ | ✗ | **0/7** |
| 34 | `/methods` | 各管理页 | P1 | ☐ | ✗ | — | ✗ | ✗ | ✗ | ✗ | **0/7** |
| 35 | `/protocols` | 各管理页 | P1 | ☐ | ✗ | — | ✗ | ✗ | ✗ | ✗ | **0/7** |
| 36 | `/references` | 各管理页 | P1 | ☐ | ✗ | — | ✗ | ✗ | ✗ | ✗ | **0/7** |
| 37 | `/workspace/knowledge-intake` | KnowledgeIntake | P1 | ☐ | ✓ | — | ✗ | ✗ | ✗ | ✗ | **1/7** |
| 38 | `/admin/orders` | AdminOrders/Detail | P1 | ☐ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **0/7** |
| 39 | `/admin/:id` | AdminOrders/Detail | P1 | ☐ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **0/7** |
| 40 | `/admin/po/review` | PoReviewDesk | P1 | ☐ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **0/7** |
| 41 | `/admin/po/shipments` | PoShipmentDesk | P1 | ☐ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **0/7** |
| 42 | `/admin/po/invoicing` | PoInvoicingDesk | P1 | ☐ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | **0/7** |
| 43 | `/admin/po/ar` | PoArReport | P2 | ☐ | ✗ | — | ✗ | ✗ | ✗ | ✗ | **0/7** |
| 44 | `/admin/po/organizations` | PoOrgManagement | P2 | ☐ | ✗ | — | ✗ | ✗ | ✗ | ✗ | **0/7** |

## 汇总（按维）

| 维 | ✓ 覆盖 | ✗ 缺 | ☐ 待人工 | 覆盖率 |
|---|---|---|---|---|
| I | 0 | 0 | 44 | **—** |
| P | 17 | 12 | 0 | **59%** |
| S | 0 | 14 | 0 | **0%** |
| R | 12 | 32 | 0 | **27%** |
| V | 5 | 39 | 0 | **11%** |
| A | 5 | 39 | 0 | **11%** |
| B | 0 | 44 | 0 | **0%** |

**总计**：✓ 39 格 / ✗ 180 格 / 待人工 44 格（共 263 格）

## 怎么读这份审计

1. **先看汇总表的覆盖率** —— 哪一维最空，先补哪一维
2. **再看逐页表的 `已覆盖 n/7`** —— 从 0/7 的页面开始
3. **I 维（☐）必须人工判** —— 打开 FULL_SITE §2.2 看该页要求哪些交互，逐个 grep spec

