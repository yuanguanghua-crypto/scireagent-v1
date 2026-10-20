# 页面映射清单（供批量扩容 R/A/V）

| # | 路由 | 组件 | 根class | 组 | 优先级 | 可直接加? |
|---|---|---|---|---|---|---|
| 1 | `/` | HomePage.vue | home | PUBLIC | P0 | ✅ |
| 2 | `/login` | LoginPage.vue | auth-page | PUBLIC | P0 | ✅ |
| 3 | `/register` | RegisterPage.vue | auth-page | PUBLIC | P0 | ✅ |
| 4 | `/search` | SearchPage.vue | search-page | PUBLIC | P0 | ✅ |
| 5 | `/applications` | ApplicationIndex.vue | application-index | PUBLIC | P0 | ✅ |
| 6 | `/applications/:id` | ApplicationDetail.vue | detail-page | PUBLIC | P0 | ❌ 需 fixture |
| 7 | `/methods` | MethodIndex.vue | method-index | PUBLIC | P0 | ✅ |
| 8 | `/methods/:id` | MethodDetail.vue | detail-page | PUBLIC | P0 | ❌ 需 fixture |
| 9 | `/protocols` | ProtocolIndex.vue | protocol-index | PUBLIC | P0 | ✅ |
| 10 | `/protocols/:id` | ProtocolDetail.vue | protocol-detail | PUBLIC | P0 | ❌ 需 fixture |
| 11 | `/products` | ProductIndex.vue | product-index | PUBLIC | P0 | ✅ |
| 12 | `/products/:id` | ProductDetail.vue | pd | PUBLIC | P0 | ❌ 需 fixture |
| 13 | `/research-goals` | ResearchGoalIndex.vue | research-goal-index | PUBLIC | P0 | ✅ |
| 14 | `/research-goals/:id` | ResearchGoalDetail.vue | research-goal-detail | PUBLIC | P0 | ❌ 需 fixture |
| 15 | `/quote-request` | QuoteRequestPage.vue | rfq-page | PUBLIC | P1 | ✅ |
| 16 | `/cart` | CartPage.vue | cart-page | PUBLIC | P1 | ✅ |
| 17 | `/:pathMatch` | ? | ? | PUBLIC | P0 | ❌ 需 fixture |
| 18 | `/settings` | SettingsPage.vue | settings-page | AUTH | P1 | ✅ |
| 19 | `/checkout` | CheckoutPage.vue | checkout-page | AUTH | P1 | ✅ |
| 20 | `/orders` | OrderListPage.vue | order-list-page | AUTH | P1 | ✅ |
| 21 | `/orders/:id` | OrderDetailPage.vue | order-detail-page | PUBLIC | P1 | ❌ 需 fixture |
| 22 | `/po/submit` | po/PoSubmit.vue | po-page | AUTH | P1 | ✅ |
| 23 | `/po/orders` | po/PoOrderList.vue | po-page | AUTH | P1 | ✅ |
| 24 | `/po/orders/:id` | po/PoOrderDetail.vue | po-page | AUTH | P1 | ❌ 需 fixture |
| 25 | `/po/addresses` | po/PoAddressList.vue | po-page | AUTH | P1 | ✅ |
| 26 | `/po/reorder` | po/PoReorder.vue | po-page | AUTH | P2 | ✅ |
| 27 | `/po/downloads` | po/PoDownloadCenter.vue | po-page | AUTH | P2 | ✅ |
| 28 | `/workspace` | workspace/AdminLayout.vue | workspace-layout | ADMIN | P1 | ✅ |
| 29 | `/workspace/products` | ? | ? | ADMIN | P1 | ⚠️ 无根class |
| 30 | `/workspace/products/new` | ? | ? | ADMIN | P0 | ⚠️ 无根class |
| 31 | `/workspace/products/new/:id/edit` | ? | ? | AUTH | P0 | ❌ 需 fixture |
| 32 | `/workspace/goals` | ? | ? | ADMIN | P1 | ⚠️ 无根class |
| 33 | `/applications` | ApplicationIndex.vue | application-index | PUBLIC | P1 | ✅ |
| 34 | `/methods` | MethodIndex.vue | method-index | PUBLIC | P1 | ✅ |
| 35 | `/protocols` | ProtocolIndex.vue | protocol-index | PUBLIC | P1 | ✅ |
| 36 | `/workspace/references` | ? | ? | ADMIN | P1 | ⚠️ 无根class |
| 37 | `/workspace/knowledge-intake` | ? | ? | ADMIN | P1 | ⚠️ 无根class |
| 38 | `/ops/orders` | admin/AdminOrdersPage.vue | admin-orders-page | ADMIN | P1 | ✅ |
| 39 | `/ops/orders/:id` | admin/AdminOrderDetail.vue | admin-order-detail | ADMIN | P1 | ❌ 需 fixture |
| 40 | `/ops/po/review` | admin/PoReviewDesk.vue | po-page | ADMIN | P1 | ✅ |
| 41 | `/ops/po/shipments` | admin/PoShipmentDesk.vue | po-page | ADMIN | P1 | ✅ |
| 42 | `/ops/po/invoicing` | admin/PoInvoicingDesk.vue | po-page | ADMIN | P1 | ✅ |
| 43 | `/ops/po/ar` | admin/PoArReport.vue | po-page | ADMIN | P2 | ✅ |
| 44 | `/ops/po/organizations` | admin/PoOrgManagement.vue | po-page | ADMIN | P2 | ✅ |

## 统计

| 项 | 数 |
|---|---|
| 可直接加 ✅ | **29** |
| 需 fixture（:id）❌ | 10 |
| 无根 class ⚠️ | 5 |

## 分组分布

- **PUBLIC**：14 页可加
- **AUTH**：8 页可加
- **ADMIN**：12 页可加
