# 全站设计审计报告

> 基于 DESIGN_STANDARDS.md 标准，扫描全部 31 个页面组件
> 日期：2026-07-10

---

## 页面分类

| 分类 | 数量 | 包含 |
|------|------|------|
| 公共知识实体页 | 8 | Application(Index+Detail), Method(Index+Detail), Protocol(Index+Detail), ResearchGoal(Index+Detail) |
| 公共产品/交易页 | 7 | ProductIndex, QuoteRequest, CartPage, CheckoutPage, OrderList/Detail, SearchPage |
| 公共其他 | 5 | HomePage, LoginPage, RegisterPage, SettingsPage, NotFound |
| 管理后台(Admin) | 2 | AdminOrdersPage, AdminOrderDetail |
| 工作台(Workspace) | 9 | AdminLayout, Dashboard, Products/ProductEdit, Goals, Apps, Methods, Protocols, References, KnowledgeIntake |

---

## 已无冲突（P1/P2/P3 修复后）

✅ 无旧 teal 色 hardcoded
✅ 无旧 domain badge 残留
✅ 全局 `.badge` 样式已统一为中性 border + 语义色点
✅ `--radius-badge` 已更新为 4px
✅ 所有页面使用 CSS 变量 `var(--color-primary)`，无直接硬编码

---

## 🔴 发现的冲突

### A. 知识实体详情页 — 实体色用错（4 页）

知识实体的卡片图标背景色使用了**泛化语义色**，而非确认的**降饱和实体色**：

| 页面 | 当前 | 应为 (DESIGN_STANDARDS §2.4) |
|------|------|------|
| `ApplicationDetail.vue` | `.icon-method`: `--color-info-bg` (蓝色) | `#7AAEDB` |
| `ApplicationDetail.vue` | `.icon-protocol`: `--color-warning-bg` (琥珀色) | `#C9A34E` |
| `ApplicationDetail.vue` | `.icon-product`: `--color-danger-bg` (红色) | `#D47C7C` |
| `MethodDetail.vue` | `.icon-protocol`: `--color-warning-bg` | `#C9A34E` |
| `MethodDetail.vue` | `.icon-product`: `--color-danger-bg` | `#D47C7C` |
| `ProtocolDetail.vue` | `.icon-product`: `--color-danger-bg` | `#D47C7C` |

### B. 知识实体详情页 — 状态标签用旧 colored bg 风格（3 页）

| 页面 | 代码 |
|------|------|
| `ApplicationDetail.vue` | `.badge-active { background: var(--color-emerald-50); color: var(--color-emerald-600); }` |
| `ApplicationDetail.vue` | `.badge-draft { background: var(--color-warning-bg); color: var(--color-warning); }` |
| `MethodDetail.vue` | `.badge-active { background: var(--color-emerald-50); color: var(--color-emerald-600); }` |
| `MethodDetail.vue` | `.badge-draft { background: var(--color-warning-bg); color: var(--color-warning); }` |

应为：中性 border + 语义色圆点（与 ProductDetail 的 `.pd-badge-dot` 一致）

### C. 工作台（Workspace）— 大量旧 colored status 标签

约 **12 个文件** 包含 `status-active` / `status-draft` 等使用 `success-light` / `warning-light` 背景的样式。涉及：

- `DashboardPage.vue`, `GoalsPage.vue`, `AppsPage.vue`, `MethodsPage.vue`, `ProtocolsPage.vue`, `ProductsPage.vue`
- `ProductEditPage.vue`（多处 toast/save-msg/ai-badge/tag）
- `AdminProductsPage.vue`, `AdminProductEdit.vue`
- `AiToolsPanel.vue`, `BiozEvidenceSection.vue`

这些是内部管理界面，与最终用户视觉一致性关联较弱。

### D. 页面级圆角不一致（已知 P2 遗留）

各页面仍保留自身设计时的硬编码圆角值（6px/8px/10px），统一需要逐页评估。

---

## 建议修复优先级

| 优先级 | 范围 | 工作量 | 影响 |
|--------|------|--------|------|
| **P-A** | 知识实体详情页实体色修正 | 3 个文件, 6 处 CSS | 高 — 用户可见的页面 |
| **P-B** | 知识实体详情页 badge 风格统一 | 2 个文件, 4 处 CSS | 高 — 与产品详情页一致 |
| **P-C** | 工作台/管理后台 badge 统一 | ~12 文件 | 低 — 内部工具 |

**建议**: 先修复 P-A + P-B（公共知识实体页面），P-C 可后续逐步处理。
