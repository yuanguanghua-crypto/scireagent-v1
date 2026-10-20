#!/usr/bin/env bash
# ============================================================================
# deploy_frontend.sh — 在生产机上构建并部署前端（安全版）
#
# 为什么需要这个脚本（2026-10-20 两个真实事故）：
#
# ★ 事故一：假部署
#   之前用 `mv dist dist_prev && mv new dist` 部署。这**换掉了目录 inode**，
#   而 Docker bind mount 在容器启动时就锁定了 inode ⇒ 容器仍读旧 inode，
#   `dist` 这个路径名指向新 inode，**容器完全看不到新产物**。
#   实测证据：容器挂载源写着 `frontend/dist`，但容器内 inode=524269 属于
#   `dist_prev_20261020`；宿主机 `dist` 的 inode 是另一个。当天两次"部署成功"
#   实际都没生效，而校验读的是宿主机文件 ⇒ **假绿**。
#   ⇒ 正确做法：**不换 inode**，用 `rsync -a --delete` 改内容。
#   ⇒ 并且部署后必须**校验容器内 md5**，不能只查宿主机。
#
# ★ 事故二：备份无限堆积
#   旧流程注释写"保留 1 份可回滚"，代码只 `cp` 不删 ⇒ 3.5 个月堆了 61 个 / 200M。
#   ⇒ 本脚本部署后自动只保留最近 $KEEP 个。
#
# 用法（在生产机执行）：
#   ./scripts/deploy_frontend.sh
#   KEEP=5 ./scripts/deploy_frontend.sh          # 保留 5 个备份
#   DRY_RUN=1 ./scripts/deploy_frontend.sh       # 只构建+校验，不部署
#
# 前置：仓库已同步到目标 commit（git fetch && merge --ff-only），node_modules 就绪
# ============================================================================
set -euo pipefail

KEEP="${KEEP:-10}"                                  # 保留最近几个 dist.bak-*
REPO="${SCIREAGENT_REPO:-/home/admin/scireagent}"
FE="$REPO/frontend"
CONTAINER="${NGINX_CONTAINER:-scireagent-nginx-1}"
DRY_RUN="${DRY_RUN:-0}"
BUILD_DIR=".dist_build"

cd "$FE"

echo "=== 1/7 前置检查 ==="

# ★ 最关键的一条：dist 的 inode 必须等于容器挂载点的 inode。
#   不等就意味着"部署到 dist 也不会被容器看到"——今天踩过。
if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "✗ 找不到容器 $CONTAINER（用 NGINX_CONTAINER=... 指定）" >&2
  exit 1
fi
TARGET_INODE="$(docker exec "$CONTAINER" stat -c %i /usr/share/nginx/html)"
DIST_INODE="$(stat -c %i dist)"
echo "  容器挂载 inode: $TARGET_INODE"
echo "  dist 目录 inode: $DIST_INODE"
if [ "$DIST_INODE" != "$TARGET_INODE" ]; then
  cat >&2 <<EOF
✗ dist 的 inode 与容器挂载点不一致 —— 部署进去容器看不到！

  常见原因：之前用 mv 换过 dist 目录。
  修正（二选一）：
    a) 找到 inode=$TARGET_INODE 的那个目录，把 dist 改成指向它：
         for d in dist*; do [ "\$(stat -c %i \$d)" = "$TARGET_INODE" ] && echo "  命中: \$d"; done
    b) 或重启 nginx 让它重新解析路径（会短暂中断）：
         docker compose restart nginx
EOF
  exit 1
fi
echo "  ✓ inode 一致"

HEAD_SHORT="$(git -C "$REPO" rev-parse --short HEAD)"
echo "  HEAD: $HEAD_SHORT"

echo "=== 2/7 构建到 $BUILD_DIR（不动线上 dist）==="
rm -rf "$BUILD_DIR"
if ! npx vite build --outDir "$BUILD_DIR" --emptyOutDir; then
  echo "✗ 构建失败，线上 dist 未改动" >&2
  rm -rf "$BUILD_DIR"
  exit 1
fi

echo "=== 3/7 校验产物 ==="
[ -f "$BUILD_DIR/index.html" ] || { echo "✗ 产物缺 index.html" >&2; exit 1; }
ASSETS=$(find "$BUILD_DIR/assets" -type f 2>/dev/null | wc -l)
[ "$ASSETS" -gt 0 ] || { echo "✗ 产物没有 assets" >&2; exit 1; }
META=$(grep -o 'build-commit" content="[^"]*"' "$BUILD_DIR/index.html" 2>/dev/null \
       | head -1 | sed 's/.*content="//; s/"$//') || true
[ -n "$META" ] || { echo "✗ 产物缺 build-commit meta（vite.config.js 的注入没生效）" >&2; exit 1; }
echo "  ✓ index.html + $ASSETS assets，build-commit=$META"
if [ "${META:0:7}" != "$HEAD_SHORT" ] && [ "$META" != "unknown" ]; then
  echo "  ⚠️ 产物标注 $META，但 HEAD 是 $HEAD_SHORT（BUILD_COMMIT 环境变量覆盖过？）" >&2
fi

if [ "$DRY_RUN" = "1" ]; then
  echo "=== DRY_RUN=1：到此为止，不部署 ==="
  rm -rf "$BUILD_DIR"
  exit 0
fi

echo "=== 4/7 备份当前 dist（cp，不换 inode）==="
BAK="dist.bak-$(date +%Y%m%d-%H%M%S)"
cp -a dist "$BAK"
echo "  ✓ $BAK"

echo "=== 5/7 部署（rsync -a --delete，保留 inode）==="
rsync -a --delete "$BUILD_DIR"/ dist/
echo "  ✓ 内容已同步"

echo "=== 6/7 校验：容器内是否真的变了（防假绿）==="
HOST_MD5="$(md5sum dist/index.html | cut -d' ' -f1)"
CONTAINER_MD5="$(docker exec "$CONTAINER" md5sum /usr/share/nginx/html/index.html | cut -d' ' -f1)"
echo "  宿主机 dist/index.html : $HOST_MD5"
echo "  容器内 index.html      : $CONTAINER_MD5"
if [ "$HOST_MD5" != "$CONTAINER_MD5" ]; then
  cat >&2 <<EOF
✗ 容器内的文件与宿主机不一致 ⇒ 部署实际没生效。
  最可能仍是 inode 问题（见步骤 1）。线上仍服务旧产物，但至少没坏。
EOF
  exit 1
fi
echo "  ✓ 容器内已更新"

echo "=== 7/7 清理旧备份（保留最近 $KEEP 个）==="
BEFORE=$(ls -d dist.bak-* 2>/dev/null | wc -l)
ls -dt dist.bak-* 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -rf || true
AFTER=$(ls -d dist.bak-* 2>/dev/null | wc -l)
echo "  备份数：$BEFORE → $AFTER（上限 $KEEP）"

rm -rf "$BUILD_DIR"

cat <<EOF

✅ 部署完成
   commit      : $META
   容器内 md5  : $CONTAINER_MD5
   备份        : 保留 $AFTER 个
   下一步      : 在本地跑 python scripts/check_deploy_consistency.py 复核 C7/C8
EOF
