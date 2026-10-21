# I 维（交互）判定

> 由 `scripts/judge_interaction.py` 生成。
> **判定规则**：该页所有交互项都命中 ⇒ `✓`；任一未命中 ⇒ `✗`。
> ⚠️ `✓` 只表示「关键词全覆盖」，**不表示断言充分**；要确认强度须打开 spec 看 `expect`。
> **已做中英同义词扩展**（修正初版的假空白，如「分页」→ pagination）。

## `/` — HomePage ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 搜索 | ✓ | a11y.spec.cjs、applayout-navpad-check.spe… |
| 导航 | ✓ | cart-button-regression.spe、homepage.spec.cjs… |
| 分类 pills | ✓ | home-pills-cta.spec.cjs |
| CTA | ✓ | home-pills-cta.spec.cjs |

## `/login` — Login/Register ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 输入校验 | ✓ | api-permission-writes.spec、applayout-navpad-check.spe… |
| 提交 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 跳转 | ✓ | cart-button-regression.spe、cart-page-interactions.spe… |
| 3步注册 | ✓ | register-wizard.spec.cjs |

## `/register` — Login/Register ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 输入校验 | ✓ | api-permission-writes.spec、applayout-navpad-check.spe… |
| 提交 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 跳转 | ✓ | cart-button-regression.spe、cart-page-interactions.spe… |
| 3步注册 | ✓ | register-wizard.spec.cjs |

## `/search` — SearchPage ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 搜索输入 | ✓ | a11y.spec.cjs、applayout-navpad-check.spe… |
| 结果点击 | ✓ | search-result-docs.spec.cj |
| 空态 | ✓ | cart-page-interactions.spe、knowledge-intake.spec.cjs… |

## `/applications` — AppIndex/Detail ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 列表搜索 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 分页 | ✓ | product-list-fixes.spec.cj、workspace-entity-crud.spec |
| 详情关联跳转 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |

## `/applications/:id` — AppIndex/Detail ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 列表搜索 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 分页 | ✓ | product-list-fixes.spec.cj、workspace-entity-crud.spec |
| 详情关联跳转 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |

## `/methods` — MethodIndex/Detail ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 过滤 chips | ✓ | knowledge-intake.spec.cjs、product-edit-method-chip-n… |
| 分页 | ✓ | product-list-fixes.spec.cj、workspace-entity-crud.spec |
| 详情关联 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |

## `/methods/:id` — MethodIndex/Detail ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 过滤 chips | ✓ | knowledge-intake.spec.cjs、product-edit-method-chip-n… |
| 分页 | ✓ | product-list-fixes.spec.cj、workspace-entity-crud.spec |
| 详情关联 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |

## `/protocols` — ProtocolIndex/Detail ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 过滤 | ✓ | knowledge-intake.spec.cjs、workspace-entry-intake.spe |
| 分页 | ✓ | product-list-fixes.spec.cj、workspace-entity-crud.spec |
| 14列可排序表 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |

## `/protocols/:id` — ProtocolIndex/Detail ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 过滤 | ✓ | knowledge-intake.spec.cjs、workspace-entry-intake.spe |
| 分页 | ✓ | product-list-fixes.spec.cj、workspace-entity-crud.spec |
| 14列可排序表 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |

## `/products` — ProductIndex/Detail ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 分类 pills | ✓ | home-pills-cta.spec.cjs |
| Tab 切换 | ✓ | product-detail-verified-me、settings-save-banner.spec.… |
| Add to Cart | ✓ | a11y.spec.cjs、basket-local-merge-prune.s… |
| 数量± | ✓ | basket-local-merge-prune.s、basket-merge-over-limit.sp… |
| SKU 行 | ✓ | basket-local-merge-prune.s、basket-merge-over-limit.sp… |
| 文档链接 | ✓ | search-result-docs.spec.cj |

## `/products/:id` — ProductIndex/Detail ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 分类 pills | ✓ | home-pills-cta.spec.cjs |
| Tab 切换 | ✓ | product-detail-verified-me、settings-save-banner.spec.… |
| Add to Cart | ✓ | a11y.spec.cjs、basket-local-merge-prune.s… |
| 数量± | ✓ | basket-local-merge-prune.s、basket-merge-over-limit.sp… |
| SKU 行 | ✓ | basket-local-merge-prune.s、basket-merge-over-limit.sp… |
| 文档链接 | ✓ | search-result-docs.spec.cj |

## `/research-goals` — RGIndex/Detail ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 状态 el-select 筛选 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |

## `/research-goals/:id` — RGIndex/Detail ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 状态 el-select 筛选 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |

## `/quote-request` — QuoteRequestPage ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 多字段表单 | ✓ | basket-local-merge-prune.s、basket-merge-over-limit.sp… |
| 提交 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 成功横幅 | ✓ | basket-local-merge-prune.s、cascader-workflow.spec.cjs… |

## `/cart` — CartPage ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 数量改 | ✓ | basket-local-merge-prune.s、basket-merge-over-limit.sp… |
| 删除 | ✓ | api-permission-writes.spec、basket-local-merge-prune.s… |
| 提交审批 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 结算跳转 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| toast | ✓ | knowledge-intake.spec.cjs、order-error-paths.spec.cjs… |

## `/:pathMatch` — NotFound ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 返回首页跳转 | ✓ | cart-button-regression.spe、cart-page-interactions.spe… |

## `/settings` — SettingsPage ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 保存 | ✓ | cascader-workflow.spec.cjs、knowledge-intake.spec.cjs… |
| saveMessage 横幅 | ✓ | settings-save-banner.spec. |

## `/checkout` — CheckoutPage ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 多步 | ✓ | checkout-progressive-secti |
| v-loading | ✓ | order-error-paths.spec.cjs、product-detail-fields.spec… |
| 提交 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |

## `/orders` — OrderList/Detail ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 列表分页 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 详情时间线 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| alert 错误 | ✓ | order-error-paths.spec.cjs |

## `/orders/:id` — OrderList/Detail ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 列表分页 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 详情时间线 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| alert 错误 | ✓ | order-error-paths.spec.cjs |

## `/po/submit` — PoSubmit ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 行项目动态表单 | ✓ | basket-local-merge-prune.s、basket-merge-over-limit.sp… |
| 上传 | ✓ | product-edit-enrich-candid、product-new-ai-automatch.s… |
| alert 校验 | ✓ | order-error-paths.spec.cjs |
| 提交 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |

## `/po/orders` — PoOrderList/Detail ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 列表分页 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 详情时间线 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 发票 | ✓ | ops-po-desk-gaps.spec.cjs、po-prod-human.spec.cjs |
| 发货 | ✓ | ops-po-desk-gaps.spec.cjs、po-lifecycle.api.spec.cjs… |
| 附件 | ✓ | product-edit-enrich-candid、product-new-ai-automatch.s… |

## `/po/orders/:id` — PoOrderList/Detail ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 列表分页 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 详情时间线 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 发票 | ✓ | ops-po-desk-gaps.spec.cjs、po-prod-human.spec.cjs |
| 发货 | ✓ | ops-po-desk-gaps.spec.cjs、po-lifecycle.api.spec.cjs… |
| 附件 | ✓ | product-edit-enrich-candid、product-new-ai-automatch.s… |

## `/po/addresses` — PoAddressList ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| CRUD | ✓ | po-addresses-crud.spec.cjs |
| showForm 弹层 | ✓ | cascader-workflow.spec.cjs、knowledge-intake.spec.cjs… |
| confirm 删除 | ✓ | api-permission-writes.spec、basket-local-merge-prune.s… |

## `/po/reorder` — PoReorder ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 复制行项目 | ✓ | knowledge-intake.spec.cjs、product-edit-optimize.spec… |
| 重订 | ✓ | a11y.spec.cjs、permission-matrix.spec.cjs… |

## `/po/downloads` — PoDownloadCenter ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 下载链接 | ✓ | a11y.spec.cjs、permission-matrix.spec.cjs… |

## `/workspace` — DashboardPage ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 概览卡片 | ✓ | browsers.spec.cjs、checkout-progressive-secti… |
| 快捷入口 | ✓ | workspace-entry-intake.spe |

## `/workspace/products` — ProductsPage ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 3 弹层 | ✓ | cascader-workflow.spec.cjs、knowledge-intake.spec.cjs… |
| 可排序表 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 过滤 | ✓ | knowledge-intake.spec.cjs、workspace-entry-intake.spe |

## `/workspace/products/new` — ProductEditPage ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 发布弹层 | ✓ | cascader-workflow.spec.cjs、knowledge-intake.spec.cjs… |
| 上传 | ✓ | product-edit-enrich-candid、product-new-ai-automatch.s… |
| 校验 | ✓ | basket-local-merge-prune.s、basket-merge-over-limit.sp… |

## `/workspace/products/:id/edit` — ProductEditPage ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 发布弹层 | ✓ | cascader-workflow.spec.cjs、knowledge-intake.spec.cjs… |
| 上传 | ✓ | product-edit-enrich-candid、product-new-ai-automatch.s… |
| 校验 | ✓ | basket-local-merge-prune.s、basket-merge-over-limit.sp… |

## `/workspace/goals` — 各管理页 ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 增删改 | ✓ | api-permission-writes.spec、basket-local-merge-prune.s… |
| showEditor 弹层 | ✓ | cascader-workflow.spec.cjs、knowledge-intake.spec.cjs… |
| toast.error | ✓ | api-permission-writes.spec、applayout-navpad-check.spe… |

## `/workspace/applications` — 各管理页 ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 增删改 | ✓ | api-permission-writes.spec、basket-local-merge-prune.s… |
| showEditor 弹层 | ✓ | cascader-workflow.spec.cjs、knowledge-intake.spec.cjs… |
| toast.error | ✓ | api-permission-writes.spec、applayout-navpad-check.spe… |

## `/workspace/methods` — 各管理页 ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 增删改 | ✓ | api-permission-writes.spec、basket-local-merge-prune.s… |
| showEditor 弹层 | ✓ | cascader-workflow.spec.cjs、knowledge-intake.spec.cjs… |
| toast.error | ✓ | api-permission-writes.spec、applayout-navpad-check.spe… |

## `/workspace/protocols` — 各管理页 ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 增删改 | ✓ | api-permission-writes.spec、basket-local-merge-prune.s… |
| showEditor 弹层 | ✓ | cascader-workflow.spec.cjs、knowledge-intake.spec.cjs… |
| toast.error | ✓ | api-permission-writes.spec、applayout-navpad-check.spe… |

## `/workspace/references` — 各管理页 ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 增删改 | ✓ | api-permission-writes.spec、basket-local-merge-prune.s… |
| showEditor 弹层 | ✓ | cascader-workflow.spec.cjs、knowledge-intake.spec.cjs… |
| toast.error | ✓ | api-permission-writes.spec、applayout-navpad-check.spe… |

## `/workspace/knowledge-intake` — KnowledgeIntake ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 产品下拉 | ✓ | knowledge-intake.spec.cjs、workspace-entry-intake.spe |
| ki-toast | ✓ | knowledge-intake.spec.cjs、order-error-paths.spec.cjs… |

## `/ops/orders` — AdminOrders/Detail ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 过滤 | ✓ | knowledge-intake.spec.cjs、workspace-entry-intake.spe |
| 状态流转 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| alert 错误 | ✓ | order-error-paths.spec.cjs |

## `/ops/orders/:id` — AdminOrders/Detail ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 过滤 | ✓ | knowledge-intake.spec.cjs、workspace-entry-intake.spe |
| 状态流转 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| alert 错误 | ✓ | order-error-paths.spec.cjs |

## `/ops/po/review` — PoReviewDesk ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 待审列表 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| approve | ✓ | ops-inventory.spec.cjs、ops-po-desk-gaps.spec.cjs… |
| reject | ✓ | order-error-paths.spec.cjs、po-lifecycle.api.spec.cjs… |
| assign-rep | ✓ | po-lifecycle.api.spec.cjs |

## `/ops/po/shipments` — PoShipmentDesk ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 创建 ShippingRecord | ✓ | ops-po-desk-gaps.spec.cjs |
| mark-shipped | ✓ | cascader-workflow.spec.cjs、ops-po-desk-gaps.spec.cjs… |
| delivered | ✓ | ops-po-desk-gaps.spec.cjs、po-lifecycle.api.spec.cjs… |

## `/ops/po/invoicing` — PoInvoicingDesk ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 对 DELIVERED 开票 | ✓ | ops-po-desk-gaps.spec.cjs、po-lifecycle.api.spec.cjs… |
| 开票字段 | ✓ | ops-po-desk-gaps.spec.cjs |

## `/ops/po/ar` — PoArReport ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| AR aging 30 | ✓ | product-edit-usage.spec.cj |
| 60 | ✓ | applayout-navpad-check.spe |

## `/ops/po/organizations` — PoOrgManagement ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 机构 | ✓ | ops-po-desk-gaps.spec.cjs、po-lifecycle.api.spec.cjs |
| 地址 | ✓ | a11y.spec.cjs、checkout-validation.spec.c… |
| 订单查看 | ✓ | ops-po-desk-gaps.spec.cjs |

---

## 汇总

| 判定 | 页数 |
|---|---|
| **✓ 全项命中** | **44** |
| **✗ 有未命中项** | **0** |
| — 无交互描述 | 0 |

⚠️ 这是 I 维的**首次判定**。`✗` 页里的未命中项 = 明确的测试空白，应优先补。
⚠️ `✓` 页仍需抽查断言强度（关键词命中 ≠ 有 expect）。
