# 全站测试 · 长程任务状态

> **这份文件是任务的锚点**。每轮开始先读它，每轮结束更新它。
> 目的：任务中断（会话结束/上下文丢失）后，能凭这一页**无损续跑**；也防止偏离目标。

---

## 0. 本轮结束状态（2026-10-21 09:40）

> ### 263 格全部判定完成：**✓263 / ✗0 / ☐0（100%）**
> `python scripts/audit_7d_auto.py` 可复现。

**⚠️ 但这不等于"全站达标"，务必先读 §1.5 的口径警示。** 覆盖率 100% 的含义是：
**每个维度都有一份真跑过的 spec 在覆盖该页**，不是"该页在所有维度上都合格"。
**2026-10-21 21:10 更新**：`DEFECTS_FOUND.md` 里 10 条缺陷**全部修完**（6 条 P0/P1 + 3 条小项 + D7），
a11y 也已从"25 页 180 处对比度 + 1 处 critical"降到 **35 页全部 0 critical / 0 serious**。

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
| **B 浏览器** | 44 | 0 | 0 | 100% | `cross-browser-smoke.spec.cjs`（**chromium 45 + firefox 45 + webkit 45** 实测） |
| **总计** | **263** | **0** | **0** | **100%** | |

---

## 1.5 ⚠️ 口径警示（**最重要的一节，别误读成"全站合格"**）

`audit_7d_auto.py` 的 ✓ 判据是「**该页在该矩阵 spec 的清单里**」，
**不证明断言充分，更不证明该页合格**。逐维说明：

| 维 | ✓ 的真实含义 | 已知不合格 |
|---|---|---|
| **A 可访问** | 该页被 axe 扫描过 | ✅ **2026-10-21 起为真通过**：35 页全部 0 critical / 0 serious（原 25 页 180 处对比度 + 1 critical 已清零，见 D7）。仍非「无障碍完美」——只覆盖 wcag2a/wcag2aa 自动可检项 |
| **B 浏览器** | 该页在 **chromium + firefox + webkit** 上加载不崩 | ✅ **2026-10-21 起三引擎全覆盖**（WebKit 经本地直连代理绕过系统代理，见 `CROSS_BROWSER_BASELINE.md` §4）。仍只验渲染 + 零 4xx，不验交互 |
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
| D7 | P2 | ~~a11y 对比度（**实测 180 处**，旧口径写 50）+ 1 critical~~ **✅ 已修 10-21**（180→0，改 6 令牌 + 4 处局部） |
| D8 | P3 | ~~`PoSubmit.vue` 死代码 alert~~ **✅ 已删 10-21** |
| D9 | P3 | ~~`/po/addresses` 过期 callout~~ **✅ 已删 10-21**（附守卫用例） |
| D10 | P2 | ~~错误只有 4 秒 toast（静默失败）~~ **✅ 已修 10-21**（抽 ErrorBanner 统一 4 页；E2E 7 passed） |

---

## 3.6 测试可信度基础设施（2026-10-21 补）

> 起因：多次把**环境问题**读成**应用问题**（后端没起 → 一堆 element not found；
> 代理接管 127.0.0.1 → WebKit 404 而 curl 200；外网字体抖动 → 随机超时）。

### ① 字体自托管（消除唯一的外网依赖）
- `index.html` 原本直接引 Google Fonts（`fonts.googleapis.com` + `fonts.gstatic.com`）
  ⇒ **每次开页都发外网请求**，代理/节点一抖就拖慢加载，造成 E2E 偶发超时；生产（大陆）同样慢。
- 现改为同源静态资源：`src/assets/fonts/*.woff2`（4 个文件，**126 KB**）+ `src/assets/css/fonts.css`。
  Inter / JetBrains Mono 取的是**可变字体单文件**（实测四档字重 woff2 的 md5 完全相同 ⇒ 用
  `font-weight: 400 700` 区间声明，只存一份）；只取 latin 子集（中文仍走系统字体栈）。
- 实测：页面外网字体请求 **0**；`document.fonts.check()` 三种字体均 true。
- **副作用（好的）**：`a11y + visual-tokens` 从 **5.9 分钟 → 31 秒**（不再等外网字体）。
- ⚠️ `dist/index.html` 仍是旧外链 ⇒ **下次发布必须重建前端产物**，否则生产仍依赖外网字体。

### ② 环境前置自检 `frontend/e2e/preflight.cjs`
跑批前先过一遍，把"环境不行"和"代码不行"分开：

| 检查 | FAIL 条件 | WARN 条件 |
|---|---|---|
| 后端 `:8000` | 不可达 / 返回非 JSON | 响应 > 3s |
| 前端 `:5173` | 不可达 / 200 但无 `#app`（被别的服务顶掉） | 无 `@vite/client`（不是 dev server）/ 响应 > 3s |
| 外网字体依赖 | **源码** `index.html` 仍引 Google Fonts | 仅 `dist/index.html` 仍是外链（产物未重建） |
| 本机代理端口 | — | 7890/7891/1080/10809 在监听 ⇒ 跑 WebKit 前建议关系统代理 |
| `backend/test_db.sqlite3` 残留 | — | 存在 ⇒ pytest 可能 `database is locked`；且会撞 pre-commit 变异演练 |

用法：`npm run test:e2e:preflight`（`test:e2e:local` 已内置为第一步）；`--strict` 让 WARN 也失败。

---

## 3.7 CI 里到底跑什么（2026-10-21 新增 · L6 接线）

`.github/workflows/ci.yml` 新增 `e2e-smoke` job（第 9 个 job）：

```
空库 migrate → seed_e2e_ci.py（最小种子）→ 起后端:8000 + 前端:5173
→ preflight 环境自检 → npm run test:e2e:ci（81 例只读）
```

**覆盖（81 例）**：`cross-browser-smoke`（44 页 + 1 自检）+ `a11y`（35 页）+ `visual-tokens`（1 条）。
**不覆盖**：其余 773 例（29 个 `@write` spec + 依赖开发库历史数据的用例）。

> ⚠️ **CI 绿 ≠ 全站绿**。CI 是"页面还能不能渲染 + 有没有 a11y 回归"的**底线闸门**；
> 全量 854 例仍只在本地跑。这条口径必须一直写在这里，别把 CI 绿当成验收。

### 关键设计（都是踩过才定下来的）
| 决定 | 原因 |
|---|---|
| CI 用**最小种子**而不是"照搬 dev 库" | dev 库有 127 产品 / 983 订单，CI 是空库，照搬必然大面积假失败 |
| 种子**显式造 `Product pk=66`** | 多个 spec 硬编码 `/products/66`，这个 id 必须真实存在 |
| `cross-browser-smoke` 的 `:id` 解析改为**尽力而为** | 原实现"任一实体缺失就 throw"，而每个用例都调 `getIds()` ⇒ 空库时 **44 页全红**（连 Home/Login 都红）。现在缺哪个只 `test.skip` 依赖它的几页并写明原因 |
| 先跑 `preflight` 再跑测试 | 把"环境没起来"和"代码坏了"分开，避免 CI 报一堆看不懂的 element not found |
| `PW_CHANNEL: ""`（空串） | Linux runner 没系统 Edge；config 里"变量存在但为空"⇒ 走 bundled chromium |

### 空库演练的意外收获（真缺陷）
第一次在空库跑，暴露了 **`el-empty` 空态描述**的 a11y 违规：
`.el-empty__description > p` 用 EP 默认 `#909399`，压在 `#f8fafc` 上只有 **2.94:1**
⇒ 4 个索引页（applications/methods/protocols/research-goals）在**空数据**时全部 serious。
本地开发库有数据、从未显示空态 ⇒ 之前的 a11y 全绿**掩盖了它**。
已覆盖 `--el-text-color-secondary → gray-600`（7.58:1）。

### 实测（2026-10-21）
| 场景 | 结果 |
|---|---|
| **空库** + 最小种子（8001/5174 隔离环境） | **77 passed / 4 skipped / 0 failed**；4 skip 全是缺实体的公开详情页（AppDetail/MethodDetail/ProtocolDetail/RGDetail），skip 原因写明"本库无该实体" |
| **本地库**跑 `npm run test:e2e:ci` | **81 passed / 1.3 分钟** |
| 本地库 a11y（35 页）回归 | **35 passed / 27.3s**，新令牌覆盖无副作用 |

---

## 3.8 L5 前后端契约检查（2026-10-21 新增）

`scripts/check_api_contract.py` + CI job `contract-check`。

**为什么是它**：D3（`o.invoice`）与 D6（`it.is_ruo`）是**同一类**缺陷 —— 前端读了一个后端不返回的字段，
判定恒真/恒假，页面完全看不出来。后端单测只测自己的形状、E2E 走真实数据也不报错
⇒ 之前**没有任何闸门能拦**。

**做法**：用项目自己的 `drf-spectacular` 生成 OpenAPI schema，抽出每个受检端点的 200 响应
（展开 `$ref`、剥掉分页/信封包装）得到「字段路径 → 类型」，与
`docs/e2e/API_CONTRACT_SCHEMA.json` 比对：
- **少了字段 / 类型变了** ⇒ FAIL
- **多了字段** ⇒ WARN（正常演进）

| 项 | 值 |
|---|---|
| 覆盖端点 | **4 个**（orders.list / orders.detail / products.list / products.detail），**158 个字段路径** |
| 未覆盖 | `admin_orders.list` / `basket.detail` / `auth.me` —— schema 里这 3 个端点没有 200 JSON 响应定义（自定义 APIView 未声明 serializer），**待补** |
| 是否依赖数据 | **不依赖**（输入是 schema 不是真实响应）⇒ 不用起服务，CI 里几秒跑完 |
| 反向验证 | ① 基线加 `[].invoice`（schema 里没有）⇒ 精确报「少了字段 `[].invoice` ★ 前端可能正在用它」，EXIT=1 ② 把 `grand_total` 类型改 `integer` ⇒ 报「类型变了」，EXIT=1 |

> ★ 第一版是"抓真实响应存快照"，实测**天然脆弱**：字段集依赖数据形态（购物车空 ⇒ items 空数组
> ⇒ 元素字段全"消失"），在 CI 薄种子下大面积假 FAIL。改用 schema 后才稳定。

**已知局限（写在脚本头部）**：不知道该前端实际用了哪些字段 ⇒ 删"没人用"的字段也会 FAIL（故意偏保守）；
只保证字段存在与类型，不保证运行时值语义。

---

## 3.9 notifications 补到 P0 量化线（2026-10-21 新增）

`apps/notifications` 是风险评分里的 **P1（静默失败）**，但此前**只有 5 条测试**且全在"发送侧"，
"入队侧"（模板渲染 / 多收件人 / 缺变量 / 附件）**一条没测**。按方案 §2.5 的量化线补齐：

| 文件 | 用例 | 覆盖 |
|---|---|---|
| `tests/test_enqueue_render.py`（新） | **24** | `render_template` 边界 6 · `EmailService.enqueue` 10 · 模型 3 · 序列化器契约 4 · key 唯一 1 |
| `tests/test_send_command_branches.py`（新） | **13** | `--force` / `--limit` / 非 PENDING 不处理 / `next_retry_at=null` 也投递 / cc 逗号解析 / 附件缺失跳过 / 成功清 last_error / 单封失败不中断 / 退避阶梯 / FAILED 不重试 / 输出文案 |
| `tests/test_send_outbox.py`（原有） | 5 | 主干：正常发送 / 未到点跳过 / HTML 替代体 / 失败重试 / 超限 FAILED |

合计 **42 条**（原 5 → 42）。

### 固化下来的三个"静默失败"语义（这是本次的主要价值）
1. **缺模板变量渲染成空串**（不抛错、不保留 `{name}` 原文）
   ⇒ 会发出"Hi , your order  is ready"这种缺词邮件。把现状钉住，将来改行为必须显式改测试。
2. **模板未配置时直接用调用方的 subject/body**（可能是空）
   ⇒ 会发出空主题邮件，而**不报错**。断言"如实使用传入值"，让"漏配模板"变成可见事实。
3. **附件路径不存在时跳过**，整封仍发出（不因附件丢了就发不出去）。

### 变异验证（守卫必须有测试）
| 变异 | 结果 |
|---|---|
| 删掉 `render_template` 的 `except: return text` 兜底 | ✅ `test_malformed_placeholder_returns_original` 变红 |
| `enqueue` 的 `next_retry_at=timezone.now()` 改成 `None` | ✅ `test_pending_is_immediately_deliverable` 变红（这条正是"cron 永远捞不到"的防线） |

> 写测试时我自己也错了一次：退避阶梯把 `retry_count 1→2` 也写成 60s，实测是 300s。
> 读码 `idx = min(retry_count, len(...)) - 1` 才对得上，已按代码修正（并写进测试注释）。

---

## 3.10 前端组件单测（vitest，2026-10-21 引入）

此前 **59 页面 / 44 组件 / 0 组件单测**，全靠 E2E（分钟级）。现在有了毫秒级反馈层。

| 项 | 值 |
|---|---|
| 框架 | vitest 5 + @vue/test-utils 2 + **happy-dom**（比 jsdom 轻） |
| 配置 | `frontend/vitest.config.mjs`（**不复用** vite.config：那里面挂着 tailwind 插件与 dev 代理，单测用不到） |
| 用例 | **51 条 / 6 文件**，跑完约 **2 秒** |
| 覆盖组件 | `ErrorBanner`(8) · `AppInput`(14) · `AppSelect`(9) · `DataPagination`(6) · `StatusBadge`(7) · `EmptyState`+`LoadingSpinner`(7) |
| 入口 | `npm run test:unit`（watch 模式 `test:unit:watch`） |
| CI | 第 8 个 job `unit-tests` |

### 第一次跑就抓到 2 个真问题（E2E 全绿也发现不了）
1. **`AppInput` 的 label 与输入框从未真正关联**（详见 `DEFECTS_FOUND.md` D11）
   —— Element Plus 的 `el-input` **吞掉 `id`**，所以 `<label for="v-0">` 指向不存在的元素。
   而 axe 不报（placeholder 兜住了可访问名）⇒ D7 全绿也没暴露。
2. **`AppSelect` 的 `|| 'Select an option'` 是无效兜底**（EP 会用自己的 `Please select` 覆盖）。

### 方法论收获（写进组件本身与测试注释）
- **"看起来关联上了" ≠ 关联上了**：必须断言**最终 DOM**（`input` 上的 `aria-label`/`id`），不能只看模板写了 `:for`。
- **EP 的属性透传规则要逐项实测**：`aria-label`/`name`/`data-*`/`placeholder` 会透传，**`id` 不会**。
- **保留"事实断言"**：`AppInput.spec.js` 里有一条 `expect(input.attributes('id')).toBeUndefined()`，
  哪天 EP 开始透传 id 它会红 —— 提示我们"可以改回 id 路线了"。

### 顺带补上的扫描漏洞
a11y 的 `/checkout` 一直是在**购物车为空**时扫的 ⇒ 表单不渲染 ⇒ CheckoutPage 里 7 个带 label 的输入**从没被扫过**。
已新增用例「CheckoutPage（购物车非空）」：真加购 → 扫 → **可访问名精确断言** → 清空购物车（零残留）。
a11y 总数从 36 → **37 条**（35 页 + 令牌 + 表单态）。

---

## 4. 下一轮该做什么（按价值排序）

| # | 任务 | 价值 | 成本 |
|---|---|---|---|
| 1 | 修 **D7** color-contrast 50 处（25 页） | **最高**（现存最大一批，影响真实可读性） | **大**（动设计令牌 `main.css`，连带 `visual-tokens.spec.cjs`） |
| ~~2~~ | ~~修 D8/D9/D10~~ | ~~中~~ | **✅ 已完成（2026-10-21）** |
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
