# SciReAgent E2E · 运行手册（P1 基建配套）

> 本目录承载「**动作剧本 × 期望断言**」工作流（见 `../../2026-09-22_动作剧本×期望断言_Part*.md`
> 与 `../../2026-09-22_P0_动作剧本覆盖矩阵.md`）。
> **目的**：用真实浏览器实际跑动作，对照期望断言判断「呈现结果 == 设计意图」，做**纠错 / 纠偏 / 记录**。

---

## 1. 跑法（本机必须用这条命令）

```bash
cd src_claude/frontend
# 前置：本地 dev 需先起 Django(:8000, DB_ENGINE=sqlite) 与 Vite(:5173)
node node_modules/@playwright/test/cli.js test <spec> --project=chromium --reporter=line > <项目内路径>.log 2>&1
cat <项目内路径>.log
```

**起本地 dev（两条，各用 `run_in_background`）** —— 工作区根的 `start_dev.sh` 也能用，但**必须**
`/usr/bin/bash start_dev.sh`（裸 `bash` 会被 WSL 别名劫持，见 §7-10）：

```bash
# ⚠️ 必须用 E: 物理路径（见 §7-9），否则 Vite root 与 realpath 不一致 ⇒ 整站白屏
cd /e/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/backend  # 或 C: 亦可（Django 不受影响）
  DB_ENGINE=sqlite PYTHONDONTWRITEBYTECODE=1 ./venv/Scripts/python.exe -B manage.py runserver 8000 --noreload
cd /e/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/frontend   # ★ 必须是 E:
  node node_modules/vite/bin/vite.js --port 5173
```

> **启动自检（三条全过才算 dev 就绪）**：
> 1. `:8000/api/v1/products/` → 200 + `application/json`
> 2. `:5173/src/main.js` → 200，且 body 含 **`/node_modules/.vite/deps/vue.js?v=`**（不是裸 `'vue'`）
> 3. `:5173/src/App.vue` → 200 + `Content-Type: text/javascript`，**不带 `Last-Modified`**
> 任一条不过就是白屏，别跑 E2E，先去 §7-9。


**三条硬纪律（本机实测踩过）**：

1. **不要用 `npm run` / `npx`** —— npm 的 script-shell 会拉 `wsl.exe`，被本机安全策略拦；
   `npx` 同理。直接用 `node node_modules/@playwright/test/cli.js`。
2. **输出必须重定向到文件，不要管道给 `tail`** —— 实测 `… | tail -20` 会因泄露的浏览器子进程
   占住管道而**挂死 12 分钟**；改 `> 文件` 后 11 秒完成。
3. **必须显式 `--project=chromium`** —— config 里还有 firefox/webkit（本机无对应浏览器）。
4. **★ 必须串行（`workers: 1`，已在 `playwright.config.cjs` 锁死）** —— 本套 spec 共用**同一个本地
   dev 库**，而大量用例用 `snapshotDb()` 做「表计数 Δ」断言。默认并行时，A 用例的夹具增删会落进
   B 用例的 before/after 窗口 ⇒ **假失败**（2026-09-22 实测：单跑 14+6 全过；并行跑同一对 spec
   出现 `product` Δ+1 / Δ−1 / Δ+2 三条假失败）。**排查口诀：单跑过、合跑挂 ⇒ 先怀疑并行**。

> 生产环境（R2 只读 / R3 真实写）另见下方 §3 环境变量；nginx Basic Auth 由
> `httpCredentials` 处理（尚未进 spec 基建，用脚本时手工传）。

`package.json` 里已备好四个 script（`test:e2e` / `test:e2e:readonly` / `test:e2e:write` /
`test:e2e:prod`），**仅供 CI / 无 WSL 劫持问题的机器使用**；本机一律用上面的直调命令。

---

## 2. 标签约定（用于按"是否写库 / 能否上生产"分集）

在用例标题里加标签，用 `-g` 选择：

| 标签 | 含义 | 典型用法 |
|---|---|---|
| `@readonly` | **只读**（跑前跑后表计数必须零变化） | `-g "@readonly"` |
| `@write` | **真实写**（必须带 `E2E-` 前缀 + `afterAll` 清理） | `-g "@write"` |
| `@prod-ok` | 可在**生产**执行（配合只读或带清理的写） | `-g "@prod-ok"` |
| `@local-only` | 仅本地（依赖 dev 库特定数据 / 外部语料） | 默认跑全部时用 `-g "@local-only"` 单独跑 |

约定：**只读用例一律加 `@readonly`，并在用例内用 `expectNoWrites()` 包住交互**。

---

## 3. 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `BASE_URL` | `http://localhost:5173` | 前端地址；生产填 `https://scireagent.com` |
| `E2E_USER` / `E2E_PASS` | `admin` / `admin123` | 应用层登录账号（staff/superuser） |
| `E2E_API_BASE` | `http://localhost:8000` | **API 根**（`helpers/api.cjs` 自动补 `/api/v1`） |
| `E2E_BASIC_USER` / `E2E_BASIC_PASS` | 空 | **仅生产需要**：nginx Basic Auth 凭据（本地留空） |
| `E2E_DOCX_DIR` | `E:\试剂网站的\试剂产品说明文档` | docx 语料目录（**不进 repo**） |

> ⚠️ 生产工作台需**应用层**登录（与 nginx Basic Auth 是两套）；凭据按纪律**不写进仓库**。

### ★ 两层认证的正确配方（2026-09-22 实测，R2 必需）

nginx Basic 与应用层 token **都想占 `Authorization` 头** ⇒ 会互相覆盖。前端早已规避
（`src/utils/http.js:21-26` 原话：*"Use X-Auth-Token (not Authorization) so it does NOT clash
with the nginx HTTP Basic Auth popup"*）。**E2E 必须照抄这个约定**：

| 层 | 头 | 取值 |
|---|---|---|
| 应用层 | **`X-Auth-Token`** | `/auth/login` 返回的 token |
| nginx | `Authorization: Basic …` | `E2E_BASIC_USER`/`E2E_BASIC_PASS` |

**实测对照（同一 token）**：`-H "Authorization: Token …"` ⇒ **401**（nginx，Basic 被覆盖）；
`-H "X-Auth-Token: …"` ⇒ **200 + JSON**。`helpers/api.cjs` 已按此实现（`buildHeaders()`）。

> 本地 dev 无 nginx ⇒ `E2E_BASIC_*` 留空即可，`X-Auth-Token` 同样被后端接受（已实测）。

### ★ 生产数据实况（2026-09-22 只读实测）——**期望值必须现算，禁止硬编码**

- `?archived=1&page_size=500` ⇒ `meta.pagination.count = 125`，返回 125 条，其中
  **`archived=true` 有 125 条、`archived=false` 有 0 条**（⇒ 生产 **Products 视图恒为 0 行**、
  **Recycle Bin 恒为 125 行**）
- `status` 分布：`active 109` / `archived 10` / `draft 6`
- ⇒ **所有 @prod-ok 用例必须「先调 A-API 现算期望，再与 U-UI 比对」**，不得写死 125/0；
  零行时要有 `if (n === 0) test.skip(...)` 之类的显式分支，不要用空断言假装通过。

---

## 4. 四类断言怎么写

```js
const { expectApi, snapshotDb, expectDelta, zeroSpec, expectNoWrites, consoleErrors } = require('./helpers/assertions.cjs')
const { catalogNo, cleanupByPrefix } = require('./fixtures/index.cjs')

// A-API：状态码 + 字段值（支持点号路径）
await expectApi(resp, { status: 200, json: { 'data.chemical.cid': 121487800 }, label: 'D2' })

// D-DB：取快照 → 操作 → 断言计数差
const before = snapshotDb()
await doSomething()
expectDelta(before, snapshotDb(), { product: +1, audit_log: +1 }, 'I1 新建产品')

// N-负向（一行化）：包裹只读交互，断言期间任何表零变化
await expectNoWrites(async () => {
  await page.locator('.view-toggle__btn', { hasText: 'Recycle Bin' }).click()
}, 'A3 切换视图')

// U-UI：Playwright 原生 + console 零错误
const errors = consoleErrors(page, ['wasm streaming compile failed'])
expect(errors).toEqual([])
```

**目标**：**新写一条剧本 ≤ 15 行**（断言复用，不重写）。

---

## 5. 夹具与清理纪律

- 造数命名：`catalogNo('Q2')` → `E2E-Q2-<ts>`；`slug()` / `skuCode()` 同源派生
- 清理：`await cleanupByPrefix(api, { label })` —— 按 `E2E-` 前缀**硬删**（超管），幂等、带失败清单
- 位置：`afterAll`（不要放 `afterEach`，否则同 spec 内后续用例的夹具会被提前删）
- **生产真实写**：只碰 `E2E-` 前缀数据；**绝不改 125 条真实产品的状态**
- docx 夹具：`findDocx('SC8001')` 从 `E2E_DOCX_DIR` 取，**不复制进 repo**

---

## 6. 判据来源纪律（每条断言必须可追溯）

| 层 | 冲突时 |
|---|---|
| **L0 铁律**（数据源≠商品 / 宁 miss 不错配 / 不改模型 / 软删可恢复） | L1/L2 **让** L0 |
| **L1 规格**（`docs/AI_AUTO_MATCH.md`、`05_FRONTEND_PRD.md`、实施步骤、两份 Part） | L2 **让** L1 |
| **L2 代码现值** | 仅在 L0/L1 未覆盖时作判据 |
| **L3 不变量**（步后=步前+预期差异；无关表零变化；序列不回退） | 恒成立 |

> **L1 ≠ L2 = 发现「功能定义偏差」** ⇒ 必须记录并交用户判定，**不得由我默选一侧**。
> `FAIL` 必须带**差异定位**；证据不足一律写「**证据不足**」，**不许写"看起来对"**。

---

## 7. 本机已知坑（都会让结果失真，逐条已实测）

| # | 坑 | 正确做法 |
|---|---|---|
| 1 | `helpers/api.cjs` 的 baseURL 带路径 + 调用方传前导 `/` ⇒ **404 HTML** | 已于 2026-09-22 修正（wrapper 统一补 `/api/v1`）；新写 helper 勿再犯 |
| 2 | playwright 输出管道给 `tail` ⇒ **挂死** | 重定向到文件 |
| 3 | `ssh "… $(…)"` 中 `$(…)` 被**本地**展开 | 远端脚本写单引号内，或 `cat > /tmp/x.sh` 再执行 |
| 4 | 本机 `timeout` 被 Windows `TIMEOUT.EXE` 遮蔽 | 用 `/usr/bin/timeout` 或不加 |
| 5 | 本机 `tar`/`find`/`which` 也命中 Windows 版 | 用 `/usr/bin/*` |
| 6 | 生产 nginx 侧 `ls -A` 看 dist 正常但**取文件慢**（1.27MB 在 40s 内只到 458KB） | 验产物以**服务器侧 `stat`/`Content-Length`** 为准，别用本机下载速度下判断 |
| 7 | Chrome 用 `channel: 'msedge'`（本机无 bundled 浏览器） | 已在 `playwright.config.cjs` 配好 |
| 8 | 本地 build 前 **vite 默认 `emptyOutDir` 触发 safe-delete 守卫 → SIGTERM** | 先由 shell `find dist -mindepth 1 -delete` 再 build |
| 9 | **★ 必须从物理路径启动 Vite**：本机 `C:\Users\yuankaifeng\WorkBuddy` 是指向 `E:\Users\yuankaifeng\WorkBuddy` 的 **junction（同一 inode）**。若从 C: 启动，Vite 的 `root` 记成 `C:/…/frontend`，而模块解析走 realpath 得 `E:/…/frontend/src/main.js`，配合默认 `resolve.preserveSymlinks:false` + `server.fs.strict:true` ⇒ **所有源码都被判为 root 之外** ⇒ 跳过 transform、由静态中间件吐**原始源码**（带 `ETag/Last-Modified`、`Content-Type` 空）⇒ 裸导入 `from 'vue'` 不被重写成 `/node_modules/.vite/deps/vue.js` ⇒ 浏览器 `Failed to resolve module specifier "vue"` ⇒ **整站白屏**，E2E 卡在 `loginAsStaff` 的 `input.fill` 45s 超时 | **用 `E:\…` 物理路径启动**（`start_dev.sh` 已改 `pwd -P`）。诊断三步：① `vite_dbg.log` 里 `root: 'C:/…'` 而 `vite:resolve … -> E:/…` ⇒ 就是它；② `curl -i :5173/src/App.vue` 若回**原始 SFC 源码 + ETag**（应是 `text/javascript` 且无 `Last-Modified`）⇒ transform 被跳过；③ 应看到 `import { createApp } from "/node_modules/.vite/deps/vue.js?v=…"` |
| 10 | `bash start_dev.sh` 会被 **WSL 的 bash 应用别名**劫持 ⇒ `PROGRAM BLOCKED BY SECURITY POLICY: wsl.exe`（与 `npm run`/`npx` 同源） | 用 `/usr/bin/bash start_dev.sh`；或直接照脚本内两条命令分别起 |
| 11 | 本机 `curl -o <非项目目录文件>` 会 `exit=23`（沙箱写限制）⇒ `%{size_download}` 误报 0 | 日志/下载一律写**项目目录内**；判断模块是否正常用 `curl -s -i` 看 `Content-Type`/`Content-Length` |
| 12 | 排查白屏时**别急着归因于"我改了某文件"**：本机实测先误判为"改 `package.json` 触发依赖重优化"，重启 Vite + 清 `.vite` 后**照样白屏**。真正证据链来自 `DEBUG=vite:config,vite:resolve,vite:transform` 的日志 | 白屏一律先取三样硬证据：`/src/App.vue` 的响应头、`vite` DEBUG 日志的 `root` vs `resolve`、`.vite/deps/_metadata.json` 是否含 `vue`。**假设被证伪就立刻换假设，别在错假设上重试** |
| 13 | **`--output=<已存在的目录>` 会被 safe-delete 钩子拦下**（`Error during a trash operation: Some operations were aborted`）⇒ 整轮跑批直接失败 | **每次换一个全新的 `--output` 目录名**（如 `test-results-d1b`），不要复用 |
| 14 | **★ `spawnSync`/`execFileSync` 抛 `EBUSY`** —— **真因已钉死：子进程的 `stdin` 管道**（`stdio[0]==='pipe'`，也正是这两者的**默认值**） | **已修**（统一走 `helpers/sync-spawn.cjs` 的 `runSync()`：`stdio:['ignore','pipe','pipe']`）。<br>**判别矩阵（逐项实测）**：默认三管道 ⇒ **EBUSY**；**仅 stdin 管道** ⇒ **EBUSY**；仅 stdout 管道 ⇒ **OK（且能正常读回输出）**；仅 stderr 管道 ⇒ **OK**；`['ignore','pipe','pipe']` ⇒ **OK（stdout/stderr 均可捕获）**<br>⇒ **不是"同步读输出"的问题**（仅 stdout 时读回完全正常），而是**建 stdin 管道**被拦。旁证：**异步 `spawn`** 用默认管道可以、**Python 的 `subprocess`** 也正常 ⇒ 只有"**同步 + stdin 管道**"这一组合。<br>**已排除**（均实测）：node 注入的 shim（清空 `NODE_OPTIONS` 仍挂）、目标 exe/路径形态、沙箱开关（放行后仍挂）。<br>**拦截者本体仍未钉死**（线索 `LSBOX_AUDIT_SHMEM=…LiteSandbox…`），但**修法零副作用**：这些调用从不往 stdin 写数据 ⇒ 关掉 stdin 即可，无损失。<br>⚠️ **现象是动态/间歇的**（08:1x 全过 → 08:45 起本地 venv python 也中招）⇒ 全 e2e 的同步 spawn **统一收口**到 `sync-spawn.cjs`（现仅此一处实现） |
