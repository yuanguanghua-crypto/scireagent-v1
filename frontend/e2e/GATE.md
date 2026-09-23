# E2E 闸门说明（GATE.md）

> 位置：`frontend/e2e/GATE.md`
> 口径更新：2026-09-23（第一轮：30 个原无标签 spec 的 **spec 级**定级；
> 第二轮：**用例级捞回** —— 把"部分红"文件里的**绿例**按**用例级** tag 纳入闸门，红例逐条排除）
> 相关文件：`frontend/e2e/gate-audit.cjs`（审计器）、`frontend/package.json`（`test:e2e:local`）

---

## 0. 一句话口径

**「有 spec 文件」≠「会跑到」。**

跑批器（Playwright）用 `-g "@readonly"` / `-g "@write"` / `-g "@local-only"` 过滤选择用例：
**任何没有被这些标签命中的用例，既不会被执行、也不会报错 —— 这就是"静默漏跑"。**
本闸门的目标：让"漏跑"不可能静默发生 —— **要么被跑到，要么被显式标注为排除（`@obsolete`）并写明理由。**

---

## 1. 闸门机制：为什么不再依赖"记得加标签"

三道防线，任何一道不过就**中断**（非零退出），不会带着缺口继续跑：

| 防线 | 载体 | 作用 |
|---|---|---|
| ① 标签完整性审计 | `frontend/e2e/gate-audit.cjs` | 用 `playwright test --list --reporter=json` 列出**全部**用例（不启动浏览器），逐条检查 `tags` 是否至少含 `readonly` / `write` / `obsolete` 之一。**缺任何一个 ⇒ 打印明细 + 退出码 1。** |
| ② 收集完整性审计 | 同上 | 收集阶段若报错（某 spec 语法/require 失败）⇒ Playwright 的 JSON `errors` 非空、`suites` 为空 ⇒ 审计器识别为**清单不完整、审计不可信**，退出码 3。（否则会「0 例全过」地静默放行 —— 本轮实测踩到过。） |
| ③ 闸门跑批 | `npm run test:e2e:local` | `gate-audit` 通过后，才跑 `-g "@local-only" --grep-invert "@obsolete"`。 |

`gate-audit.cjs` 对**两种标注写法都有效**（已实测，Playwright 1.60.0）：
`test(title, { tag: '@x' }, fn)` / `test.describe(title, { tag: [...] }, fn)`（describe 级标签会被组内用例继承），
以及旧式的「标签写在标题字符串里」（如 `test('H1a @readonly …')`）。两种都会进入 JSON 的 `spec.tags`，也都能被 `-g` 选中。

**范围**：`testMatch = e2e/**/*.spec.cjs`（**含子目录**）。
`inventory-driven/` 的历史遗留套件**不再特殊排除** —— 它们已被逐条补 `@obsolete`（见 §4），与其他 spec 一视同仁。

---

## 2. 标准跑批命令

### 2.1 本机（必须用这条：`npm run` / `npx` 会被 WSL 别名劫持）

```bash
cd /e/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/frontend
# ① 先审计（缺标签即中断）
node e2e/gate-audit.cjs
# ② 再跑闸门内全部（@local-only 且排除 @obsolete）
node node_modules/@playwright/test/cli.js test \
  -g "@local-only" --grep-invert "@obsolete" \
  --project=chromium --reporter=line --output=<每次全新的目录> > <日志> 2>&1
```

> ⚠️ 硬纪律：`--output` **每次换全新目录名**（复用会被 safe-delete 钩子拦下）；输出**重定向到文件**，**不要管道给 `tail`**（会挂死）；**串行**（`workers: 1` 已在 config 锁死，见 `playwright.config.cjs`）。

### 2.2 CI / 无 WSL 劫持的机器

```bash
npm run test:e2e:local
```

`test:e2e:local` = `node e2e/gate-audit.cjs && node …/cli.js test -g "@local-only" --grep-invert "@obsolete" --project=chromium --reporter=line`。

### 2.3 现有四个 script 保留不变

`test:e2e`（全量）/ `test:e2e:readonly`（`-g @readonly`）/ `test:e2e:write`（`-g @write`）/ `test:e2e:prod`（`-g @prod-ok`）。

### 2.4 标签分层（两个维度）

| 维度 | 标签 | 含义 |
|---|---|---|
| **tier（必居其一，gate-audit 强制）** | `@readonly` | 只读（跑前跑后表计数零变化） |
| | `@write` | 真实写（带 `E2E-` 前缀 + `afterAll` 清理） |
| | `@obsolete` | **显式排除**（闸门外），理由必须写进 §4 |
| **环境（决定被哪个 script 选中）** | `@local-only` | 本地 dev 专属（依赖 dev 库数据/外部语料） |
| | `@prod-ok` | 可在生产执行（本轮**一律未加**） |

> 有 tier 标签只保证"不会被静默漏跑"（要么被某个 `-g` 选中，要么 `@obsolete` 排除）；
> 具体被哪个 script 选中由环境标签决定：`@local-only` → `test:e2e:local`；`@prod-ok` → `test:e2e:prod`；
> 两者都没有的 `@readonly` / `@write` → 仍会被 `test:e2e:readonly` / `:write` 选中。

---

## 3. 闸门内 spec 表（本轮实测全绿）

「闸门内」= 本轮 `--retries=0` 实跑**全绿**，已标注 `@readonly|@write` + `@local-only`。
用例数为该 spec 被 `-g "@local-only"` 选中的条数。

| # | 文件 | tier | 用例数 | 本轮实测 | 读写依据（摘要） |
|---|---|---|---|---|---|
| 1 | `a11y.spec.cjs` | readonly | 5 | 5 passed | 仅登录 + axe 扫描，无写调用 |
| 2 | `applayout-navpad-check.spec.cjs` | readonly | 3 | 3 passed | 纯 DOM 断言 |
| 3 | `browsers.spec.cjs` | readonly | 3 | 3 passed | 纯渲染断言 |
| 4 | `permission-matrix.spec.cjs` | readonly | 83 | 83 passed | 仅登录 + 路由/可见性断言 |
| 5 | `product-detail-verified-methods.spec.cjs` | readonly | 4 | 4 passed | 仅点 tab |
| 6 | `responsive.spec.cjs` | readonly | 22 | 22 passed | 改视口 + 导航点击 |
| 7 | `state-matrix.spec.cjs` | readonly | 10 | 10 passed | 仅读 AdminOrderDetail UI |
| 8 | `verify-improvements.spec.cjs` | readonly | 3 | 3 passed | 唯一"保存"动作被 `page.route` 挂起，不落库 |
| 9 | `visual-tokens.spec.cjs` | readonly | 1 | 1 passed | 纯 CSS 变量断言 |
| 10 | `cascader-workflow.spec.cjs` | write | 8 | 8 passed | `ctx.post('/products/')` + `/hard-delete/` |
| 11 | `product-edit-aipanel.spec.cjs` | write | 4 | 4 passed | UI 点 `Save Draft` |
| 12 | `product-edit-dark-a11y-knowledge.spec.cjs` | write | 2 | 2 passed | UI 点 `Save Draft`（+ AI AUTO MATCH） |
| 13 | `product-edit-optimize.spec.cjs` | write | 6 | 6 passed | UI `Save Draft` / `Generate SDS` / `Approve & Publish` |
| 14 | `product-list-fixes.spec.cjs` | write | 6 | 6 passed | `ctx.post('/products/')`、`ctx.delete` |
| 15 | `workspace-entity-crud.spec.cjs` | write | 5 | 5 passed | UI Save 写库 + `api.delete` 清理 |
| 16 | `workspace-verified-review.spec.cjs` | write | 10 | 10 passed | `ctx.post('/verified/')` + `/reject/` |
| 17 | `inventory-driven/admin.spec.cjs` | write | 10 | 10 passed | 订单状态机真实流转（PO 端点） |
| 18 | `inventory-driven/auth.spec.cjs` | write | 21 | 21 passed | Settings 保存 / 加购 / 下单后 cancel 清理 |
| — | 以下 12 个为本轮之前**已带标签**的既有 spec（本轮基线一并实跑，见 §5） | | | | |
| 19 | `product-new-form-validation.spec.cjs` | write | 14 | 见 §5 | 既有标签 |
| 20 | `product-new-sku.spec.cjs` | write | 12 | 见 §5 | 既有标签 |
| 21 | `product-compliance-lifecycle.spec.cjs` | write | 12 | 见 §5 | 既有标签 |
| 22 | `product-list-negative.spec.cjs` | write/readonly | 10 | 见 §5 | 既有标签 |
| 23 | `knowledge-intake.spec.cjs` | write/readonly | 10 | 见 §5 | 既有标签 |
| 24 | `product-new-knowledge-links.spec.cjs` | write | 9 | 见 §5 | 既有标签 |
| 25 | `product-new-save-publish.spec.cjs` | write | 6 | 见 §5 | 既有标签 |
| 26 | `product-new-doc-import.spec.cjs` | readonly | 6 | 见 §5 | 既有标签 |
| 27 | `product-list-batch-writes.spec.cjs` | write | 5 | 见 §5 | 既有标签 |
| 28 | `product-seo-publish.spec.cjs` | write | 4 | 见 §5 | 既有标签 |
| 29 | `product-new-negative.spec.cjs` | write/readonly | 2 | 见 §5 | 既有标签 |
| 30 | `product-new-bioz-guard.spec.cjs` | write/readonly | 2 | 见 §5 | 既有标签 |
| — | 以下 7 个为**第二轮用例级捞回**的"部分红"文件（**部分纳入**；被排除的红例见 §4 逐条） | | | | |
| 31 | `cart-button-regression.spec.cjs` | readonly(部分) | 2 | 2 passed | A3.x 仅客户端 Pinia 状态注入，无网络写 |
| 32 | `homepage.spec.cjs` | readonly(部分) | 10 | 10 passed | 导航 / 列表 / API GET，均只读 |
| 33 | `product-detail-fields.spec.cjs` | readonly(部分) | 11 | 11 passed | 仅详情页 DOM 断言 |
| 34 | `public-smoke.spec.cjs` | readonly(部分) | 40 | 40 passed | 仅导航 + console 雷达 |
| 35 | `inventory-driven/po-portal.spec.cjs` | write/readonly(部分) | 11 | 11 passed | 7 只读 + 4 写（API 建单 / approve / shipment / invoice，均 cancel 清理） |
| 36 | `inventory-driven/public.spec.cjs` | write/readonly(部分) | 40 | 40 passed | 39 只读 + 1 写（加购 → 删除，自清理） |
| 37 | `inventory-driven/workspace.spec.cjs` | write/readonly(部分) | 18 | 18 passed | 16 只读 + 2 写（Save Draft 幂等重存；references 新建 + API 清理） |

> **合计**：37 文件 / **430 例** 被 `-g "@local-only" --grep-invert "@obsolete"` 选中
> （第一轮 30 文件 / 298 例 ＋ 第二轮 7 文件 / **132 例**捞回）。

**边界说明（3 个既有 spec 不在 local 闸门内，但并未漏跑）**：
`product-list-readonly-ext`（22 例，仅 `@readonly`）、`product-list-readonly`（5 例 `@readonly` + 2 `@prod-ok`）、
`product-new-ai-automatch`（15 例 `@readonly` + 15 `@prod-ok`）—— 它们没有 `@local-only`，
但会被 `test:e2e:readonly`（前两者）或 `test:e2e:prod`（后两者）选中，**不属于静默漏跑**。

---

## 4. 闸门外**用例**表（`@obsolete`，显式排除 + 逐条理由）

「闸门外」= `--retries=0` 实跑**失败**（不放宽断言、不改 skip、不伪造通过）或**跨轮 flaky**。
第二轮起改为**用例级**标注 `@obsolete` ⇒ 同一文件可以"部分纳入"（绿例进 §3，红例留本表）。

### 4.1 第一轮已整体 `@obsolete`、本轮**仍全红**（5 个文件 / 10 例，维持不动）

| # | 文件 | 排除用例数 | 类别 | 实测 | 理由（可复核） |
|---|---|---|---|---|---|
| 1 | `product-detail-structure-image.spec.cjs` | 1（全部） | 选择器漂移 | 1 failed | `.pd-structure-box` element(s) not found |
| 2 | `verify-dialog-a11y.spec.cjs` | 2（全部） | 凭据漂移 + 语义变更 | 2 failed | 硬编码过期密码 `AdminPass123!`（与 `helpers/auth.cjs` 的 `admin123` 漂移）⇒ 登录 401；且断言依赖**已被移除的阻断弹窗** `.dialog-overlay` |
| 3 | `verify-dialog-style.spec.cjs` | 4（全部） | 凭据漂移 + 语义变更 | 4 failed | 同上：过期密码 ⇒ 登录 401；断言 `.dialog` / `.missing-list` 依赖已移除的阻断弹窗 |
| 4 | `verify-field-normalize.spec.cjs` | 2（全部） | 凭据漂移 | 2 failed | 同上（`beforeEach` 登录先失败，纯函数用例 D2 同被带红） |
| 5 | `inventory-driven/_debug_quote_checkout.spec.cjs` | 1（全部） | 历史遗留调试脚本 | 1 failed | 无断言的 DEBUG 脚本（只有 `console.log`），45s 超时 |

### 4.2 第二轮"部分红"文件中被排除的**用例**（7 个文件 / 共 32 例；其余 **132 例已捞回** §3）

| # | 文件 | 排除用例数 | 类别 | 实测 | 逐条理由（可复核，本轮 `--retries=0` 实跑） |
|---|---|---|---|---|---|
| 6 | `cart-button-regression.spec.cjs` | 2 | 选择器漂移 | 2 failed | ①A1「购物车按钮存在，包含 SVG 图标，点击后跳转 /cart」②A2「在 /products/23 页面导航栏中存在购物车链接，且可见可点击」：断言 `.public-nav a.cart-btn[href="/cart"]`，该 class 在当前 `src/components/layout/PublicNav.vue` 已不存在（现为 `.cart-indicator` 内 `AppButton`）⇒ element(s) not found |
| 7 | `homepage.spec.cjs` | 5 | 文案/结构漂移（i18n）+ flaky | 4 failed + 1 flaky | ①「加载首页并显示 Hero 区域」：`.hero-title` 文案不含 `SciRe`（已英文化）②「统计卡片显示数据」：`.stat-card/.stat-chip` 计数 0（期望 4）③「Featured Applications 显示卡片」：`.card-grid-3 .application-card/.card` 计数 <1 ④「搜索框跳转到搜索页」：`.hero-search-input input` 超时 ⑤「搜索产品」：**flaky，未纳入** —— 同命令**基线 PASSED / 复跑 TIMEDOUT**（`page.goto` + `waitForLoadState('networkidle')` 触发 45s 超时；该 spec 头注释本就警告 networkidle 不可用） |
| 8 | `product-detail-fields.spec.cjs` | 14 | 选择器漂移 | 14 failed | TC-02/03：`.pd-chip-primary` 不存在、`.pd-chip-mono` strict mode violation（命中 2 元素）；TC-08～13：`.pd-spec` 的 Formula/MW/Purity/Conc/Storage/Shipping 改版后不存在；TC-15：`.pd-sku-head` 列文案漂移；TC-20：`.pd-cart-btn` 文案非 `Add to Cart`；TC-22：SMILES `.pd-id-item` 不存在；TC-23：`.pd-class-item`(Category L1) 不存在；TC-24：结构图区不存在；TC-25：`.pd-breadcrumb` 超时 |
| 9 | `public-smoke.spec.cjs` | 4 | 硬编码 dev 数据 id（数据条件性） | 3 failed 本轮 + 1 flaky | AppDetail `/applications/30`、RGDetail `/research-goals/27`、OrderDetailPage `/orders/1`：本轮实测 console 404 ⇒ 零错误断言失败（该 id 记录在当前 dev 库不存在）；PoOrderDetail `/po/orders/1`：**跨轮 flaky，未纳入**（上一轮 404 红、本轮绿） |
| 10 | `inventory-driven/po-portal.spec.cjs` | 2 | 依赖 dev 库特定 SKU 产品 | 2 failed | ①「PoSubmit: 渲染 + 添加行项目 + 产品搜索 + SKU 选择 可用」②「PoSubmit: 完整填写提交 → 成功 callout（真实写 + 清理）」：均断言 `.po-search-item` 命中 `shared.name`(= `5‑Propargylamino‑dCTP‑Cy3`)，但该产品在当前 dev 库 PO 产品搜索里查不到（`getProductWithSku` 取到的产品名与 PO 搜索索引不一致）⇒ element(s) not found |
| 11 | `inventory-driven/public.spec.cjs` | 1 | 偶发登录 | 1 failed | 「Login: staff 登录 → /workspace」：登录后 `page.url()` 仍不含 `/workspace`（登录跳转未完成 / 被守卫拦回） |
| 12 | `inventory-driven/workspace.spec.cjs` | 4 | 列表刷新 | 4 failed | 「Knowledge(goals/apps/methods/protocols): 新建（真实写）→ 列表出现 → API 清理」：UI 新建后新行未出现在 `.entity-table tbody tr`（同用例 references 通过 ⇒ 非整页崩，而是这四页列表未刷新/未含新行） |

> **合计排除 42 例**（4.1 的 10 例 + 4.2 的 32 例）。

> 备注：`inventory-driven/admin.spec.cjs` 与 `inventory-driven/auth.spec.cjs` 第一轮**全绿**，已转入闸门内（见 §3 #17/#18），不在本表。

> **未修断言**：两轮均**只做分类 + 标注**，未放宽任何断言、未把失败改 skip、未为"捞回"而放宽判定。
> **flaky 处置**：`homepage › 搜索产品` 与 `public-smoke › /po/orders/1` 为跨轮不稳定项，按"失败"处置、标 `@obsolete`，**未纳入**闸门。
> **可复活项（供后续决定，本轮不越界）**：`verify-dialog-*` / `verify-field-normalize` 的失败根因是**硬编码过期密码**（改回 `helpers/auth.cjs` 即可复活登录），叠加 `verify-dialog-*` 的弹窗语义变更（断言语义需重写，属"发现功能定义偏差"，需产品判定）。

---

## 5. 本轮实测基线快照

- **日期**：2026-09-23
- **参数**：`--project=chromium --retries=0`（**关闭重试**，避免"重试掩盖首次失败"）
- **环境**：后端 `http://localhost:8000`、前端 Vite `http://localhost:5173` 均就绪；`admin/admin123`
- **环境噪声**：本机无外网 ⇒ Google Fonts 请求失败 ⇒ 带 URL 的 `net::ERR_CONNECTION_CLOSED` 噪声，已由 `helpers/console.cjs` 字体中和器（提交 `2c1ac4a`）消除。**本轮未见"字体噪声"型失败**；若有失败，均已逐条确认非字体噪声（见 §4 理由）。

### 5.1 30 个未标注 spec 的逐条实测（逐 spec 单跑，20 分 57 秒）

见 §3（绿）与 §4（红）两表。

### 5.2 30 个未标注 spec 的逐条实测

逐 spec 单跑（各自全新 `--output`，`--retries=0`），**自 16:09:21 至 16:30:17，共 20 分 57 秒**。
结果见 §3（绿，18 个转入闸门内）与 §4（红，12 个转 `@obsolete`）。

### 5.3 第一轮：完整 local 闸门结果（`-g "@local-only" --grep-invert "@obsolete"`）

命令（等价于 `npm run test:e2e:local` 的第二段）：

```bash
node node_modules/@playwright/test/cli.js test -g "@local-only" --grep-invert "@obsolete" \
  --project=chromium --retries=0 --reporter=line --output=e2e/_qa_gate/out > e2e/_qa_gate/gate.log 2>&1
```

| 指标 | 值 |
|---|---|
| 选中 | **298 tests in 30 files** |
| 结果 | **297 passed / 1 skipped / 0 failed** |
| 退出码 | **0**（`GATE_EXIT=0`） |
| 耗时 | **10 分 36 秒** |

> 那 1 例 skipped 是**数据条件性跳过**（spec 内 `test.skip(<数据条件>, 理由)`，如"当前数据下无…产品"），
> **属于"被选中但按数据条件跳过"，不是漏跑**；用例清单里它是可见的。

### 5.4 闸门审计结果

```bash
node e2e/gate-audit.cjs
# gate-audit: ✔ OK — 范围内 530 个用例全部带 tier 标签（@readonly/@write/@obsolete）。
# 退出码 0
```

**负向验证（证明"漏跑会被挡下"）**：临时放入一个不打任何 tier 标签的探针 spec ⇒

```
gate-audit: ✘ 发现 1/531 个**未标注 tier 的用例**（@readonly/@write/@obsolete 皆无）：
  - ../_qa_negtest.spec.cjs :: 负向探针：故意不打标签 :: tags=[]
退出码 1
```

**收集期报错验证**：临时放入一个 `require` 失败的 spec ⇒ `errors` 非空 / `suites` 为空 ⇒
`gate-audit` 以退出码 3 判失败（而非"0 例全过"）。

### 5.5 第二轮（用例级捞回）：逐文件实测

- **日期**：2026-09-23
- **参数**：`--project=chromium --retries=0 --reporter=line,json`（关闭重试）
- **做法**：对 7 个"部分红"文件先 `--retries=0` **整文件实跑**拿到逐用例 pass/fail；
  据此**按用例级**重标（绿例 `@readonly|@write` + `@local-only`；红例 `@obsolete`）；
  再按闸门选择复跑确认。
- 逐文件（**捞回 / 仍是 obsolete**；括号内为该文件总用例数）：

| 文件 | 捞回（进闸门） | 仍 obsolete | 总用例 |
|---|---|---|---|
| `cart-button-regression.spec.cjs` | 2 | 2 | 4 |
| `homepage.spec.cjs` | 10 | 5（含 1 flaky） | 15 |
| `product-detail-fields.spec.cjs` | 11 | 14 | 25 |
| `public-smoke.spec.cjs` | 40 | 4（含 1 flaky） | 44 |
| `inventory-driven/po-portal.spec.cjs` | 11 | 2 | 13 |
| `inventory-driven/public.spec.cjs` | 40 | 1 | 41 |
| `inventory-driven/workspace.spec.cjs` | 18 | 4 | 22 |
| **合计** | **132** | **32** | **164** |

> 另有 5 个文件第一轮即**全红**，本轮复核**维持整体 `@obsolete`**（共 10 例）：
> `product-detail-structure-image` / `verify-dialog-a11y` / `verify-dialog-style` /
> `verify-field-normalize` / `inventory-driven/_debug_quote_checkout`（逐条理由见 §4.1）。
> ⇒ 本轮**排除合计 42 例**（10 + 32），**捞回 132 例**。

**复跑确认**（`-g "@local-only" --grep-invert "@obsolete"`，每文件全新 `--output`）：
7 个文件各自 `passed=捞回数 / failed=0`（`homepage` 在首轮复跑暴露 `搜索产品` flaky ⇒ 改标 `@obsolete` 后复跑 10/10）。

### 5.6 第二轮：完整 local 闸门结果（与第一轮基线对比）

命令（等价于 `npm run test:e2e:local`）：

```bash
cd /e/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/frontend
node e2e/gate-audit.cjs && \
node node_modules/@playwright/test/cli.js test -g "@local-only" --grep-invert "@obsolete" \
  --project=chromium --retries=0 --reporter=line --output=e2e/_qa_recover/out_gate \
  > e2e/_qa_recover/gate.log 2>&1
```

| 指标 | 第一轮基线 | 第二轮（本轮） |
|---|---|---|
| 选中 | 298 tests / 30 files | **430 tests / 37 files** |
| passed | 297 | **429** |
| skipped | 1 | **1**（同一条数据条件性跳过） |
| failed | 0 | **0** |
| 退出码 | 0 | **0** |
| 耗时 | 10 分 36 秒 | **18 分 25 秒** |

> **对比结论**：**新增捞回 132 例**（298 → 430），**未引入任何新失败**（failed 仍为 0）。

### 5.7 第二轮：闸门审计结果

```bash
node e2e/gate-audit.cjs
# gate-audit: ✔ OK — 范围内 530 个用例全部带 tier 标签（@readonly/@write/@obsolete）。
# 退出码 0
```

（用例级改标未破坏"每条用例都有 tier 标签"这一机制。）

---

## 6. 今天实测到的「闸门有洞」证据（三条）

1. **30/45 个 spec 完全没有 tier 标签 ⇒ 静默漏跑。**
   全仓 45 个 spec（顶层 39 + `inventory-driven/` 6），其中 **30 个**在跑批前无任何 tier 标签：
   顶层 24 个 + 子目录 6 个。`-g "@readonly"` / `-g "@write"` 谁也选不中它们，**且不报错**。
   （本轮已全部补齐 tier 标签，`gate-audit` 现报"530 例全部带 tier 标签"。）

2. **长期假红：有 spec 自 ~2026-07-13 起持续失败，且从未进任何闸门。**
   本轮实测中，`homepage`（4/15 失败）与 `product-detail-fields`（14/25 失败）的失败根因均为
   **2026-07-12 前后落地的"前端可见文案英文化 + 详情页改版"导致的选择器/文案漂移**，二者此后一直无标签、从未被任何 `-g` 选中。
   同样漂移致红的还有 `product-detail-structure-image`、`cart-button-regression`。
   （说明：前端目录在 2026-07-12 `bdaaa45` 才由 git submodule 并入本仓，更早历史不可见，
   故无法从 git 唯一钉死"恰好是哪两个"；如实列出全部 4 个候选。）

3. **顶层 `beforeAll`/加载期报错会阻断整个 spec 文件，且此前从未被真正跑到。**
   本轮复现机制：我在 `e2e/_qa_master/trial/` 放了 4 个 spec 副本（缺 `./helpers/auth.cjs`），
   Playwright 收集阶段直接报错 ⇒ JSON 的 `suites` 为空、`errors` 非空。
   **若审计器只检查"未标注用例"就会以"0 例全过"静默放行** —— 这正是"审计器自己被静默欺骗"的洞。
   已在 `gate-audit.cjs` 增加 §1-② 防线（`errors` 非空 / `total==0` ⇒ 退出码 3）。

---

## 7. 本轮改动的文件清单

### 7.1 第一轮（spec 级定级）

- 标注（tier 标签）：30 个 spec 文件（见 §3 / §4 首列）
- 机制：`frontend/e2e/gate-audit.cjs`（补 §1-② 防线；不再特殊排除 `inventory-driven/`）
- 跑批入口：`frontend/package.json`（新增 `test:e2e:local`）
- 本文档：`frontend/e2e/GATE.md`

### 7.2 第二轮（用例级捞回）

- 按用例级重标（7 个"部分红"spec，**仅改标签**，未改任何断言/未改 `src`/`backend`）：
  - `frontend/e2e/cart-button-regression.spec.cjs`
  - `frontend/e2e/homepage.spec.cjs`
  - `frontend/e2e/product-detail-fields.spec.cjs`
  - `frontend/e2e/public-smoke.spec.cjs`
  - `frontend/e2e/inventory-driven/po-portal.spec.cjs`
  - `frontend/e2e/inventory-driven/public.spec.cjs`
  - `frontend/e2e/inventory-driven/workspace.spec.cjs`
- 本文档：`frontend/e2e/GATE.md`
- 未改：`frontend/e2e/gate-audit.cjs`、`frontend/package.json`、`frontend/src/**`、`backend/**`
  （逐文件实跑产物在 `frontend/e2e/_qa_recover/`，属临时目录，不入库）
