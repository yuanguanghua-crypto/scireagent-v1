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

## 已判定清单

| # | 页面 | I | P | S | R | V | A | B | 判定日 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `/` HomePage | ✗ | — | — | ✓ | ✗ | ✓ | ✗ | 10-20 |
| 2 | `/login` | ✗ | ✓ | — | ✗ | ✗ | ✗ | ✗ | 10-20 |
| 3 | `/register` | ✗ | ✗ | — | ✗ | ✗ | ✗ | ✗ | 10-20 |

> 待填：其余 43 页（P0 优先，见 `COVERAGE_LEDGER.md` 的 P0 清单）
