#!/bin/sh
# Docker 容器启动入口：先跑迁移（幂等），可选建管理员，再启动 CMD。
set -e

echo ">> Running database migrations..."
python manage.py migrate --noinput

if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  echo ">> Ensuring admin superuser exists (DJANGO_SUPERUSER_*)..."
  python manage.py createsuperuser --noinput 2>/dev/null || true
fi

echo ">> Starting server..."
exec "$@"
