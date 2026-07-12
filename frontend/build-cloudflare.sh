#!/usr/bin/env sh
# Cloudflare Pages 构建脚本
# 用法：把本文件设为 Cloudflare Pages 的 "Build command"，Output 设为 dist，Root 设为 frontend。
# 平台变量：
#   VITE_API_BASE_URL  真实后端基地址，例如 https://scireagent-backend.hf.space/api/v1
# 构建后把该值注入到 public/runtime-config.js（window.__RUNTIME_CONFIG__.API_BASE_URL），
# 前端据此在运行时指向后端，无需重建。

set -e

# 默认走相对路径（同源 / 本地），仅当显式提供时才替换为绝对后端域名
BACKEND="${VITE_API_BASE_URL:-}"

if [ -n "$BACKEND" ]; then
  # 先重置为 git 中的干净占位版本（避免上次构建已替换导致占位符丢失）
  git checkout -- public/runtime-config.js 2>/dev/null || true
  # 注入到 runtime-config.js（替换占位符 __BACKEND_API_BASE__）
  sed -i "s#__BACKEND_API_BASE__#${BACKEND}#g" public/runtime-config.js
  echo ">> Injected backend API base: $BACKEND"
else
  echo ">> VITE_API_BASE_URL not set; frontend will use same-origin /api/v1"
fi

echo ">> Building frontend..."
npm ci
vite build
echo ">> Build complete. Output in dist/"
