# PO 采购门户 · 生产验收报告

> **⚠️ 本报告是「某时刻的快照」，不是永久事实。任何后续开发引用本文前，请先读 §7「引用须知」。**

---

## 0. 报告元信息（时间戳必读）

| 项 | 值 |
|---|---|
| **报告生成日期** | **2026-10-15（GMT+8）** |
| **测试执行时间窗** | 2026-10-14 22:30 ~ 2026-10-15 09:10（跨午夜） |
| **被测环境** | **生产**（`https://scireagent.com`，`47.82.156.48`） |
| **代码版本（验收时）** | git **`2fdc508`** —— 四地一致：本地 HEAD = GitHub origin/master = 服务器源码 = 运行产物 |
| **后端** | Django + DRF，容器 `scireagent-backend-1`，迁移已应用到 `accounts.0007` |
| **前端运行产物** | `frontend/dist/index.html` md5 = **`e6eaa98414578d05c0eb0ade74bb481f`** |
| **TLS 证书** | Let's Encrypt，`notAfter = 2027-01-12`（**于 2026-10-14 23:25 续期**，见 §5 问题①） |
| **执行/记录** | WorkBuddy（自动化真浏览器 Playwright + API 脚本） |

---

## 1. 环境基线（验收当日的生产条件）

### 1.1 部署拓扑
| 组件 | 说明 |
|---|---|
| 域名 | `https://scireagent.com`（DNS 直指 `47.82.156.48`，**站前无 CDN**） |
| 服务器 | `/home/admin/scireagent`；容器 3 个：`backend` / `db`(postgres:16-alpine) / `nginx`(alpine) |
| 前端 | `frontend/dist` **bind-mount** 进 nginx `/usr/share/nginx/html` |
| 后端 | gunicorn，`docker compose up -d --build backend` 自动迁移 |

### 1.2 两层认证（**关键机制，易引错**）
| 层 | 位置 | 账号 | 说明 |
|---|---|---|---|
| **第 1 层** nginx HTTP Basic Auth | **server 级**（`auth_basic` 对所有 location 生效，**含 `/api/`**） | `scire01`~`scire06` | 用 **`Authorization: Basic …`** |
| **第 2 层** 应用层登录 | Django `POST /api/v1/auth/login` | `admin` / `scire02` / `scire03`（+ 测试号） | 业务 token 走 **`X-Auth-Token`** 头 |

> ⚠️ **两层都用 `Authorization` 会冲突** ⇒ 业务 token 必须走 **`X-Auth-Token`**（前端 `src/utils/http.js` 已如此实现）。
> 正确调用式：`curl -u scire01:<pw> -H "X-Auth-Token: <token>" https://scireagent.com/api/v1/...`

### 1.3 本次使用的账号（**测试账号，非真实客户**）
| 账号 | 角色 | 备注 |
|---|---|---|
| `e2e_customer` / `E2ePass123!` | researcher（客户） | 生产已存在 |
| `admin` / `admin123` | staff（内部） | 生产已存在 |
| `proc_mgr` / `E2ePass123!` | procurement（非 staff） | **密码为本报告执行时临时设置**（原密码未记录，该号为 `proc@example.com`，历史 `last_login=None` 的 demo 号） |

### 1.4 页面路由前缀（**2026-10-14 变更**）
| 类型 | 现路径（`2fdc508` 起） | 旧路径（**已废弃**） |
|---|---|---|
| 客户侧 | `/po/submit`、`/po/orders`、`/po/orders/:id`、`/po/addresses`、`/po/reorder`、`/po/downloads` | 不变 |
| 内部台 | **`/ops/orders`**、**`/ops/po/review|shipments|invoicing|ar|organizations`** | ~~`/admin/orders`、`/admin/po/*`~~ |

---

## 2. 验收范围与方法

| 方法 | 覆盖 | 只读/写入 |
|---|---|---|
| **A. 真浏览器全站巡检**（`frontend/e2e/po-prod-sweep.spec.cjs`） | 10 个 PO 页 × 4 角色（匿名/客户/staff/procurement）+ 跳转 + 按钮 + 白屏检测 | **只读** |
| **B. API 级完整写流程** | 提交→审核→发货→签收→开票→收款 全链路 | **写入**（跑完已清理） |
| **C. 匿名写/读探针** | 9 个写端点 × 匿名 + 3 个读端点 + 表计数 | 只读（哨兵） |
| **D. 污染四查** | 夹具混入真实数据面检测 | 只读 |

**不在范围内**：P2 功能（冷链/Re-order/客户注册/危险品/账户价）、邮件真实投递（cron 未配）、`allocate` 备货（见 §6）。

---

## 3. 验收结果（逐项 + 证据）

### 3.1 真浏览器全站巡检 —— **4 passed（2.8m）**
| 用例 | 结果 |
|---|---|
| 匿名访问全部 10 个 PO 页 → 落 `/login` | ✅ |
| 客户：5 个客户页渲染 + 内部台被拦 + 提交页控件齐全（PO 号可选 / Quote 下拉 / 加行 / 提交） | ✅ |
| staff：内部台 5 页渲染 + 审核台「View Items」展开显示 Available 库存列 | ✅ |
| procurement（非 staff）：内部台 5 页渲染 | ✅ |

### 3.2 API 级完整写流程 —— **端到端成功**
| 步 | 状态 | 证据 |
|---|---|---|
| ② 提交 PO | `po_received` | `ORD-9ECBE6E4` |
| ③ 审核 Approve | `confirmed` | — |
| ④ 发货 Create Shipment + Mark Shipped | `shipped` | shipment #3 |
| ⑤ 签收 Mark Delivered | `delivered` | — |
| ⑥ 开票 Issue Invoice | `invoiced` | invoice #3 |
| ⑦ 收款 Record Payment | **`paid`** | 全链路走通 |

> **已清理**：2 条测试单（`po_number LIKE 'E2E-PROD-%'`）已删除，剩余 **0**。

### 3.3 匿名写/读探针
- 写探针：**9/9 = 401**（含 `allocate` / `confirm-quote` / PO 提交等）
- 匿名读对照：**3/3 = 200**
- 关键表 Δ：`order/invoice/allocation` = **0/0/0**（零写入）

### 3.4 污染四查
`product.catalog_no LIKE 'E2E-%'` / `product.name LIKE '%E2E%'` / `sku.sku_code LIKE 'E2E-%'` / `reference.title LIKE '%E2E%'` → **全 0** ✅

---

## 4. 本次发现并修复的生产事故（2 项）

### 问题① TLS 证书过期 4 天 → **已修复**
- **现象**：浏览器 `ERR_CERT_DATE_INVALID`，HTTPS 实际不可用（curl 一直带 `-k`，此前未暴露）
- **事实**：旧证书 `notAfter = 2026-10-10`（过期 4 天）
- **根因（两重）**：
  1. 站点证书在**自定义目录** `deploy/certbot/conf`，系统 `certbot.timer` 只续默认目录 `/etc/letsencrypt` ⇒ 从未续到
  2. renewal conf 里 **`deploy_hook` 被误放进 `[[webroot_map]]` 段** ⇒ 手工 renew 也失败
- **处置**：修正 conf → 续期成功（新 `notAfter = 2027-01-12`）；新增 `/etc/cron.d/scireagent-certbot`（每天 03:30 用自定义目录续期）

### 问题② 内部台在生产不可达 → **已修复**
- **现象**：`/admin/po/*` 被 nginx `location /admin/`（Django admin）抢注 → 302 到 `Welcome back to SciReagent Admin`
- **叠加**：SPA 里**没有任何内部台导航入口**
- **根因**：SPA 内部台路由前缀 `/admin/*` 与 Django admin 的 `/admin/` 冲突
- **处置**：SPA 内部台路由 **`/admin/*` → `/ops/*`**（方案 A，提交 `2fdc508`），nginx 无需改

---

## 5. 生产数据状态快照（**2026-10-15 09:10 实测**）

> ⚠️ **本表是快照，数据随时会变。** 后续开发**不要**把它当成永久事实。

| 表 | 数量 | 分布 |
|---|---|---|
| `product` | 125 | **全部 `archived=true`**（status=active 109 / archived 10 / draft 6）⇒ **前台可见 0** |
| `inventory` | **0** | 无任何库存记录 |
| `sku` | 36 | 如 `898` = `SC8001-1` / $79 |
| `order` | 16 | confirmed 9 / po_received 4 / quote_pending 3 |

---

## 6. 已知限制（验收时确实存在，非缺陷）

1. **客户无法在 UI 下单**：产品全在回收站（前台可见 0）＋ 无库存 ⇒ PoSubmit 页搜不到商品。**这是数据状态，非代码缺陷**（用户此前定"暂不恢复产品"）。
2. **`allocate`（备货锁定）无数据可测**：`inventory = 0`。
3. **邮件仅入队，未真实投递**：邮件发送命令已实现，cron 定时器未配置。
4. **登录限流**：`LoginRateThrottle = 5 次/分钟/IP` ⇒ 自动化测试需控制登录次数。
5. **仅测 chromium**：firefox / webkit 未纳入本轮。

---

## 7. ⚠️ 引用须知（防止后续关联/迭代开发引用出错）

> 本节是本报告的**使用前提**。引用本报告任何结论前，先核对下表。

| # | 事项 | **验收时值（2026-10-15）** | 会变吗 | 引用不当的后果 |
|---|---|---|---|---|
| 1 | **内部台路由前缀** | **`/ops/po/*`、`/ops/orders`** | 稳定 | 引用 `/admin/po/*` → 被 Django admin 抢（302） |
| 2 | **业务 token 头** | **`X-Auth-Token`**（**不是** `Authorization`） | 稳定 | 用 `Authorization: Token` → **401** |
| 3 | **nginx Basic 作用域** | **server 级**（覆盖 `/api/`） | 可能变 | 以为 API 免 Basic → 401 |
| 4 | **产品可见性** | **0（125 个全 archived）** | **会变** ⚠️ | 误判"平台没商品"或"客户能下单" |
| 5 | **库存** | **0 行** | **会变** ⚠️ | 误判 `allocate` 可用 |
| 6 | **E2E 账号密码** | `proc_mgr` 密码**已被本报告执行者改为 `E2ePass123!`** | **可能变** ⚠️ | 用记录外的旧密码登录失败 |
| 7 | **代码版本** | `2fdc508`（四地一致） | **会变** ⚠️ | 用本报告的路由/接口描述去核对新版代码 → 对不上 |
| 8 | **TLS 证书到期** | `2027-01-12`（+ 每日 03:30 自动续期 cron） | 会变 | — |
| 9 | **登录限流** | `5/min/IP` | 稳定 | 自动化超限 → 429 |
| 10 | **验收结论的适用范围** | 仅对 **`2fdc508` + 上述环境** 成立 | — | 跨版本/跨环境套用 → 失真 |

**引用纪律（建议）**：
- 引用 §1.4 路由、§1.2 认证 → **可长期沿用**（属架构事实）。
- 引用 §5 数据、§6 限制 → **必须先重跑一次核实**（`docker exec scireagent-db-1 psql -U scireagent -d scireagent -c "..."`），因为它们是**时点快照**。
- 引用 §3 验收结果 → 需注明"**验收于 `2fdc508` / 2026-10-15**"，不得表述为"当前一直可用"。

---

## 8. 交付物与回滚点

### 8.1 交付物
| 文件 | 说明 |
|---|---|
| `frontend/e2e/po-prod-sweep.spec.cjs` | 生产真浏览器全站巡检（两层认证，只读） |
| `frontend/e2e/po-lifecycle.{api,ui,fullflow}.spec.cjs` | dev 环境三层 PO E2E（API / 页面 / 全流程） |
| `backend/seed_e2e_{customer,procurement,po_fixture}.py` | E2E 账号与夹具种子 |
| 提交 | `2fdc508`（路由改前缀）等，已推送 origin |

### 8.2 回滚点
- 前端：服务器 `frontend/dist.bak-*`（每次部署前备份）
- 源码：git `--ff-only` 可回退（服务器为 git 跟踪部署）
- 证书：renewal conf 已备份（`.bak-*`）

### 8.3 复现命令
```bash
# 真浏览器巡检（剥代理 + 单 worker）
cd frontend
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
node node_modules/@playwright/test/cli.js test e2e/po-prod-sweep.spec.cjs \
  --project=chromium --workers=1 --retries=0 --output=e2e-artifacts-prod
```

---

## 9. 验收结论

> 在 **2026-10-14~15**、代码版本 **`2fdc508`**、生产环境 **`https://scireagent.com`** 下：
> **PO 采购门户的后端写链路（提交→审核→发货→签收→开票→收款）与内部台 UI 均可用；权限收紧（匿名 401）与零写入均通过。**
> 过程中发现并修复了 **2 个真实生产事故**（TLS 证书过期、内部台路由被 Django admin 抢注）。
> **限制**：客户侧 UI 下单因"产品全在回收站 + 无库存"当前不可用（数据状态，非代码缺陷）。
