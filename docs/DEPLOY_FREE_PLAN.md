# SciReAgent 免费平台部署方案（Hugging Face Spaces + Supabase + Cloudflare Pages）

> 目标：让外地同事在浏览器里**真实浏览、测试、操作**全站（含加购/下单/PO 全流程），零服务器成本。
> 适用：测试 / 演示阶段。正式生产请升级到付费实例 + 独立域名 + HTTPS + 定期备份（见末尾「何时升级到 AWS」）。
> 文档版本：2026-07-12（与本仓库代码同步）

---

## 0. 为什么是这个组合

后端硬依赖 `rdkit`（化学结构渲染，核心功能），运行时内存占用高。免费平台里：

| 平台 | 免费内存 | 结论 |
|------|----------|------|
| Render | 512MB | ❌ Django+rdkit 大概率 OOM |
| **Hugging Face Spaces (Docker)** | **16GB** | ✅ rdkit 无压力，免费 |
| Koyeb / Fly 等 | 需绑卡 | ❌ 不满足纯免费 |

故：
- **后端** → Hugging Face Spaces（Docker SDK，免费 16GB，rdkit 安全）
- **数据库** → Supabase 免费 Postgres（500MB，GiTHub 学生/普通均可用）
- **前端** → Cloudflare Pages（免费、无带宽上限、SPA 友好）

> 代价：HF Space 免费版约 48 小时无访问会休眠，唤醒约 30–60 秒（仅后端，前端 Cloudflare 无休眠）。对测试找 bug 完全可接受。正式上线换 AWS 即无此问题。

---

## 1. 架构与访问流

```
外地同事浏览器
  └─ Cloudflare Pages  https://<project>.pages.dev        ← 前端 Vue build 产物
       └─ 运行时配置 runtime-config.js 指向：
            └─ HF Space 域名  https://<space>.hf.space      ← Django + Gunicorn (rdkit)
                 └─ Supabase Postgres                       ← 业务数据
```

要点：
- 前端 API base 通过 **运行时配置** `public/runtime-config.js` 注入（构建时填入后端域名），前端据此调用 `https://<space>.hf.space/api/v1/...`。见 `frontend/src/utils/http.js`。
- 后端 `ALLOWED_HOSTS=*`、CORS 含前端域名（由 entrypoint 用 `SPACE_HOST` 自动设置），无需手动改代码。

---

## 1.1 大本地数据集（jena / bioprocorpus）处理

后端依赖两个本地语料，均已由 `.gitignore` 排除、**不进 GitHub**；且 Docker 构建也不打进镜像（`.dockerignore` 排除），避免镜像膨胀/构建超时。两者在**文件缺失时均静默降级为空索引（不崩溃）**，仅影响个别 AI 功能：

| 数据集 | 大小 | 用途 | 缺失时影响 | 部署策略 |
|--------|------|------|------------|----------|
| `backend/data/jena/jena_products_v2.jsonl` | ~3MB | AI AUTO MATCH 标识符匹配 | 无匹配建议，其余正常 | **bake 进镜像**（已加 `.gitignore`/`.dockerignore` 例外） |
| `backend/data/bioprocorpus/` | ~514MB | 协议推荐 / 文献推荐检索语料 | 推荐/文献接口返回空，浏览/加购/下单正常 | **不进镜像**；按需启动期下载 |

### BioProCorpus 按需下载（可选，默认不下载）
仅在需要「协议推荐 / 文献推荐」功能时开启。HF Space Secrets / 容器环境变量设置：
```
DOWNLOAD_BIOPROC=1
DATASET_BASE_URL=https://<你的对象存储>/bioprocorpus/      # 指向 .tar.gz 或 manifest.txt 目录
# 或：HF_DATASET_REPO=youruser/bioprocorpus                # 用 huggingface_hub 拉取
```
- entrypoint 在迁移前调用 `scripts/download_bioprocorpus.py`：目录非空则跳过；下载失败仅告警、功能降级。
- 数据源需你自行托管（S3 / Supabase Storage / GitHub Release / HF dataset）。**本项目不提供托管 URL**——这是你的大文件，请放到你能控制的位置。
- 若不设 `DOWNLOAD_BIOPROC=1`：镜像不含该 514MB，启动快、体积小；协议推荐接口返回空，同事测试网站其余功能完全无碍。

> 测试阶段建议**先不下载** BioProCorpus（绝大多数功能点不受影响），等需要专门验证协议推荐时再开。jena 已随镜像内置，AI AUTO MATCH 默认可用。

---

## 2. 前置账号（全部免费，需自行注册）

| 平台 | 用途 | 获取 |
|------|------|------|
| GitHub | 代码已推（私有仓库 `yuanguanghua-crypto/scireagent`） | 已完成 |
| Hugging Face | 后端 Docker 空间 | https://huggingface.co/join |
| Supabase | Postgres 数据库 | https://supabase.com |
| Cloudflare | 前端 Pages | https://pages.cloudflare.dev （可用 GitHub 登录） |

> 部署动作需要这些平台凭据：HF 的 **Write Token**（设置→Access Tokens）、Supabase **连接串**、Cloudflare Pages 关联 GitHub 仓库（网页操作即可，无需 token）。由你提供 HF Token 后，可脚本化建 Space 并推送镜像。

---

## 3. 仓库已做的准备（本仓库已包含）

| 文件 | 改动 | 原因 |
|------|------|------|
| `backend/Dockerfile` | `python:3.12-slim`；collectstatic 改 `development` 设置避免构建期连库；`CMD` 读 `PORT` | HF Space 注入 `PORT=7860`；构建期无生产密钥 |
| `backend/docker-entrypoint.sh` | 解析 `DATABASE_URL`→`DB_*`；`SPACE_HOST`→动态 `ALLOWED_HOSTS`/`CORS`；强制 `DEBUG=False` | 适配 Supabase + HF Space |
| `backend/.dockerignore` | 排除 `venv/`、`node_modules/`、`.git` | 镜像干净 |
| `frontend/src/utils/http.js` | 读取 `window.__RUNTIME_CONFIG__.API_BASE_URL`，缺省走 `/api/v1` | 运行时指向真实后端，免重建 |
| `frontend/public/runtime-config.js` | 占位 `__BACKEND_API_BASE__`，构建时注入 | 部署期填后端域名 |
| `frontend/build-cloudflare.sh` | Cloudflare 构建脚本（注入后端域名+`vite build`） | Pages 构建命令 |
| `frontend/public/_routes.json` | SPA 回退，排除 `/api /static /media` | Pages 路由 |
| `backend/scripts/migrate_sqlite_to_postgres.sh` | 本地 SQLite→Supabase 数据迁移 | 复用现有测试数据 |

---

## 4. 部署步骤

### 4.1 Supabase：建 Postgres
1. 登录 Supabase → New project → 记下 **Connection string (URI)**，形如：
   `postgres://postgres:<password>@db.<project>.supabase.co:5432/postgres`
2. 端口用直连 `5432`。

### 4.2 Hugging Face Spaces：部署后端（Docker SDK）
1. HF → 设置 → Access Tokens → 生成 **Write** token（如 `hf_xxx`）。
2. 在项目里建 Space：
   - Space name：`scireagent-backend`
   - SDK：**Docker**
   - 可见性：Public（或 Private，但同事需有 HF 账号并被邀请）
3. 把仓库代码推到该 Space 的 git（Space 本质是带特殊远端的 git 仓库，`sdk:Docker` 时直接用仓库根 Dockerfile）：
   ```bash
   # 在 backend 目录
   git init tmp-space && cd tmp-space
   git remote add space https://<HF_USER>:<HF_TOKEN>@huggingface.co/spaces/<HF_USER>/scireagent-backend
   # 复制 backend 内容 + 提交 + push（或用 huggingface_hub CLI）
   ```
4. Space Settings → Variables and secrets 设置：
   - `DATABASE_URL` = 4.1 的连接串
   - `SECRET_KEY` = 随机强串（`python -c "import secrets;print(secrets.token_urlsafe(50))"`）
   - `DJANGO_SUPERUSER_USERNAME` = `admin`
   - `DJANGO_SUPERUSER_PASSWORD` = 强密码
   - `DJANGO_SUPERUSER_EMAIL` = `admin@example.com`
   - （`SPACE_HOST` 由平台自动注入，无需手填）
5. 部署后 Space 给域名 `https://<HF_USER>-scireagent-backend.hf.space`，**记下它**。

### 4.3 数据迁移（本地 SQLite → Supabase）
```bash
cd backend
# 1) 导出本地数据
DB_ENGINE=sqlite ./scripts/migrate_sqlite_to_postgres.sh dump
# 2) 导入到 Supabase（设置好 DATABASE_URL + SECRET_KEY）
DATABASE_URL="postgres://postgres:<pw>@db.<proj>.supabase.co:5432/postgres" \
SECRET_KEY="临时串" \
./scripts/migrate_sqlite_to_postgres.sh load
# 3) media 文件单独传（见脚本尾部说明）
```
> 若不想迁移旧数据，可跳过——entrypoint 会自动 `migrate` 建空表，登录 admin 后手动录入。

### 4.4 Cloudflare Pages：部署前端
1. Cloudflare Dashboard → Workers & Pages → Create → Pages → 关联 GitHub 仓库 `yuanguanghua-crypto/scireagent`。
2. 项目设置：
   - **Root directory**：`frontend`
   - **Build command**：`./build-cloudflare.sh`
   - **Build output directory**：`dist`
   - **环境变量**：`VITE_API_BASE_URL` = `https://<HF_USER>-scireagent-backend.hf.space/api/v1`（4.2 的域名 + `/api/v1`）
3. 保存并部署。Pages 给域名 `https://<project>.pages.dev`，**发给同事即可**。

### 4.5 验证
- 打开 Cloudflare 域名：首页正常、搜索/浏览产品。
- 游客加购 → 跳登录 → 用 `admin`/你设的 `DJANGO_SUPERUSER_PASSWORD` 登录 → 进 `/workspace` 与 `/admin`。
- 产品详情页「从 SMILES 生成结构图」验证 rdkit 在 HF 16GB 下正常渲染。
- 走一遍 PO 流程验证后端与 Supabase 连通。

---

## 5. 后端环境变量清单（HF Space Secrets）

| 变量 | 值 |
|------|----|
| `DATABASE_URL` | Supabase 连接串（4.1） |
| `SECRET_KEY` | 随机强串 |
| `DEBUG` | `False`（entrypoint 强制） |
| `DJANGO_SUPERUSER_USERNAME` | `admin` |
| `DJANGO_SUPERUSER_PASSWORD` | 强密码 |
| `DJANGO_SUPERUSER_EMAIL` | `admin@example.com` |
| `SPACE_HOST` | 自动注入（勿填） |
| `PORT` | 自动注入（默认 7860） |

---

## 6. 注意事项

- **休眠**：HF Space 免费版约 48h 无访问休眠，唤醒 30–60s；Cloudflare 前端不休眠。
- **媒体文件**：HF Space 文件系统临时，重启可能清空 `/media`；测试阶段可接受，正式环境挂持久卷或对象存储（Supabase Storage / S3）。
- **密钥安全**：`SECRET_KEY`、Supabase 密码、HF Token 不要写进仓库。本仓库 `.env` 已被 `.dockerignore` 排除，`runtime-config.js` 仅含占位符。
- **CORS**：前端走绝对后端域名，后端 entrypoint 已用 `SPACE_HOST` 把前端域名加入 `CORS_ALLOWED_ORIGINS`；若同事用自定义域，可在 Space Secrets 增 `CORS_ALLOWED_ORIGINS` 追加。

---

## 7. 回滚

- Cloudflare Pages：部署历史一键回滚。
- HF Space：git push 上一版 / Space 设置 Rollback。
- Git：本仓库 `git revert` 后重部署。

---

## 8. 何时升级到 AWS（正式上线）

免费组合适合测试。正式上线建议迁移到 **AWS**：

| 组件 | 免费方案 | AWS 对应 |
|------|----------|----------|
| 后端 | HF Spaces (16GB, 会休眠) | **ECS Fargate** 或 **Elastic Beanstalk**（Docker 直接复用本 Dockerfile）；内存按需 1–4GB，常驻不休眠 |
| 数据库 | Supabase Postgres | **RDS for PostgreSQL**（多可用区、自动备份、只读副本） |
| 前端 | Cloudflare Pages | **S3 + CloudFront**（或继续用 Cloudflare） |
| 媒体 | 临时盘 | **S3** + CloudFront |
| 域名/HTTPS | `.pages.dev` / `.hf.space` | **Route 53** + **ACM** 证书 |
| 密钥 | Space Secrets | **Secrets Manager** / **Systems Manager Parameter Store** |
| 容器镜像 | HF 构建 | **ECR** 托管镜像 |

迁移成本评估：
- 后端 Dockerfile / entrypoint 已云原生就绪（读 `DATABASE_URL`、`PORT`、`SECRET_KEY`），**改环境变量即可上 ECS**，无需重构代码。
- 数据库从 Supabase 迁 RDS：同为 Postgres，`pg_dump`/`pg_restore` 或复用本仓库 `migrate_sqlite_to_postgres.sh` 思路（dumpdata/loaddata）即可。
- 前端 Cloudflare→S3+CloudFront：`vite build` 产物直接上传，构建脚本复用。
- 预估工作量：基础设施搭建 0.5–1 天 + 数据迁移 + DNS 切换。

> 结论：现在用免费平台让同事快速测试、找 bug；等测试稳定、准备正式发布时，按上表迁移到 AWS，代码与 Docker 几乎零改动。
