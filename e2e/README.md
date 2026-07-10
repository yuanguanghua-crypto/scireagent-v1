# SciReAgent — E2E 测试套件 (Playwright)

对科研试剂平台 **SciReAgent** 研究工作台的端到端（E2E）冒烟测试。
以"真人操作浏览器"的方式逐一驱动左侧导航功能，断言各页面渲染出**真实数据**；
并对 Product 做完整的 **创建 → 编辑 → 清理** 闭环，验证 CRUD 全链路可用。

---

## 1. 套件目的

- **回归保护**：每次前端/后端改动后，快速确认工作台核心链路未被破坏。
- **真实数据断言**：不仅检查元素存在，还断言表格渲染出 >0 行真实业务数据
  （Products / Goals / Applications / Methods / Protocols / References）。
- **CRUD 闭环**：自动创建一个带 `E2E_TEST_` 前缀的临时产品，编辑后再删除，
  确保测试**不污染**生产/开发数据库（跑完库内应无任何 `E2E_TEST` 残留）。

---

## 2. 运行方式

> 前置：前端 dev server 须在 `http://localhost:5173`，后端 API 须在 `http://127.0.0.1:8000`，
> 且已安装 Chromium（`npx playwright install chromium`）。

在 `e2e/` 目录下执行：

```bash
# 方式 A（推荐）：使用受管 Node 22.22.2 的 npx
npx playwright test

# 若 npx 解析到其它 node 版本，用受管 Node 显式调用 CLI：
C:\Users\yuankaifeng\.workbuddy\binaries\node\versions\22.22.2\node.exe node_modules/@playwright/test/cli.js test
```

说明：本环境 `node_modules/.bin/playwright` 是 bash 包装脚本，直接 `node .bin/playwright` 会报错；
请走上面的 `cli.js` 入口或 `npx`。

常用参数：

```bash
npx playwright test --headed        # 看浏览器界面调试
npx playwright test --reporter=list # 仅列表输出
npx playwright test tests/workspace-e2e.spec.js  # 单文件
npx playwright show-report          # 查看 HTML 报告
```

配置文件：`playwright.config.js`（baseURL=:5173，headless=true，workers=1，
reporter=list+html+json，单测 `timeout: 90000`、`expect.timeout: 20000`，
`launchOptions.args: ['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage']`）。
**不**在此启动/停止 dev server，避免干扰正在运行的应用。

---

## 3. 已知约束 / 跳过项

| 约束 | 说明 |
|------|------|
| **AI 按钮跳过** | 校验 / 推荐 / AI AUTO MATCH 等按钮依赖外部 API key（`.env` 中缺失），点击会失败，故测试**刻意不点击**这些按钮。 |
| **需先起服务** | 本套件假设前后端已在运行；它只做测试，不负责启停服务。 |
| **单 worker 串行** | `workers: 1`、`fullyParallel: false`，避免 CRUD 用例间相互干扰（共享 admin 会话）。 |
| **console 守卫** | `helpers.js` 的 `page` fixture 会监听未捕获 JS 异常 / console.error，若出现则判测试失败（过滤了 favicon、vite HMR 等无害噪声）。 |
| **容器 Chromium 稳定性** | `launchOptions` 加 `--no-sandbox --disable-setuid-sandbox --disable-dev-shm-usage`，避免沙箱里 `/dev/shm` 过小导致浏览器崩溃（表现：`Target page, context or browser has been closed`）。 |
| **登录竞态（已硬化）** | 见第 5 节。`login()` + `gotoWorkspace()`（被弹回时**重新登录再重试**）消除竞态。 |
| **可复现性门槛** | 本套件要求**连续两遍 `9 passed / 0 failed`** 才算通过；单次绿不可作为完成依据（曾出现单次绿、复跑 flaky 的情况）。 |

---

## 4. 功能覆盖清单

共 **9 个用例**（全部位于 `tests/workspace-e2e.spec.js`）。以下为**干净库（109 条产品）**
下的真实渲染条数，可作为断言基线与复跑对照：

| # | 用例 | 覆盖 | 真实数据（干净库） |
|---|------|------|------------------|
| 1 | Authentication | 未登录访问 `/workspace` → 跳转 `/login`；登录后落到 Dashboard | — |
| 2 | Dashboard stat cards | 4 张统计卡均渲染真实数字 | Dashboard total=**109** |
| 3 | Products list | 产品表渲染真实行 | rows=**109** |
| 4 | Research Goals list | 目标表渲染真实行 | rows=**8** |
| 5 | Applications list | 应用表渲染真实行 | rows=**8** |
| 6 | Methods list | 方法表渲染真实行 | rows=**11** |
| 7 | Protocols list | 协议表渲染真实行 | rows=**89** |
| 8 | References list | 参考文献表渲染真实行 | rows=**187** |
| 9 | Product CRUD | 新建 → 编辑 → `finally` 清理（UI 删除或 API 回退） | 创建并清理，库恢复 109 |

> 注意：若某次运行前库里已有上一轮失败遗留的 `E2E_TEST` 孤儿，第 2、3 项会临时
> 显示 110；这不是断言失败（仍 `>0`），但应在收尾清理掉，使 `Product.objects.count()==109`。

所有断言均为**行为级正向断言**（如 `toBeGreaterThan(0)`），未为通过而放宽。

---

## 5. 根因与修复记录（登录竞态 + 去抖硬化）

**现象**：原先 Goals / References / Product CRUD 三个用例失败，快照均显示
**公开首页（含 Sign In / Register）**，而非工作台页面。单次修复后曾出现"单次绿、
复跑 flaky（8/9 且留孤儿）"——说明仅靠 `login()` 等待不够，竞态在**后续整页
`page.goto()` 重载**时仍会偶发，且容器内 Chromium 偶发崩溃。

**根因**：`isStaff` 来自 auth store 的 `user.value?.is_staff`，而 `user` 由
**异步** `getMe()`（store 初始化时触发）填充。路由 `beforeEach` 只同步检查 token，
真正的 `isStaff` 守卫写在各工作台页面的 `<script setup>` 里：
`if (!auth.isStaff) router.replace('/')`。于是**每次整页 `page.goto()` 重载**时，
守卫在 `getMe()` 返回前以 `isStaff=false` 运行，把页面弹回公开首页——这是一个
作用在**所有受保护路由**上的竞态，而非三个独立问题。

**修复（仅测试侧 `tests/`）——去抖硬化：**

1. `helpers.js` 的 `login()` 在 `waitForURL(/\/workspace$/)` 后，
   额外 `await page.waitForSelector('.stat-card', { timeout: 20000 })`，
   `.stat-card` 仅在 staff 会话下渲染，确保 isStaff 已 hydrate。
2. `gotoWorkspace(page, path)`：封装 workspace 路由跳转，等待工作台标记
   （`.stat-card / .products-table / .entity-page / .product-edit`）真正出现；
   **关键硬化**——若检测到被弹回公开首页（`/` 或 `/login`，或页面有 "Sign In"），
   **重新调用 `login(page)`（落到已 hydrate 的 /workspace）再重试**，直接打掉 auth 竞态，
   而不是干等。最多 6 次尝试，配合下述超时预算不会触发单测 40s 限制。
3. `playwright.config.js`：
   - `launchOptions.args: ['--no-sandbox','--disable-setuid-sandbox','--disable-dev-shm-usage']`
     消除沙箱里 `/dev/shm` 过小导致的浏览器崩溃（`browser has been closed`）。
   - `timeout: 90000`、`expect.timeout: 20000`，给重试留预算。
4. 规格文件中所有 `page.goto('/workspace/...')` 均已改用 `gotoWorkspace`
   （Authentication 用例中"未登录应跳转"的 `page.goto('/workspace')` 故意保留原样）。
5. **CRUD 清理放进 `try/finally`**：新增 `cleanupE2EProduct(page, id, catNo)` helper，
   **无论用例成败都删除本次创建的 `E2E_TEST_` 产品**（优先 UI 删除，回退到带会话
   token 的 `DELETE /api/v1/products/<id>/`），永不留孤儿。

**结果**：硬化后**连续两遍 9 passed / 0 failed**，且 Django shell 确认
`Product.objects.filter(catalog_no__contains='E2E_TEST').count()==0`、
`Product.objects.count()==109`。竞态与 flaky 已消除。

---

## 6. 测试数据清理

- CRUD 用例创建的产品带 `E2E_TEST_` 前缀；清理逻辑在 `try/finally` 中调用
  `cleanupE2EProduct()`，**无论成败必删**：优先 UI "永久删除"，失败回退到
  带会话 token 的 `DELETE /api/v1/products/<id>/`（权威移除，返回 2xx 即生效）。
- 收尾须确认库内无 `E2E_TEST` 残留（权威方式，SQLite dev 库）：
  ```bash
  cd backend && venv/Scripts/python.exe manage.py shell -c \
    "from apps.commerce.models import Product; \
     print(Product.objects.filter(catalog_no__contains='E2E_TEST').count(), \
           Product.objects.count())"
  # 期望输出: 0  109
  ```
  也可用 API 粗检：`GET /api/v1/products/?search=E2E_TEST` 应返回 0 条。
- 若某轮在 `finally` 之外异常导致清理未执行而遗留数据，可手动清理：
  ```bash
  TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
    -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}' \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['token'])")
  curl -X DELETE "http://127.0.0.1:8000/api/v1/products/<id>/" -H "Authorization: Token $TOKEN"
  ```

---

## 7. 目录结构

```
e2e/
├── playwright.config.js        # Playwright 配置
├── README.md                   # 本文档
├── probe.js                    # 一次性探测/调试脚本（非测试）
├── tests/
│   ├── helpers.js              # login() / gotoWorkspace() / cleanupE2EProduct() / selectFirstCascader() 等共享 helper
│   └── workspace-e2e.spec.js   # 9 个 E2E 用例
├── test-results/               # 失败快照（error-context.md）与 json 报告
└── playwright-report/          # HTML 报告
```
