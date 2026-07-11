# SciReAgent 免费平台部署方案（GitHub + Vercel + Railway + Supabase）

> 目标：让外地同事在浏览器里**真实浏览、测试、操作**全站（含加购/下单/PO 全流程），零成本。
> 适用：测试 / 演示阶段。正式生产请换付费实例 + 独立域名 + HTTPS + 定期备份。
> 文档版本：2026-07-11

---

## 1. 架构与访问流

```
外地同事浏览器
  └─ Vercel 域名  https://<project>.vercel.app   ← 前端静态包（Vue build 产物）
       └─ vercel.json 重写：把 /api /admin /static /media 反代到
            └─ Railway 域名  https://<backend>.railway.app   ← Django + Gunicorn
                 └─ Supabase Postgres（免费 500MB）← 业务数据
```

要点：
- 前端 API base 是**相对路径** `/api/v1`（见 `src/utils/http.js`），所以 Vercel 用重写把 `/api/*` 指到后端域名，浏览器看来仍同域 → **无需 CORS、前端零代码改动**。
- 后端 `ALLOWED_HOSTS=*` 已设，无需为域名改代码。

---

## 2. 前置账号（全部免费，需自行注册）

| 平台 | 用途 | 免费额度注意 |
|------|------|--------------|
| GitHub | 托管代码（frontend 仓库 + backend 仓库） | 私有仓库免费 |
| Vercel | 托管前端静态包 | 自动 HTTPS，构建额度充足 |
| Railway | 托管后端 Django 容器 | 免费额度有限，可能休眠/冷启动 |
| Supabase | 托管 Postgres | 免费 500MB，够测试 |

> 部署动作需要这些平台的 **token / CLI 登录**：Vercel Token、Railway CLI 登录、Supabase 连接串。由你提供后执行。

---

## 3. 仓库已做的准备（本次提交包含）

| 文件 | 改动 | 原因 |
|------|------|------|
| `backend/Dockerfile` | `python:3.13-slim` → `python:3.12-slim` | 依赖 `rdkit` 仅 cp312 wheel，3.13 构建必败 |
| `backend/Dockerfile` | 增加 `docker-entrypoint.sh` 入口 | 容器启动**自动 `migrate`**（并可选建管理员），解决启动后库表不存在 500 |
| `backend/.dockerignore` | 新增 | 排除 `venv/`、`node_modules/`、`.git` 等，避免打进镜像 |
| `frontend/.dockerignore` | 新增 | 排除 `node_modules/`、`dist/` |
| `frontend/vercel.json` | 新增 | 把 `/api /admin /static /media` 重写到后端域名（见 §4.5 填真实域名） |

> 说明：本地开发仍用 venv + SQLite，不受上述 Docker 文件影响。

---

## 4. 部署步骤

### 4.1 GitHub：推两个仓库
- **frontend 仓库**：`frontend/` 本就是独立 git 仓库，直接推到 GitHub（如 `scireagent-frontend`）。
- **backend 仓库**：父仓 `src_claude` 内含 `backend/`，把它整体推到 GitHub（如 `scireagent-backend`）。部署时 Railway 的 **Root Directory 设为 `backend`**。
  - 父仓无 `.gitmodules`，`frontend` 在父仓只是 gitlink，推父仓不会触发子模块拉取，构建 backend 不受影响。

### 4.2 Supabase：建 Postgres
1. 登录 Supabase → New project → 记下 **Host / Database / User / Password / Port**（Connection string 里都有）。
2. 默认库名 `postgres`，用户 `postgres`。端口通常用 `5432`（直连）或 `6543`（事务池）。测试用 `5432` 即可。

### 4.3 Railway：部署后端（依据 `web-deploy` 技能指引）
```bash
# 1) 登录并初始化（在 backend 目录或设 Root Directory=backend）
railway login
railway init

# 2) 设置环境变量（值是 §5 的清单）
railway variables set DB_ENGINE=postgresql
railway variables set DB_NAME=postgres
railway variables set DB_USER=postgres
railway variables set DB_PASSWORD=<Supabase 密码>
railway variables set DB_HOST=<Supabase host>
railway variables set DB_PORT=5432
railway variables set SECRET_KEY=<随机强串>
railway variables set ALLOWED_HOSTS="*"
railway variables set DJANGO_SUPERUSER_USERNAME=admin
railway variables set DJANGO_SUPERUSER_PASSWORD=<强密码>
railway variables set DJANGO_SUPERUSER_EMAIL=admin@example.com

# 3) 部署（自动用 backend/Dockerfile 构建；entrypoint 会自动 migrate + 建 admin）
railway up

# 4) 查看日志确认迁移成功、Gunicorn 起来
railway logs
```
- 部署成功后 Railway 会给一个后端域名（如 `https://scireagent-backend.up.railway.app`），**记下它**。

### 4.4 Vercel：部署前端（依据 `vercel-deploy` 技能）
```bash
# 1) 设置 token（从 https://vercel.com/account/tokens 生成）
export VERCEL_TOKEN="<你的 Vercel token>"

# 2) 在 frontend 目录链接/导入项目并部署（预览）
npx vercel --token "$VERCEL_TOKEN" --yes
# 或生产：npx vercel --token "$VERCEL_TOKEN" --prod --yes

# 3) 查看状态
# scripts/vercel_status.sh --project <project>
```
> Vercel 会自动识别 Vite，`buildCommand=npm run build`、`outputDirectory=dist`（已在 vercel.json 写死）。

### 4.5 回填后端域名并重部署（关键）
1. 打开 `frontend/vercel.json`，把 `<RAILWAY_BACKEND_URL>` 替换为 4.3 拿到的后端域名（**不带末尾斜杠**），例如：
   `"destination": "https://scireagent-backend.up.railway.app/api/$1"`
2. 提交并重新部署前端（`npx vercel --prod --yes`），使重写生效。
> ⚠️ 若忘了这步，前端页面能开但所有 `/api` 请求会 404。

### 4.6 验证
- 打开 Vercel 域名：首页正常、能搜索/浏览产品。
- 游客加购 → 跳登录 → 用 `admin` / 你设的 `DJANGO_SUPERUSER_PASSWORD` 登录 → 进 `/workspace` 与 `/admin/po/review`。
- 走一遍 PO 流程验证后端与 Supabase 连通。

---

## 5. 后端环境变量清单（Railway 设置）

| 变量 | 值 |
|------|----|
| `DB_ENGINE` | `postgresql` |
| `DB_NAME` | `postgres`（或 Supabase 库名） |
| `DB_USER` | `postgres` |
| `DB_PASSWORD` | Supabase 密码 |
| `DB_HOST` | Supabase host |
| `DB_PORT` | `5432` |
| `SECRET_KEY` | 随机强串（如 `python -c "import secrets;print(secrets.token_urlsafe(50))"`） |
| `ALLOWED_HOSTS` | `*`（测试期） |
| `DEBUG` | `False` |
| `DJANGO_SUPERUSER_USERNAME` | `admin` |
| `DJANGO_SUPERUSER_PASSWORD` | 强密码 |
| `DJANGO_SUPERUSER_EMAIL` | `admin@example.com` |

---

## 6. 注意事项

- **免费额度**：Railway 免费实例可能休眠，首次访问冷启动几秒；Supabase 免费 500MB；Vercel 免费额度充足。适合测试/演示，不适合长期高并发。
- **媒体文件**：免费实例文件系统重启可能清空上传的 `/media`，测试无所谓；正式环境需挂持久卷或换对象存储。
- **密钥安全**：`SECRET_KEY`、Supabase 密码、Vercel Token **不要写进仓库或截图外传**。`.env` 已被 `.dockerignore` 排除。
- **CORS**：本方案用 Vercel 重写实现同域，后端无需开 CORS。
- **`vercel-deploy` 技能提示**：其 `vercel_env.sh --set` 会把值 `echo` 到终端（审计发现的 P2 小瑕疵），设敏感变量后勿粘贴那段终端输出。

---

## 7. 回滚

- Vercel：`npx vercel rollback` 或重部署上一版。
- Railway：`railway rollback`。
- Git：前端/后端均 `git revert` 后重部署。

---

## 8. 部署技能审计说明

本次安装了两个市场技能并已做安全审计（仅 1 个 P2 级小提示，无高危）：
- **`vercel-deploy`**：封装官方 `vercel` CLI；脚本无删除/外发操作；仅 `--set` 时终端回显值。✅ 可用。
- **`web-deploy`**：纯部署指南文档，覆盖 Vercel / Railway / GitHub Pages；无附带危险脚本。✅ 可用。
