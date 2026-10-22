# PostgreSQL 本地手册（L4 并发测试用）

**结论先说**：**你不需要 initdb**。项目已有一个 PG 17 集群，而且**已经在运行**。

| 项 | 值 | 怎么确认的 |
|---|---|---|
| 数据目录 | `E:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\pgdata-l4` | `ls` 存在，`PG_VERSION` = 17 |
| 端口 | **5433** | `netstat` 见 `127.0.0.1:5433 LISTENING`（PID 1682960） |
| 角色 | **`scireagent`**（*不是* `postgres`，该角色不存在） | 用 `postgres` 连 → `FATAL: role "postgres" does not exist` |
| 数据库 | **`scireagent_l4`** | 连接成功；`public` 下 **69 张表**；`manage.py migrate --check` 退出码 0 |
| 认证 | `trust`（本地免密） | `pg_hba.conf` 三行 `trust` |

---

## 1. 复查它是否在跑（10 秒）

```powershell
Get-NetTCPConnection -LocalPort 5433 -State Listen | Select-Object LocalAddress,LocalPort,OwningProcess
```

判读：**有输出 = 在跑**，直接跳到第 3 步。

## 2. 停止 / 启动（只有需要时才做）

```powershell
$data = "E:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\pgdata-l4"

# 停止
& "C:\Program Files\PostgreSQL\17\bin\pg_ctl.exe" -D $data -m fast stop

# 启动（-p 5433 必须显式给，否则会用默认 5432）
& "C:\Program Files\PostgreSQL\17\bin\pg_ctl.exe" -D $data `
    -l "$data\server.log" -o "-p 5433 -c listen_addresses=127.0.0.1" -W start

# 看状态
& "C:\Program Files\PostgreSQL\17\bin\pg_ctl.exe" -D $data status
```

> ⚠️ **我（AI）跑不了这两条**：沙箱对 `postgres.exe` / `initdb.exe` 有拦截，
> 执行会返回"命令被安全策略拦截"。**必须由你在自己的终端执行**。
> 这也是为什么 `scripts/run_pg_tests.py` 的注释里直接写了"需要手动启动"。

## 3. 跑 PG 并发测试（验证 L4 那批只有 PG 能验的用例）

```powershell
cd E:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\src_claude\backend
venv\Scripts\python.exe ..\scripts\run_pg_tests.py
```

**实测输出（2026-10-22）**：
```
✅ PG 可连：127.0.0.1:5433 / db=scireagent_l4 / user=scireagent
目标：inventory, order_no, invoice_no
6 passed
✅ 通过（无「需 Postgres」跳过项）。
```

> 这个脚本的关键设计：连不上 PG 会**直接退出（码 2）**，不会静默退回 sqlite。
> 否则你会看到"13 passed, 4 skipped"以为测过了，其实并发一条都没跑。

## 4. 做 HTTP 层的并发对比（sqlite vs PG）

```powershell
# 4.1 在 PG 上造夹具（只允许 _l4 结尾的库，防误连生产）
cd E:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\src_claude
$env:DB_ENGINE="django.db.backends.postgresql"; $env:DB_NAME="scireagent_l4"
$env:DB_USER="scireagent"; $env:DB_HOST="127.0.0.1"; $env:DB_PORT="5433"
backend\venv\Scripts\python.exe scripts\probe_seed_pg_concurrency.py

# 4.2 起一个指向 PG 的后端（另开一个终端）
cd backend
venv\Scripts\python.exe manage.py runserver 127.0.0.1:8012 --noreload

# 4.3 打并发（回到 src_claude）
$env:PROBE_BASE="http://127.0.0.1:8012"
backend\venv\Scripts\python.exe scripts\http_concurrency_probe.py --n 10 `
  --out docs/e2e/CONCURRENCY_PROBE_PG.json --label "PostgreSQL 17.11"
```

**实测对比（同一天、同一套代码）**：

| 实验 | SQLite | PostgreSQL |
|---|---|---|
| 库存入库 10 并发（每次 +1） | 500 × 8、200 × 2，总量 +2（期望 +10） | **200 × 10，总量 +10** |
| PO 提交 10 并发 | 500 × 9、201 × 1 | **201 × 10** |

## 5. 「放开 initdb 执行许可」到底指什么

那个拦截来自**沙箱层**，不是 PostgreSQL 也不是项目配置。共三种处理方式：

| 方案 | 怎么做 | 代价 |
|---|---|---|
| **A. 用已有集群（推荐）** | 什么都不用做，见第 1 步 | **零成本**，PG 已在跑 |
| **B. 你自己终端执行** | 见第 2 步的 `pg_ctl` 命令 | 只需你敲一次；集群已在则无需 |
| **C. 放开沙箱许可** | 在 WorkBuddy 的沙箱/权限设置里允许 `initdb.exe`、`postgres.exe`，或对单条命令选择"在沙箱外运行"并批准 | 降低沙箱保护强度，**不推荐**；仅在你确实要新建集群时才需要 |

**什么情况下才真需要 initdb**：只有"从零新建一个集群"才需要。
本项目已有 `pgdata-l4`，且 `migrate --check` 干净 ⇒ **不需要**。

## 6. 常见坑

| 现象 | 原因 | 处理 |
|---|---|---|
| `role "postgres" does not exist` | 该集群的超级用户是 `scireagent`，不是 `postgres` | 用 `-U scireagent` |
| 连 5433 拒绝 | 服务没起 | 第 2 步启动 |
| 连 5432 拒绝 | 默认端口不对，本项目用 **5433** | 显式 `-p 5433` / `DB_PORT=5433` |
| 测试通过但实际全 skip | 没给全 5 个 `DB_*` 变量，静默落回 sqlite | 用 `run_pg_tests.py`，它会硬失败 |
| 并发测试结果和本地不一致 | sqlite 的 `select_for_update` 是 no-op | 并发结论只认 PG |
