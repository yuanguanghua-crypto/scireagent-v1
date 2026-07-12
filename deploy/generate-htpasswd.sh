#!/usr/bin/env bash
# 生成 / 追加 Nginx HTTP Basic Auth 账号到 deploy/.htpasswd
# 用途：内部测试人员访问限制（详见 docs/DEPLOY_ALIBABA.md §11）
# 运行环境：Ubuntu 服务器（需 openssl，已默认安装）。在本仓库根目录执行。
#
# 用法：
#   bash deploy/generate-htpasswd.sh init <用户名>     # 新建 .htpasswd 并加第一个账号（文件已存在则报错）
#   bash deploy/generate-htpasswd.sh add  <用户名>     # 向已有 .htpasswd 追加一个账号
#   （省略用户名则交互式输入；密码一律交互式输入，不回显）
#
# 示例（6 人团队）：
#   bash deploy/generate-htpasswd.sh init alice
#   bash deploy/generate-htpasswd.sh add  bob
#   bash deploy/generate-htpasswd.sh add  carol
#   bash deploy/generate-htpasswd.sh add  dave
#   bash deploy/generate-htpasswd.sh add  erin
#   bash deploy/generate-htpasswd.sh add  frank
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HTPASSWD="$SCRIPT_DIR/.htpasswd"

cmd="${1:-}"
user="${2:-}"

if [[ "$cmd" != "init" && "$cmd" != "add" ]]; then
  echo "用法:"
  echo "  $0 init <用户名>    # 创建 .htpasswd 并添加第一个账号（若文件已存在则报错）"
  echo "  $0 add  <用户名>    # 向已有 .htpasswd 追加账号"
  exit 1
fi

if [[ -z "$user" ]]; then
  read -rp "请输入用户名: " user
fi

if [[ "$cmd" == "init" && -f "$HTPASSWD" ]]; then
  echo "错误: $HTPASSWD 已存在，请用 'add' 追加账号，或先删除该文件再 init。"
  exit 1
fi

read -rsp "请输入密码（不回显）: " pass
echo
read -rsp "请再次输入密码: " pass2
echo
if [[ "$pass" != "$pass2" ]]; then
  echo "错误: 两次密码不一致"
  exit 1
fi

# 用 openssl 生成 apr1 哈希（nginx basic auth 标准格式 user:hash）
hash="$(openssl passwd -apr1 "$pass")"
if [[ "$cmd" == "init" ]]; then
  printf '%s:%s\n' "$user" "$hash" > "$HTPASSWD"
else
  printf '%s:%s\n' "$user" "$hash" >> "$HTPASSWD"
fi
chmod 600 "$HTPASSWD"
echo "OK: 账号 '$user' 已写入 $HTPASSWD"
echo "当前账号数: $(wc -l < "$HTPASSWD")"
