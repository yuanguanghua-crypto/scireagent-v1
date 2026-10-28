#!/usr/bin/env bash
# 本地 PostgreSQL 启停 —— 一条命令，不需要记 pg_ctl 参数
#
# 为什么需要这个脚本（2026-10-28）：
#   本项目所有代码路径都以 PostgreSQL 为唯一目标库（生产 16.14）。此前本地开发用 sqlite，
#   结果是「生产在用的全文检索、并发互斥」两类代码路径从未被验证过 —— 实测切到 PG 后
#   立刻暴露 5 条假绿测试 + 1 条会把整个测试跑永久卡死的死锁。
#   ⇒ 本地必须用 PG，且不能要求操作者记得 `-D`/`-o`/端口这些细节。
#
# 用法：
#   bash scripts/dev_db.sh start     # 启动（已在跑则直接返回成功）
#   bash scripts/dev_db.sh stop      # 停止
#   bash scripts/dev_db.sh status    # 看状态（0=在跑 1=没跑）
#   bash scripts/dev_db.sh ensure    # 不在跑就启动（测试脚本内部用）
#
# 可覆盖的环境变量：
#   SCIREAGENT_PGDATA  PG 数据目录（默认 <workspace>/pgdata-l4）
#   SCIREAGENT_PGPORT  端口（默认 5433）
#   SCIREAGENT_PGUSER  超级用户（默认 scireagent；本集群是 trust 认证，无密码）
set -uo pipefail

PGDATA="${SCIREAGENT_PGDATA:-$(cd "$(dirname "$0")/../.." && pwd)/pgdata-l4}"
PGPORT="${SCIREAGENT_PGPORT:-5433}"
PGUSER="${SCIREAGENT_PGUSER:-scireagent}"

# pg_ctl 定位：优先 pg_config（装了 PATH 的话），否则退回 Windows 默认安装路径
if command -v pg_config >/dev/null 2>&1; then
  PGBIN="$(pg_config --bindir)"
else
  PGBIN=""
  for c in "/c/Program Files/PostgreSQL/17/bin" "/c/Program Files/PostgreSQL/16/bin"; do
    [ -x "$c/pg_ctl.exe" ] && { PGBIN="$c"; break; }
  done
fi
PGCTL="$PGBIN/pg_ctl.exe"
[ -x "$PGCTL" ] || PGCTL="$PGBIN/pg_ctl"
PGISREADY="$PGBIN/pg_isready.exe"
[ -x "$PGISREADY" ] || PGISREADY="$PGBIN/pg_isready"

if [ ! -x "$PGCTL" ]; then
  echo "✗ 找不到 pg_ctl（试过 pg_config 与 C:\\Program Files\\PostgreSQL\\{17,16}\\bin）" >&2
  echo "  请安装 PostgreSQL，或用 SCIREAGENT_PGDATA/pg_config 指定位置。" >&2
  exit 2
fi
if [ ! -d "$PGDATA" ]; then
  echo "✗ 数据目录不存在：$PGDATA" >&2
  echo "  首次使用需初始化（仅一次）：" >&2
  echo "    \"$PGBIN/initdb\" -D \"$PGDATA\" -U $PGUSER -A trust -E UTF8" >&2
  exit 2
fi

is_up() {
  if [ -x "$PGISREADY" ]; then
    "$PGISREADY" -h 127.0.0.1 -p "$PGPORT" >/dev/null 2>&1
  else
    (echo > "/dev/tcp/127.0.0.1/$PGPORT") >/dev/null 2>&1
  fi
}

case "${1:-status}" in
  start)
    if is_up; then echo "✓ PostgreSQL 已在 $PGPORT 运行"; exit 0; fi
    # ⚠️ 必须用 pg_ctl（不要直接跑 postgres.exe）：Windows 下 pg_ctl 会自动降权，
    #    而直接跑 postgres.exe 在管理员身份下会被拒绝（"administrative permissions"）。
    "$PGCTL" -D "$PGDATA" -o "-p $PGPORT -c listen_addresses=127.0.0.1" -W start >/dev/null 2>&1
    for _ in $(seq 1 30); do is_up && { echo "✓ PostgreSQL 已启动（端口 $PGPORT）"; exit 0; }; sleep 1; done
    echo "✗ 启动失败，看日志：$PGDATA/server.log（或手动前台跑一次看报错）" >&2
    exit 1
    ;;
  stop)
    if ! is_up; then echo "✓ PostgreSQL 本来就没在跑"; exit 0; fi
    "$PGCTL" -D "$PGDATA" -m fast -W stop >/dev/null 2>&1
    echo "✓ PostgreSQL 已停止"
    ;;
  status)
    if is_up; then echo "在跑：127.0.0.1:$PGPORT"; exit 0; else echo "没在跑"; exit 1; fi
    ;;
  ensure)
    if is_up; then exit 0; fi
    exec "$0" start
    ;;
  *)
    echo "用法: bash scripts/dev_db.sh {start|stop|status|ensure}" >&2
    exit 2
    ;;
esac
