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

## 3.11 迁移演练台账（2026-10-21 新增）

方案 §9.2 S6 要求"74 个迁移补记录 → 台账"。现在有了：**`docs/e2e/MIGRATION_DRILL_LEDGER.md`**
（由 `scripts/migration_ledger.py` 自动生成，重跑即重写，**勿手改**）。

### 结果（实测）
| 项 | 值 |
|---|---|
| 覆盖 | **10 个 app / 74 个迁移** |
| 迁移链路 | **10/10 通过**（正向 → 应用 → 幂等重放 → 反向回滚） |
| 存量数据覆盖 | **5/10**（bridges / commerce / documents / inventory / transactions） |
| 耗时 | 约 1m55s（含 10 次独立实例创建/迁移/回滚） |
| CI | 第 9 个 job `migration-drill`；台账若有变化会打 warning 提示提交 |

### 粒度（别误读）
**一个 app 一行**：drill 会把该 app 的**全部迁移**跑完整链路 ⇒ 74 个迁移都在这 10 条链路里。
**不是**"逐个迁移单独回滚"（那要 74×4 次实例创建，成本极高、收益低）。

### 为什么要分开报"链路"与"存量数据"
drill 的第②步（造贴近生产形态的存量数据）有三种结果，含义完全不同：
- **真造出数据** ⇒ 覆盖了"有存量数据时迁移"（证明力强）
- **跳过**（如"此刻迁移图里没有 commerce"）⇒ 该 app 实际是**空库迁移**（链路有效，但不证明"有数据也能迁"）
- **seed 报错** ⇒ 这才需要人看

台账把三者分开列，**不把"空库能迁"混成"有数据也能迁"**。

---

## 3.12 为了台账可信，先修了 3 个**工具**缺陷（2026-10-21）

`migration_drill.py` 本身有三个 bug，会让台账产生**错信息**，已修：

| # | 缺陷 | 后果 | 修法 |
|---|---|---|---|
| 1 | 目标 app 的**首个迁移**时，把 `"zero"` 当迁移节点传给 `project_state()` | 抛 `NodeNotFoundError: Node ('app','zero') not a valid node` ⇒ 整个演练被误判失败（③④⑤ 其实都通过）。**10 个 app 的 0001 全军覆没** | 目标是首个迁移时跳过造数，标"不适用" |
| 2 | seed 里的 `state.apps.get_model("commerce", ...)` 在**该 app 不在迁移图**时抛 `LookupError` | 记成"造数失败"⇒ 演练判失败。**6/10 app 因此红** | 捕获 `LookupError` 记为"跳过"，文案不含"失败"字样 |
| 3 | `seed_orders` 不传 `po_number`，落默认 `''`，而**历史版本该字段是 `unique=True`** | 第二条订单撞 `UNIQUE constraint failed: order.po_number`（inventory 卡在这） | 每条订单显式给唯一 PO 号，使造数在**任何历史 schema** 下都成立 |

> ⚠️ 这三个都是"**工具**的问题，不是迁移的问题"。修之前如果直接拿台账交差，会报 6/10 通过——
> 而后人排查会去怀疑迁移，白费功夫。**工具的错误结论比没有结论更贵。**

> 附带一条佐证：缺陷 3 反过来印证了 `Order.po_number` 的演进史——
> 现在它已是**条件唯一约束**（`models.py` 注释记录了"任意登录用户连建两单、第二单 500"那个 bug），
> 而演练跑在历史 schema 上时它还是 `unique=True`。

---

## 3.13 L7 安全专项（2026-10-21 新增）

L1–L6 都在问"功能对不对"，L7 问的是"**能不能被人钻**"。本轮做了三件事。

### 3.13.1 先建闸门，再点点排查

根源不在某个用例写错了，而在**结构性默认值**：`config/settings/base.py:163-189` 的
`REST_FRAMEWORK` **没有** `DEFAULT_PERMISSION_CLASSES` ⇒ DRF 落回 `AllowAny` ⇒
**任何忘记写 `permission_classes` 的写端点都是匿名可写**。这不是假设：
`SKUViewSet` 曾因此"匿名可写 SKU"，靠人工发现才补上（`commerce/api/v1/views.py:323` 有记录）。

所以第一件事是 `scripts/permission_audit.py`——**枚举全站每个端点实际生效的权限类**。

| 为什么不用 grep | 为什么不用 drf-spectacular 的 security 字段 |
|---|---|
| 视图可通过 `@action(permission_classes=[...])`、`get_permissions()` 动态返回、或 `as_view()` 的 initkwargs 传权限 —— grep 数 `permission_classes` 出现次数**证明不了安全** | 它给的是**推断**结果；本脚本**实例化真实视图类**去调 `get_permissions()`，与生产运行时判定同源 |

首跑结果（**实测**）：332 个端点（path × method）。

| 级别 | 数量 | 含义 |
|---|---|---|
| P0 | **7** | 匿名可写 —— **全部是登录/注册/找回验证/询价单提交等本来就该匿名的入口**，逐条核对后无一是缺陷 |
| P1 | 33 | 匿名可读（商品目录/搜索/sitemap/docs 等，需确认"本来就该公开"） |
| DYNAMIC | 0 | `get_permissions()` 无法静态求值（本期没有） |
| INFO | 292 | 需认证 |

> ⚠️ **第一版脚本报出 76 个 P0，是误报，根因值得记**：它把"`http_method_names` **允许**哪些方法"
> 当成了"端点**实现**了哪些方法"。DRF `dispatch()` 是
> `handler = getattr(self, method.lower(), self.http_method_not_allowed)`
> —— 类里没写 `put` ⇒ **恒 405，与权限无关**。
> 于是"只实现 `post` 的登录页"被报成 4 个匿名可写端点。
> **修法：判据改成 `hasattr(cls, method)`。** 76 → 7。
>
> 教训：**"匿名可写"的判据必须同时满足两点** —— 权限放行 **且** 该方法真的实现了。
> 少任何一条，报警都会多到没人看。

### 3.13.2 闸门形态：棘轮，不是一次性大签字

CI 里加了 `permission-check` job（第 8 个，现共 **10 个**）。

**为什么不让"40 个端点全部 `reviewed=true` 才 PASS"**：那样最省事的过法就是
**批量把 reviewed 写成 true** ⇒ 假签字 ⇒ 闸门退化成仪式。真实价值在**拦住新增**：

- 新出现的 **P0 / DYNAMIC** ⇒ FAIL
- 存量端点**严重度升级**（如 P1→P0）⇒ FAIL
- 存量 P1 作为**可见债务**打印出来，随处置逐条签字

**闸门已验证过（变异测试）**：把 `VerifiedApproveView` 的 `IsStaffUser` 临时改成
`AllowAny` ⇒ 立刻输出
`[新增 P0] POST /api/v1/verified/<int:pk>/approve/ (VerifiedApproveView)` 并 FAIL；
复原后 `git diff` 为空、闸门回 PASS。
**没做过变异验证的闸门等于没有闸门。**

### 3.13.3 这一层真正抓到的东西

权限清单是"面"，具体缺陷还得逐条挖。本轮抓到 4 组（D12–D15，详见 `DEFECTS_FOUND.md`）：

| 编号 | 缺陷 | 级别 | 一句话 |
|---|---|---|---|
| **D12** | `PATCH /verified/<pk>/` 任意登录用户可改任意人的"已验证适用性"证据 | P1 | 且 `curator` 不变 ⇒ 篡改**记在原审核人名下**，审计链被伪造 |
| **D13** | 匿名 `GET /organizations` 吐出客户名录 + 联系人 PII | P1 | 不传 `q` 时 `q=''` ⇒ `icontains('')` 命中全表 |
| **D14** | nginx `/media/` 同源直出，绕过全部按单授权 | P1 | 发票号 `INV-YYYY-NNNN` 可枚举；COA/SDS 的"未发布 404"门形同虚设 |
| **D15** | `unit_price` 可写（单点防御）+ `POST /orders/` 孤儿写口 | P2 | 一个复用序列化器的新端点就能让价格篡改敞开 |

**已排除的（同样是结论，别重复查）**：
- 购物车 `PATCH`/`DELETE` 虽然是 `AllowAny`，但**逐行核实过做了归属校验**：非本人一律返 404，且匿名行 `session_key=''` 与 `guest_*` 永不相等 ⇒ 两侧都咬不住。**不是 IDOR**
- 所有序列化器的 `password` 都是 `write_only`（`register`/`login`）；`UserSerializer` 只在 4 处被用，**全部是"本人"**，从不序列化他人
- 17 个 `ModelViewSet` 逐个核对过 `get_queryset()`：**没有**"有 `user`/`organization` 外键却 `return .all()` 且权限非管理员"的裸 IDOR
- `graph` / `search` / `site/navigation` 输出面只有公开知识实体，无 PII
- 全局异常处理器不拼 traceback/SQL/路径；生产 `DEBUG=False`（`production.py:5` 硬写）

### 3.13.4 ⚠️ 首次成文时的「已发现但未修」清单（第 1、2 条**已在当日修掉**）

> 保留这张表是为了留下"当初为什么不擅自修"的判断依据 —— 那两条属**产品决策**，
> 不是技术判断。决策已由用户拍板（同意修），结果见 §3.13.5。

| # | 问题 | 当初为何不擅自修 | 现状 |
|---|---|---|---|
| 1 | **注册时可自选 `role='procurement'`**（`serializers.py:15-18,29`，`validate` 只挡了 `editor`/`admin`）⇒ 等价于内部采购员：可改库存、批订单、开票、**把任意发票标记为已收款**（`services.py:519` 写死 `status=VERIFIED`）、拉全库订单（`transactions/api/v1/views.py:39-40`） | 前端 `RegisterPage.vue:78-85` **确有** "Procurement Manager" 注册卡片 ⇒ 是**产品设计**，不是笔误。堵它就会改变产品行为 | ✅ **已修（D16）**，见 §3.13.5 |
| 2 | 注册可**自助加入任意机构**（`organization_choice='join'` + 任意 `organization_id`），而 `Organization.approval_required`（`accounts/models.py:43`）**全仓无任何读取点** ⇒ 一旦"同机构"，`_is_order_viewer` 的机构分支（`po_views.py:319-320`）就放行该机构**所有**发票 PDF / PO 附件 / 代客户接受报价 | 同上，属产品/审批流决策 | ✅ **已修（D16）**，见 §3.13.5 |
| 3 | `DEBUG` 默认 `True`（`base.py:18` `getenv('DEBUG','True')`）+ `wsgi.py:3`/`asgi.py:3` 默认 `development` ⇒ 误部署时一个匿名请求可拿到约 71 KB 的 Django 技术页（traceback + settings + 绝对路径） | 改默认值影响本机开发体验，且生产链路已有 `production.py` 硬写 `DEBUG=False` + Dockerfile 切 settings ⇒ 属部署加固项，应先确认部署方式 | ⬜ 未修，见 §3.13.6 |
| 4 | `/api/schema/`、`/api/docs/` 匿名可拉（实测 408,643 字节，含 `/api/v1/admin/orders/`） | 是否公开 API 文档是产品选择（很多项目**故意**公开） | ⬜ 未修，见 §3.13.6 |

### 3.13.5 第 1、2 条 → **已修（D16，2026-10-21 当日）**

§3.13 首次成文时把「注册可自选 `procurement`」与「可自助加入任意机构」列为待决策项。
决策结果：**两条都修，且必须同批**。详细证据见 `DEFECTS_FOUND.md` D16，此处只记结论与依赖关系。

| 步骤 | 改动 | 为什么必须有 |
|---|---|---|
| ① | 注册 `role` 固定为 `researcher`（字段保留但不采信） | `procurement` = 供应商内部运营，保护 13 个内部端点（审批/开票/收款/改库存/机构管理）。**客户侧一件都用不上** |
| ② | join 增加**机构归属凭据**：注册邮箱域名 == 机构 `contact_email` 域名，且非公共邮箱域名 | 否则"有 org id 就进"，org id 还能匿名拿到 ⇒ 成为同机构后可读该机构全部发票/PO 附件 |
| ③ | `AddressPermission` 写权限 → **本机构成员** | 否则 ① 一上线，客户侧 `/po/addresses` 就 403，打断真实业务 |

**依赖方向必须记住**：③ 的放开**依赖** ② 的收紧。顺序反过来就是"先拆门再修锁"。

**为什么选域名匹配而不是人工审批**：运营人手少，人工审批是新增负担；域名由机构控制 DNS、伪造不了 ⇒ 零运营介入、零审批人工，同时挡住自助伪造。公共邮箱域名（gmail/qq/163/outlook…）必须排除，否则凭据没有排他性。

**前端一并对齐**：`RegisterPage.vue` 采购经理卡片的文案原为
"I manage procurement and **approve orders** for my organization" —— 这句话**承诺了一个客户拿不到的能力**（客户侧订单审批根本不是这条权限口径），已改为 "I handle purchasing and shipping details…"，并把卡片发送的 `role` 改成 `researcher`。

**验证**：新增 19 例（`test_membership_guard.py` 11 + `test_address_write_permission.py` 8），修前红 13 条，修后 `apps/accounts` **92 passed / 0 failed**（改动前 73）。
3 条旧 join 测试的桩数据补了 `contact_email`（钉的是旧契约，不是"改到绿"）；`test_po_gaps.py` 里那条 `test_create_requires_procurement` 改名为 `test_create_allowed_for_org_member`，**保留"organization 由后端按 user.organization 推入"这条关键断言**。

### 3.13.6 仍然「未修」的两条

| # | 问题 | 为什么不擅自修 |
|---|---|---|
| 1 | `DEBUG` 默认 `True`（`base.py:18` `getenv('DEBUG','True')`）+ `wsgi.py:3`/`asgi.py:3` 默认 `development` ⇒ 误部署时一个匿名请求可拿到约 71 KB 的 Django 技术页（traceback + settings + 绝对路径） | 改默认值影响本机开发体验；生产链路已由 `production.py` 硬写 `DEBUG=False` + Dockerfile 切 settings 兜底 ⇒ 属部署加固，需先确认部署方式 |
| 2 | `/api/schema/`、`/api/docs/` 匿名可拉（实测 408,643 字节，含 `/api/v1/admin/orders/`） | 是否公开 API 文档是产品选择（不少项目**故意**公开） |

---

## 3.14 外部数据源录制回放（cassette，2026-10-21 新增）

### 3.14.1 为什么必须做（以及为什么之前一直没做）
平台有 5 类外部依赖：PubChem、PubMed、ChEMBL、Europe PMC、Bioz，还有 LLM API。
它们此前的测试待遇只有两种：
- **完全不测**（外网不通就跳过）⇒ 容错逻辑、解析逻辑、降级链从来没被验证过
- **手写 mock 响应** ⇒ 手写的 JSON 与真实响应必然有差异，"测试全绿、真机 500"

外网本身也不可靠：同一台机器实测 PubChem **有时 1.8s 返回、有时 20s 超时**，
走代理还会 SSL 失败 ⇒ 同一个测试今天绿明天红，没人分得清是代码坏了还是网坏了。

cassette 把**真实响应**录下来再回放：离线可跑、且保真。

> 顺带一个事实变化：本轮开工时 PubChem 是超时的，**现在实测 `http=200 / 1.8s`**。
> 这正好说明"依赖外网的测试结果"有多不可靠 —— 所以录制回放不依赖网络好坏。

### 3.14.2 设计取舍（三处关键决定）

| 决定 | 为什么 |
|---|---|
| **默认 `off`**，必须显式 `SCIREAGENT_HTTP_MODE` 才启用 | 生产/开发/E2E 都依赖真实外部数据。任何"默认开"的设计都会在某天悄悄返回旧数据（3 个月前录的分子式），而且**没人看得出来** |
| **回放未命中抛 `CassetteMiss`，绝不静默回源** | 静默回源会让 CI 重新依赖外网，且测试表面绿、实际走网络 —— 那正是要消灭的假绿。报错里直接给出重录命令 |
| **key 只由请求语义决定**（method + scheme+host + path + **排序后**的 query + body），剔除 headers/cookies/超时 | 把 UA、时间戳、令牌算进 key 会让它永远不稳定；而 query 不排序会因调用方拼参顺序不同而 miss。`params` dict 与 URL 里已有 query **合并后**再排序（requests 就是这样发的） |

安全：cassette 会进仓库 ⇒ 响应头走**白名单**（只留 `content-type` / `retry-after`），
`Authorization` / `Cookie` / `X-Api-Key` 一律不落盘；body 超过 2MB **整条跳过录制**
（存半截数据会让回放"成功"但内容残缺，比 miss 更危险）。

### 3.14.3 落在哪一行（这是最关键的技术判断）
全仓**唯一**直接调 `requests` 的地方是 `core/datasource_client.py:171`（`_do_request`）。
PubMed / Europe PMC / Bioz / ChEMBL / PubChem enhancer 全部经
`request_with_resilience` ⇒ **录制只插这一处**，业务代码零改动。

### 3.14.4 ⚠️ 已知缺口：3 处 `urllib` 直连绕过统一客户端
第一版侦察**只搜了 `requests` / `httpx`，漏了 `urllib`** ⇒ 一度误判"已全部收口"。
换关键词复查后确认这 3 个文件绕过了统一客户端（也因此绕过了 cassette、限速、重试）：

| 文件 | 用途 | 后果 |
|---|---|---|
| `apps/documents/services/pubchem_fetcher.py:67-68` | PubChem SDS/COA 补全 | **PubChem 有两条路径**：`pubchem_enhancer`/`product_validator` 走统一客户端（可录），`pubchem_fetcher` 走 urllib（**不可录**） |
| `apps/bridges/services/evidence_miner.py:48,58` | 外部证据抓取 | 不可录 + 无统一限速重试 |
| `apps/knowledge/services/llm_extractor.py:146,209` | **LLM API 调用**（DeepSeek） | 不可录。而 T2 全量重跑曾因余额耗尽（HTTP 402）阻塞 ⇒ 录制回放**在这里价值最高** |

**没有擅自迁移**：迁移 LLM 调用涉及计费、超时、错误码语义，
不是一个"顺手改"的改动。已列为后续项，不混进本次。

### 3.14.5 落地内容与验证
- `backend/core/http_cassette.py`（新）—— 录制/回放核心，独立可测
- `backend/core/datasource_client.py` —— `_do_request` 里加 3 个分支（off/record/replay）
- `scripts/record_datasources.py`（新）—— **调真实业务函数**录制（手拼 URL 会与生产构造不一致 ⇒ 回放必 miss）
- `backend/cassettes/pubchem.jsonl`（2 条）、`pubmed.jsonl`（1 条）—— 真实录制，入库

| 验证 | 结果 |
|---|---|
| `core/tests/test_http_cassette.py` | **21 passed**（模式解析 / key 稳定性 9 条 / 端到端 record-replay / 最终 URL 记录 / 头脱敏 / 大 body 跳过 / 回放 503 仍可重试） |
| `core/tests/test_datasource_replay.py` | **5 passed / 0 skipped**（0 skip 说明 cassette 真被用上了） |
| **变异验证 A**：replay 未命中改成静默放过 | ⇒ `test_replay_miss_raises_instead_of_going_online` **红** |
| **变异验证 B**：响应头白名单失效 | ⇒ `test_authorization_and_cookie_never_persisted` **红** |
| **变异验证 C**：删掉「CID→SMILES」那条录制 | ⇒ `test_compare_smiles_offline_full_chain` **红**，而只依赖第一条的 `test_lookup_by_cas_offline` 仍绿 |
| 离线自证 | 3 条回放用例都把 `requests.request` 打成"一碰就炸"，并断言 `call_count == 0` |

**录制时发现并修掉的一个隐蔽缺陷**：第一版 `build_record` 存的 URL 是**调用方传入的**
`url`，而不是 requests **拼好的最终地址**。实测 PubMed 调的是
`request_with_resilience('GET', '.../efetch.fcgi', params={'db':..., 'id':...})`
—— 传入的 url 只有 `efetch.fcgi`，参数在另一个形参里。于是 cassette 里存成了
`efetch.fcgi`（**丢了检索条件**），回放出来的 `resp.url` 也是残的。
改存 `resp.url`，并补用例 `test_record_stores_final_url_with_params` 钉住
（重录后 PubMed 那条已是 `efetch.fcgi?db=pubmed&id=24151172&rettype=abstract&retmode=xml`）。
> 注意职责区分：**key 仍由「传入 url + params」算出**，与"存什么 url"无关 ——
> 前者决定命中，后者是可读性与下游正确性。

真实录制结果（线上 API 原始响应）：
`PubChemClient.compare_smiles('CC(=O)OC1=CC=CC=C1C(=O)O', '50-78-2')`
→ `{"match": true, "cid": 2244, "pubchem_smiles": "CC(=O)OC1=CC=CC=C1C(=O)O", "mismatch_fields": []}`
（回放拿到的是同一份真实数据，不是手写假值）

> ⚠️ 变异测试两次踩 CRLF 坑：`read_text()` + `\n` 锚点匹配不上 ⇒ 第一次"注入成功"其实没改到文件，
> 跑出来 20 passed 是**假绿**。改成 `splitlines()` 按行号替换才真正生效。
> **变异测试自己也要验证"变异真的注入了"**，否则等于没测。

---

## 3.15 L7 性能闸门（2026-10-21 新增）

### 3.15.1 三个刻意的取舍（先说为什么，数字才有意义）

| 决定 | 为什么 |
|---|---|
| **进程内测**（Django test client），不起服务不打网络 | 起 `runserver` + HTTP 打请求会把端口/连接复用/DNS/防火墙都算进去，同机两次能差 3 倍。进程内测的是「视图 + ORM + 序列化」的真实成本，重复测量稳定。代价：不含网络栈，**绝对值不能当 SLA**，只能同环境前后对比 |
| **不进 CI 做「相对基线」比较**，只保留绝对上限 | 单机测量天然有波动（GC/文件缓存/后台进程）。拿 p95 精确比基线，在共享 CI runner 上会**频繁假红** —— 那比没闸门更糟，因为人会开始忽略它 |
| **必须先断言 `status == 200`** | 不是理论风险，本脚本第一版就踩了：`ALLOWED_HOSTS` 不含 `testserver` ⇒ 全部端点返回 **400**，而 400 只要 8ms，看起来"性能极好"。**测量脚本不校验状态码 = 给自己造假数据** |

> ⚠️ 所以本闸门**没有加进 CI job**。这是判断，不是遗漏：CI 是空库 + 共享 runner，
> 端点返回空数组、耗时极低，2000ms 的绝对上限几乎永不触发 ⇒ 会变成"绿灯装饰"。
> **正确用法是发版前跑**：`--strict` 对比基线，`--factor 2.0`。

### 3.15.2 首测就抓到两个真问题

| 端点 | 修前 | 修后 | 性质 |
|---|---|---|---|
| `/api/v1/site/navigation` | **2.78MB / p95 267ms** | **20.4KB / p95 18.1ms** | 真缺陷，已修 |
| `/api/v1/site/home` | 42.3KB / p95 **322ms** | 未改 | **只报告**，见下 |
| `/api/v1/sitemap.xml` | 2.41MB / p95 548ms | 未改 | 合理（sitemap 本就该列全站） |

**`site/navigation` 的根因不是 SQL**：实测 SQL 只 28ms，**235ms 全在 Python 侧**——
把**全部 28,566 个 active application** 造成 dict 再序列化成 2.78MB。
而这份数据**没有任何消费者**：`frontend/src/stores/app.js` 的 `fetchNavigation()`
**全仓零调用**，也没有组件读 `appStore.navigation`。
⇒ 2.78MB 白花，且是**匿名可触发**的带宽放大点。
修法：`applications` 加 `limit`（默认 200 / 上限 2000），`meta` 回 `application_total`
与 `applications_truncated`。**这是契约变更**，已核实前端零消费方；
需要全量的走 `/api/v1/applications/`（有分页）。

**`site/home` 为什么只看不修**：profile 显示 **51 次查询**，其中一条 application 查询
**213ms**。这已经超出"加个缓存"的范围（涉及 site_home 的取数结构与索引），
按纪律**不在性能闸门这一轮顺手改业务逻辑**。已记为后续项。

### 3.15.3 闸门自身的有效性验证
**变异测试**：把 `navigation` 的 `apps = qs[:limit]` 改回 `apps = qs`（恢复全量）
⇒ 闸门精确报 **`/api/v1/site/navigation` p95 272.1ms = 基线 18.5ms 的 14.7x，FAIL**，
而其余 8 个端点 0.9–1.0x **无一条误报**。复原后 PASS。
⇒ 既证明"能抓退化"，也证明"阈值 2.0x 不会因正常波动误报"。

### 3.15.4 落地
- `scripts/perf_gate.py`（新）—— `--update` 建基线 / `--strict` 相对对比 / `--factor` 可调
- `docs/e2e/PERF_BASELINE.json`（新）—— 9 个匿名端点的 p50/p95/bytes
- `apps/knowledge/tests/test_site_api.py` —— 新增 5 例钉住 limit 行为（默认截断 / `?limit=` 生效 / 上限夹紧 / 非法值回落 / 小数据不报截断）
- `apps/knowledge/api/v1/site_views.py` —— `site_navigation` 加 limit

**基线维护纪律**：性能基线与机器强相关，**换机器 / 改 docker 资源限制后必须 `--update` 重做**
（旧数字在新机器上没有意义）。本机是 sqlite，生产是 PostgreSQL ⇒ 绝对值不可外推。

---

## 3.16 L4 并发（真实 PostgreSQL，2026-10-21 打通）

### 3.16.1 这一层为什么拖到最后
`select_for_update()` 在 **sqlite 上是 no-op**（实发 SQL 不含 `FOR UPDATE`），
而 sqlite 又是整库文件锁 ⇒ 并发用例在 sqlite 上要么**假通过**（锁根本没起作用）、
要么**假失败**（写冲突被放大成 `database is locked`）。**两种结果都不可信**，
所以那批用例一直"诚实 skip"，而"并发互斥性"始终只是**推断**。

### 3.16.2 环境决策：为什么装本机
| 选项 | 为什么不选 |
|---|---|
| 装服务器 | 生产 2 vCPU / 3.5GB，已在跑 gunicorn(3×4) + nginx + PG 16；并发测试本身就是压 CPU，会**抢线上资源**，而且测出来的数字被线上负载污染。且 pytest 会建/删 `test_*` 库，误伤生产代价极高 |
| 本机直连生产 PG | **连不上**：`docker-compose.yml` 的 `db` 服务**没有 `ports:` 映射**，只在 compose 网络内（`DB_HOST=db`）。要连必须把 DB 端口暴露到公网 —— 明确的安全倒退 |
| **本机独立集群** | ✅ 行级隔离，测试库随便建随便删，`dev≠prod` |

**版本差**：本机 **17.11**，生产 **16（alpine）**。`select_for_update` 的锁语义在
16–18 之间稳定，不影响本次验证结论；但记录在此，避免后人误以为版本完全一致。

### 3.16.3 落地形态（有一处环境限制必须知道）
winget 装 `PostgreSQL.PostgreSQL.17`，安装器退出码 1 但**二进制完整可用**
（`psql` / `pg_ctl` / `postgres` 均正常）。集群由 `initdb -A trust` 建在
`2026-07-08-11-22-32\pgdata-l4`（**git 仓库外**，不污染），端口 **5433**、
`listen_addresses=127.0.0.1`。

> ⚠️ **`initdb.exe` 与 `postgres.exe` 被本机安全策略拦截**（agent 侧执行会得到
> "命令被安全策略拦截" / `0xC0000409`），但 **`psql` / `pg_ctl --version` 正常**。
> 所以集群的**创建与启动需人工执行一次**（用户终端不受此限制），之后 agent 侧
> 可用 `psql` / `psycopg2` 正常连接跑测试。已排除 NTFS/端口占用/目录属主三个原因。

### 3.16.4 新增的两个并发不变量（断言业务事实，不是断言"代码写了锁"）
`apps/inventory/tests/test_pg_concurrency.py`（`django_db(transaction=True)`）：

| 用例 | 断言 |
|---|---|
| `test_allocate_does_not_oversell` | 库存 3、8 个并发各要 1 ⇒ **正好 3 成功 / 5 被拒**，最终 `available=0`、`allocated=3`（既不超卖也不少卖） |
| `test_receipt_does_not_lose_updates` | 8 个并发入库各 +1 ⇒ `available == 8`（读-改-写不丢更新） |
| `test_allocate_and_receipt_interleave_safely` | 入库与分配交错 ⇒ `available + allocated` **守恒**（锁的是同一个对象） |

### 3.16.5 ★ 变异验证：证明这些测试真的能抓到问题
一次就绿最需要警惕。**把 `apps/inventory/services.py` 里三处 `.select_for_update()` 全部摘掉**后重跑：

| 用例 | 变异后实测 |
|---|---|
| 不超卖 | **成功 5 个**（应为 3）⇒ **真超卖了 2 件** |
| 不丢更新 | 8 次 +1 后 `available = 7` ⇒ 丢了 1 次 |
| 总量守恒 | `available=1 + allocated=3 = 4`（应为 5）⇒ 凭空少了 1 件 |

复原后全部回到绿（md5 比对确认）。⇒ 这批用例**不是摆设**，且`select_for_update`
在这三条路径上**确实必需**。

### 3.16.6 订单号并发（原有用例，首次真跑通过）
`test_order_sequence.py::TestPostgresOnlyConcurrency` 此前在 sqlite 下 skip。
第一次在 PG 上跑**失败了**，但失败原因是**测试自己的设计问题**：
8 个线程共用**同一个 user 的同一份购物车**，第一个成功的 checkout 把它清空，
其余拿到 `EMPTY_BASKET`（实测 3 条 400）。原断言"8 个都成功"永远不可能成立，
而且它测的根本不是并发取号。
⇒ 改为**每个线程操作自己的购物车**、只共享同一个 `OrderSequence` 取号器。
修改后：8 线程并发 checkout，**单号两两不同、序号稠密 1..8**，通过。

顺带修了两处测试卫生问题（都不影响断言强度）：
- 失败时只记状态码 → 改为**连响应体一起记**（否则 `[400,400,400]` 无法区分
  "并发互斥失效"与"校验层拒绝"，而两者处置完全不同）
- worker 结束不关连接 → teardown 报
  `database "test_scireagent_l4" is being accessed by other users (4 sessions)`
  ⇒ 加 `connections.close_all()`

### 3.16.7 一键执行（并防"静默退化"）
`scripts/run_pg_tests.py`：
```bash
cd backend && venv/Scripts/python.exe ../scripts/run_pg_tests.py
```
它做三件脚本该做的事：
1. **前置检查**：5433 连不上就**直接退出（码 2）**，并打印启动命令 ——
   绝不"退化成 sqlite 然后假装成功"
2. 注入 `DB_*` 环境变量后跑全部 PG-only 用例
3. ★ **防静默通过**：退出码 0 时若输出里出现「需 Postgres」跳过，
   判 **FAIL（码 3）**。因为最危险的失败模式是 `DB_*` 没生效 ⇒ 回落 sqlite ⇒
   整批 skip ⇒ **退出码 0、看起来通过、并发一条都没验**。
   **已变异验证**：把 `DB_ENGINE` 故意改成 `sqlite` ⇒ 4 条全 skip ⇒ 脚本输出
   `❌ 有并发用例因「需 Postgres」被跳过` 并返回 **3**。

### 3.16.8 覆盖边界（诚实说明）
全仓 **23 处** `select_for_update`，本次实测覆盖：
- ✅ 订单号取号（`transactions/services.py:212`）
- ✅ 库存分配 / 入库 / 盘点（`inventory/services.py:33,144`）
- ⬜ **发票号取号**（`transactions/services.py:232`，与 OrderSequence 同构，未单独测）
- ⬜ 发货标记（`transactions/services.py:391,431`）
- ⬜ 其余 18 处

**没有声称"L4 全覆盖"**。已测的是风险最高的三处（钱与库存）。

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

## 5. 五条元规律（**能改变判断的**才留在这里）

> 这一节曾经是 14 条"踩过的坑"清单。清单的问题不是不真实，而是**越长越没人看**，
> 且大量条目属于通用素养（shell 转义、换行符、路径拼接）——踩过一次就有肌肉记忆，
> 写进铁律只会稀释注意力。单次环境事实更不该记：**过期数字比没数字更危险**。
> 所以压成下面 5 条。具体缺陷的完整证据在 `DEFECTS_FOUND.md`（D1–D16）。

| # | 规律 | 为什么（背后的真实实例） |
|---|---|---|
| **1** | **「没找到」≠「不存在」** —— 换关键词、换路径形态、换工具再验一次 | 只搜 `requests`/`httpx` 漏了 `urllib` ⇒ 误判"外部调用已全部收口"，实际有 3 处绕过；英文 grep 搜中文注释 ⇒ 假阴性；命令链 `&&` 断了却以为跑了；`\| head` 把输出截断，**你以为看到的就是全部** |
| **2** | **「绿了」≠「测了」** —— 看分母、看状态码、必须写反向断言 | A 维 44 个 ✓ 但只有 10/35 真通过；`skipped` 被当成恒定无害项；性能首测**全部 400**（8ms 看着"极快"）其实测的是错误页；`ErrorBanner` 只断言"出现"不断言"不该出现"⇒ 横幅常显却全绿；单测内部循环，数组空了也绿 |
| **3** | **「写了」≠「生效了」** —— 改完必须验证**改动真的落地了** | Playwright `firefoxUserPrefs` 放错位置被**静默忽略**；变异注入撞 CRLF 没改到文件却报"注入成功"⇒ 20 passed 是假的；a11y 令牌写 `:root` 无效、必须写进 `.el-table` 作用域；`beforeEach` 先清数据再登录 ⇒ 被守卫重定向，后续全崩 |
| **4** | **工具自己的错，比「没有结论」更贵** —— 它给出的错误结论会被当成事实沿用 | `migration_drill` 三个 bug ⇒ 误报 6/10 失败，后人会去怀疑**迁移本身**；`permission_audit` 首版把"允许的方法"当成"实现的方法"⇒ 76 个假 P0；`perf_gate` 首版写死 `id=1` ⇒ 永久假红，**而永久假红一定会被忽略** |
| **5** | **共享资源会互相污染** —— 并发/复用之前先问「它们共用什么」 | 两个 pytest 共用 `test_db.sqlite3` ⇒ 整片 ERROR，被误读成"测试是摆设"；并行 Playwright 共享库 ⇒ 需唯一标记 + 只断言自己那条；线程不关 DB 连接 ⇒ teardown 报 `being accessed by other users`；共用组件不修根因、逐页打补丁 ⇒ N 处行为不一致 |

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
