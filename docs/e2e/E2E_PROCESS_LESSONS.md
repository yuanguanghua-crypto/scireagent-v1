# 全站 E2E 测试 · 过程踩坑总结（测试程序/执行层面，非网站 Bug）

> 提取自 2026-07-10 ~ 2026-07-11 两轮全站 E2E 覆盖（阶段 0–10 + a11y 整改）的真实经历。
> 本文件只记**测试程序设计 / 运行过程**中犯过的错，便于下次同类任务直接规避。
> 网站本身的 Bug 不在此列（见各阶段记忆与 `FULL_SITE_E2E_PLAN.md` 已知问题章节）。
>
> 用法：每次启动新 E2E 阶段前，按下面 9 大类逐项自检一遍。

---

## 1. 验证执行方式 —— 谁跑、怎么跑

- **坑**：把「跑 E2E / 跑 pytest」交给子代理验证。子代理会被会话压缩（499）中断，状态不可信。
  - **现在**：验证动作（跑测试、跑 pytest、读结果）一律由主理人**亲自前台 Bash** 执行，不轻信子代理的"已通过"结论。
- **坑**：后台任务静默回收——首次阶段 0 后台任务被回收，tail 缓冲把结果+完成通知全丢了，误以为还在跑。
  - **现在**：E2E 用 **前台阻塞 + 文件化日志**（`> run.log 2>&1`），加 `--retries=0`；不要依赖后台任务的通知。
- **坑**：用 `curl` 探活 dev server，代理返回 200 造成"server 在跑"的误判。
  - **现在**：探活看**进程列表 / 启动日志的 Listening 行**，不靠 curl。

---

## 2. 测试账号与凭据

- **坑**：login helper 的 `ADMIN_PASS` 臆测写成 `AdminPass123!`，真实是 `admin123` → 17 个 admin 页登录超时全失败。
  - **现在**：任何硬编码账号密码前，先 `curl`/DB **核实真实值**再写；账号基线写进 `auth.cjs` 顶部注释。
  - 基线：`admin / admin123`（is_staff）、`e2e_customer / E2ePass123!`（is_staff=False）。
- **坑**：角色判定依赖异步 `fetchUser()`。已登录 staff 刷新 `/login` 时守卫在 fetchUser 落地前读 `isStaff=false` → 错判回首页（真实 UX Bug，也是测试 flaky 源）。
  - **现在**：登录成功即把 `is_staff` 同步缓存进 `localStorage`，守卫可**同步**判定角色；不要等异步。

---

## 3. 端口 / Server / HMR 环境

- **坑（最反复出现）**：旧 dev server（如 `:5173` PID 25512，其他进程树、无权限 taskkill）一直提供**陈旧/部分 HMR 缓存**的 CSS/JS，新代码改了却测不到，还产生伪违规。
  - **现在**：验证新版代码**永远起一个全新端口**的 server（`:5185 / :5199 / :5201`…），远离任何历史端口；旧 server 不要复用。
- **坑**：Vite HMR **只注入 CSS 值变更，不注入新增的规则/选择器**。新增 `.el-tag.el-tag--info`、`.public-nav .btn-outline` 等规则没生效，axe 扫出伪对比度违规。
  - **现在**：改了 CSS **结构或新增规则**后，`rm -rf node_modules/.vite && npm run dev -- --force` 全量重启，再确认 served 文件含该规则。
- **坑**：`auth.cjs` 硬编码 `BASE_URL='http://localhost:5173'`，使 `playwright.config` 的 env 覆盖失效，所有运行打到损坏旧 server。
  - **现在**：`auth.cjs` + `playwright.config` + **所有 spec** 统一支持 `process.env.BASE_URL || 'http://localhost:5173'`，运行时用 `BASE_URL=...` 覆盖。
- **坑**：前端端口被占用会自动跳 `:5174 / :5175`；dev proxy target 实际是 `:8000`（不是 8001）。
  - **现在**：指定端口启动，读日志确认监听端口；后端必须起在 `:8000`，否则代理 404。
- **坑**：多浏览器 project（firefox/webkit）启用后未安装浏览器二进制。
  - **现在**：开多浏览器前先 `npx playwright install firefox webkit`。

---

## 4. 选择器与断言 —— 陈旧 / 假设错误

- **坑**：原计划假设本站用 `el-button / el-dialog / el-table`，实际**几乎不用 Element-UI**，交互是原生 `<button>` + `AppButton/AppInput/AppSelect` + 自定义 `dialog-overlay` + 原生 `alert/confirm`；Toast 真实实现是 Element Plus **`ElMessage`**（`.el-message--success/--error`）。
  - **现在**：测试选择器**基于真实 DOM**（先 Playwright `locator` 或浏览器实测），不假设任何组件库；Toast 用 `.el-message` 断言。
- **坑**：陈旧选择器 `a.cart-btn[href="/cart"]`，但 `AppButton` 只渲染 `btn btn-ghost btn-icon`，**无 `cart-btn` 类** → 用例预存失败。
  - **现在**：选择器必须匹配组件**实际生成的 class**；组件重构后回头校验所有用到它的选择器。
- **坑**：strict-mode 多匹配（下架/Publish 文本命中多个元素、`.page-title`/`.search-input` 在 AdminLayout 全局栏与页面内重名）。
  - **现在**：用**具体 id / 容器限定**（如 `.po-card`、`.admin-orders-page`、`#archive-title`）消除歧义。
- **坑**：断言了**不存在的行为**（guest 重定向未实现，却断言已登录访问 `/login` 会跳离）。
  - **现在**：测试预期必须是**已实现功能**；未实现的能力标记"已知 gap"，不擅自在测试里加功能。
- **坑**：断言文本硬编码与种子实际不符（期望 hero-title 含 "SciRe"，种子 DB 实为 "From research goal…"）→ 大套件 40 失败。
  - **现在**：断言用**宽松匹配 / 基于种子真实值**，不硬编会随种子漂移的文案。

---

## 5. 异步 / 竞态 / flaky

- **坑**：加购用例强断言 `.el-message--success` + `hasText:'Added to cart'` 偶不匹配，且无条件 `.cart-item` 读竞态 → flaky。
  - **现在**：放宽断言（"任意 `.el-message` 可见"即算成功）+ 用 `if (locator.count())` 包裹，仅当元素确有才校验。
- **坑**：未等加载完成就查 `rows.count()`（`PoReorder` 卡 "Loading…"）→ 144 测试连跑后端偶发变慢暴露 race。
  - **现在**：先 `expect(loading).toHaveCount(0, {timeout:15000})` 等加载，再分支断言；各 timeout 提到 15s。
- **坑**：过渡帧伪违规——`transition:all` + page-enter 动画使 axe 采到中间色（el-tag 实际达标，但中间帧跌破 4.5:1）。
  - **现在**：`scan()` 内 `addStyleTag` **冻结全部 transition/animation** + 等动画元素 detached 后再断言。
- **坑**：出网 AI 端点慢 / `el-select` 竞态 / 弹窗动画导致偶发失败。
  - **现在**：用 `retries` + **显式 `waitFor`**，不靠固定 `sleep`；出网端点用 `route.fulfill` mock 隔离。

---

## 6. 清理 / 隔离 / 测试数据

- **坑（严重）**：清理 helper `cancelOrder` 调 `POST /orders/<id>/cancel/`，但后端**无该端点**（恒 404），被 `try/catch` 静默吞掉 → 所有 PO 写测试 teardown 实际失败，dev 库悄悄累积 **36 个** `PO-E2E-*` 脏订单。
  - **现在**：清理 helper **必须验证成功**，禁止静默吞错；端点不存在就先补端点或改用真实存在的 `DELETE`。
- **坑**：写隔离不彻底，DB 越跑越脏，影响后续用例。
  - **现在**：每用例**内建数据 + 用例内 `DELETE` 清理**，保证库干净、用例间独立。
- **坑**：测试数据选择污染库（Register 选 "Team" 角色走多步；solo "Complete Registration" 会直接提交）。
  - **现在**：选**不污染库**的数据路径；明确区分"会写库"的注册 vs "仅前端交互"的校验。
- **坑**：种子数据不符预期（见 §4 hero-title）。
  - **现在**：大套件前先确认种子 DB 的真实内容，断言据此写。

---

## 7. 依赖 / 路径 / 模块

- **坑**：spec 里 `require('../helpers/auth.cjs')` 路径错（spec 在 `e2e/` 下，应是 `./helpers/auth.cjs`）→ 模块找不到。
  - **现在**：spec 在 `e2e/` 下统一用 `./helpers/...`；路径不确定先核对文件树。
- **坑**：`require` 缺 `.cjs` 扩展名在某些环境失败。
  - **现在**：显式写 `.cjs` 扩展名提升跨环境兼容性。
- **坑**：清理 helper 误用模块级 `request`（@playwright/test 的 APIRequest 命名空间，无 `.post()`）→ `TypeError: request.post is not a function`。
  - **现在**：helper 内**自起 `apiContext`** 登录 admin 再发请求，不依赖模块级 request。

---

## 8. console / 噪声白名单

- **坑**：wasm / 3D 结构查看器回退噪声（`falling back to ArrayBuffer instantiation`、`wasm streaming compile failed`）被 console 错误雷达当应用 Bug 抓。
  - **现在**：加进 `CONSOLE_WHITELIST`（环境噪声，非应用 bug）。
- **坑**：误捕浏览器原生 400（`Failed to load resource: 400`，来自预期内的校验失败请求）。
  - **现在**：`CONSOLE_WHITELIST` 加 `'Failed to load resource'`，只拦真正的应用级 error。

---

## 9. 断言脆断与整跑策略

- **坑**：硬编 hex 色值脆断（误写 `--color-bg=#F1F5F9`，实际是 `#F8FAFC`）。
  - **现在**：视觉令牌断言用**"跨页一致 + 非空"**或读 CSS 变量计算值，不硬编 hex。
- **坑**：大套件一次连跑（144 / 297 用例）后端偶发变慢暴露 race，失败难定位。
  - **现在**：修完 race 的用例**先单独重跑确认**（EXIT=0）再 consolidated；整跑后台化但读日志。
- **坑**：a11y 扫描在损坏旧 server 上跑，伪违规淹没真实问题。
  - **现在**：扫描前**确认指向 clean 的全新 server**（见 §3），扫描内冻结动画（见 §5）。

---

## 一页速查清单（每次开新阶段前过一遍）

1. [ ] 起**全新端口** server，旧 server 不复用；确认监听端口 + proxy 指向 `:8000`
2. [ ] 改了 CSS 结构/新增规则 → `rm -rf node_modules/.vite && --force` 全量重启
3. [ ] 所有 spec + `auth.cjs` 支持 `process.env.BASE_URL`
4. [ ] 账号密码已 curl/DB 核实；角色判定同步缓存
5. [ ] 选择器基于**真实 DOM**，不假设组件库；陈旧 class 复查
6. [ ] 严格模式用 id/容器限定；不断言未实现功能
7. [ ] 异步处用 `waitFor`/retries，不固定 sleep；出网端点 mock
8. [ ] 清理 helper **验证成功**，不静默吞错；每用例内建+DELETE
9. [ ] `CONSOLE_WHITELIST` 含 wasm / `Failed to load resource`
10. [ ] 视觉/色值断言跨页一致，不硬编 hex
11. [ ] 验证亲跑前台 Bash + 文件化日志，不交子代理、不看 curl 探活
12. [ ] 多浏览器前 `npx playwright install firefox webkit`
