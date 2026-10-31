# nginx `/assets/` 404 修复（2026-10-31）

## 症状

页面白屏，浏览器 Console 报：

```
SyntaxError: Unexpected token '<'
```

受影响：所有**懒加载路由**（`/workspace/users`、`/workspace/email-templates`、
`/workspace/email-outbox`、`/workspace/audit-log`、`/ops/inventory`、`/ops/rfq`、
`/ops/orders` 等）。首页正常，因为它被打进主 bundle。

## 根因（实测）

`deploy/nginx.conf` 只有一条 SPA fallback：

```nginx
location / {
    try_files $uri $uri/ /index.html;
}
```

`/assets/` 没有独立 location，于是**请求不存在的 chunk 时也会回退到 index.html**，
返回 **HTTP 200 + text/html**（实测 2,166 字节）。

浏览器请求的是 `.js`，拿到的是 HTML ⇒ 解析 HTML 的第一个字符 `<` 就抛
`Unexpected token '<'` ⇒ 组件永远挂不上 ⇒ 白屏。

危害不止"报错难懂"：
- HTTP 层是 **200**，监控/CDN/浏览器都认为成功
- 中间缓存可能把这个错误的 HTML 响应缓存住 ⇒ **清缓存前一直坏**

## 修复

```nginx
location /assets/ {
    try_files $uri =404;
}
```

缺失的 chunk 现在返回 404，语义正确、不可缓存。

## 已验证（生产）

| 检查 | 修复前 | 修复后 |
|---|---|---|
| 请求不存在的 chunk | 200 + text/html | **404** + text/html |
| 请求存在的 chunk | 200 + application/javascript | 200 + application/javascript |
| 站根 | 200 | 200 |
| SPA 深链 `/workspace/users` | 200 | 200 |
| `listen 443` | 2 处 | 2 处（未受影响） |

## ✅ 已解耦（2026-10-31 改造）

原先 `deploy/nginx.conf` 是 tracked 文件，但服务器版被 certbot 就地改写（443 启用 +
证书路径 + Basic Auth + CSP），与仓库占位版内容不同。每次同步都要手工走
「备份 → checkout 丢弃本地改 → merge → 恢复」，极易漏步骤，一旦把占位版落到生产
就 443 消失、HTTPS 全站 down。

**现在已彻底解耦：**

| 文件 | 状态 |
|---|---|
| `deploy/nginx.conf` | **不入库**（.gitignore），生产配置只存服务器 |
| `deploy/nginx.conf.example` | 模板（含 443 注释版 + `location /assets/` 404 块 + 使用说明） |

### 以后怎么改 nginx 配置

**直接在服务器上编辑** `/home/admin/scireagent/deploy/nginx.conf`，不要从本地覆盖。

```bash
# 服务器上
vim /home/admin/scireagent/deploy/nginx.conf
docker compose restart nginx        # 必须 restart：bind mount 按 inode 挂载，reload 不够

# 三条验证（缺一不可）
docker exec scireagent-nginx-1 grep -c 'listen 443' /etc/nginx/conf.d/default.conf   # 2
curl -sk -o /dev/null -w '%{http_code}\n' https://scireagent.com/                  # 401 或 200
curl -sk -o /dev/null -w '%{http_code}\n' https://scireagent.com/assets/notexist.js  # 404
```

`git merge` 从此不再触碰这个文件，也不会删除它。

### 新环境初始化

```bash
cp deploy/nginx.conf.example deploy/nginx.conf
bash deploy/generate-htpasswd.sh
certbot --nginx -d <域名>            # 自动追加 443 块并申请证书
docker compose up -d nginx
```
