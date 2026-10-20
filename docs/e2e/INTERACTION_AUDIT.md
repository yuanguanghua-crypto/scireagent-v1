# I 维（交互）半自动审计

> 由 `scripts/audit_interaction.py` 生成。
> ⚠️ **命中 ≠ 测了**：spec 里出现关键词，可能只是变量名/选择器，未必有断言。
> ⇒ 本表用来**缩小人工范围**，最终判定必须打开 spec 看 `expect(...)`。
> 已做的降噪：短词（≤4 字符）走词边界；**排除注释行**。

## `/` — HomePage

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 搜索 | 3 | homepage.spec.cjs、ops-inventory.spec.cjs、po-prod-human.spec.cjs |
| 导航 | 5 | cart-button-regression.spec.cj、homepage.spec.cjs、po-lifecycle.fullflow.spec.cjs… |
| 分类 pills | 2 | cascader-workflow.spec.cjs、product-edit-aipanel.spec.cjs |
| CTA | 0 | **无** |

## `/login /register` — Login/Register

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 输入校验 | 0 | **无** |
| 提交 | 6 | basket-local-merge-prune.spec.、basket-merge-over-limit.spec.c、po-lifecycle.api.spec.cjs… |
| 跳转 | 5 | cart-button-regression.spec.cj、homepage.spec.cjs、product-list-readonly-ext.spec… |
| 步注册 | 0 | **无** |

## `/search` — SearchPage

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 搜索输入 | 0 | **无** |
| 结果点击 | 0 | **无** |
| 空态 | 5 | knowledge-intake.spec.cjs、product-list-fixes.spec.cjs、product-list-readonly-ext.spec… |

## `/applications+:id` — AppIndex/Detail

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 列表搜索 | 0 | **无** |
| 分页 | 0 | **无** |
| 详情关联跳转 | 5 | cart-button-regression.spec.cj、homepage.spec.cjs、product-list-readonly-ext.spec… |

## `/methods+:id` — MethodIndex/Detail

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 过滤 chips | 6 | knowledge-intake.spec.cjs、product-edit-method-chip-names、product-edit-pending-candidate… |
| 分页 | 0 | **无** |
| 详情关联 | 0 | **无** |

## `/protocols+:id` — ProtocolIndex/Detail

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 过滤 | 1 | knowledge-intake.spec.cjs |
| 分页 | 0 | **无** |
| 列可排序表 | 0 | **无** |

## `/products+:id` — ProductIndex/Detail

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 分类 pills | 2 | cascader-workflow.spec.cjs、product-edit-aipanel.spec.cjs |
| Tab 切换 | 5 | product-detail-verified-method、product-edit-enrich-candidates、product-list-negative.spec.cjs… |
| Add to Cart | 34 | a11y.spec.cjs、applayout-navpad-check.spec.cj、basket-local-merge-prune.spec.… |
| 数量± | 3 | basket-local-merge-prune.spec.、basket-merge-over-limit.spec.c、cart-button-regression.spec.cj |
| SKU 行 | 13 | basket-local-merge-prune.spec.、basket-merge-over-limit.spec.c、cascader-workflow.spec.cjs… |
| 文档链接 | 0 | **无** |

## `/research-goals+:id` — RGIndex/Detail

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 状态 el-select 筛选 | 42 | a11y.spec.cjs、api-permission-writes.spec.cjs、applayout-navpad-check.spec.cj… |

## `/quote-request` — QuoteRequestPage

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 多字段表单 | 0 | **无** |
| 提交 | 6 | basket-local-merge-prune.spec.、basket-merge-over-limit.spec.c、po-lifecycle.api.spec.cjs… |
| 成功横幅 | 0 | **无** |

## `/cart` — CartPage

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 数量改 | 0 | **无** |
| 删除 | 3 | basket-local-merge-prune.spec.、knowledge-intake.spec.cjs、product-new-knowledge-links.sp |
| 提交审批 | 0 | **无** |
| 结算跳转 | 0 | **无** |
| toast | 13 | knowledge-intake.spec.cjs、product-compliance-lifecycle.s、product-edit-aipanel.spec.cjs… |

## `/:pathMatch` — NotFound

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 返回首页跳转 | 5 | cart-button-regression.spec.cj、homepage.spec.cjs、product-list-readonly-ext.spec… |

## `/settings` — SettingsPage

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 输入 | 2 | knowledge-intake.spec.cjs、product-seo-publish.spec.cjs |
| 保存 | 14 | cascader-workflow.spec.cjs、product-compliance-lifecycle.s、product-edit-enrich-candidates… |
| saveMessage 横幅 | 1 | product-list-readonly.spec.cjs |

## `/checkout` — CheckoutPage

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 输入 | 2 | knowledge-intake.spec.cjs、product-seo-publish.spec.cjs |
| 多步 | 0 | **无** |
| v-loading | 2 | product-detail-fields.spec.cjs、verify-improvements.spec.cjs |
| 提交 | 6 | basket-local-merge-prune.spec.、basket-merge-over-limit.spec.c、po-lifecycle.api.spec.cjs… |

## `/orders+:id` — OrderList/Detail

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 列表分页 | 0 | **无** |
| 详情时间线 | 0 | **无** |
| alert 错误 | 8 | basket-local-merge-prune.spec.、basket-merge-over-limit.spec.c、knowledge-intake.spec.cjs… |

## `/po/submit` — PoSubmit

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 行项目动态表单 | 0 | **无** |
| 上传 | 1 | product-new-doc-import.spec.cj |
| alert 校验 | 4 | basket-local-merge-prune.spec.、basket-merge-over-limit.spec.c、ops-inventory.spec.cjs… |
| 提交 | 6 | basket-local-merge-prune.spec.、basket-merge-over-limit.spec.c、po-lifecycle.api.spec.cjs… |

## `/po/orders+:id` — PoOrderList/Detail

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 列表分页 | 0 | **无** |
| 详情时间线 | 0 | **无** |
| 发票 | 1 | po-prod-human.spec.cjs |
| 发货 | 3 | po-lifecycle.api.spec.cjs、po-lifecycle.fullflow.spec.cjs、po-prod-human.spec.cjs |
| 附件 | 0 | **无** |

## `/po/addresses` — PoAddressList

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| CRUD | 0 | **无** |
| showForm 弹层 | 5 | product-compliance-lifecycle.s、product-list-negative.spec.cjs、product-list-readonly-ext.spec… |
| confirm 删除 | 10 | basket-local-merge-prune.spec.、cascader-workflow.spec.cjs、knowledge-intake.spec.cjs… |

## `/po/reorder` — PoReorder

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 复制行项目 | 0 | **无** |
| 重订 | 0 | **无** |

## `/po/downloads` — PoDownloadCenter

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 下载链接 | 0 | **无** |

## `/workspace(dashboard)` — DashboardPage

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 概览卡片 | 0 | **无** |
| 快捷入口 | 0 | **无** |
| LoadingSpinner | 0 | **无** |

## `/workspace/products` — ProductsPage

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 按钮 | 15 | cart-button-regression.spec.cj、ops-inventory.spec.cjs、product-batch-ai.spec.cjs… |
| 弹层 | 5 | product-compliance-lifecycle.s、product-list-negative.spec.cjs、product-list-readonly-ext.spec… |
| 可排序表 | 0 | **无** |
| 过滤 | 1 | knowledge-intake.spec.cjs |

## `/workspace/products/new+:id/edit` — ProductEditPage

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| **37 按钮 | 15 | cart-button-regression.spec.cj、ops-inventory.spec.cjs、product-batch-ai.spec.cjs… |
| 输入 | 2 | knowledge-intake.spec.cjs、product-seo-publish.spec.cjs |
| 发布弹层 | 0 | **无** |
| 上传 | 1 | product-new-doc-import.spec.cj |
| 校验** | 4 | basket-local-merge-prune.spec.、basket-merge-over-limit.spec.c、ops-inventory.spec.cjs… |

## `/workspace/goals /workspace/applications /workspace/methods /workspace/protocols /workspace/references` — 各管理页

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 增删改 | 0 | **无** |
| showEditor 弹层 | 5 | product-compliance-lifecycle.s、product-list-negative.spec.cjs、product-list-readonly-ext.spec… |
| toast.error | 35 | api-permission-writes.spec.cjs、applayout-navpad-check.spec.cj、basket-local-merge-prune.spec.… |

## `/workspace/knowledge-intake` — KnowledgeIntake

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 输入 | 2 | knowledge-intake.spec.cjs、product-seo-publish.spec.cjs |
| 产品下拉 | 0 | **无** |
| ki-toast | 13 | knowledge-intake.spec.cjs、product-compliance-lifecycle.s、product-edit-aipanel.spec.cjs… |

## `/ops/orders+:id` — AdminOrders/Detail

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 过滤 | 1 | knowledge-intake.spec.cjs |
| 状态流转 | 0 | **无** |
| alert 错误 | 8 | basket-local-merge-prune.spec.、basket-merge-over-limit.spec.c、knowledge-intake.spec.cjs… |

## `/ops/po/review` — PoReviewDesk

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 待审列表 | 0 | **无** |
| approve | 8 | ops-inventory.spec.cjs、po-lifecycle.api.spec.cjs、po-lifecycle.fullflow.spec.cjs… |
| reject | 2 | po-lifecycle.api.spec.cjs、workspace-verified-review.spec |
| assign-rep | 1 | po-lifecycle.api.spec.cjs |

## `/ops/po/shipments` — PoShipmentDesk

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 创建 ShippingRecord | 11 | api-permission-writes.spec.cjs、po-prod-human.spec.cjs、product-edit-enrich-candidates… |
| mark-shipped | 7 | cascader-workflow.spec.cjs、po-lifecycle.api.spec.cjs、po-lifecycle.fullflow.spec.cjs… |
| delivered | 4 | po-lifecycle.api.spec.cjs、po-lifecycle.fullflow.spec.cjs、po-prod-human.spec.cjs… |

## `/ops/po/invoicing` — PoInvoicingDesk

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 对 DELIVERED 开票 | 4 | po-lifecycle.api.spec.cjs、po-lifecycle.fullflow.spec.cjs、po-prod-human.spec.cjs… |
| 开票字段 | 0 | **无** |

## `/ops/po/ar` — PoArReport

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| AR aging 30 | 4 | permission-matrix.spec.cjs、po-prod-sweep.spec.cjs、product-edit-usage.spec.cjs… |
| 展示 | 1 | product-edit-pending-candidate |

## `/ops/po/organizations` — PoOrgManagement

| 交互项 | 命中 spec 数 | 命中的文件（前 3） |
|---|---|---|
| 机构 | 1 | po-lifecycle.api.spec.cjs |
| 地址 | 0 | **无** |
| 订单查看 | 0 | **无** |

---

## 汇总

| 指标 | 数值 |
|---|---|
| 交互项总数 | **96** |
| 有关键词命中的 | 56（58%） |
| **完全没命中（重点排查）** | **40** |

> ⚠️ 再强调：命中率只说明「关键词在代码里出现过」，**不代表断言存在**。
> 真正判定要看：打开 spec → 找到那个交互 → 确认有 `expect(...)` 断言它。
