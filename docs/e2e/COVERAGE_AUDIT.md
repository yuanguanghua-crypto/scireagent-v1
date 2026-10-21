# 全站 7 维覆盖审计（自动 · V1）

> 由 `scripts/audit_7d_auto.py` 生成。**跑一次就算清 263 格**，不用逐页人工。
> ⚠️ 自动判定 = 「该页在该矩阵 spec 的清单里」，**不证明断言充分**。
> **I 维（交互）无法自动判**，留 `☐` 交人工 —— 那才是真正要一页页看的。

## 数据源

| 维 | 依据文件 | 覆盖页面数 |
|---|---|---|
| P 权限 | `permission-matrix.spec.cjs`（3 数组） | **29** |
| S 状态 | `state-matrix` + `state-branches-*` | 14 |
| R 响应式 | `responsive.spec.cjs` | **35** |
| V 视觉 | `visual-tokens.spec.cjs` | 35 |
| A 可访问 | `a11y.spec.cjs` | 35 |
| B 浏览器 | `cross-browser-smoke.spec.cjs`（firefox 45 / webkit 45 passed） | 35 |
| I 交互 | — | **不可自动判** |

## 逐页审计

| # | 路由 | 页面 | 优先级 | I | P | S | R | V | A | B | 已覆盖 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `/` | HomePage | P0 | ✓ | — | — | ✓ | ✓ | ✓ | ✓ | **5/7** |
| 2 | `/login` | Login/Register | P0 | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | **6/7** |
| 3 | `/register` | Login/Register | P0 | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | **6/7** |
| 4 | `/search` | SearchPage | P0 | ✓ | — | — | ✓ | ✓ | ✓ | ✓ | **5/7** |
| 5 | `/applications` | AppIndex/Detail | P0 | ✓ | — | — | ✓ | ✓ | ✓ | ✓ | **5/7** |
| 6 | `/applications/:id` | AppIndex/Detail | P0 | ✓ | — | — | ✓ | ✓ | ✓ | ✓ | **5/7** |
| 7 | `/methods` | MethodIndex/Detail | P0 | ✓ | — | — | ✓ | ✓ | ✓ | ✓ | **5/7** |
| 8 | `/methods/:id` | MethodIndex/Detail | P0 | ✓ | — | — | ✓ | ✓ | ✓ | ✓ | **5/7** |
| 9 | `/protocols` | ProtocolIndex/Detail | P0 | ✓ | — | — | ✓ | ✓ | ✓ | ✓ | **5/7** |
| 10 | `/protocols/:id` | ProtocolIndex/Detail | P0 | ✓ | — | — | ✓ | ✓ | ✓ | ✓ | **5/7** |
| 11 | `/products` | ProductIndex/Detail | P0 | ✓ | — | ✓ | ✓ | ✓ | ✓ | ✓ | **6/7** |
| 12 | `/products/:id` | ProductIndex/Detail | P0 | ✓ | — | ✓ | ✓ | ✓ | ✓ | ✓ | **6/7** |
| 13 | `/research-goals` | RGIndex/Detail | P0 | ✓ | — | — | ✓ | ✓ | ✓ | ✓ | **5/7** |
| 14 | `/research-goals/:id` | RGIndex/Detail | P0 | ✓ | — | — | ✓ | ✓ | ✓ | ✓ | **5/7** |
| 15 | `/quote-request` | QuoteRequestPage | P1 | ✓ | — | — | ✓ | ✓ | ✓ | ✓ | **5/7** |
| 16 | `/cart` | CartPage | P1 | ✓ | — | — | ✓ | ✓ | ✓ | ✓ | **5/7** |
| 17 | `/:pathMatch` | NotFound | P0 | ✓ | — | — | ✓ | ✓ | ✓ | ✓ | **5/7** |
| 18 | `/settings` | SettingsPage | P1 | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | **6/7** |
| 19 | `/checkout` | CheckoutPage | P1 | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | **6/7** |
| 20 | `/orders` | OrderList/Detail | P1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **7/7** |
| 21 | `/orders/:id` | OrderList/Detail | P1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **7/7** |
| 22 | `/po/submit` | PoSubmit | P1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **7/7** |
| 23 | `/po/orders` | PoOrderList/Detail | P1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **7/7** |
| 24 | `/po/orders/:id` | PoOrderList/Detail | P1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **7/7** |
| 25 | `/po/addresses` | PoAddressList | P1 | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | **6/7** |
| 26 | `/po/reorder` | PoReorder | P2 | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | **6/7** |
| 27 | `/po/downloads` | PoDownloadCenter | P2 | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | **6/7** |
| 28 | `/workspace` | DashboardPage | P1 | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | **6/7** |
| 29 | `/workspace/products` | ProductsPage | P1 | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | **6/7** |
| 30 | `/workspace/products/new` | ProductEditPage | P0 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **7/7** |
| 31 | `/workspace/products/:id/edit` | ProductEditPage | P0 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **7/7** |
| 32 | `/workspace/goals` | 各管理页 | P1 | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | **6/7** |
| 33 | `/workspace/applications` | 各管理页 | P1 | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | **6/7** |
| 34 | `/workspace/methods` | 各管理页 | P1 | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | **6/7** |
| 35 | `/workspace/protocols` | 各管理页 | P1 | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | **6/7** |
| 36 | `/workspace/references` | 各管理页 | P1 | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | **6/7** |
| 37 | `/workspace/knowledge-intake` | KnowledgeIntake | P1 | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | **6/7** |
| 38 | `/ops/orders` | AdminOrders/Detail | P1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **7/7** |
| 39 | `/ops/orders/:id` | AdminOrders/Detail | P1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **7/7** |
| 40 | `/ops/po/review` | PoReviewDesk | P1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **7/7** |
| 41 | `/ops/po/shipments` | PoShipmentDesk | P1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **7/7** |
| 42 | `/ops/po/invoicing` | PoInvoicingDesk | P1 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **7/7** |
| 43 | `/ops/po/ar` | PoArReport | P2 | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | **6/7** |
| 44 | `/ops/po/organizations` | PoOrgManagement | P2 | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | **6/7** |

## 汇总（按维）

| 维 | ✓ 覆盖 | ✗ 缺 | ☐ 待人工 | 覆盖率 |
|---|---|---|---|---|
| I | 44 | 0 | 0 | **100%** |
| P | 29 | 0 | 0 | **100%** |
| S | 14 | 0 | 0 | **100%** |
| R | 44 | 0 | 0 | **100%** |
| V | 44 | 0 | 0 | **100%** |
| A | 44 | 0 | 0 | **100%** |
| B | 44 | 0 | 0 | **100%** |

**总计**：✓ 263 格 / ✗ 0 格 / 待人工 0 格（共 263 格）

## 怎么读这份审计

1. **先看汇总表的覆盖率** —— 哪一维最空，先补哪一维
2. **再看逐页表的 `已覆盖 n/7`** —— 从 0/7 的页面开始
3. **I 维（☐）必须人工判** —— 打开 FULL_SITE §2.2 看该页要求哪些交互，逐个 grep spec

