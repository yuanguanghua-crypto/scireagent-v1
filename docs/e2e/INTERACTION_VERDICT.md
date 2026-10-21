# I 维（交互）判定

> 由 `scripts/judge_interaction.py` 生成。
> **判定规则**：该页所有交互项都命中 ⇒ `✓`；任一未命中 ⇒ `✗`。
> ⚠️ `✓` 只表示「关键词全覆盖」，**不表示断言充分**；要确认强度须打开 spec 看 `expect`。
> **已做中英同义词扩展**（修正初版的假空白，如「分页」→ pagination）。

## `/` — HomePage ⇒ **✗**

| 交互项 | 命中 | spec |
|---|---|---|
| 搜索 | ✓ | a11y.spec.cjs、applayout-navpad-check.spe… |
| 导航 | ✓ | cart-button-regression.spe、homepage.spec.cjs… |
| 分类 pills | **✗** | 无 |
| CTA | **✗** | 无 |

## `/login` — Login/Register ⇒ **✗**

| 交互项 | 命中 | spec |
|---|---|---|
| 输入校验 | ✓ | api-permission-writes.spec、applayout-navpad-check.spe… |
| 提交 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 跳转 | ✓ | cart-button-regression.spe、cart-page-interactions.spe… |
| 3步注册 | **✗** | 无 |

## `/register` — Login/Register ⇒ **✗**

| 交互项 | 命中 | spec |
|---|---|---|
| 输入校验 | ✓ | api-permission-writes.spec、applayout-navpad-check.spe… |
| 提交 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 跳转 | ✓ | cart-button-regression.spe、cart-page-interactions.spe… |
| 3步注册 | **✗** | 无 |

## `/search` — SearchPage ⇒ **✗**

| 交互项 | 命中 | spec |
|---|---|---|
| 搜索输入 | ✓ | a11y.spec.cjs、applayout-navpad-check.spe… |
| 结果点击 | **✗** | 无 |
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
| 过滤 | ✓ | knowledge-intake.spec.cjs |
| 分页 | ✓ | product-list-fixes.spec.cj、workspace-entity-crud.spec |
| 14列可排序表 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |

## `/protocols/:id` — ProtocolIndex/Detail ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 过滤 | ✓ | knowledge-intake.spec.cjs |
| 分页 | ✓ | product-list-fixes.spec.cj、workspace-entity-crud.spec |
| 14列可排序表 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |

## `/products` — ProductIndex/Detail ⇒ **✗**

| 交互项 | 命中 | spec |
|---|---|---|
| 分类 pills | **✗** | 无 |
| Tab 切换 | ✓ | product-detail-verified-me、workspace-verified-review. |
| Add to Cart | ✓ | a11y.spec.cjs、basket-local-merge-prune.s… |
| 数量± | ✓ | basket-local-merge-prune.s、basket-merge-over-limit.sp… |
| SKU 行 | ✓ | basket-local-merge-prune.s、basket-merge-over-limit.sp… |
| 文档链接 | **✗** | 无 |

## `/products/:id` — ProductIndex/Detail ⇒ **✗**

| 交互项 | 命中 | spec |
|---|---|---|
| 分类 pills | **✗** | 无 |
| Tab 切换 | ✓ | product-detail-verified-me、workspace-verified-review. |
| Add to Cart | ✓ | a11y.spec.cjs、basket-local-merge-prune.s… |
| 数量± | ✓ | basket-local-merge-prune.s、basket-merge-over-limit.sp… |
| SKU 行 | ✓ | basket-local-merge-prune.s、basket-merge-over-limit.sp… |
| 文档链接 | **✗** | 无 |

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
| toast | ✓ | knowledge-intake.spec.cjs、product-compliance-lifecyc… |

## `/:pathMatch` — NotFound ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 返回首页跳转 | ✓ | cart-button-regression.spe、cart-page-interactions.spe… |

## `/settings` — SettingsPage ⇒ **✗**

| 交互项 | 命中 | spec |
|---|---|---|
| 保存 | ✓ | cascader-workflow.spec.cjs、knowledge-intake.spec.cjs… |
| saveMessage 横幅 | **✗** | 无 |

## `/checkout` — CheckoutPage ⇒ **✗**

| 交互项 | 命中 | spec |
|---|---|---|
| 多步 | **✗** | 无 |
| v-loading | ✓ | product-detail-fields.spec、verify-improvements.spec.c |
| 提交 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |

## `/orders` — OrderList/Detail ⇒ **✗**

| 交互项 | 命中 | spec |
|---|---|---|
| 列表分页 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 详情时间线 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| alert 错误 | **✗** | 无 |

## `/orders/:id` — OrderList/Detail ⇒ **✗**

| 交互项 | 命中 | spec |
|---|---|---|
| 列表分页 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 详情时间线 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| alert 错误 | **✗** | 无 |

## `/po/submit` — PoSubmit ⇒ **✗**

| 交互项 | 命中 | spec |
|---|---|---|
| 行项目动态表单 | ✓ | basket-local-merge-prune.s、basket-merge-over-limit.sp… |
| 上传 | ✓ | product-edit-enrich-candid、product-new-ai-automatch.s… |
| alert 校验 | **✗** | 无 |
| 提交 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |

## `/po/orders` — PoOrderList/Detail ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 列表分页 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 详情时间线 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 发票 | ✓ | po-prod-human.spec.cjs |
| 发货 | ✓ | po-lifecycle.api.spec.cjs、po-lifecycle.fullflow.spec… |
| 附件 | ✓ | product-edit-enrich-candid、product-new-ai-automatch.s… |

## `/po/orders/:id` — PoOrderList/Detail ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 列表分页 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 详情时间线 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 发票 | ✓ | po-prod-human.spec.cjs |
| 发货 | ✓ | po-lifecycle.api.spec.cjs、po-lifecycle.fullflow.spec… |
| 附件 | ✓ | product-edit-enrich-candid、product-new-ai-automatch.s… |

## `/po/addresses` — PoAddressList ⇒ **✗**

| 交互项 | 命中 | spec |
|---|---|---|
| CRUD | **✗** | 无 |
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

## `/workspace` — DashboardPage ⇒ **✗**

| 交互项 | 命中 | spec |
|---|---|---|
| 概览卡片 | ✓ | browsers.spec.cjs、homepage.spec.cjs… |
| 快捷入口 | **✗** | 无 |
| LoadingSpinner | **✗** | 无 |

## `/workspace/products` — ProductsPage ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 3 弹层 | ✓ | cascader-workflow.spec.cjs、knowledge-intake.spec.cjs… |
| 可排序表 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| 过滤 | ✓ | knowledge-intake.spec.cjs |

## `/workspace/products/new` — ProductEditPage ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 发布弹层 | ✓ | cascader-workflow.spec.cjs、knowledge-intake.spec.cjs… |
| 上传 | ✓ | product-edit-enrich-candid、product-new-ai-automatch.s… |
| 校验 | ✓ | basket-local-merge-prune.s、basket-merge-over-limit.sp… |

## `/workspace/products/new/:id/edit` — ProductEditPage ⇒ **✓**

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

## `/workspace/knowledge-intake` — KnowledgeIntake ⇒ **✗**

| 交互项 | 命中 | spec |
|---|---|---|
| 产品下拉 | **✗** | 无 |
| ki-toast | ✓ | knowledge-intake.spec.cjs、product-compliance-lifecyc… |

## `/ops/orders` — AdminOrders/Detail ⇒ **✗**

| 交互项 | 命中 | spec |
|---|---|---|
| 过滤 | ✓ | knowledge-intake.spec.cjs |
| 状态流转 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| alert 错误 | **✗** | 无 |

## `/ops/orders/:id` — AdminOrders/Detail ⇒ **✗**

| 交互项 | 命中 | spec |
|---|---|---|
| 过滤 | ✓ | knowledge-intake.spec.cjs |
| 状态流转 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| alert 错误 | **✗** | 无 |

## `/ops/po/review` — PoReviewDesk ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| 待审列表 | ✓ | a11y.spec.cjs、api-permission-writes.spec… |
| approve | ✓ | ops-inventory.spec.cjs、po-lifecycle.api.spec.cjs… |
| reject | ✓ | po-lifecycle.api.spec.cjs、workspace-verified-review. |
| assign-rep | ✓ | po-lifecycle.api.spec.cjs |

## `/ops/po/shipments` — PoShipmentDesk ⇒ **✗**

| 交互项 | 命中 | spec |
|---|---|---|
| 创建 ShippingRecord | **✗** | 无 |
| mark-shipped | ✓ | cascader-workflow.spec.cjs、po-lifecycle.api.spec.cjs… |
| delivered | ✓ | po-lifecycle.api.spec.cjs、po-lifecycle.fullflow.spec… |

## `/ops/po/invoicing` — PoInvoicingDesk ⇒ **✗**

| 交互项 | 命中 | spec |
|---|---|---|
| 对 DELIVERED 开票 | ✓ | po-lifecycle.api.spec.cjs、po-lifecycle.fullflow.spec… |
| 开票字段 | **✗** | 无 |

## `/ops/po/ar` — PoArReport ⇒ **✓**

| 交互项 | 命中 | spec |
|---|---|---|
| AR aging 30 | ✓ | product-edit-usage.spec.cj |
| 60 | ✓ | applayout-navpad-check.spe |

## `/ops/po/organizations` — PoOrgManagement ⇒ **✗**

| 交互项 | 命中 | spec |
|---|---|---|
| 机构 | ✓ | po-lifecycle.api.spec.cjs |
| 地址 | ✓ | a11y.spec.cjs、checkout-validation.spec.c… |
| 订单查看 | **✗** | 无 |

---

## 汇总

| 判定 | 页数 |
|---|---|
| **✓ 全项命中** | **25** |
| **✗ 有未命中项** | **19** |
| — 无交互描述 | 0 |

⚠️ 这是 I 维的**首次判定**。`✗` 页里的未命中项 = 明确的测试空白，应优先补。
⚠️ `✓` 页仍需抽查断言强度（关键词命中 ≠ 有 expect）。
