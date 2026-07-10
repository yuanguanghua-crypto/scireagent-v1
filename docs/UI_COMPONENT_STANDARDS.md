# SciReagent 前端 UI 组件统一规范（Simple PRD）

> **文档状态**：初稿 · v0.1  
> **适用范围**：SciReagent 前端（Vue3 + Vite + Tailwind CSS v4 + Element Plus v2.9.1）  
> **策略路径**：路径 B — 渐进式抽象公共组件  
> **创建日期**：2026-07-09

---

## 1. 产品目标

SciReagent 前端存在严重的 UI 组件碎片化问题：按钮有 7+ 种写法、消息提示有 4 种方式、弹窗有 3 种实现。这些问题导致 UI 风格不一致、样式冗余（每个页面重复定义自己的 scoped 按钮/输入框类）、新功能开发时需要 N 套样式方案、维护成本高。**通过本次规范统一，在 `components/common/` 下创建 3 个核心可复用组件（AppButton、AppDialog、AppToast），确立统一的 props / slots / API 约定，使开发者在任何页面都可以一致地使用这些组件，消除碎片化。**

---

## 2. 现状矩阵

### 2.1 按钮（Button）

| 页面/文件 | 写法 | 优先级 |
|---|---|---|
| **Design System** (`main.css`) | `.btn` + `.btn-primary` / `.btn-secondary` / `.btn-outline` / `.btn-ghost` / `.btn-danger` / `.btn-accent` / `.btn-link`，含 sizes `.btn-sm` / `.btn-md` / `.btn-lg` / `.btn-icon` | P0 |
| **AppHeader.vue** | 使用 DS 的 `.btn.btn-ghost.btn-sm` 作为 auth 按钮；自定义 `.header-btn`（scoped，纯图标按钮） | P1 |
| **PublicNav.vue** | 自定义 `.nav-btn` / `.nav-btn-outline` / `.nav-btn-solid`（scoped，完全独立于 DS） | P1 |
| **CartPage.vue** | **重新定义**自己的 scoped `.btn` / `.btn-primary` / `.btn-outline` / `.btn-full`（与 DS 样式相似但不一致） | P1 |
| **CheckoutPage.vue** | 自定义 `.btn-checkout` + 独立 `.btn-primary`（scoped） | P1 |
| **ProductEditPage.vue** | 使用 DS 的 `.btn` / `.btn-primary` / `.btn-secondary` / `.btn-ghost` / `.btn-sm`，大量引用 | P1 |
| **ProductDetail.vue** | 自定义 `.pd-cart-btn` / `.pd-rfq-btn` / `.pd-doc-btn` / `.pd-doc-btn-ghost`（scoped） | P1 |
| **MethodIndex / ProtocolIndex** | 直接使用 `<el-button type="primary">`（Element Plus 原生） | P2 |
| **ErrorState.vue**（common） | 使用 `<el-button type="primary">`（Element Plus 原生） | P2 |

### 2.2 弹窗/对话框（Dialog / Modal）

| 页面/文件 | 写法 | 优先级 |
|---|---|---|
| **Design System** (`main.css`) | `.dialog-overlay` + `.dialog` / `.dialog--wide` / `.dialog--narrow` / `.dialog--danger`，含 `.dialog-warn` / `.dialog-suggest` 等块 | P0 |
| **ProductEditPage.vue** | 使用 DS 的 `.dialog-overlay` + `.dialog`（发布确认 + 内联编辑器） | P1 |
| **CompliancePreviewModal.vue** | 独立组件，自定义 `.preview-overlay` + `.preview-dialog`（iframe 预览） | P2 |
| **Element Plus** | `<el-dialog>` 在项目中未发现使用；`<el-message-box>` 仅 CSS 覆盖 | — |

### 2.3 消息提示（Toast / Message）

| 页面/文件 | 写法 | 优先级 |
|---|---|---|
| **`http.js`**（全局拦截器） | `ElMessage.error()` 直接调用（3 处：业务错误、401、其他错误） | P0 |
| **CartPage.vue** | 自定义 `.toast` + `showToast()` 函数（scoped CSS，固定 2s 自动消失） | P1 |
| **ProductDetail.vue** | 自定义 `.pd-toast` + `showToast()` 函数（scoped CSS，固定 2.5s） | P1 |
| **ProductEditPage.vue** | 自定义 `.toast` + `saveFeedback` 响应式对象（scoped CSS，持久显示至下次操作） | P1 |
| **ProductsPage.vue** | `ElMessage.success()` / `ElMessage.warning()` / `ElMessage.error()`（Workspace 管理页） | P1 |
| **GoalsPage / AppsPage / MethodsPage / ProtocolsPage / ReferencesPage** | `ElMessage.error()`（Workspace 管理页） | P2 |

### 2.4 表单输入（Form Input）

| 页面/文件 | 写法 | 优先级 |
|---|---|---|
| **Design System** (`main.css`) | `.input` / `.input-sm` / `.input-lg` / `.input-error` / `.input-success` + `.form-group` / `.form-label` / `.form-hint` / `.form-error` | P0 |
| **CheckoutPage.vue** | 自定义 `.form-input` / `.form-textarea` / `.form-input--error`（scoped CSS，与 DS 设计意图一致但代码重复） | 后续 |
| **ProductEditPage.vue** | 内联 `<input>` / `<select>` / `<textarea>` 自行 scoped 样式 | 后续 |
| **Element Plus** | `<el-input>` / `<el-select>` / `<el-cascader>` 在 ProductEditPage 中混用 | 后续 |

---

## 3. 首批统一范围

**按钮 / 弹窗 / 消息提示**三大类先行。理由：

1. **影响面最广**：按钮在每个页面都出现，7+ 种写法使风格一致性最差
2. **最简单、低风险**：这三类组件接口明确（props + slots + events），不依赖后端数据模型，替换时不需要修改业务逻辑
3. **高可见性**：用户交互最多的就是按钮和弹窗/提示，统一后视觉一致性立竿见影
4. **Element Plus 已有良好基础**：`main.css` 已包含完整的 `.el-message` / `.el-message-box` 样式覆盖，AppToast 可以直接封装 `ElMessage`

> **后续批次**（不在本次范围）：表单输入（CheckoutPage 的 `.form-input`、ProductEditPage 的 `<el-input>`）、卡片（DS 已定义 `.card` 类）、表格（DS 已定义 `.table` 类）、导航（DS 已定义 `.nav-item` / `.tab`）、徽章（DS 已定义 `.badge` 类）。这些 DS 已有定义，碎片化程度较低，可后续逐个规范化。

---

## 4. 组件规范

### 4.1 AppButton.vue — 统一按钮组件

**目标**：统一所有页面中按钮的视觉风格，消除 `.btn` / `.btn-primary` / `.btn-ghost` / `.nav-btn` / `.header-btn` / `.pd-cart-btn` / `.btn-checkout` / `el-button` 等 7+ 种写法。

#### Props 设计

| Prop | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `variant` | `'primary' \| 'secondary' \| 'outline' \| 'ghost' \| 'danger' \| 'accent' \| 'link'` | `'primary'` | 变体。映射到 Design System 的 `.btn-primary` / `.btn-secondary` / `.btn-outline` / `.btn-ghost` / `.btn-danger` / `.btn-accent` / `.btn-link` |
| `size` | `'sm' \| 'md' \| 'lg' \| 'icon' \| 'icon-sm'` | `'md'` | 尺寸。映射到 DS 的 `.btn-sm` / `.btn-md` / `.btn-lg` / `.btn-icon` / `.btn-icon-sm` |
| `loading` | `boolean` | `false` | 加载态，显示 spin 动画，禁用点击 |
| `disabled` | `boolean` | `false` | 禁用状态 |
| `icon` | `boolean` | `false` | 是否为纯图标按钮（无文字），适用于 header-btn / nav-btn 场景 |
| `nativeType` | `'button' \| 'submit' \| 'reset'` | `'button'` | 原生 type 属性 |
| `href` | `string` | — | 如果传入，渲染为 `<a>` 链接（替代 `<router-link>` 场景） |
| `to` | `string \| object` | — | 如果传入，渲染为 `<router-link>`（替代 AppHeader / PublicNav 中 router-link 按钮场景） |

#### Slots

| Slot | 说明 |
|---|---|
| `default` | 按钮文字/内容 |
| `icon` | 图标内容（将使用 DS 的 gap 样式） |

#### 跨页面使用场景映射

| 当前写法 | 迁移后写法 |
|---|---|
| `class="btn btn-primary"` | `<AppButton variant="primary">` |
| `class="btn btn-ghost btn-sm"` | `<AppButton variant="ghost" size="sm">` |
| `class="btn btn-outline btn-full"` | `<AppButton variant="outline" style="width:100%">` |
| `class="btn btn-secondary"` | `<AppButton variant="secondary">` |
| `class="btn-checkout"` | `<AppButton variant="primary" size="lg" style="width:100%">` |
| `class="pd-cart-btn"` | `<AppButton variant="primary" size="sm">` |
| `class="pd-rfq-btn"` | `<AppButton variant="outline">` |
| `class="pd-doc-btn-ghost"` | `<AppButton variant="ghost" size="sm">` |
| `class="header-btn"`（纯图标） | `<AppButton variant="ghost" icon>` |
| `class="nav-btn nav-btn-solid"` | `<AppButton variant="primary" size="sm">` |
| `class="nav-btn nav-btn-outline"` | `<AppButton variant="outline" size="sm">` |
| `<el-button type="primary">` | `<AppButton variant="primary">`（或保留 el-button 在独立组件中） |

#### 实现方式

- **基于 Design System 的 CSS 类**：内部使用 `class="btn"` + 对应 variant/size class，不依赖 Element Plus
- **loading 状态**：复用 DS 的 `.btn-loading` 动画（`main.css` line 753-772）
- **router-link 支持**：当传入 `to` prop 时，渲染为 `<router-link class="btn ...">`，替代 AppHeader 中的 `class="btn btn-ghost btn-sm header-auth-btn"`
- **图标按钮**：当 `icon` 为 true 时应用 `.btn-icon` 尺寸

### 4.2 AppDialog.vue — 统一弹窗组件

**目标**：统一 ProductEditPage（DS 自定义 dialog）和 CompliancePreviewModal（独立弹窗）的弹窗实现。

#### Props 设计

| Prop | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `visible` | `boolean` | `false` | 控制弹窗显示/隐藏（v-model 支持） |
| `title` | `string` | `''` | 弹窗标题 |
| `width` | `string` | `'480px'` | 弹窗宽度（CSS 值），对应 DS 的 `max-width: 480px` |
| `variant` | `'default' \| 'danger'` | `'default'` | 变体，danger 渲染 `.dialog--danger`（红色顶部边框） |
| `closeOnClickOverlay` | `boolean` | `true` | 点击遮罩层关闭 |
| `confirmText` | `string` | `'确认'` | 确认按钮文案 |
| `cancelText` | `string` | `'取消'` | 取消按钮文案 |
| `showConfirm` | `boolean` | `true` | 显示确认按钮 |
| `showCancel` | `boolean` | `true` | 显示取消按钮 |
| `confirmLoading` | `boolean` | `false` | 确认按钮 loading 状态 |
| `titleId` | `string` | — | ARIA `aria-labelledby` 值（复用 ProductEditPage 的 `useDialogA11y` 方案） |

#### Events

| Event | 参数 | 说明 |
|---|---|---|
| `update:visible` | `boolean` | 弹窗可见性变化 |
| `confirm` | — | 点击确认按钮 |
| `cancel` | — | 点击取消/关闭按钮 |

#### Slots

| Slot | 说明 |
|---|---|
| `default` | 弹窗主体内容 |
| `footer` | 自定义底部操作区（覆盖默认的 confirm/cancel 按钮） |

#### 三种变体

1. **确认弹窗**（default）：标准对话框，用于发布确认等场景
2. **警告弹窗**（default + 内嵌 `.dialog-warn` 块）：内部调用方可使用 `dialog-warn` 块样式
3. **危险弹窗**（`variant="danger"`）：红色顶部边框 + 标题红色，用于删除确认等

#### 实现方式

- 渲染结构复用 DS：`.dialog-overlay` > `.dialog`（+ `.dialog--danger` 变体）
- 按钮使用 `AppButton` 组件
- 接入 `useDialogA11y` composable（已在 ProductEditPage 中实现）管理焦点捕获、ESC 关闭、ARIA 属性
- CSS 动画复用 DS 的 `dialog-fade-in` / `dialog-slide-up`

#### 使用示例

```vue
<!-- 发布确认弹窗（替换 ProductEditPage 中手写的 dialog-overlay + dialog） -->
<AppDialog
  v-model:visible="showPublishDialog"
  title="Confirm Publish"
  @confirm="publish"
  @cancel="showPublishDialog = false"
>
  <div v-if="!isComplete" class="dialog-warn">
    <p>Product is incomplete — required fields missing:</p>
    <ul><li v-for="item in incompleteItems">✗ {{ item }}</li></ul>
  </div>
  <p>Confirm publishing this product?</p>
</AppDialog>
```

### 4.3 AppToast.js — 统一消息提示（函数式 API）

**目标**：统一全局 API。消除 4 种消息提示实现（`ElMessage.error()` / 自定义 `.toast` / 内联 `saveFeedback` / 服务端消息渲染）。

#### API 设计

```js
// 全局函数式调用（封装 Element Plus ElMessage，复用其 CSS override）
toast.success(msg, duration?)
toast.error(msg, duration?)
toast.warning(msg, duration?)
toast.info(msg, duration?)
```

| 参数 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `msg` | `string` | 必填 | 提示消息文本 |
| `duration` | `number` | `3000` | 展示时长（ms），`0` 为不自动关闭 |

#### 实现方式

- 内部封装 `ElMessage`，利用已有 `main.css` 的 `.el-message` / `.el-message--success/error/warning/info` 覆盖样式
- 导出为命名导出 + 默认导出，同时在 `main.js` 挂载到全局属性

```js
// components/common/AppToast.js
import { ElMessage } from 'element-plus'

export const toast = {
  success(msg, duration = 3000) {
    ElMessage.success({ message: msg, duration })
  },
  error(msg, duration = 3000) {
    ElMessage.error({ message: msg, duration })
  },
  warning(msg, duration = 3000) {
    ElMessage.warning({ message: msg, duration })
  },
  info(msg, duration = 3000) {
    ElMessage.info({ message: msg, duration })
  },
}

export default toast
```

在 `main.js` 中挂载：
```js
import { toast } from '@/components/common/AppToast'
app.config.globalProperties.$toast = toast
```

#### 跨页面迁移映射

| 当前写法 | 迁移后写法 |
|---|---|
| `ElMessage.error(msg)`（http.js） | `toast.error(msg)` |
| `ElMessage.success(msg)`（ProductsPage） | `toast.success(msg)` |
| `ElMessage.warning(msg)`（ProductsPage） | `toast.warning(msg)` |
| 自定义 `showToast(msg)` + `.toast`（CartPage） | `toast.success(msg)` |
| 自定义 `showToast(msg)` + `.pd-toast`（ProductDetail） | `toast.success(msg)` |
| 自定义 `saveFeedback` + `.toast`（ProductEditPage） | 保留原有逻辑（持久显示），或改用 `toast` 系列 |

---

## 5. 组件库导出约定

### 5.1 文件结构

```
frontend/src/components/common/
├── AppButton.vue
├── AppDialog.vue
├── AppToast.js          ← 函数式，非 Vue 组件
├── index.js             ← 统一导出入口（新增）
├── ErrorState.vue       ← 已有
├── EmptyState.vue       ← 已有
├── LoadingSpinner.vue   ← 已有
└── ...                  ← 其他现有 common 组件
```

### 5.2 统一导出（`index.js`）

```js
export { default as AppButton } from './AppButton.vue'
export { default as AppDialog } from './AppDialog.vue'
export { default as AppToast, toast } from './AppToast.js'

// 保留已有导出
export { default as DataPagination } from './DataPagination.vue'
export { default as EmptyState } from './EmptyState.vue'
export { default as ErrorState } from './ErrorState.vue'
export { default as LoadingSpinner } from './LoadingSpinner.vue'
// ...
```

### 5.3 注册策略

- **AppToast**（函数式 API）：在 `main.js` 中全局挂载为 `$toast`
- **AppButton / AppDialog**（Vue 组件）：**按需引入**，不从 `main.js` 全局注册。原因：
  - 减少全局注册的开销
  - 工具链（Tree-shaking）可正确去除未使用的组件
  - 保持逐步迁移的灵活性（旧页面不需要立即修改）

```vue
<script setup>
import { AppButton, AppDialog } from '@/components/common'
</script>
```

---

## 6. 迁移策略

### Phase 1：创建组件 + 工具页迁移（预估 2-3 天）

**目标**：完成三个组件的创建，替换所有 Workspace 管理后台页面（工具页）的按钮和消息提示引用。

**创建文件**：
- `frontend/src/components/common/AppButton.vue` — 新文件
- `frontend/src/components/common/AppDialog.vue` — 新文件
- `frontend/src/components/common/AppToast.js` — 新文件
- `frontend/src/components/common/index.js` — 更新（增加导出）

**文件清单**：
| 文件 | 修改类型 | 改动量 |
|---|---|---|
| `AppButton.vue` | 新建 | ~120 行 |
| `AppDialog.vue` | 新建 | ~150 行 |
| `AppToast.js` | 新建 | ~30 行 |
| `components/common/index.js` | 更新导出 | +5 行 |
| `main.js` | 注册 `$toast` | +2 行 |
| `src/views/workspace/ProductsPage.vue` | 替换 `ElMessage` → `toast` | ~7 处 |
| `src/views/workspace/GoalsPage.vue` | 替换 `ElMessage` → `toast` | 1 处 |
| `src/views/workspace/AppsPage.vue` | 替换 `ElMessage` → `toast` | 1 处 |
| `src/views/workspace/MethodsPage.vue` | 替换 `ElMessage` → `toast` | 1 处 |
| `src/views/workspace/ProtocolsPage.vue` | 替换 `ElMessage` → `toast` | 1 处 |
| `src/views/workspace/ReferencesPage.vue` | 替换 `ElMessage` → `toast` | 1 处 |

**预期工作量**：1 名开发者约 2-3 天

### Phase 2：核心页面迁移（预估 3-4 天）

**目标**：替换购物车、结账、产品详情等用户高频页面的自定义样式。

**文件清单**：
| 文件 | 修改类型 | 改动量 |
|---|---|---|
| `CartPage.vue` | 替换按钮 + toast | ~10 处按钮 + 移除 scoped `.btn`/`.toast` 类 |
| `CheckoutPage.vue` | 替换按钮 | ~2 处按钮 + 移除 scoped `.btn-checkout`/`.btn-primary` |
| `ProductDetail.vue` | 替换按钮 + toast | ~8 处按钮 + 移除 scoped `.pd-cart-btn`/`.pd-toast` 等 |
| `ProductEditPage.vue` | 替换按钮 + dialog | ~30 处按钮 + 2 个 dialog + 移除 scoped `.toast` |
| `AppHeader.vue` | 替换 header-btn | ~3 处按钮 + 移除 scoped `.header-btn` |
| `PublicNav.vue` | 替换 nav-btn | ~4 处按钮 + 移除 scoped `.nav-btn` |
| `MethodIndex.vue` | 替换 el-button | 2 处 |
| `ProtocolIndex.vue` | 替换 el-button | 2 处 |
| `ProtocolDetail.vue` | 替换 el-button | 1 处 |
| `ResearchGoalDetail.vue` | 替换 el-button | 2 处 |
| `ErrorState.vue` | 替换 el-button | 1 处 |
| `CompliancePreviewModal.vue` | 评估是否替换为 AppDialog | 单独组件 |

**预期工作量**：1 名开发者约 3-4 天

### Phase 3：收尾清理（预估 1-2 天）

**目标**：
1. 删除各页面不再使用的 scoped 按钮/弹窗/消息样式（`.cart-page .btn`, `.pd-cart-btn`, `.toast`, `.btn-checkout`, `.nav-btn`, `.header-btn` 等）
2. 在 Design System 的 `main.css` 中确认自定义组件类是否与 DS 重复，移除重复定义
3. 确认 Element Plus 的 `<el-button>` 不再在业务页面中使用（保留 `ErrorState.vue` 特殊场景）
4. 视觉回归测试：逐一页面确认按钮/弹窗/消息提示样式正确

**预期工作量**：1 名开发者约 1-2 天

### 总工作量预估：6-9 人天

---

## 7. Design System 一致性确认

| 项目 | 现状 | 建议 |
|---|---|---|
| **按钮 primary color** | Design System 使用 `teal-700`（`#0F766E`） | **保留**，所有 AppButton primary 变体使用 `teal-700` |
| **弹窗默认宽度** | DS 定义 `max-width: 480px` | **保留**，AppDialog 默认 480px |
| **弹窗 wide 宽度** | DS 定义 `max-width: 640px`（`.dialog--wide`） | 通过 `width="640px"` prop 实现 |
| **弹窗窄宽度** | DS 定义 `max-width: 360px`（`.dialog--narrow`） | 通过 `width="360px"` prop 实现 |
| **Toast 默认展示时间** | 各页面：Cart 2s，ProductDetail 2.5s，ElMessage 默认 3s | 统一默认 **3s**（与 ElMessage 默认一致） |
| **Toast 位置** | DS 已覆盖 `.el-message { top: 60px }` | 保留，不改变 |
| **Tailwind CSS 组件类** | 已通过 `@theme` 定义完整的 color/spacing/radius/typography token | **不需要**额外添加 Tailwind 类，AppButton 使用 DS CSS 类即可 |
| **Element Plus 全局注册** | `main.js` 已 `app.use(ElementPlus)` | **保留**，AppToast 内部使用 ElMessage |
| **`el-button`** | 已注册但项目中实际用量有限（~13 处） | 建议将 `<el-button>` 逐步替换为 `<AppButton>`，保持统一 |

---

## 8. 待确认问题

1. **AppButton 是否要支持 `el-button` 的功能？** 如 `preset`、`circle`、`text` 等 Element Plus 特有的 props。当前建议：**不实现**，按 DS 的 7 种 variant + 5 种 size 足以覆盖所有使用场景。
2. **AppDialog 是否需要基于 `<el-dialog>` 实现？** 当前建议：**不基于** Element Plus，直接使用 DS 的 `.dialog-overlay` + `.dialog` 类，保持轻量。
3. **CompliancePreviewModal.vue**（iframe 预览弹窗）是功能独立组件，它的 dialog 外壳是否需要统一为 AppDialog？当前建议：**暂不统一**，该组件结构特殊（iframe 全高），等 Phase 2 评估。
4. **AppButton 的 loading 状态在 `<a>` / `<router-link>` 模式下是否有效？** 当前建议：`<a>` 和 `<router-link>` 模式下不支持 loading（原生 `<a>` 没有 disabled 语义）。
5. **ProductEditPage 的 `saveFeedback`** 是持久 toast（显示到下次操作），与 AppToast 的自动消失行为不同。建议：**保留** ProductEditPage 的 `saveFeedback` 逻辑，仅将其渲染方式改为 AppToast 风格或直接使用 `toast` API（设置 `duration: 0`）。
6. **`http.js` 中的 `ElMessage.error()`** 是否替换为 `toast.error()`？考虑到 http.js 是公共模块，为避免循环依赖，建议直接保持 `ElMessage.error()`。
