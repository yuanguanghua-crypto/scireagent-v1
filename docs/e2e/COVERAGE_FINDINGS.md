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

## 已判定清单

| # | 页面 | I | P | S | R | V | A | B | 判定日 |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `/` HomePage | ✗ | — | — | ✓ | ✗ | ✓ | ✗ | 10-20 |

> 待填：其余 43 页（P0 优先，见 `COVERAGE_LEDGER.md` 的 P0 清单）
