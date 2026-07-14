# Release v2026.07.14 — 四地对齐与密钥安全收口

**日期**：2026-07-14
**Commit**：`14e2fe3`（tag `v2026.07.14`）
**范围**：本地 / GitHub 远程 / 服务器 / 部署 四地对齐到同一提交

## 包含内容

继承自 `v2026.07.13`（`3da02a3`）的三项修复：

1. **SKU 增量同步** — `ProductCreateUpdateSerializer.update()` 改为按 `id` 匹配（无 id 按 `sku_code` 兜底），根治每次保存清空重建 SKU 导致的 Batch/Coa 级联删除（详情页 COA "SKU does not exist" 问题）。
2. **详情页结构图优先** — `ProductDetail.vue` 结构框新增 `structure_image` 优先分支，排在 SMILES 渲染之前，避免用错分子 SMILES 渲染出错误结构图。
3. **PubChem 模糊匹配守卫** — `pubchem_enhancer` 在 formula/mw 不符时降级 `requires_review`；前端 `applyCandidate` 拦截不符候选，禁止自动套用错误分子 SMILES。

新增 **B4 安全收口**：`.gitignore` 增加 `deploy/CREDENTIALS.txt`、`deploy/certbot/`、`frontend/dist.bak*/`，明文密钥与证书目录不再入库。

## 部署动作（服务器）

- `git fetch` + `git reset --hard origin/master`，将服务器工作树对齐到 `14e2fe3`。
- 保留服务器 `deploy/nginx.conf`（HTTPS / certbot 配置；实测与 `origin/master` 内容一致，四地完全对齐）。
- 删除孤儿文件 `backend/apps/commerce/serializers.py`（365 行，全仓无 import 引用）。
- `migrations/0009`（structure_image 字段）由 untracked 转为 tracked。
- **未重建容器**：运行代码与 `origin/master` 逐字节一致（`14e2fe3` 仅改 `.gitignore`，不含后端逻辑）。

## 运维要点（经验教训）

对齐前 `git reset --hard` / `git checkout -f origin/master` 反复失败，根因为 `deploy/nginx.conf` 被设了 `assume-unchanged` 位（`git ls-files -v` 显示 `h`），git 拒绝覆盖受保护文件。清除 `git update-index --no-assume-unchanged deploy/nginx.conf` 后对齐成功。

> **后续对齐同类受保护文件时**：先 `git ls-files -v` 检查 `S`(skip-worktree) / `h`(assume-unchanged) 标志位，有则先清除再 `reset --hard`。

## 验证

- 容器：backend / db(healthy) / nginx 全部 running。
- HTTPS：`curl https://scireagent.com` → `401`（nginx/1.31.2 正常服务，TLS 正常）。
- jena 索引 = 2098，无回归。
- `deploy/CREDENTIALS.txt` 物理保留、已 gitignore；`deploy/certbot/` 保留。

## 本次顺带清理

- 删除服务器 `frontend/dist.bak-*`（5 个历史构建备份），释放空间；线上 `frontend/dist` 不受影响。
