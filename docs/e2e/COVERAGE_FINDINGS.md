# 覆盖判定记录（人工 · 含证据）

> **这份文件是人工判定结果，不会被脚本覆盖。**
> `COVERAGE_LEDGER.md` 是自动生成的**骨架**（重跑会刷新）；本文件是**填进去的内容**。
>
> 每格必须带证据（`文件:行号` 或 grep 结果），**不接受"我觉得测了"**。

---

## 判定示范：`/` HomePage（P0，适用 5 维）

**判定日期**：2026-10-20
**相关 spec**：`homepage.spec.cjs`（15 test）、`responsive.spec.cjs`、`a11y.spec.cjs`、`public-smoke.spec.cjs`

| 维 | 判定 | 证据 | 结论 |
|---|---|---|---|
| **I 交互** | **✗ 部分** | FULL_SITE §2.2 要求「搜索/导航/分类 pills/CTA」。实测：`hero` 7 次、`featured` 3 次、`导航` 3 次 ✅；但 **`pills` 0 次、`CTA` 0 次** ❌ | **差两个交互没测** |
| **R 响应式** | **✓** | `responsive.spec.cjs` 含 `{ name: 'Home', path: '/', sel: '.home' }`，跑 4 视口：desktop 1280 / laptop 1024 / tablet 768 / mobile 375 | 覆盖 |
| **V 视觉** | **✗** | `homepage.spec.cjs` 里 `toHaveCSS` / `color` / `borderRadius` / `fontFamily` **全部 0 次** | **无任何设计令牌断言** |
| **A 可访问性** | **✓** | `a11y.spec.cjs:52` 有 `{ name: 'Home', path: '/', sel: '.home' }`，用 `@axe-core/playwright` AxeBuilder 扫描 | 覆盖 |
| **B 浏览器** | **✗** | `playwright.config.cjs` 定义了 3 个 project（chromium / firefox / webkit），**但所有 npm script 只跑 `--project=chromium`** | **FF/WK 从未跑过**（GATE.md 记载 dev server 下 FF/WK 模块响应损坏，是已知阻塞） |

**小计：2 ✓ / 3 ✗**

### 要补的三件事（按性价比）

| # | 补什么 | 怎么补 | 成本 |
|---|---|---|---|
| 1 | **I 维：分类 pills + CTA** | 在 `homepage.spec.cjs` 加 2 个 test：点 pills 断言筛选生效；点 CTA 断言跳转 | 小（沿用现有 helper） |
| 2 | **V 维：设计令牌** | 加断言 `expect(hero).toHaveCSS('border-radius', '4px')` 等 —— 只测**关键令牌**（主色/圆角/字体），不做像素级 | 中（要确认令牌实际值） |
| 3 | **B 维：FF/WK** | **先解决 GATE.md 记载的 dev server 模块响应损坏**，否则加了也跑不通 | **大**（基础设施问题） |

⚠️ **第 3 条不要贸然做** —— 它是已知阻塞，不是"补个 test"能解的。

---

## 判定方法（后续页面照这个做）

```bash
cd frontend/e2e

# 1) 找到涉及该页的 spec
grep -l "<页面组件名>" *.spec.cjs

# 2) I 维：FULL_SITE 要求哪些交互？逐个 grep
grep -c "pills\|CTA\|hero\|featured" <spec>

# 3) R 维：有没有视口测试
grep -c "setViewportSize\|viewport" <spec>
grep -A20 "name: '<页面名>'" responsive.spec.cjs    # responsive.spec 是否含该页

# 4) V 维：有没有样式断言
grep -c "toHaveCSS\|borderRadius\|fontFamily" <spec>

# 5) A 维：a11y.spec 是否含该页
grep "name: '<页面名>'" a11y.spec.cjs

# 6) B 维：实际跑几个浏览器
grep -n "project=" ../package.json
```

**判定口径（三个不要）**

1. **不要因为"有 spec 文件"就算 ✓** —— 要看断言是否覆盖该维
2. **不要因为"config 里配了 3 个浏览器"就算 ✓** —— 要看实际跑的是不是 3 个
3. **不确定就留 `☐`**，别猜 —— 半填的台账比空台账更危险

---

## 判定：`/login`（P0，适用 6 维）

**判定日期**：2026-10-20
**相关 spec**：`permission-matrix.spec.cjs`(2 test)、`responsive/a11y/visual-tokens`（**均不含此页**）

| 维 | 判定 | 证据 |
|---|---|---|
| **I 交互** | **✗** | FULL_SITE 要求「输入校验/提交/跳转/3步注册」。全仓 grep：`输入校验` 0 个 spec、`空密码` 0、`错误密码` 0 ⇒ **表单校验完全没测** |
| **P 权限** | **✓** | `permission-matrix.spec.cjs:98-110`：`staff 已登录访问 /login → 跳 /workspace`、`customer 已登录访问 /login → 跳 /` 两条都在 |
| **R 响应式** | **✗** | `responsive.spec.cjs` 只含 5 页（`/` `/products` `/products/66` `/ops/orders` `/workspace`），**不含 /login** |
| **V 视觉** | **✗** | `visual-tokens.spec.cjs` 同样只 5 页，**不含 /login** |
| **A 可访问性** | **✗** | `a11y.spec.cjs` 同样只 5 页，**不含 /login** |
| **B 浏览器** | **✗** | 所有 npm script 只跑 `--project=chromium` |

**小计：1 ✓ / 5 ✗**

---

## 判定：`/register`（P0，适用 6 维）

| 维 | 判定 | 证据 |
|---|---|---|
| **I 交互** | **✗** | 「3 步注册」流程**全仓无对应 test** |
| **P 权限** | **✗** | `permission-matrix.spec.cjs` 提 `/register` **0 次** —— 它只测了 `/login` 的已登录重定向，**注册页没测** |
| **R / V / A** | **全部 ✗** | 三个 spec 的页面清单都不含 `/register` |
| **B 浏览器** | **✗** | 只跑 chromium |

**小计：0 ✓ / 6 ✗**

---

## 🚨 由此暴露的全站性问题（比单页问题严重）

`responsive` / `a11y` / `visual-tokens` **三个 spec 覆盖的页面完全一样，都只有 5 页**：

```
/  /products  /products/66  /ops/orders  /workspace
```

而台账是 **44 页**。

| 维 | 覆盖率 | 说明 |
|---|---|---|
| **R 响应式** | **5 / 44 ≈ 11%** | 39 页从未测过视口 |
| **A 可访问性** | **5 / 44 ≈ 11%** | 39 页从未扫过 axe |
| **V 视觉** | **5 / 44 ≈ 11%** | 39 页从未断言设计令牌 |
| **B 浏览器** | **0 / 44（实际）** | config 配了 3 个 project，但**所有 script 只跑 chromium** |

⇒ **这三维是"抽样测试"，不是"全站覆盖"**。
⇒ 台账把这个真相显性化了 —— 在此之前，看到"有 responsive.spec / 有 a11y.spec"很容易误以为全站都覆盖了。

---

## ✅ R 维已扩容：5 页 → 11 页（2026-10-20 实测）

**改动**：`responsive.spec.cjs` 的 `PUBLIC` 3→7 页、`STAFF` 2→4 页（合计 **11 页**）：

```js
PUBLIC 新增：Search(/search) Login(/login) Register(/register) QuoteRequest(/quote-request)
STAFF  新增：WorkspaceProducts(/workspace/products) ProductNew(/workspace/products/new)
```

> ⚠️ 更正：我先前说「5 → 9 页」是算错了，实际是 **11 页**（PUBLIC 7 + STAFF 4）。
> 核对：`11 × 4 视口 + 2 导航 = 46 test`，与实测 46 吻合。

### 分档机制（已实现并实测）

用环境变量 `E2E_TIER` 控制视口数：

```bash
# 快档（默认）：2 视口（desktop + mobile）
npx playwright test e2e/responsive.spec.cjs --project=chromium

# 全档：4 视口
E2E_TIER=full npx playwright test e2e/responsive.spec.cjs --project=chromium
```

| 档位 | 页面 | 视口 | test 数 | **实测时长** |
|---|---|---|---|---|
| **fast**（默认） | 11 | 2（desktop+mobile） | **23** | **4.2 分钟** |
| **full** | 11 | 4 | **46** | **7.6 分钟** |
| full（扩到 44 页后，**推断**） | 44 | 4 | ~178 | **~30 分钟** |

**建议用法**

| 场景 | 用哪档 |
|---|---|
| 每次 PR / 提交前 | `fast`（4 分钟，可接受） |
| nightly / 发版前 | `full` |
| 改动了响应式/CSS | 必跑 `full` |

⚠️ **「44 页 ≈ 30 分钟」是推断**（按线性外推），未实测 —— 因为 44 页里含 `:id` 动态路由，需要先建 fixture 才能加。

### 仍待做
- `a11y.spec.cjs` / `visual-tokens.spec.cjs` 仍是 5 页（未扩）
- `:id` 类页面（如 `/applications/:id`）需要真实 ID，**不能直接加**，要先建 fixture

---

## 🚨 A 维扩容结果：22 页扫完，扫出 36 处真实 a11y 违规（2026-10-20）

**改动**：`a11y.spec.cjs` 的 `PUBLIC` 3→12 页、`STAFF` 2→10 页。
**实测**：**8 passed / 14 failed**（8.3 分钟）—— 失败**不是 sel 写错**（0 个 timeout），是**真违规**。

### 干净的 8 页

```
Home / Products / ProductDetail / LoginPage / RegisterPage / SearchPage / CartPage / Workspace
```
⇒ 这些页 `total=0 critical=0 serious=0`

### 有违规的 14 页

| 页 | total | critical | serious |
|---|---|---|---|
| **PoSubmit** | 3 | **2** | 1 |
| **ResearchGoalIndex** | 2 | **1** | 1 |
| **PoOrderList** | 2 | **1** | 1 |
| **QuoteRequestPage** | 1 | **1** | 0 |
| ApplicationIndex | 1 | 0 | 1 |
| MethodIndex | 1 | 0 | 1 |
| ProtocolIndex | 1 | 0 | 1 |
| SettingsPage | 1 | 0 | 1 |
| CheckoutPage | 1 | 0 | 1 |
| OrderListPage | 1 | 0 | 1 |
| AdminOrders | 1 | 0 | 1 |
| PoAddressList | 1 | 0 | 1 |
| PoReorder | 1 | 0 | 1 |
| PoDownloadCenter | 1 | 0 | 1 |

### 违规只有 3 类（共 36 处）

| axe 规则 | 级别 | 处数 | 含义 |
|---|---|---|---|
| `color-contrast` | serious | **26** | 文字对比度不达 WCAG 阈值 |
| `label` | **critical** | **6** | 表单元素没有关联 label |
| `select-name` | **critical** | **4** | `<select>` 无可访问名称 |

### ⚠️ 我**没有**为了让测试变绿去降级断言

这是关键选择：14 页失败 = **14 页真的有 a11y 问题**，不是测试写错。
如果去掉断言或删页面，就是**第二次"假绿"**（今天已经踩过一次 C8）。

**结论：测试保持红，债被显性化。** 修好一页就绿一页。

### 修复建议（按性价比）

| 优先 | 修什么 | 影响页数 | 成本 |
|---|---|---|---|
| 1 | **`select-name`**（4 处） | PoSubmit 等 | **小**（加 `aria-label`） |
| 2 | **`label`**（6 处） | PoSubmit / ResearchGoalIndex / QuoteRequestPage / PoOrderList | **小**（加 `<label for>` 或 `aria-label`） |
| 3 | **`color-contrast`**（26 处） | 10 页 | 中（要调设计令牌或文字色，可能影响视觉一致性） |

⚠️ 第 3 条要小心：改对比度会动**设计令牌**，可能和 `visual-tokens.spec` 的"全站一致"断言冲突 ⇒ 必须一起改。

---

## 已判定清单

> ⚠️ **2026-10-20 修正**：`scripts/audit_7d_auto.py` 自动审计上线后，发现我前两页的人工判定**有两处错误**：
> - `/` 的 **V 维**：我判 ✗（只看了 `homepage.spec.cjs`），实际 `visual-tokens.spec.cjs` **含 `/`** ⇒ 应为 **✓**
> - `/login` `/register` 的 **R 维**：我判 ✗（判定时还没扩容），实际今天已加进 `responsive.spec.cjs` ⇒ 应为 **✓**
>
> ⇒ **人工逐页判容易漏**（因为要同时记得 5 个 spec 的清单）。**以自动审计为准**。

| # | 页面 | I | P | S | R | V | A | B | 判定日 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `/` HomePage | ☐ | — | — | ✓ | **✓** | ✓ | ✗ | 10-20 修正 |
| 2 | `/login` | ☐ | ✓ | — | **✓** | ✗ | ✗ | ✗ | 10-20 修正 |
| 3 | `/register` | ☐ | ✗ | — | **✓** | ✗ | ✗ | ✗ | 10-20 修正 |

> 待填：其余 41 页的 I 维（其余 6 维已由 `COVERAGE_AUDIT.md` 自动判定）

---

## 📊 全站审计结果（自动 · 2026-10-20）

`scripts/audit_7d_auto.py` 一次算清 263 格：

| 维 | ✓ | ✗ | 待人工 | 覆盖率 |
|---|---|---|---|---|
| **I 交互** | 0 | 0 | **44** | **未判（必须人工）** |
| **P 权限** | 17 | 12 | 0 | **59%** |
| **S 状态** | 0 | 14 | 0 | **0%** |
| **R 响应式** | 12 | 32 | 0 | **27%** |
| **V 视觉** | 5 | 39 | 0 | **11%** |
| **A 可访问** | 5 | 39 | 0 | **11%** |
| **B 浏览器** | 0 | 44 | 0 | **0%** |

**总计：✓39 / ✗180 / ☐44（263 格）⇒ 已知覆盖率 39 / 219 = 18%**

### 这就是"全站测试"的真实起点

| 维 | 缺什么 | 补齐难度 |
|---|---|---|
| **B 浏览器** | 44 页从未跑 FF/WK | **大**（GATE.md：dev server 下 FF/WK 模块响应损坏） |
| **S 状态** | state-matrix 只测 PO 状态，未按页面覆盖 | 中 |
| **A 可访问** | 39 页没扫过 axe | **小**（把页面数组扩到 44 页） |
| **V 视觉** | 39 页没断言设计令牌 | **小**（同上） |
| **R 响应式** | 32 页没测视口 | **小**（同上，但需 fixture 支持 `:id`） |
| **P 权限** | 12 页不在矩阵 | 小 |
| **I 交互** | **44 页全未判** | **大**（必须逐页人工看交互是否都有断言） |
