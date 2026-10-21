# 全站测试 · 长程任务状态

> **这份文件是任务的锚点**。每轮开始先读它，每轮结束更新它。
> 目的：任务中断（会话结束/上下文丢失）后，能凭这一页**无损续跑**；也防止偏离目标。

---

## 0. 本轮结束状态（2026-10-21 09:40）

> ### 263 格全部判定完成：**✓263 / ✗0 / ☐0（100%）**
> `python scripts/audit_7d_auto.py` 可复现。

**⚠️ 但这不等于"全站达标"，务必先读 §1.5 的口径警示。** 覆盖率 100% 的含义是：
**每个维度都有一份真跑过的 spec 在覆盖该页**，不是"该页在所有维度上都合格"。
已知不合格项集中在 **a11y**（25 页 50 处对比度、1 处 critical）和 **10 条功能缺陷**
（见 `DEFECTS_FOUND.md`）。

**下一轮该做什么**：不再是补覆盖率，而是**修 `DEFECTS_FOUND.md` 的缺陷**（P0 两条优先）。
**判断是否"全站测完"**：重跑 `audit_7d_auto.py` 得 `✓263 / ✗0 / ☐0` 即算测完；
此后每次改代码用 `TEST_EXECUTION_CARD.md` 的 5 条命令做日常回归。

---

## 0.1 目标与完成判据（对照检查）

**目标**：对全站 44 个页面 × 7 个维度（263 格）完成测试覆盖评估，并尽可能补齐。

| # | 判据 | 状态 |
|---|---|---|
| 1 | 263 格全部有明确判定，**不允许留 `☐`** | ✅ `☐ = 0` |
| 2 | 每个 `✗` 都有明确处置 | ✅ `✗ = 0`（原有 80 个 ✗ 全部转绿，处置见 §2） |
| 3 | 用 `audit_7d_auto.py` 重跑能复现最终数字 | ✅ `✓263 / ✗0 / ☐0` |

---

## 1. 当前进度（2026-10-21 09:40 实测）

| 维 | ✓ | ✗ | ☐ | 覆盖率 | 依据 |
|---|---|---|---|---|---|
| **I 交互** | 44 | 0 | 0 | 100% | `INTERACTION_VERDICT.md`（41 页关键词命中 + 4 项原子级同义词） |
| **P 权限** | 29 | 0 | 0 | 100% | `permission-matrix.spec.cjs`（含 `/register` 的 guest 重定向补齐） |
| **S 状态** | 14 | 0 | 0 | 100% | `state-matrix` + `state-branches-commerce/po`（24 用例） |
| **R 响应式** | 44 | 0 | 0 | 100% | `responsive.spec.cjs`（`E2E_TIER=fast` 2 视口 / `full` 4 视口） |
| **V 视觉** | 44 | 0 | 0 | 100% | `visual-tokens.spec.cjs` |
| **A 可访问** | 44 | 0 | 0 | 100% | `a11y.spec.cjs`（**仅有覆盖，通过率见 §1.5**） |
| **B 浏览器** | 44 | 0 | 0 | 100% | `cross-browser-smoke.spec.cjs`（chromium 45 + firefox 45 实测） |
| **总计** | **263** | **0** | **0** | **100%** | |

---

## 1.5 ⚠️ 口径警示（**最重要的一节，别误读成"全站合格"**）

`audit_7d_auto.py` 的 ✓ 判据是「**该页在该矩阵 spec 的清单里**」，
**不证明断言充分，更不证明该页合格**。逐维说明：

| 维 | ✓ 的真实含义 | 已知不合格 |
|---|---|---|
| **A 可访问** | 该页被 axe 扫描过 | **35 页里只有 10 页零违规**；25 页有 `serious`（color-contrast 共 50 处）；`ResearchGoalIndex` 仍有 **1 处 critical**（疑 EP 库判定） |
| **B 浏览器** | 该页在 chromium + **firefox** 上加载不崩 | **WebKit 未覆盖**（本机系统代理无法绕开，见 `CROSS_BROWSER_BASELINE.md` §4）；且只验"渲染+零 4xx"，不验交互 |
| **I 交互** | 该页交互项的关键词被某 spec 覆盖 | 41 页为关键词命中；**4 项**（3步注册 / 多步 / 产品下拉）用了**原子级同义词表**（`ATOM_SYN`）匹配，已附证据 |
| **S 状态** | 该页的状态分支有 spec | 每页都逐分支穷举过，且优先写**反向断言**；个别分支构造不出（如"共享库恒有待审单"导致空态不可达），已在 spec 注释与报告里写明 |
| **P / R / V** | 在对应清单里 | R/V 是**真跑绿**（R: 70 passed / V: 全站令牌一致），P 是"在矩阵里访问得到" |

---

## 2. 本轮战果（2026-10-21 08:00 → 09:40）

**起点**：✓183 / ✗80（I ✗21、S ✗14、B ✗44、P ✗1）
**终点**：✓263 / ✗0 / ☐0

| # | 任务 | 结果 |
|---|---|---|
| 1 | **I 维 19 项空白**（4 组并行补） | 8 个新 spec、**39 passed / 1 skipped**，I 维 ✓26 → **✓44** |
| 2 | **I 维判定器补 4 项原子级同义词** | 修的是**假阴性**（措辞 vs 实现用词不同），每条附 spec 证据 |
| 3 | **S 维 14 页状态分支** | `state-branches-commerce`(11) + `state-branches-po`(13) = **24 passed**，S 维 ✓0 → **✓14** |
| 4 | **B 维根因更正 + 打通 Firefox** | 44 格从"判死"变"实测绿"，见 §2.5 |
| 5 | **P 维最后 1 格** | `/register` 与 `/login` 同为 `meta.guest` ⇒ 补 2 条重定向用例，**4 passed** |
| 6 | **修文档路由错误 1 处** | `/workspace/products/new/:id/edit` → 真实路由 `/workspace/products/:id/edit`（连带修 3 份文档） |

新增 spec 清单（均在 `frontend/e2e/`）：

| spec | 覆盖 |
|---|---|
| `ops-po-desk-gaps.spec.cjs` | `/ops/po/shipments` 创建发货单、`/ops/po/invoicing` 开票字段、`/ops/po/organizations` 订单查看 |
| `po-addresses-crud.spec.cjs` | `/po/addresses` 增→改→删闭环 |
| `order-error-paths.spec.cjs` | 4 个订单页的**错误路径**（故障注入）+ `/po/submit` 校验 |
| `register-wizard.spec.cjs` | 3 步注册向导（推进/回退保值/末步注入失败），**零写入** |
| `search-result-docs.spec.cjs` | `/search` 结果点击、`/products/:id` 文档链接 + 下载 200 |
| `settings-save-banner.spec.cjs` | `/settings` saveMessage 横幅（出现/4s 消失/切页清空） |
| `checkout-progressive-sections.spec.cjs` | `/checkout` 四段结构 + 支付方式分段推进/回退 |
| `workspace-entry-intake.spec.cjs` | `/workspace` 快捷入口、`/workspace/knowledge-intake` 产品选择 |
| `state-branches-commerce.spec.cjs` | 6 页状态分支（产品列表/详情、订单列表/详情、产品新建/编辑） |
| `state-branches-po.spec.cjs` | 8 页状态分支（提交/订单/详情/内部台/审核台/发货台/开票台） |
| `cross-browser-smoke.spec.cjs` | **全站 44 页**跨浏览器冒烟 + 清单完整性自检 |

---

## 2.5 ★ B 维：旧结论是**误判**，根因已更正

**旧记载**（`frontend/e2e/GATE.md` §8.1）：「`Vite dev server(5173)` + Playwright Firefox/WebKit
这条路走不通：FF 下所有模块加载报错」⇒ 判定跨浏览器闸门"待投入"，绕道 `vite preview` + dist。

**实测真因**：本机**系统代理**（FlClash）把 `http://localhost:5173/@vite/client` 接走并返回 **404**，
导致 SPA 从未挂载（`#app` innerHTML 长度 = 0）。证据链：

| # | 实验 | 结果 |
|---|---|---|
| 1 | FF 打开 dev server | `/@vite/client`、`/src/main.js` **404** + `NS_ERROR_CORRUPTED_CONTENT` |
| 2 | **`curl` 同一 URL（带 Firefox UA）** | **200 `text/javascript`** ⇒ 服务端没问题 |
| 3 | Chromium（msedge）同一 URL | 正常挂载 |
| 4 | FF + `network.proxy.type=0` | `#app` 挂载 **30329 字符**、失败请求 **0** |

**修法**（已入库）：`frontend/playwright.config.cjs` 的 firefox project 加
`use.launchOptions.firefoxUserPrefs = { 'network.proxy.type': 0 }`。
⚠️ 必须放 `launchOptions` —— 写成 `use.firefoxUserPrefs` 会被**静默忽略**（实测与没改一样）。

**WebKit 仍不可用**：`direct://` 报 `Could not resolve proxy name`，`127.0.0.1` 一样 404，
`NO_PROXY` 无效，且无 Firefox 那种开关 ⇒ 只能在无系统代理的机器/CI 跑。

基线数字见 `docs/e2e/CROSS_BROWSER_BASELINE.md`（firefox 45 passed / chromium 45 passed）。

---

## 3. 已发现的真实缺陷 → `DEFECTS_FOUND.md`

本轮测试的**最高价值产出**是 10 条真缺陷（2 条 P0、4 条 P1）。摘要：

| # | 级别 | 一句话 |
|---|---|---|
| D1 | **P0** | ~~`/ops/po/organizations` 订单查看忽略机构筛选~~ **✅ 已修 10-21**（后端 filterset 补 org；后端 5 例 + E2E 2 例） |
| D2 | **P0** | ~~`/orders` 无分页 ⇒ 第 21 单起看不到~~ **✅ 已修 10-21**（store 读信封 meta.count + 接 DataPagination；E2E 2 例） |
| D3 | P1 | ~~`/ops/po/invoicing` 一开票订单就消失~~ **✅ 已修 10-21**（队列改按状态过滤；E2E 正+反 2 例，含变异验证） |
| D4 | P1 | ~~`/ops/orders` 状态筛选缺 PO 流程态 + 无分页~~ **✅ 已修 10-21**（词表统一到 poConstants；补分页；E2E 3 例） |
| D5 | P1 | ~~`/po/orders` 筛选缺 quote_pending/quoted~~ **✅ 已修 10-21**（补 legacy 组 + 修 total + 补分页；E2E 3 例） |
| D6 | P1 | ~~`/po/orders/:id` RUO 声明恒显示~~ **✅ 已修 10-21**（serializer 加 is_ruo 三态；后端 3 例 + E2E 4 例，含变异验证） |
| D7 | P2 | a11y：25 页 50 处 color-contrast + 1 处 critical 未清 |
| D8 | P3 | `PoSubmit.vue:156-159` 第三条 alert 是**死代码** |
| D9 | P3 | `/po/addresses` 顶部 callout 文案过期（CRUD 其实全通） |
| D10 | P2 | `/orders` `/ops/orders` 错误只有 4 秒 toast，**静默失败**（接口挂了像"没数据"） |

---

## 4. 下一轮该做什么（按价值排序）

| # | 任务 | 价值 | 成本 |
|---|---|---|---|
| 1 | 修 **D7** color-contrast 50 处（25 页） | **最高**（现存最大一批，影响真实可读性） | **大**（动设计令牌 `main.css`，连带 `visual-tokens.spec.cjs`） |
| 2 | 修 **D8/D9/D10**（`PoSubmit` 死代码 alert、`/po/addresses` 过期文案、错误提示不统一只有 4s toast） | 中 | 小（都是局部改动） |
| 3 | WebKit 跨浏览器（需无代理环境/CI） | 中 | 大（环境依赖） |

**已修完的（2026-10-21 一天内核掉 6 条，2 条 P0）**：D1 跨机构订单可见 · D2 订单第 21 单起不可达 · D3 开票后订单消失 · D4 `/ops/orders` 筛选缺 PO 态+无分页 · D5 `/po/orders` 筛选缺 legacy 态 · D6 RUO 声明恒显示。

⚠️ 修完缺陷后**必须**把对应用例从"记录现状"改成"断言正确行为"，
例如 D1 的 `test.fixme` 要去掉变成真断言，否则修了也没人拦。

---

## 5. 踩过的坑（不要重犯）

| # | 坑 | 正确做法 |
|---|---|---|
| 1 | **grep 判"不存在"** | 换关键词/换路径形态再验（正则转义 `/\/admin\//` 也要想到） |
| 2 | **中文引号破坏 Python 字符串** | 脚本里用 `「」`，不要用 `"` |
| 2b | **反引号被 shell 执行** | `python -c "....\`AppInput\`..."` 里的反引号会被 bash 当命令替换，**内容静默丢失**。改文档用编辑器，或脚本从**文件**读写 |
| 3 | **`\| head` 杀 dev server（SIGPIPE）** | 输出重定向到文件，不要 head |
| 4 | **命令链 `&&` 断后误以为跑了** | 核对 EXIT + 日志行数 + 关键标记 |
| 5 | **`skipped` 当成"通过"** | 看 `passed/failed/skipped` 三者 |
| 6 | **`io.open().write()` 重写整个文件** | 加 `newline=""`，并核对 diff 规模 |
| 7 | **单 test 内部循环 ⇒ 数组空了也绿** | 加 `expect(collected.length)` 断言（`cross-browser-smoke` 就自检 `ALL.length === 44`） |
| 8 | **`beforeEach` 先清数据再登录** | 先登录（否则被守卫重定向，后续全崩） |
| 9 | **逐页修通用组件问题** | 先查 `components/common/`，改一处全站受益 |
| 10 | **fnm 变量路径手拼** | 用脚本从配置读取 |
| **11** | **看到"所有模块 404"就断定"浏览器/dev server 坏了"** | **先用 `curl` 从外部验同一个 URL**（本轮 B 维误判就是这么产生的，白扔了几轮） |
| **12** | **Playwright 配置项放错位置被静默忽略** | `firefoxUserPrefs` 不是 TestOption 顶层键，必须进 `launchOptions`；改完必须跑一条用例验证**真的生效** |
| **13** | **判定器"✓"被当成"合格"** | ✓ 只是"有覆盖"，通过率必须单独测（A 维 44 ✓ 但只有 10/35 真通过） |
| **14** | **并发跑 playwright 会用共享库互相污染** | 新建数据打唯一标记 + 只断言自己那条 + 禁用 `snapshotDb()` Δ 断言 |

---

## 6. 工具速查

```bash
# 全站 7 维审计（自动 6 维 + 读 I 维判定）→ 一跑就得 263 格结论
python scripts/audit_7d_auto.py            # → docs/e2e/COVERAGE_AUDIT.md

# I 维判定（拆交互项 + 中英同义词 + 原子级 ATOM_SYN）→ docs/e2e/INTERACTION_VERDICT.md
python scripts/judge_interaction.py

# 台账骨架（44 页 × 7 维）
python scripts/gen_coverage_ledger.py      # → docs/e2e/COVERAGE_LEDGER.md

# 页面映射（路由/组件/根 class/权限组）
python scripts/build_page_map.py           # → docs/e2e/PAGE_MAP.md

# 路由比对（台账 vs router）
python scripts/compare_routes.py

# E2E（必须先起 8000 + 5173）
cd frontend && npx playwright test e2e/<spec> --project=chromium --reporter=line --output=/tmp/x > /tmp/x.log 2>&1
#   跨浏览器（firefox 已可用）
cd frontend && npx playwright test e2e/cross-browser-smoke.spec.cjs --project=firefox --reporter=line
```

⚠️ **跑前先 `rm -rf test-results`**（或统一用 `--output=/tmp/...`）：`test-results` 文件数 >50 时
`safe-delete` 钩子会拦，表现为测试 5 秒失败。

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

**本机特殊约束**：系统代理（FlClash）会拦 `localhost` 的 ESM 请求 ⇒
① Firefox 必须 `network.proxy.type=0`（已配）；② WebKit 无法绕开；③ 其他命令行工具按需 `unset *_proxy`。
