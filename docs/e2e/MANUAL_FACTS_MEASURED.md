# 说明书实测事实清单（Measured Facts）

**生成日期** 2026-10-22 · **对应代码** `cc4e8f2` · **性质** 只记录**实际观测到的**结果，不记录推断

> 本文件是 `SITE_ROLE_OPERATION_MANUAL.md` 的**证据层**。
> 说明书里凡是标 `[M-nn]` 的断言，出处都在这里，且可用下列命令复跑。

---

## 0. 实验环境（可复现）

| 项 | 值 | 为什么这样设计 |
|---|---|---|
| 后端 | `127.0.0.1:8011`，`DB_ENGINE=sqlite SCIREAGENT_DB_NAME=<abs>/db_probe.sqlite3` | **独立 DB 副本**，写操作不碰开发库 `db.sqlite3` |
| 数据库 | `backend/db_probe.sqlite3`（`cp db.sqlite3` 而来，99MB） | 真实数据量，不是空库 |
| 前端 | `127.0.0.1:5174`，`VITE_API_PROXY=http://127.0.0.1:8011` | 与用户开发栈（5173/8000）隔离，互不干扰 |
| 账号 | `probe_researcher` / `probe_orgadmin` / `probe_procure` / `probe_adminrole` / `probe_staff` / `probe_super` / `probe_unverified`，密码 `Probe#2026!` | 7 个身份在**副本**里精确构造；不依赖生产/开发库里来源不明的账号 |
| 浏览器 | Playwright + `chromium`（msedge channel） | 与既有 e2e 同栈 |
| 代理 | 全部命令 `env -u HTTP_PROXY -u HTTPS_PROXY ...` + `NO_PROXY=127.0.0.1,localhost` | 本机 `http_proxy=127.0.0.1:56679` 会把回环请求转发出去，**实测得到 502** |

### 复跑命令

```bash
cd src_claude
# ① 建副本与探测账号
cp backend/db.sqlite3 backend/db_probe.sqlite3
cd backend && DB_ENGINE=sqlite SCIREAGENT_DB_NAME="$(pwd)/db_probe.sqlite3" \
  venv/Scripts/python.exe ../scripts/probe_seed_accounts.py

# ② 起探测后端（端口 8011）
DB_ENGINE=sqlite SCIREAGENT_DB_NAME="$(pwd)/db_probe.sqlite3" \
  venv/Scripts/python.exe manage.py runserver 127.0.0.1:8011 --noreload

# ③ 起指向它的前端（必须用 E: 物理路径，C: 是联接会让 vite 解析失败）
cd /e/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/frontend
VITE_API_PROXY=http://127.0.0.1:8011 ./node_modules/.bin/vite --port 5174 --strictPort

# ④ 真实 HTTP 权限探测（8 身份 × 199 端点）
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
  python scripts/http_role_probe.py

# ⑤ 求值 vs 实测比对
python scripts/compare_probe_vs_http.py

# ⑥ 浏览器实测（三批）
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy NO_PROXY=127.0.0.1,localhost \
  BASE_URL=http://127.0.0.1:5174 npx playwright test manual-facts-probe --project=chromium --reporter=line --retries=0
# 同理 manual-facts-probe2 / manual-facts-probe3
```

---

## 1. 权限层：真实 HTTP vs 静态求值

### M-01 全量探测结果（8 身份 × 199 端点，2026-10-22 11:47）

命令：`python scripts/http_role_probe.py`（写方法用空 body、对象路由用假 id `999999999`）

| 身份 | 读通过 | 写通过 | 被拒(401+403) |
|---|---|---|---|
| anon | 69/84 | 7/115 | 123 |
| researcher | 75/84 | 31/115 | 93 |
| org_admin | **75/84** | **31/115** | **93** |
| procurement | 80/84 | 42/115 | 77 |
| admin_role | 80/84 | **43/115** | 76 |
| staff | **84/84** | 114/115 | **1** |
| superuser | **84/84** | **115/115** | **0** |
| unverified | — | — | **登录即 403，拿不到 token** |

**读通过的端点集合，各身份都包含前一身份的全部**（单调）—— 这是数据可信的旁证。

### M-02 与静态求值的一致度：**1389 / 1393 = 99.7%**

命令：`python scripts/compare_probe_vs_http.py`（输出 `docs/e2e/PROBE_VS_HTTP_DIFF.json`）

| 不一致类型 | 条数 | 含义 |
|---|---|---|
| 求值说 PASS，真打被拒 | **0** | 静态没有低估限制 |
| 求值说 DENY，真打通过 | **4** | 全是同一端点 `POST /api/v1/verified/`（见 M-15） |

⇒ **"权限矩阵"这份数据的可信度被 HTTP 层验证过了**；唯一的偏差已定位并修正。

### M-03 每个身份内部，读/写判定与身份语义自洽
- `admin_role` 比 `procurement` 多 **1 个写端点**（43 vs 42）—— 与"唯一差异是 assign-rep"一致
- `staff` 只有 **1 个**端点被拒（114/115 通过）—— 即 `DELETE /products/{id}/hard-delete/`（`IsSuperUser`）
- `org_admin` 与 `researcher` **逐项完全相同**（75/84、31/115、93）—— 实测坐实"`is_org_admin` 零影响"

### M-04 未验证用户：**根本拿不到 token**（推翻旧表述）

真实请求 `POST /api/v1/auth/login`（`probe_unverified`）：
```
HTTP 403
{"success":false,"data":null,"meta":{"error":{
  "detail":"Email address is not verified. Please check your inbox for the verification link (or request a new one from the sign-in page).",
  "email_verified": ...}}}
```
⇒ **实测结论**：未验证身份在 API 层**不可达**（无 token）。
  旧文档写"与 researcher 逐项相同（读 123/132、写 43/203）"——那是**权限类求值**的结果，
  真实 HTTP 场景下它连门都进不去。两句话都对，但**不可混说**：
  - 认证层：登录被拒，API 不可达 **[M-04 实测]**
  - 权限层：权限类不看 `email_verified`，若已有 token 则不受限 **[求值，未实证]**

### M-05 登出确实在服务端销毁 token

命令：`http_role_probe.py` 里的 `verify_logout()`
```
before=200  →  POST /auth/logout = 200  →  同一 token 再请求 = 401
```
**[实测]** 登出后该 token 立即失效。

---

## 2. 页面层：真实浏览器（Playwright）

> 每个 case 都在 `frontend/e2e/manual-facts-probe*.spec.cjs` 里，输出 `[FACT] {...}` JSON。

### M-10 procurement 打开 `/ops/orders` —— "不可用"是什么样子 **[实测]**

```
url            : http://127.0.0.1:5174/ops/orders      （没被踢走）
表格行数        : 0
403 命中        : /api/v1/admin/orders/、/api/v1/admin/dashboard-stats/
页面文本（摘）  : "Couldn't load orders.
                  You do not have permission to perform this action.
                  ... No orders found"
```
**推翻旧表述**：旧文档写"进去就是空白 / 白屏"。实测**不是白屏** ——
页面渲染了完整外壳 + 一条错误横幅 + 一个 **`No orders found` 空态**。
⇒ 真实缺陷更糟：**错误提示与"没有订单"同时出现，操作员会以为全库真的没订单。**

### M-11 `/ops/orders/:id` 同 **[实测]**
```
url 停留；403 /api/v1/admin/orders/1/
文本: "Couldn't load this order. You do not have permission to perform this action."
```

### M-12 `/workspace/verified` 同 **[实测]**
```
url 停留；403 /api/v1/verified/
文本: "Failed to load review queue."
```
（此页**没有**误导性空态，只有错误提示 —— 与 M-10 不同，值得区分。）

### M-13 `/workspace` 首页统计卡 **[实测]**
```
403 /api/v1/admin/dashboard-stats/
文本: "Failed to load dashboard data"
```

### M-14 `/workspace/products` —— 能看不能写，且按钮不作任何区分 **[实测]**
```
表格行数: 69                     ← 数据能加载
Actions 菜单项（真实渲染）:
  Edit / Unpublish / Discontinue / Move to Recycle Bin
```
⇒ **实测坐实**：4 个写操作入口**全部渲染、无一禁用、无权限提示**。
采购点下去才会 403。这是"页面能进、按钮点了没反应"的准确形态。

### M-15 `POST /api/v1/verified/` 对**任意登录用户**开放 **[实测 + 建了真实数据]**

静态求值说是 `IsStaffUser`，HTTP 实测 researcher **201 创建成功**：
```
POST /api/v1/verified/  {product_id:62, method_id:35, evidence_note:"probe 实测创建"}
→ 201  {"id":1885, "status":"review", "curator":"probe_researcher", "relation_type":"verified_applicability"}
```
后续可见性（同一次实验）：
| 谁 | 能否看到这条草稿 | 结果 |
|---|---|---|
| staff | 审核队列 `GET /verified/?status=review` | **200，含 id=1885** |
| 匿名 | `GET /products/62/methods/` | 200，**不含 1885**（只出 ACTIVE） |
| 匿名 | `GET /products/62/detail` | **404** |

**根因（读码）**：`bridges/api/v1/views.py:79-82`
```python
def get_permissions(self):
    if self.request.method == 'GET': return [IsStaffUser()]
    return [IsAuthenticated()]      # ← POST 只要登录
```
docstring 自述"POST → 创建 REVIEW 草稿（IsAuthenticated）"，是**有意的设计**，不是漏洞。
但影响真实存在：**任何客户都能往审核队列塞条目**（草稿不公开，故非数据泄漏，是审核负担 + 社工面）。

### M-16 `/settings` 改密码 —— 假成功 **[实测]**
```
3 个 password 输入框；点击 Update Password 后
页面出现: "Password update feature will be available soon."
```
⇒ 提示语气是**成功**（不是错误），且**没有任何网络请求**（改密接口不存在）。

### M-17 登录页「Resend verification email」—— 点了什么也没发生 **[实测]**
```
点击前请求计数: 0
点击后请求计数: 0
新增请求      : []
pageerror     : []
unhandledrejection: []
页面文本变化  : 无
```
**诚实边界**：代码层面 `handleResend` 读 `form.email.trim()`（`LoginPage.vue:112`，`form` 无 `email` 字段），
但**浏览器没有观测到异常抛出**（Vue 内部错误处理吞掉了）。
⇒ 文档只能写可观测事实：**点击后零请求、零提示、零变化**；
   "因为 `form.email` 未定义所以抛 TypeError" 属**读码推断**，需标注来源。

### M-18 researcher 访问 `/workspace` → 被踢回首页 **[实测]**
```
GET /workspace  →  URL = http://127.0.0.1:5174/
```

### M-19 token 失效 → 清 token + 落到 `/login` **[实测]**
```
把 localStorage.token 改为非法值 → 访问 /orders
结果:  URL = /login，localStorage.token = null
```

### M-20 403 的用户可见文案 = DRF 英文原文 **[实测]**
两处独立观测到同一句话（M-10 页面横幅、M-21 toast）：
```
You do not have permission to perform this action.
```
⇒ 确认"不告诉用户缺哪个权限、也不提示该找谁"。

### M-21 `Assign Rep` —— procurement 是死按钮，admin_role 会 500 **[实测]**

Playwright 真点（`/ops/po/review`，18 张卡片，Rep ID 输入框存在）：

| 身份 | 填入 | 请求 | 结果 |
|---|---|---|---|
| procurement | `probe_staff` | `403 POST /orders/1197/assign-rep/` | toast `You do not have permission to perform this action.` |
| admin_role | `probe_staff` | **`500`** | toast `Action failed`（响应是 **HTML 错误页**，非 JSON 信封） |
| admin_role | `26`（数字） | **`200`** | **成功**，返回订单详情 |
| admin_role | `999999` | 404 | `{"code":"NOT_FOUND","message":"Invalid rep_id"}` |

**根因（读码）**：`transactions/api/v1/po_views.py:130`
```python
rep = User.objects.get(pk=rep_id, role__in=['procurement','admin'])
except User.DoesNotExist: ...
```
只 catch `DoesNotExist`；传入非数字字符串时 Django 抛 `ValueError` ⇒ **500 + HTML 错误页**。

**这是一条新缺陷（旧文档没有）**：
> `Rep ID` 输入框占位符不说明"填数字用户 ID"，按字面填用户名 ⇒ **500 白屏错误页**。
> 正确行为应是 400 + "rep_id 必须是用户数字 ID"。

---

## 3. 实测推翻了旧版说明书的哪些话（逐条对照）

| # | 旧表述（V1.0/V1.1） | 实测结果 | 处置 |
|---|---|---|---|
| 1 | procurement 打开订单管理页"**进去就是空白/白屏**" | 有完整外壳 + 错误横幅 + **`No orders found` 空态**（M-10） | 改为"0 行 + 错误横幅 + 误导性空态并列" |
| 2 | "`POST /verified/` 与其他 verified 端点一样是 `IsStaffUser`" | 任意登录用户可创建 review 草稿，201（M-15） | 矩阵与正文都改：POST = `IsAuthenticated` |
| 3 | "未验证用户 API 权限与 researcher 逐项相同" | 实测**拿不到 token**，API 不可达（M-04） | 拆成"认证层不可达"与"权限层不校验"两句 |
| 4 | "Assign Rep 对 procurement 是必 403 的死按钮" | 对，**且有英文 toast**（M-21） | 保留结论，补上"不是静默" |
| 5 | "admin_role 唯一独有能力=Assign Rep" | 对，但**填用户名会 500**（M-21） | 新增缺陷条目 |
| 6 | "改密码假成功" | 完全确认（M-16） | 升级为 `[实测]` |
| 7 | "登录页重发按钮必崩（TypeError）" | 可观测行为=零请求零提示；异常未被观测到（M-17） | 拆成"实测现象"+"读码推断原因" |
| 8 | "401 会整页跳转" | 确认清 token + 落 `/login`（M-19）；是否整页重载未直接测 | 降级为"清 token 并跳转"，去掉"整页"的断言 |

---

## 4. 对象级权限 / queryset 收窄（第二轮补齐，上一轮的最大空白）

上一轮用假 id 探测时 `get_object()` 先 404，`has_object_permission` 根本没执行。
本轮用 `probe_seed_cross_org.py` 造了**真实对象**再打：

| 夹具 | 值 |
|---|---|
| Org A / Org B | id=10 / id=11 |
| `probe_ouser_a`（A 成员） | id=31 |
| `probe_ouser_a2`（A 的**第二人**） | id=32 |
| `probe_ouser_b`（B 成员） | id=33 |
| 地址 | A=6（org10）、B=7（org11） |
| 订单 | A=1257（user31）、B=1258（user33） |

### M-30 订单与地址：靠 `get_queryset` 收窄，表现为 **404 而不是 403**

| 场景 | 身份 | 结果 | 判读 |
|---|---|---|---|
| 读自己的订单/地址 | probe_ouser_a | **200** | 正常 |
| 跨机构读地址 B | probe_ouser_a | **404** `code=not_found`，message `No Address matches the given query.` | 查不到（收窄），不是"查得到但不许" |
| 跨机构**改**地址 B（带 body） | probe_ouser_a | **404** | 写也被挡 |
| 跨机构**删**地址 B | probe_ouser_a | **404** | 且事后 B 仍能读到自己的地址（**未被删**） |
| 跨机构读订单 B | probe_ouser_a | **404** | 收窄 |
| **对别人订单 accept 报价** | probe_ouser_a | **403** | ★ 与上面不同：这是"查得到但不许"，说明该端点有显式归属校验 |
| 订单/地址列表 | A / B | 各自**只含自己的**（A 列表无 B 单、B 列表无 A 单） | 列表隔离生效 |

### M-31 同机构第二人可以改第一人的地址（实测 200，且已持久化）

```
probe_ouser_a2  PUT /api/v1/addresses/6/  {"attention":"EDITED-BY-A2"}
→ 200
事后查库：Address 6 attention = "EDITED-BY-A2"
```
⇒ 坐实 `AddressPermission` 注释里写的"同机构成员可改彼此的地址——本来就是机构内协作"。

### M-32 **staff / procurement 也读不到客户地址**（预期外）

```
probe_staff      GET /api/v1/addresses/7/  → 404
probe_procure    GET /api/v1/addresses/7/  → 404
```
原因：地址 ViewSet 的 `get_queryset` 按**请求者自己所属机构**过滤，staff 属于 `Probe Lab`、不在 org 11 ⇒ `.none()`。
⇒ **地址簿对所有人（含内部员工）都严格按"你所属机构"隔离**，内部台无法查看客户地址。
这是说明书里原来没写的实际限制（不是缺陷，但要写进运营预期）。

### M-33 发票 PDF：非本人 403、匿名 401
```
anon            GET /invoices/266/pdf/ → 401
probe_ouser_a   GET /invoices/266/pdf/ → 403
probe_ouser_b   GET /invoices/266/pdf/ → 403
```

### M-34 购物车 / 愿望清单：跨用户 404
```
B PATCH  /basket/items/779        → 404      （A 建的行）
B DELETE /basket/items/779/delete → 404
B PATCH  /wishlist/6/             → 404      （A 的清单）
A 事后 GET /wishlist/             → 200      （未被改动）
```

### M-35 SDS 下载门控生效（published 可下、draft 不可）
```
anon GET /sds-revisions/1/download/   (published) → 200，13,764 字节
anon GET /sds-revisions/17/download/  (draft)     → 404
```
⇒ 草稿用 **404** 而不是 403，不泄露"该文档存在"。

> COA 无法测：**副本里 `Coa` 表 0 条记录**（`Coa.objects.count() == 0`），没有对象可打。
> 门控代码与 SDS 同构，但**未实测**，不冒充。

---

## 5. 邮件链路（§4 原第 5 项）：**从未发出，且发出去也是空邮件**

### M-40 验证邮件"发出"= 只打印到后端日志

注册两个账号后，后端 stdout 出现完整邮件正文（console backend）：
```
Subject: Verify your SciReAgent account email
From: noreply@scireagent.com
To: probe_reg_rese_1792641672@probe.local
https://scireagent.com/verify-email?token=b3fad0e6-de1d-47d0-ac48-acf6e1e132e9
```
而接口同时返回 201 + `"Registration successful. We have sent a verification link to your email address"`
⇒ **文案说"已发送"，实际用户收不到**（`EMAIL_BACKEND` 在无 `MAILGUN_API_KEY` 时是
`console.EmailBackend`，`config/settings/base.py:352-354`）。本地/dev 一律如此。

### M-41 业务通知队列：**2984 封全在 pending，历史零发送**

```
EmailOutbox 状态分布：{pending: 2984}     ← 没有任何 sent/failed
template_key 分布：po_submitted 1023、order_confirmed 756、shipped 490、
                  delivered 423、invoice_issued 290
```
没有任何 crontab / celery beat / docker-compose 调度引用 `send_outbox_emails`
⇒ 只能人工跑命令。

### M-42 即使跑命令，发出去的也是**空主题空正文**

```
$ manage.py send_outbox_emails --limit 2
→ "Sent 2, failed 0"
→ 打印的邮件：Subject: （空）   正文（空）
状态：{pending: 2982, sent: 2}
```
根因（实测）：**`EmailTemplate` 表 0 条记录**。
`EmailService.enqueue` 在模板缺失时不报错、直接用空字符串入队
（`notifications/services.py:30-40`）⇒ **通知邮件全是空壳**。

### M-43 注册时提交 `role=procurement` 落库仍是 `researcher`（提权链已堵）
```
POST /auth/register {"role":"procurement", ...} → 201
落库：probe_reg_proc_... role=researcher  staff=False  verified=False
```
⇒ 序列化器接受该值但不采纳（`serializers.py:59` 允许，`create` 强制 researcher）。

---

## 6. 跨浏览器（§4 原第 6 项）：三浏览器事实一致

同一套 `manual-facts-probe*.spec.cjs`（12 个 case）在三个引擎上跑：

| 引擎 | 结果 | 关键事实是否一致 |
|---|---|---|
| chromium（msedge channel） | **12 passed / 0 failed** | 基准 |
| firefox（`network.proxy.type=0`） | **12 passed / 0 failed** | ✅ 全部一致（仅 console 少一条 403 记录） |
| webkit（走 `e2e/direct-proxy.cjs` 直连代理） | **12 passed / 0 failed**（6.6 min） | ✅ 全部一致 |

WebKit 额外噪声：vite HMR websocket 连接失败（`Unexpected response code: 400`），
不影响页面渲染与业务事实（`#app` 正常、403/UI 文案一致）。

## 7. 视觉 / 响应式（§4 原第 7 项）：72 / 72 通过

```
npx playwright test visual-tokens responsive --project=chromium → 72 passed (33.2s)
```
覆盖：3 个视口（desktop/tablet/mobile 375×667）× 多页面「加载不崩」+ 全站设计令牌与品牌色一致。

> **诚实边界**：既有用例断言的是"**加载不崩**"与"令牌一致"，**不是像素级视觉回归**。
> 真正的视觉回归需要基线截图比对，本仓库目前没有。

## 8. 并发（§4 原第 4 项）：SQLite 下并发写大面积 500；PG 未能测

**先说不确定性**：`SQLite` 的 `select_for_update()` 是 **no-op**，所以本实验**证明不了行级锁互斥**。
它证明的是"应用层在 SQLite 下的真实行为"。

### M-50 库存入库并发 N=10（每次 +1，同一 sku+location）
```
初始 available=1000 → 结束 available=1000   实际增量 0（期望 10）
响应码：500 × 8、200 × 2
后端日志：django.db.utils.OperationalError: database is locked
```
### M-51 PO 提交并发 N=10（空 body）
```
响应码：201 × 1（真的建成一张订单）、500 × 9
同上：database is locked
```
**判读**：SQLite 写锁争用 → `OperationalError` → **直接冒泡成 500**。
`core/db_retry.py` 只重试 PG 的 `40P01`/`40001`，**不覆盖** sqlite 的 `database is locked`。
⇒ 本地/dev 并发写会 500；**生产 PG 的行为本轮未测**（见 §9 阻塞说明）。

## 9. 生产环境（§4 原第 3 项）：**全站 401，匿名不可达**

只发 GET、不带任何凭证、共 10 条路径（`scripts/prod_anon_probe.py`）：

| 路径 | 状态 | WWW-Authenticate |
|---|---|---|
| `/` | **401** | `Basic realm="SciReAgent Internal Test"` |
| `/robots.txt` | **401** | 同上 |
| `/sitemap.xml` | **401** | 同上 |
| `/api/v1/health/` | **401** | 同上 |
| `/api/v1/site/home` | **401** | 同上 |
| `/api/v1/products/` | **401** | 同上 |
| `/api/v1/search/suggest?q=a` | **401** | 同上 |
| `/api/v1/orders/` | **401** | 同上 |
| `/api/v1/admin/orders/` | **401** | 同上 |
| `/api/v1/verified/` | **401** | 同上 |

**三条可下结论的事实**：
1. **生产当前对整个互联网不可访问** —— 连首页、`robots.txt`、`sitemap.xml` 都要 Basic 认证
2. realm 名是 `SciReAgent Internal Test` ⇒ 站点仍是**内部测试态**，未对外
3. 我们做的 sitemap 分片/SEO 优化**当前对搜索引擎无效**（爬虫同样吃 401）

> 这条与项目口径铁律一致：**汇报只能是"开发测试态 + 种子数据"，不能说"已上线"**。

---

## 10. 本次实测**仍未覆盖**的（只剩 2 项，且都写明阻塞原因）

| # | 未覆盖项 | 阻塞原因（实测确认，不是偷懒） | 解锁条件 |
|---|---|---|---|
| 1 | **生产环境登录态 / 写操作 / 内部台** | 生产全站挂 nginx Basic 认证（`realm="SciReAgent Internal Test"`，10/10 路径 401）。本地**没有** `deploy/CREDENTIALS.txt`。不猜口令、不试弱口令 | 提供 nginx basic-auth 账号 + 一个生产应用层账号；且需明确授权在生产做**读**操作（写操作不建议在生产验） |
| 2 | **PostgreSQL 下的并发互斥** | `initdb.exe` / `postgres.exe` 被本机安全策略拦截（实测报"命令被安全策略拦截"），无法起 PG 集群；`pgdata-l4` 目录已不存在 | 用户手动启动 PG（或允许 `initdb`），然后跑 `scripts/run_pg_tests.py` + 本文件的并发脚本改指 PG |

**以下原列各项本轮已全部补齐**：对象级权限 / queryset 收窄（§4）、邮件链路（§5）、
跨浏览器（§6）、视觉响应式（§7）、并发行为（§8）、生产匿名边界（§9）。

**仍然只做到"未覆盖"的一条**：跨浏览器只覆盖了 chromium/firefox/webkit 三家的**功能事实**，
没有做像素级视觉回归（仓库无基线截图机制）。

---

## 11. 方法学教训（累计）

| # | 坑 | 现象 | 正确做法 |
|---|---|---|---|
| 1 | **探测器自己把 token 打死了** | 第一版全量扫描第 137 个请求起整片 401，researcher 读通过(49)反而少于匿名(69) | 批量扫描必须**排除** `POST /auth/logout`；破坏性认证端点单独测 |
| 2 | 数字不单调就是信号 | 身份越高、权限越少 —— 物理上不可能 | **先看单调性**再信数字 |
| 3 | 本机代理污染回环 | `http_proxy=127.0.0.1:56679` ⇒ 所有 127.0.0.1 请求得 **502** | 一律 `ProxyHandler({})` / `env -u ...` / `NO_PROXY` |
| 4 | vite 在 C: 联接盘上解析失败 | `Pre-transform error: Failed to load url /src/main.js`，页面**全白** | 必须从 `E:` 物理路径启动 vite |
| 5 | `nohup ... &` 起服务被回收 | 端口不监听、日志 0 字节 | 用后台任务机制（`run_in_background`） |
| 6 | 换身份必须换 context | 同 context 里 `localStorage.clear()` + 导航 ⇒ `ERR_ABORTED` | 每个身份 `browser.newContext()` |
| 7 | **脚本用错解释器** | 并发脚本要 ORM，却用托管 python 跑 ⇒ `No module named 'django'` | 需要 ORM 的脚本必须用 `backend/venv/Scripts/python.exe` |
| 8 | `django.apps` 属性判断写错 | `if not django.apps.apps.ready` ⇒ `AttributeError` | 直接 `django.setup()`（重复调用安全），别探测 `django.apps` |
