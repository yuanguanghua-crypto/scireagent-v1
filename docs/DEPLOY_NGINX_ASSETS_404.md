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

## ⚠️ 部署注意：这个文件不能直接 merge

`deploy/nginx.conf` 是 **tracked 文件**，但服务器上的版本被 certbot 就地改写过
（443 启用 + 证书路径 + Basic Auth 等），与仓库里的**占位版（443 注释）**内容不同。

仓库版的这次修改已在本地提交，但**服务器不能直接 `git merge --ff-only`**，
否则会用占位版覆盖生产 443 配置 → HTTPS 全站 down。

### 正确的部署流程（每次需要同步 nginx.conf 时）

```bash
cd /home/admin/scireagent
cp deploy/nginx.conf /tmp/prod-nginx.conf      # ① 保存生产版
git checkout -- deploy/nginx.conf              # ② 丢弃本地修改，让 merge 能过
git merge --ff-only origin/master              # ③ 仓库版落地（占位 + assets 404 块）
cp /tmp/prod-nginx.conf deploy/nginx.conf      # ④ 恢复生产版（含 443）
docker compose restart nginx                   # ⑤ bind mount 需 restart，reload 不够
curl -sk -o /dev/null -w "%{http_code}\n" https://scireagent.com/   # ⑥ 必须 401/200
```

**若不涉及 nginx.conf 的常规部署，跳过上述流程，直接 merge 即可**——
只要待合并的提交没碰这个文件，git 不会报冲突。

### 长期建议

把 `deploy/nginx.conf` 改为 `.gitignore` + 提供 `deploy/nginx.conf.example` 占位模板，
生产配置只存服务器。这样彻底消除"本地版与生产版打架"的问题。
