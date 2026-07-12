# SciReAgent 部署指南 — 阿里云国际站单机全栈（推荐）

> 适用：把本机最终版本部署到**阿里云国际站（香港 / 新加坡）轻量应用服务器**，单机跑全套：
> PostgreSQL + Django(gunicorn) + Nginx(反代 API + 托管前端 dist)。
> 地域选香港/新加坡的理由：你在国内、同事在美国，两边都正常访问、无需 ICP 备案、延迟可接受。
> 大数据集（bioprocorpus 514MB / jena 3MB）**一次性上传到服务器持久盘常驻**，不进镜像、不每次冷启动重拉。

---

## 0. 架构总览

```
                        ┌──────────────── 阿里云轻量服务器 (香港/新加坡) ────────────────┐
   浏览器 / 同事访问 ──▶ │  80/443  Nginx 容器                                            │
   https://域名         │   ├─ 托管 frontend/dist (SPA)                                  │
                        │   ├─ /api /admin  ──proxy──▶ Django 容器 (gunicorn :8000)      │
                        │   ├─ /static /media ──读挂载卷                                 │
                        │   │                                                          │
                        │   Django 容器                                                │
                        │   ├─ 读 PostgreSQL 容器 (db:5432)                             │
                        │   ├─ 读 ./data/bioprocorpus (绑定挂载, 常驻)  ← 一次性上传     │
                        │   └─ jena 已随镜像发布 (3MB)                                   │
                        └──────────────────────────────────────────────────────────────┘
```

仓库内已准备好：
- `docker-compose.yml` — db + backend + nginx 三服务编排
- `deploy/nginx.conf` — Nginx 配置（SPA 回退 + 反代 + 静态/媒体）
- `deploy/.env.example` — 生产环境变量模板
- `backend/Dockerfile` + `backend/docker-entrypoint.sh` — 云原生镜像（读 `DB_*`/`SECRET_KEY`/`PORT`/`DEBUG`）
- `frontend/build-cloudflare.sh` — 前端构建（注入后端域名，主机无关，通用）
- `backend/scripts/migrate_sqlite_to_postgres.sh` — 本地 SQLite → Postgres 数据迁移

---

## 1. 购买与初始化服务器

1. 登录 **阿里云国际站** https://www.alibabacloud.com → 轻量应用服务器（Lightweight Application Server）。
2. 地域选 **中国香港** 或 **新加坡**；镜像选 **Ubuntu 22.04 LTS**；规格 **2 vCPU / 4 GB 起**（rdkit 较吃内存，4GB 稳妥；若跑得吃力升 8GB）。
3. 防火墙放行 **22 / 80 / 443**。
4. 购买域名（可选，国际站无需备案）并把 **A 记录**指向服务器公网 IP。
5. SSH 登录后初始化：

```bash
# 安装 Docker + compose 插件
sudo apt update && sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER   # 退出重登生效
docker --version && docker compose version
```

---

## 2. 拉取代码与配置

```bash
git clone https://github.com/yuanguanghua-crypto/scireagent.git
cd scireagent

# 生产环境变量
cp deploy/.env.example .env
nano .env     # 改 SECRET_KEY / DB_PASSWORD / DJANGO_SUPERUSER_PASSWORD / ALLOWED_HOSTS / CORS_ALLOWED_ORIGINS
```

`.env` 关键项（其余见文件内注释）：

| 变量 | 说明 |
|---|---|
| `SECRET_KEY` | `openssl rand -base64 48` 生成，切勿留默认 |
| `ALLOWED_HOSTS` | 你的域名，逗号分隔（如 `example.com,www.example.com`） |
| `CORS_ALLOWED_ORIGINS` | `https://你的域名`（前端来源） |
| `DB_PASSWORD` / `DJANGO_SUPERUSER_PASSWORD` | 强密码 |
| `BIOPROCORPUS_DIR` | 保持默认 `/app/backend/data/bioprocorpus`（对应 compose 挂载） |

> `.env` 已被 `.gitignore` 忽略，不会进仓库。

---

## 3. 构建前端

前端用**运行时配置** `public/runtime-config.js` 指向后端域名，构建时注入，无需改代码：

```bash
cd frontend
# 注入后端基地址（协议+域名+/api/v1），构建产出 dist/
VITE_API_BASE_URL=https://<你的域名>/api/v1 ./build-cloudflare.sh
cd ..
```

构建完成后 `frontend/dist/` 存在，Nginx 会挂载它。（`frontend/dist/` 已被 gitignore 忽略。）

---

## 4. 上传大数据集（一次性，常驻持久盘）

bioprocorpus(514MB) 不进镜像，部署时一次性传到服务器；jena(3MB) 已随镜像发布，无需操作。

```bash
# 在本机（代码所在机器）执行，把数据集推到服务器的绑定挂载目录
mkdir -p data/bioprocorpus
scp -r backend/data/bioprocorpus/* <你的SSH用户>@<服务器IP>:~/scireagent/data/bioprocorpus/

# 若也想把 jena 放到外部路径（可选，默认用镜像内那份即可）：
# scp -r backend/data/jena/* <用户>@<IP>:~/scireagent/data/jena/
```

> compose 已把主机 `./data/bioprocorpus` 只读绑定进容器 `/app/backend/data/bioprocorpus`，与 `BIOPROCORPUS_DIR` 默认路径一致。服务器重启后文件仍在（持久盘）。

**替代方案（不手动 scp）**：在 `.env` 设 `DOWNLOAD_BIOPROC=1` + `DATASET_BASE_URL`(或 `HF_DATASET_REPO`)，容器启动期自动拉取（仅首次；之后容器内已存在则跳过）。详见 `backend/scripts/download_bioprocorpus.py`。

---

## 5. 启动

```bash
docker compose up -d --build
docker compose ps            # 三个服务应均为 healthy/running
docker compose logs -f backend   # 看迁移与管理员创建日志
```

启动后 entrypoint 会自动：`migrate` 建表 → 建管理员（若 `DJANGO_SUPERUSER_*` 已设）→ 可选下载数据集 → 启动 gunicorn。

访问 `http://<服务器IP>`（或你的域名）即可看到前端；`/admin` 用上面设的管理员登录。

---

## 6. 迁移本地数据（可选，复用现有测试/生产数据）

本机已有一份 SQLite 数据想搬到云上：

```bash
# 1) 本机导出 fixture
cd backend
DB_ENGINE=sqlite ./scripts/migrate_sqlite_to_postgres.sh dump     # 产出 data/migrate_dump.json

# 2) 传到服务器并在容器内导入（容器内 Postgres 通过 db:5432 访问）
scp data/migrate_dump.json <用户>@<IP>:~/scireagent/backend/data/migrate_dump.json
# 在服务器上：
docker compose exec backend python manage.py loaddata data/migrate_dump.json
# 媒体文件单独传：
scp -r media/* <用户>@<IP>:~/scireagent/media/   # 服务器 media 卷对应 /app/media
```

> 若数据库为空（全新部署），跳过第 6 步，直接在前端 /admin 建数据即可。

---

## 7. 启用 HTTPS（生产必做）

国际站无需备案，直接用 Let's Encrypt 免费证书：

```bash
# 在服务器上安装 certbot 并申请（需已解析域名 A 记录）
sudo apt install -y certbot
sudo certbot certonly --webroot -w ~/scireagent/frontend/dist -d <你的域名> -d www.<你的域名>

# 把证书挂进 nginx 容器：deploy/certbot/conf 已在 compose 中挂载 /etc/letsencrypt
# 取消 deploy/nginx.conf 末尾 443 server 段的注释，并把 server_name / 证书路径改成你的域名
# 重启 nginx：
docker compose restart nginx
```

也可在服务器装 `certbot` 的 nginx 插件自动改写配置。证书续期：`sudo certbot renew`。

---

## 8. 日常运维

```bash
docker compose ps                 # 状态
docker compose logs -f <服务>     # 看日志 (backend/db/nginx)
docker compose pull && docker compose up -d --build   # 更新代码后重新部署
docker compose down               # 停止（数据卷保留）
```

- **更新代码**：`git pull` → 改 `.env`（如有） → `docker compose up -d --build`。
- **备份数据库**：`docker compose exec db pg_dump -U scireagent scireagent > backup.sql`。
- **查看数据集是否就位**：`docker compose exec backend ls -la /app/backend/data/bioprocorpus`。

---

## 9. 费用估算（香港/新加坡轻量）

| 规格 | 年费（约） | 说明 |
|---|---|---|
| 2C4G | ¥300–500/年 | 够用（rdkit + gunicorn + postgres） |
| 2C8G | ¥500–800/年 | 更稳，推荐 |
| 4C8G | ¥800–1200/年 | 余量充足 |

比 HF 免费版+$5/月持久盘（≈¥430/年且仍有冷启动/休眠限制）更省心、更整，且无"休眠后重拉 514MB"问题。

---

## 10. 以后上 AWS（正式上线）

代码与镜像**零改动**，仅换基础设施：
- 镜像推到 **ECR**，跑在 **ECS Fargate**（或 EKS）。
- 数据库换 **RDS PostgreSQL**（改 `DB_*` 或 `DATABASE_URL` 环境变量）。
- 前端 `dist/` 传 **S3 + CloudFront**（或保持 Nginx/ALB）。
- 大数据集放 **EBS 卷** 或 **S3 挂载**，环境变量 `BIOPROCORPUS_DIR` 指向挂载点。
- `docker-compose.yml` / `deploy/nginx.conf` / `deploy/.env.example` 全部云原生就绪，可直接作为 ECS task / Helm 的参考。

---

## 附：与「HF 免费方案」的取舍

| 维度 | 阿里云单机（本方案） | HF Spaces 免费 + Supabase + Cloudflare |
|---|---|---|
| 大数据集 | 一次上传常驻，零重拉 | 免费版临时盘+休眠，每次唤醒重拉 514MB |
| 架构 | 单机全栈，运维点少 | 三平台拼接 |
| 备案 | 国际站无需 | 无需 |
| 费用 | ¥300–800/年 | HF $5/月持久盘 + 另购库（≈¥430/年起） |
| 适用 | 必要后台模块 + 少量内部用户 | 纯静态/无重数据的轻量 demo |

HF 免费方案仍保留在 `docs/DEPLOY_FREE_PLAN.md` 作为零成本备选。
