#!/usr/bin/env bash
# 跑后端测试 —— 一条命令，自动起库 + 自动设置 6 个环境变量
#
# 为什么需要这个脚本（2026-10-28）：
#   跑 PG 测试要同时给 5 个变量（DB_ENGINE/DB_NAME/DB_USER/DB_HOST/DB_PORT）+ SECRET_KEY。
#   漏一项就会**静默落回 sqlite**，然后看到"全绿"却什么也没验证到 —— 这正是本项目
#   吃了几个月的亏（生产在用的全文检索/并发路径一次都没跑过）。
#   所以这里：① 先确保 PG 在跑；② 变量全部显式给；③ **打印实际用的引擎**，
#   让"到底连的是哪个库"一眼可见，不给"假绿"留空间。
#
# 用法：
#   bash scripts/dev_test.sh                       # 跑全量
#   bash scripts/dev_test.sh apps/inventory        # 只跑某目录/文件（透传给 pytest）
#   bash scripts/dev_test.sh -k oversell           # 透传任意 pytest 参数
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
BACKEND="$REPO/backend"

PGHOST="${SCIREAGENT_PGHOST:-127.0.0.1}"
PGPORT="${SCIREAGENT_PGPORT:-5433}"
PGDB="${SCIREAGENT_PGDB:-scireagent_l4}"
PGUSER="${SCIREAGENT_PGUSER:-scireagent}"

# ① 确保数据库在跑（不在跑就起）
bash "$HERE/dev_db.sh" ensure || { echo "✗ 数据库起不来，终止（不会有任何测试被执行）" >&2; exit 2; }

# ② 显式给全环境变量：绝不依赖 .env，避免"以为在测 PG、其实落回 sqlite"
export DB_ENGINE="django.db.backends.postgresql"
export DB_NAME="$PGDB"
export DB_USER="$PGUSER"
export DB_PASSWORD=""
export DB_HOST="$PGHOST"
export DB_PORT="$PGPORT"
# SECRET_KEY：pytest 的 argv 里没有 'test'，base.py 会强制要求它
export SECRET_KEY="${SECRET_KEY:-local-test-only-not-a-real-secret}"

# ③ 自证连接目标（防止静默落回其它库）
echo "── 测试数据库：${DB_ENGINE} | ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME} ──"

cd "$BACKEND" || exit 2
PY="$BACKEND/venv/Scripts/python.exe"
[ -x "$PY" ] || PY="python"

exec "$PY" -m pytest -q --tb=short -p no:cacheprovider "$@"
