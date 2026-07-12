#!/usr/bin/env bash
# 数据迁移：本地 SQLite -> Supabase(Postgres)
# 仅迁移数据库内容；媒体文件(media/)为文件系统，需另行传输（见脚本末尾说明）。
#
# 用法：
#   1) 备份本地数据到 fixture：
#        DB_ENGINE=sqlite ./scripts/migrate_sqlite_to_postgres.sh dump
#   2) 在 Supabase 项目建好后，导入 fixture（指向云端 Postgres）：
#        DATABASE_URL="postgres://user:pass@db.xxxx.supabase.co:5432/postgres" \
#        SECRET_KEY="临时任意串" \
#        ./scripts/migrate_sqlite_to_postgres.sh load
#
# 说明：
#   - 使用 Django 原生 dumpdata/loaddata，避免手写 SQL、避免数据结构差异。
#   - 导入前会先 migrate 建表，再 loaddata（fixture 已含 pk，幂等覆盖）。
#   - 媒体文件不在此脚本内；请单独用 scp/rsync 把 backend/media 传到后端主机。

set -e
cd "$(dirname "$0")/.."   # 回到 backend 目录
PY="${PYTHON:-python}"

MODE="${1:-dump}"

if [ "$MODE" = "dump" ]; then
  echo ">> Dumping local (SQLite) data to data/migrate_dump.json ..."
  DB_ENGINE=sqlite "$PY" manage.py dumpdata \
    --natural-foreign \
    --natural-primary \
    --indent 2 \
    -o data/migrate_dump.json \
    accounts \
    knowledge \
    commerce \
    transactions \
    quotes \
    assets \
    core

elif [ "$MODE" = "load" ]; then
  if [ -z "${DATABASE_URL:-}" ]; then
    echo "ERROR: 请设置 DATABASE_URL 指向 Supabase Postgres" >&2
    exit 1
  fi
  echo ">> Migrating target database ..."
  "$PY" manage.py migrate --noinput
  echo ">> Loading fixture data/migrate_dump.json into Supabase ..."
  "$PY" manage.py loaddata data/migrate_dump.json
  echo ">> Done. 请在后端 /admin 核对数据条数。"

else
  echo "用法: $0 [dump|load]" >&2
  exit 1
fi

echo ""
echo "=== 媒体文件（不入库）单独传输 ==="
echo "把 backend/media/ 整个目录传到后端运行环境（HF Space / 云主机）的 /app/media："
echo "  scp -r backend/media <user>@<host>:/app/media"
echo "并在后端设置 MEDIA_ROOT=/app/media（当前生产设置已默认 /app/media）。"
