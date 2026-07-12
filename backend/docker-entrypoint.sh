#!/bin/sh
# Docker 容器启动入口：先跑迁移（幂等），可选建管理员，再启动 CMD。
# 适配三种部署目标：
#   - Hugging Face Spaces (Docker SDK)：注入 PORT(7860)、SPACE_HOST、SPACE_ID
#   - Supabase / 任意 Postgres：通过 DATABASE_URL 提供连接串
#   - 本地 Docker / Railway：常规环境变量
set -e

# --- 1) 解析 DATABASE_URL（Supabase 等提供连接串）为 Django 期望的 DB_* 变量 ---
if [ -n "${DATABASE_URL:-}" ]; then
  export DB_ENGINE=django.db.backends.postgresql
  export DB_NAME=$(echo "$DATABASE_URL" | sed -E 's#.*/([^/?]+)(\?.*)?$#\1#')
  export DB_USER=$(echo "$DATABASE_URL" | sed -E 's#.*://([^:@/]+).*#\1#')
  export DB_PASSWORD=$(echo "$DATABASE_URL" | sed -E 's#.*://[^:@/]+:([^@/]+)@.*#\1#')
  export DB_HOST=$(echo "$DATABASE_URL" | sed -E 's#.*@([^:/]+).*#\1#')
  export DB_PORT=$(echo "$DATABASE_URL" | sed -E 's#.*:([0-9]+)/.*#\1#')
  echo ">> Using DATABASE_URL -> host=$DB_HOST db=$DB_NAME"
fi

# --- 2) Hugging Face Spaces：用 SPACE_HOST 动态拼接公开域名并放开 ALLOWED_HOSTS / CORS ---
if [ -n "${SPACE_HOST:-}" ]; then
  SPACE_URL="https://${SPACE_HOST}"
  export ALLOWED_HOSTS="*"
  if [ -n "${CORS_ALLOWED_ORIGINS:-}" ]; then
    export CORS_ALLOWED_ORIGINS="${CORS_ALLOWED_ORIGINS},${SPACE_URL}"
  else
    export CORS_ALLOWED_ORIGINS="${SPACE_URL}"
  fi
  echo ">> Hugging Face Space detected: ${SPACE_URL}"
fi

# --- 3) 生产环境强制关闭 DEBUG ---
export DEBUG=False

# --- 4) 可选下载大语料 BioProCorpus（约 514MB，不进镜像）。
#   仅当显式设置 DOWNLOAD_BIOPROC=1 并提供 DATASET_BASE_URL / HF_DATASET_REPO 时拉取。
#   未下载时协议推荐/文献推荐接口静默返回空（见 protocol_recommender.py）。
if [ "${DOWNLOAD_BIOPROC:-0}" = "1" ]; then
  if [ -n "${DATASET_BASE_URL:-}" ] || [ -n "${HF_DATASET_REPO:-}" ]; then
    echo ">> DOWNLOAD_BIOPROC=1：拉取 BioProCorpus 语料..."
    python scripts/download_bioprocorpus.py || echo ">> 警告：BioProCorpus 下载失败，相关功能将降级。"
  else
    echo ">> DOWNLOAD_BIOPROC=1 但未提供 DATASET_BASE_URL/HF_DATASET_REPO，跳过。"
  fi
fi

echo ">> Running database migrations..."
python manage.py migrate --noinput

if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  echo ">> Ensuring admin superuser exists (DJANGO_SUPERUSER_*)..."
  python manage.py createsuperuser --noinput 2>/dev/null || true
fi

echo ">> Starting server..."
exec "$@"
