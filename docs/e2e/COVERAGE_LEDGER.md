# 全站测试覆盖台账（骨架 V1）

> **本文件由 `scripts/gen_coverage_ledger.py` 生成 —— 重跑会覆盖人工填写内容。**
> **人工判定结果请写进 `docs/e2e/COVERAGE_FINDINGS.md`**（带证据，不会被覆盖）。
> 来源：`docs/e2e/FULL_SITE_E2E_PLAN.md` §2.2（程序化提取 44 页，不手抄）

## ⚠️ 先说清楚：为什么这里没有「覆盖率」

我试过用「关键词匹配 spec」自动算覆盖率，**两次都失败**：

| 尝试 | 结果 |
|---|---|
| 只匹配页面名 | `/login` 判成「无 spec」= **假空洞** |
| 再加路由片段 | `a11y.spec` / `permission-matrix` 这类**全站扫描**让 44 页全部「有 spec」= **假 100%** |

**根本原因**：本项目 56 个 spec 是**点菜单进入**的（符合「不许 goto 直达」铁律，全仓 `goto` 只有 2 处），
所以覆盖度**无法从代码静态反推** —— 必须看断言、看点击路径。

⇒ 本台账**只给骨架**：格子由人填。这比给一个假的 100% 有用。

## ✅ 源表缺陷已修复（2026-10-20）

生成台账时曾查出 `FULL_SITE_E2E_PLAN.md` §2.2 表格**列数不齐**：
表头声明 10 列，但 **30 行里有 29 行只有 9 列**（整列 B 维未填，末格直接是优先级）。

**已逐行核过**（30 行模式一致、0 异常）后补齐：给 29 行插入了 B 列并标 `☐`（待评估，非「不适用」）。
复核结果：**30 行全部 10 列**。

⇒ 所以本台账的**维度分区现在是可信的**（此前不可信）。

## 判读规则

| 符号 | 含义 |
|---|---|
| `☐` | **待评估** —— 需要有人确认这一维测没测 |
| `—` | **不适用** —— FULL_SITE 规划如此，不是缺失 |
| `✓` | 已覆盖（**你填的**，附 spec 名或说明） |
| `✗` | 确认未覆盖（**你填的**） |

## 七维含义（摘自 FULL_SITE §2.0）

| 维 | 含义 |
|---|---|
| **I 交互** | 每个按钮/输入/选择/弹窗/下拉/Tab/上传/分页/排序/Toast/加载态都被触发 |
| **P 权限** | 4 角色（匿名 / customer / staff / admin）× 受限页的预期行为 |
| **S 状态** | 业务状态分支（PO 8 态 / 订单旧态 / 产品 active·draft·discontinued）的 UI 差异 |
| **R 响应式** | 桌面 / 笔记本 / 平板 / 移动 4 视口，布局不崩、关键交互可用 |
| **V 视觉** | 设计令牌一致（主色 / 圆角 / badge+点 / 字体） |
| **A 可访问性** | WCAG：label 关联 / 对比度 / 焦点顺序 / aria |
| **B 浏览器** | chromium / firefox / webkit 行为一致 |


### 公开页（无需登录）

| # | 路由 | 页面 | I | P | S | R | V | A | B | 优先级 | 相关 spec（仅检索线索，非覆盖证据） |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `/` | HomePage | ☐ | — | — | ☐ | ☐ | ☐ | ☐ | P0 | public-smoke.spec.cjs |
| 2 | `/login` | Login/Register | ☐ | ☐ | — | ☐ | ☐ | ☐ | ☐ | P0 | a11y.spec.cjs、api-permission-writes.sp… |
| 3 | `/register` | Login/Register | ☐ | ☐ | — | ☐ | ☐ | ☐ | ☐ | P0 | a11y.spec.cjs、api-permission-writes.sp… |
| 4 | `/search` | SearchPage | ☐ | — | — | ☐ | ☐ | ☐ | ☐ | P0 | applayout-navpad-check.s、homepage.spec.cjs… |
| 5 | `/applications` | AppIndex/Detail | ☐ | — | — | ☐ | ☐ | ☐ | ☐ | P0 | a11y.spec.cjs、api-permission-writes.sp… |
| 6 | `/applications/:id` | AppIndex/Detail | ☐ | — | — | ☐ | ☐ | ☐ | ☐ | P0 | a11y.spec.cjs、api-permission-writes.sp… |
| 7 | `/methods` | MethodIndex/Detail | ☐ | — | — | ☐ | ☐ | ☐ | ☐ | P0 | a11y.spec.cjs、api-permission-writes.sp… |
| 8 | `/methods/:id` | MethodIndex/Detail | ☐ | — | — | ☐ | ☐ | ☐ | ☐ | P0 | a11y.spec.cjs、api-permission-writes.sp… |
| 9 | `/protocols` | ProtocolIndex/Detail | ☐ | — | — | ☐ | ☐ | ☐ | ☐ | P0 | a11y.spec.cjs、api-permission-writes.sp… |
| 10 | `/protocols/:id` | ProtocolIndex/Detail | ☐ | — | — | ☐ | ☐ | ☐ | ☐ | P0 | a11y.spec.cjs、api-permission-writes.sp… |
| 11 | `/products` | ProductIndex/Detail | ☐ | — | ☐ | ☐ | ☐ | ☐ | ☐ | P0 | a11y.spec.cjs、api-permission-writes.sp… |
| 12 | `/products/:id` | ProductIndex/Detail | ☐ | — | ☐ | ☐ | ☐ | ☐ | ☐ | P0 | a11y.spec.cjs、api-permission-writes.sp… |
| 13 | `/research-goals` | RGIndex/Detail | ☐ | — | — | ☐ | ☐ | ☐ | ☐ | P0 | a11y.spec.cjs、api-permission-writes.sp… |
| 14 | `/research-goals/:id` | RGIndex/Detail | ☐ | — | — | ☐ | ☐ | ☐ | ☐ | P0 | a11y.spec.cjs、api-permission-writes.sp… |
| 15 | `/quote-request` | QuoteRequestPage | ☐ | — | — | ☐ | ☐ | ☐ | ☐ | P1 | api-permission-writes.sp、public-smoke.spec.cjs… |
| 16 | `/cart` | CartPage | ☐ | — | — | ☐ | ☐ | ☐ | ☐ | P1 | basket-local-merge-prune、basket-merge-over-limit.… |
| 17 | `/:pathMatch` | NotFound | ☐ | — | — | ☐ | ☐ | ☐ | ☐ | P0 | product-new-ai-automatch、public-smoke.spec.cjs |

### 认证用户页（requiresAuth）

| # | 路由 | 页面 | I | P | S | R | V | A | B | 优先级 | 相关 spec（仅检索线索，非覆盖证据） |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 18 | `/settings` | SettingsPage | ☐ | ☐ | — | ☐ | ☐ | ☐ | ☐ | P1 | basket-merge-over-limit.、internal-access-procurem… |
| 19 | `/checkout` | CheckoutPage | ☐ | ☐ | — | ☐ | ☐ | ☐ | ☐ | P1 | api-permission-writes.sp、permission-matrix.spec.c… |
| 20 | `/orders` | OrderList/Detail | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | P1 | a11y.spec.cjs、api-permission-writes.sp… |
| 21 | `/orders/:id` | OrderList/Detail | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | P1 | a11y.spec.cjs、api-permission-writes.sp… |
| 22 | `/po/submit` | PoSubmit | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | P1 | api-permission-writes.sp、basket-local-merge-prune… |
| 23 | `/po/orders` | PoOrderList/Detail | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | P1 | a11y.spec.cjs、api-permission-writes.sp… |
| 24 | `/po/orders/:id` | PoOrderList/Detail | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | P1 | a11y.spec.cjs、api-permission-writes.sp… |
| 25 | `/po/addresses` | PoAddressList | ☐ | ☐ | — | ☐ | ☐ | ☐ | ☐ | P1 | permission-matrix.spec.c、po-prod-sweep.spec.cjs… |
| 26 | `/po/reorder` | PoReorder | ☐ | ☐ | — | ☐ | ☐ | ☐ | ☐ | P2 | permission-matrix.spec.c、po-prod-sweep.spec.cjs… |
| 27 | `/po/downloads` | PoDownloadCenter | ☐ | ☐ | — | ☐ | ☐ | ☐ | ☐ | P2 | permission-matrix.spec.c、po-prod-sweep.spec.cjs… |

### 管理员页（requiresAdmin，is_staff）

| # | 路由 | 页面 | I | P | S | R | V | A | B | 优先级 | 相关 spec（仅检索线索，非覆盖证据） |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 28 | `/workspace` | DashboardPage | ☐ | ☐ | — | ☐ | ☐ | ☐ | ☐ | P1 | a11y.spec.cjs、cascader-workflow.spec.c… |
| 29 | `/workspace/products` | ProductsPage | ☐ | ☐ | — | ☐ | ☐ | ☐ | ☐ | P1 | a11y.spec.cjs、api-permission-writes.sp… |
| 30 | `/workspace/products/new` | ProductEditPage | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | P0 | a11y.spec.cjs、api-permission-writes.sp… |
| 31 | `/workspace/products/new/:id/edit` | ProductEditPage | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | P0 | a11y.spec.cjs、api-permission-writes.sp… |
| 32 | `/workspace/goals` | 各管理页 | ☐ | ☐ | — | ☐ | ☐ | ☐ | ☐ | P1 | a11y.spec.cjs、cascader-workflow.spec.c… |
| 33 | `/workspace/applications` | 各管理页 | ☐ | ☐ | — | ☐ | ☐ | ☐ | ☐ | P1 | a11y.spec.cjs、applayout-navpad-check.s… |
| 34 | `/workspace/methods` | 各管理页 | ☐ | ☐ | — | ☐ | ☐ | ☐ | ☐ | P1 | a11y.spec.cjs、api-permission-writes.sp… |
| 35 | `/workspace/protocols` | 各管理页 | ☐ | ☐ | — | ☐ | ☐ | ☐ | ☐ | P1 | a11y.spec.cjs、cascader-workflow.spec.c… |
| 36 | `/workspace/references` | 各管理页 | ☐ | ☐ | — | ☐ | ☐ | ☐ | ☐ | P1 | a11y.spec.cjs、cascader-workflow.spec.c… |
| 37 | `/workspace/knowledge-intake` | KnowledgeIntake | ☐ | ☐ | — | ☐ | ☐ | ☐ | ☐ | P1 | a11y.spec.cjs、basket-local-merge-prune… |
| 38 | `/ops/orders` | AdminOrders/Detail | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | P1 | a11y.spec.cjs、api-permission-writes.sp… |
| 39 | `/ops/orders/:id` | AdminOrders/Detail | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | P1 | a11y.spec.cjs、api-permission-writes.sp… |
| 40 | `/ops/po/review` | PoReviewDesk | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | P1 | permission-matrix.spec.c、po-lifecycle.fullflow.sp… |
| 41 | `/ops/po/shipments` | PoShipmentDesk | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | P1 | permission-matrix.spec.c、po-lifecycle.api.spec.cj… |
| 42 | `/ops/po/invoicing` | PoInvoicingDesk | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | ☐ | P1 | permission-matrix.spec.c、po-lifecycle.fullflow.sp… |
| 43 | `/ops/po/ar` | PoArReport | ☐ | ☐ | — | ☐ | ☐ | ☐ | ☐ | P2 | public-smoke.spec.cjs |
| 44 | `/ops/po/organizations` | PoOrgManagement | ☐ | ☐ | — | ☐ | ☐ | ☐ | ☐ | P2 | permission-matrix.spec.c、po-prod-sweep.spec.cjs… |

## 骨架规模

| 指标 | 数值 |
|---|---|
| 页面数 | **44** |
| 待评估格子 `☐` | **263** |
| 不适用 `—` | 45 |

> ⚠️ 上面**不写完成率**，因为没人填过。要算完成率，先把 `☐` 填成 `✓`/`✗`。

## 怎么填（建议顺序）

1. **先填 P0 页面**（下表），一页一页来，别摊大饼
2. 打开该页对应的 spec（看最后一列的线索），**逐维确认「这一维真的断言了吗」**
   - 有断言 → 填 `✓` + spec 名
   - 没断言 → 填 `✗`（这就是要补的）
   - 不确定 → 保持 `☐`，别猜
3. **填完一页再填下一页** —— 半填的台账比空台账更危险（会让人以为看过了）

### P0 页面清单（先填这些）

| 路由 | 页面 | 待评估格数 |
|---|---|---|
| `/` | HomePage | 5 |
| `/login` | Login/Register | 6 |
| `/register` | Login/Register | 6 |
| `/search` | SearchPage | 5 |
| `/applications` | AppIndex/Detail | 5 |
| `/applications/:id` | AppIndex/Detail | 5 |
| `/methods` | MethodIndex/Detail | 5 |
| `/methods/:id` | MethodIndex/Detail | 5 |
| `/protocols` | ProtocolIndex/Detail | 5 |
| `/protocols/:id` | ProtocolIndex/Detail | 5 |
| `/products` | ProductIndex/Detail | 6 |
| `/products/:id` | ProductIndex/Detail | 6 |
| `/research-goals` | RGIndex/Detail | 5 |
| `/research-goals/:id` | RGIndex/Detail | 5 |
| `/:pathMatch` | NotFound | 5 |
| `/workspace/products/new` | ProductEditPage | 7 |
| `/workspace/products/new/:id/edit` | ProductEditPage | 7 |

## 更新方式

```bash
python scripts/gen_coverage_ledger.py   # 重跑刷新骨架
```

⚠️ 重跑会覆盖人工填写的 `✓`/`✗`。**填完后请把台账另存为 `COVERAGE_LEDGER_FILLED.md`**，
或直接把填写结果落到 spec 文件的注释里（更持久）。

