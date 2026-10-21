# 跨浏览器基线（B 维）

> 建立于 2026-10-21。**这份文件是 B 维判定的实测依据**：`scripts/audit_7d_auto.py` 要求
> 本文件存在且记录了 `firefox` 的 passed 数 > 0，才把页面判为 B 维 ✓（见该脚本 B 段注释）。

## 1. 结论

| 引擎 | 状态 | 依据 |
|---|---|---|
| **Chromium**（实际走系统 Edge，`channel: 'msedge'`） | ✅ 可跑 | 全站冒烟 45 passed |
| **Firefox** | ✅ 可跑 | 全站冒烟 45 passed（`network.proxy.type=0`） |
| **WebKit** | ✅ **2026-10-21 打通** | 全站冒烟 45 passed（**经本地直连代理**，见 §4） |

> ★ 2026-10-21 二次更正：本文件 §4 原写「WebKit 本机不可用、只能换环境」——**已推翻**。
> 真因不是"代理不可绕"，而是 **WebKit 页面网络栈不读系统 bypass**；给它指一个本地直连转发代理即可。
> **用户无需关闭系统代理**。

## 2. 实测基线（2026-10-21）

```
cd frontend
E2E_API_BASE 不需要（本地 dev），直接：
npx playwright test e2e/cross-browser-smoke.spec.cjs --project=firefox  --reporter=line --output=/tmp/pw-xbr-ff
npx playwright test e2e/cross-browser-smoke.spec.cjs --project=chromium --reporter=line --output=/tmp/pw-xbr-cr
```

| 引擎 | passed | failed | skipped | 耗时 |
|---|---|---|---|---|
| **chromium** | **45** | 0 | 0 | 1.7m |
| **firefox** | **45** | 0 | 0 | 59.1s |
| **webkit** | **45** | 0 | 0 | 52.9s |

45 = 全站 **44 个路由**各 1 例 + 1 例「页面清单完整性」自检（`ALL.length === 44`，防循环漏项假绿）。

被测页面清单与断言见 `frontend/e2e/cross-browser-smoke.spec.cjs`；每页三条硬断言：
① 根元素可见 ② 零 `pageerror` ③ `/api/` 下零 4xx/5xx。

> 负数对照（证明断言不是摆设）：临时把目标改成 `/products/99999999`，两个引擎都捕获到
> `api4xx=1` 而失败；随后删除该对照。

## 3. Firefox 之前为什么跑不起来（**根因更正**）

`frontend/e2e/GATE.md` §8.1 原记载：

> ❌ `Vite dev server(5173)` + Playwright Firefox/WebKit 这条路走不通：FF 下所有模块加载报错

并据此判定跨浏览器闸门「待投入」，建议后续改用 `vite preview` + `dist` 绕开 dev server。
**这个归因是错的。** 2026-10-21 实测证据链：

| # | 实验 | 结果 | 说明 |
|---|---|---|---|
| 1 | FF 打开 `http://localhost:5173/` | `/@vite/client` 与 `/src/main.js` 返回 **404**、`NS_ERROR_CORRUPTED_CONTENT`、`#app` innerHTML 长度 **0** | 症状与旧记载一致 |
| 2 | `curl` 同一 URL（含 **Firefox UA**） | **200 `text/javascript`** | ⇒ 服务端正常，**不是** dev server 的问题 |
| 3 | Chromium（msedge）打开同一 URL | 正常挂载 | 同一台机、同一 dev server |
| 4 | FF + `network.proxy.type = 0` | `#app` 挂载 **30329 字符**、失败请求 **0** | ⇒ **关掉系统代理就通** |

⇒ **真因：本机系统代理**（FlClash 之类）把 `localhost:5173` 的 ESM 请求接走并返回 404。
Chromium 由 Playwright 启动时未继承系统代理，所以一直是好的；Firefox 默认读系统代理，于是全挂。

**修法**（已入库，`frontend/playwright.config.cjs` 的 firefox project）：

```js
use: {
  browserName: 'firefox',
  launchOptions: { firefoxUserPrefs: { 'network.proxy.type': 0 } },  // 0 = 直连，不用系统代理
}
```

⚠️ **必须放 `launchOptions`**：写成 `use: { firefoxUserPrefs: {...} }` 会被**静默忽略**
（实测：改完仍 `#app` 长度 0、`.hero-title` element not found，与没改一样）。

## 4. WebKit 怎么打通的（含失败的尝试，保留作教训）

### 4.1 失败的尝试（都不是解）

| 尝试 | 结果 |
|---|---|
| `proxy: { server: 'direct://' }` | ❌ `Could not resolve proxy name` —— WebKit 不认 `direct://` 这个 scheme |
| `newContext({ proxy: { server: 'direct://' } })` | ❌ 同上 |
| `BASE_URL` 换成 `http://127.0.0.1:5173` | ❌ 仍 404（代理连 127.0.0.1 也接） |
| `NO_PROXY` 环境变量 | ❌ 无效（WebKit 不读） |
| **关掉系统代理开关**（改注册表 `ProxyEnable=0`） | ✅ 有效但**要动用户系统设置**，不理想 |
| `firefoxUserPrefs` 等价开关 | ❌ WebKit 没有对应项 |

关键诊断（2026-10-21 实测，同一时刻同一台机）：

| 观测 | 结果 | 说明 |
|---|---|---|
| 系统代理 | `127.0.0.1:7890`，**bypass 已含 `localhost;127.*`** | 不是"没配 bypass" |
| 网卡 | 只有以太网，**无 TUN** | 是系统代理模式，不是 TUN 拦截 |
| `curl` / `page.request` 抓 `127.0.0.1:5173/@vite/client` | **200** | 网络路径本身通 |
| WebKit **页面**加载同一 URL | **404**（13 个请求全挂，`#app`=0） | ⇒ **WebKit 页面网络栈不读系统 bypass** |
| WebKit 显式配 Playwright `proxy` | **认** | 这是突破口 |

### 4.2 解法：本地「直连转发代理」

`frontend/e2e/direct-proxy.cjs` —— 一个 30 行的最小转发代理（支持绝对 URI 与 CONNECT，**原样转发不拦截**），
只监听 `127.0.0.1:8130`。让 WebKit 显式走它 ⇒ 流量不进 FlClash。

- `playwright.config.cjs` 里：**本次跑批含 webkit 时**（`--project=webkit` 或不指定 project）
  自动把它作为 `webServer` 拉起，并给 webkit project 注入 `use.proxy`。
- 覆盖开关：`E2E_DIRECT_PROXY=1` 强制开 / `=0` 强制关；端口用 `E2E_DIRECT_PROXY_PORT`。
- ✅ **用户无需关闭系统代理，也无需改任何系统设置**；Chromium/Firefox 的既有绿不受影响。

实测：默认 `#app`=0 / 13 个 404 ⇒ 走直连代理后 `#app`=**30329 字符、0 失败请求**，
44 页冒烟 **45 passed / 52.9s**。

> ⚠️ 若某天 WebKit 又全红，先看 `#app` 是否为 0 + 是否有 `404 http://127.0.0.1:5173/@vite/client`：
> 若是，说明直连代理没起来（端口占用/command 失败），而不是应用坏了。

## 5. 复现要求（改判据时先看这段）

- 改了 `cross-browser-smoke.spec.cjs` 的页面清单 ⇒ **必须重跑两个引擎并更新本文件第 2 节表格**。
- 本文件里的 `| firefox | <N> |` 与 `| webkit | <N> |` 两行是审计脚本的判据输入，**格式不要改**（正则读它）。
- 若某天 Firefox 又挂：先按第 3 节实验 1–4 重跑一遍，**别直接断定"浏览器坏了"**。
