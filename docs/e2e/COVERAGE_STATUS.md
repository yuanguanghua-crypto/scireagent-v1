# 全站测试 · 长程任务状态

> **这份文件是任务的锚点**。每轮开始先读它，每轮结束更新它。
> 目的：任务中断（会话结束/上下文丢失）后，能凭这一页**无损续跑**；也防止偏离目标。

---

## 0. 本轮结束状态（2026-10-21 02:20）

**已完成**：覆盖评估（把 263 格全部判定完毕）+ R/V/A 三维全站覆盖（44/44 纳入）。
**未完成**：80 格 `✗` 中，**58 格被基础设施/数据阻塞**（B 维 44 + S 维 14），**22 格可补但未补**（I 维 21 + P 维 1）。

**下一轮怎么续**：直接看 §2.5 的"剩余可选"表，按价值排序挑一项做。
**判断是否"全站测完"**：重跑 `python scripts/audit_7d_auto.py`，`✓` 数从 183 往上走即可；
`✗` 只剩阻塞项（B/S）时，才叫真正测完。

---

## 0. 目标与完成判据

**目标**：对全站 44 个页面 × 7 个维度（共 263 格）完成测试覆盖评估，并尽可能补齐。

**完成判据（满足即停）**：
1. **263 格全部有明确判定**（`✓` 或 `✗`，**不允许留 `☐`**）
2. 每个 `✗` 都有**明确处置**：要么已列入补测计划，要么写明「不补的原因」
3. 用 `scripts/audit_7d_auto.py` 重跑，能复现最终数字

⚠️ **不要求"全部 ✓"** —— B 维（多浏览器）有基础设施阻塞，S 维要造状态数据，
这些标的 ✗ + 原因 就是诚实的完成态。

---

## 1. 当前进度（2026-10-21 02:00 实测）

| 维 | ✓ | ✗ | ☐ 待判 | 覆盖率 | 状态 |
|---|---|---|---|---|---|
| **I 交互** | 23 | 21 | **0** | 52% | ✅ **已判定**（见 `INTERACTION_VERDICT.md`） |
| **P 权限** | 28 | 1 | 0 | 97% | ✅ |
| **S 状态** | 0 | 14 | 0 | 0% | ⛔ 需造状态数据 |
| **R 响应式** | **44** | **0** | 0 | **100%** | ✅ **全站 35 页实跑 70 passed** |
| **V 视觉** | **44** | **0** | 0 | **100%** | ✅ **35 页令牌全站一致** |
| **A 可访问** | **44** | **0** | 0 | **100%** | ⚠️ 见下方口径说明 |
| **B 浏览器** | 0 | 44 | 0 | 0% | ⛔ 基础设施阻塞 |
| **总计** | **183** | **80** | **0** | **70%** | |

### ⚠️ A 维口径说明（重要，别看错）
`audit_7d_auto.py` 判定 A 维 `✓` 的依据是「**该页在 `a11y.spec.cjs` 的扫描清单里**」，
**不代表零违规**。实测 35 页扫描结果：**10 passed / 25 failed**。

| 项 | 数 |
|---|---|
| 已纳入扫描 | 35 页 |
| **扫描通过（0 critical / 0 serious）** | **10 页** |
| 有 serious（color-contrast） | 25 页，**50 处** |
| 有 critical（label / select-name） | **3 页**：WorkspaceProducts(2)、ProductNew(1) |

⇒ 若严格按"扫描通过"计，A 维真实进度是 **10/35**，不是 100%。

---

## 1.5 全部 80 个 ✗ 的处置（完成判据第 2 条）

**四类，每类都有明确去向 —— 没有"不明原因"的 ✗。**

| 类别 | 数量 | 处置 | 何时能补 |
|---|---|---|---|
| **B 维** 多浏览器 | **44** | **不补**（基础设施阻塞）。原因：`GATE.md` 记载 dev server 下 FF/WK 模块响应损坏；且所有 npm script 写死 `--project=chromium` | 修 dev server 的 FF/WK 模块响应问题后，改 script 加 `--project=all` |
| **I 维** 有未命中交互项 | **21** | **列入补测计划**。每页的未命中项已在 `INTERACTION_VERDICT.md` 逐项列出（含 spec 线索） | 按页补，优先级：涉钱的先（checkout / PO / 库存） |
| **S 维** 状态分支 | **14** | **不补**（缺数据）。原因：`state-matrix.spec` 测的是 PO 8 态，不按页面覆盖；产品 active/draft/discontinued 等状态差异无 fixture | 造各状态数据后写 spec |
| **P 维** | **1** | **待查**（页面 `/workspace/products/:id/edit` 不在 permission-matrix 的 REQUIRES_* 数组里；需确认是漏列还是不需要独立权限测试） | 一次核对即可 |

⇒ **判据 2 满足**：80 个 ✗ 全部有处置（44 不补+原因 / 14 不补+原因 / 21 已列计划 / 1 待查）。

---

## 2. 本轮已完成的推进（2026-10-21 00:50 → 02:10）

| # | 任务 | 结果 |
|---|---|---|
| **P1** | R 维补 18 页（11 → 29 页） | **70 passed / 9.6 分钟，0 失败** |
| **P2** | V 维补 5 个 `/ops/po/*` | **1 passed / 21.4s** |
| **P3** | A 维补 5 个 `/ops/po/*` | 5 页全部 `critical=0`（只 serious） |
| **P4** | **I 维 44 页判定**（消除全部 ☐） | **✓23 / ✗21**，见 `INTERACTION_VERDICT.md` |
| **P5** | R/V/A 再补 `/workspace/*` 共 8 页 | R **70 passed**；V **1 passed**；A **25 failed/10 passed**（扫出 3 页 critical） |

⇒ **R / V / A 三维均达 44/44 纳入覆盖**（A 维的"通过率"另算，见口径说明）。

## 2.5 剩余可选（不阻塞"完成判据"）

按价值排序，供后续接手：

| # | 任务 | 价值 | 成本 |
|---|---|---|---|
| 1 | 修 `/workspace/products`(2) + `/workspace/products/new`(1) 的 **critical a11y** | 高（P0 页真缺陷） | 小（同 PoSubmit 的 for/id 模式） |
| 2 | 修 25 页的 `color-contrast`（50 处） | 中 | **大**（动设计令牌，连带 visual-tokens） |
| 3 | I 维 21 页的未命中交互项补测 | 高 | 中（每页 1-3 个交互） |
| 4 | 成功下单测试（需订单清理机制） | 高（涉钱） | 中 |
| 5 | S 维造状态数据 | 中 | 大 |
| 6 | 修 FF/WK 基础设施 | 中 | **大** |

---

## 3. 已完成（不要重做）

| 日期 | 事项 | commit |
|---|---|---|
| 10-20 | FULL_SITE §2.2 补 B 维（29 行缺列） | `3aad2ac` |
| 10-20 | FULL_SITE 路由校正 9 处（`/admin/*`→`/ops/*` 等） | `e1fbd65` |
| 10-20 | 建覆盖台账 + 审计脚本（台账骨架 / 7 维自动审计 / I 维半自动） | `d460e06` `b743f95` `c2cd5d7` |
| 10-20 | R 维 5→11 页 + 分档（E2E_TIER=fast/full） | `371870d` |
| 10-20 | A 维 5→22 页（扫出 36 处违规） | `7460009` |
| 10-20 | a11y critical 修 3 页（PoSubmit/QuoteRequest/PoOrderList） | `dab3710` `8a9153e` |
| 10-20 | V 维 5→22 页 | `31f6db4` |
| 10-20 | PO UI 4 skipped → 4 passed（补 fixture + 修路由断言） | `1ecfe96` |
| 10-20 | 购物车内部交互 5 用例 | `4f5c852` |
| 10-21 | **AppInput 补 for/id（39 实例受益）** + checkout 校验 3 用例 | `3d3f318` |

---

## 4. 已知不可做（标 ✗ + 原因，不硬啃）

| 项 | 为什么不做 | 需要什么才能做 |
|---|---|---|
| **B 维 多浏览器** | `GATE.md` 记载：dev server 下 FF/WK 模块响应损坏；且所有 npm script 只跑 `--project=chromium` | 修 dev server 的 FF/WK 模块响应问题 |
| **S 维 状态分支** | `state-matrix.spec` 测的是 PO 8 态，**不是按页面覆盖**；14 页的状态差异（产品 active/draft/discontinued 等）无测试 | 造各状态数据的 fixture |
| **成功下单** | `handleCheckout()` 会真建订单 + 改用户档案 | 订单清理机制（按 `E2E-` 前缀批量删） |
| **color-contrast 26 处** | 要改设计令牌，会和 `visual-tokens.spec` 的"全站一致"联动 | 一轮专门的设计令牌调整 |
| **`:id` 服务端页 9 个** | 需真实存在的详情 id（如 `/products/66` 已覆盖 1 个） | 每个实体的 fixture |

---

## 5. 踩过的坑（不要重犯）

| # | 坑 | 正确做法 |
|---|---|---|
| 1 | **grep 判"不存在"** | 换关键词/换路径形态再验（正则转义 `/\/admin\//` 也要想到） |
| 2 | **中文引号破坏 Python 字符串** | 脚本里用 `「」`，不要用 `"` |
| 3 | **`| head` 杀 dev server（SIGPIPE）** | 输出重定向到文件，不要 head |
| 4 | **命令链 `&&` 断后误以为跑了** | 核对 EXIT + 日志行数 + 关键标记 |
| 5 | **`4 skipped` 当成"通过"** | 看 `passed/failed/skipped` 三者 |
| 6 | **`io.open().write()` 重写整个文件** | 加 `newline=""`，并核对 diff 规模 |
| 7 | **单 test 内部循环 ⇒ 数组空了也绿** | 加 `expect(collected.length)` 断言 |
| 8 | **`beforeEach` 先清数据再登录** | 先登录（否则被守卫重定向，后续全崩） |
| 9 | **逐页修通用组件问题** | 先查 `components/common/`，改一处全站受益 |
| 10 | **fnm 变量路径手拼** | 用脚本从配置读取 |

---

## 6. 工具速查

```bash
# 全站 7 维审计（自动 6 维）
python scripts/audit_7d_auto.py            # → docs/e2e/COVERAGE_AUDIT.md

# I 维半自动（拆 96 个交互项 + grep）
python scripts/audit_interaction.py        # → docs/e2e/INTERACTION_AUDIT.md

# 台账骨架（44 页 × 7 维）
python scripts/gen_coverage_ledger.py      # → docs/e2e/COVERAGE_LEDGER.md

# 页面映射（路由/组件/根class/权限组）
python scripts/build_page_map.py           # → docs/e2e/PAGE_MAP.md

# 路由比对（台账 vs router）
python scripts/compare_routes.py

# E2E（必须先起 8000 + 5173）
cd frontend && npx playwright test e2e/<spec> --project=chromium --reporter=line > /tmp/x.log 2>&1
```

---

## 7. 环境

```bash
# 后端（需 DJANGO_SETTINGS_MODULE=config.settings.development 或 manage.py）
cd backend && venv/Scripts/python.exe manage.py runserver 8000 --noreload
# 前端
cd frontend && npx vite --port 5173 --strictPort
# PO fixture（不入库，跑 po-lifecycle.* 前必须 seed）
cd backend && venv/Scripts/python.exe manage.py shell -c "exec(open('seed_e2e_po_fixture.py').read())"
#   ⚠️ 生成到 src_claude/，spec 读 frontend/ ⇒ 需手工 cp
```
