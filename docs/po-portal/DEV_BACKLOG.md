# DEV_BACKLOG —— 开发缺失工作清单（源自 LAUNCH_READINESS v4.1）

> 版本：v1（2026-10-15）｜ 基线：v4.1 框架审计（`23518af`）｜ **只含开发范围**
> 🟠G 决策项、外部法律/税务依赖、运营流程**不在本表**（见 v4.1 §0.1/§12）。
> 状态：`open` / `in-progress` / `done`；完成须附验证证据（测试/E2E/生产实测）。

---

## P0 · 种子客户集（GO-1，~2-3 周）

| ID | 工作项 | 层 | 范围 | 量级 | 依赖 | 验收标准 | 状态 |
|---|---|---|---|---|---|---|---|
| DEV-1 | **库存管理工具**（F3） | L1 | Inventory API（receipt/adjust/list/movements）+ `/ops/inventory` UI + 变动流水台账 | 1-2 周 | 无（模型/服务已就绪） | 设计稿 `INVENTORY_TOOL_DESIGN.md` 全部测试绿 + E2E | **done**（2026-10-15，`a2d7fb5`+`d943da8` 已部署生产；pytest 17+回归全绿；E2E `ops-inventory` **4 passed**；生产 401/403/200 实测） |
| DEV-2 | **GDPR 最小包** | L0 | 隐私政策页 + Cookie 同意横幅 + 条款页 + 页脚链接（文本模板先行，律师后审） | 3-5 天 | 律师后审 | 三页可访问 + 横幅可关（localStorage）+ 真浏览器无 console error | open |
| DEV-3 | **DB 自动备份** | 运维 | pg_dump 脚本 + cron + 保留 30 天 + 异地拷贝 | 2-3 天 | RPO 决策（建议日备/30 天） | 备份文件存在且 `pg_restore --list` 可读 + cron 在 crontab | open |
| DEV-4 | **RUO 标注体系** | L1/L2 | SKU/商品字段 + 商品页 + 发票 PDF + 订单页展示 "For Research Use Only" | 1-2 天 | 无 | 商品页与 PDF 均含标注（E2E 断言） | open |
| DEV-5 | **监控告警** | 运维 | uptime 探针（products/orders/证书到期）+ 失败邮件告警 + 证书 30 天预警 | 2-3 天 | 无 | 停后端 5 分钟能收到告警（演练一次） | open |
| DEV-6 | **生产验证补课** | 全 | 实测转 P-verified：`/basket` 全流程 · confirm-quote · COA/SDS 下载 · 续期 cron 模拟触发 | 1 天 | DEV-3 | 各项在验收报告追加记录 | open |

## P1 · 公网推广前（GO-2 增量，~2 周）

| ID | 工作项 | 层 | 范围 | 量级 | 依赖 | 验收标准 | 状态 |
|---|---|---|---|---|---|---|---|
| DEV-7 | **SEO 套餐** | L3 | 每页 meta description/OG/canonical + 动态 `sitemap.xml`（商品/知识页）+ `robots.txt` + schema.org | 3-5 天 | 无 | sitemap 可访问且含商品/知识 URL；首页含 description/OG（curl 断言） | open |
| DEV-8 | **主包拆分** | L3 | vite `manualChunks`（element-plus/图表库独立） | 1-2 天 | 无 | 主包 <500KB 且全量 E2E 绿 | open |
| DEV-9 | **CSP 安全头** | 运维 | nginx CSP + SPA 兼容（nonce 评估）+ X-Frame-Options | 1-2 天 | 无 | 响应头含 CSP 且真浏览器巡检 4 passed | open |
| DEV-10 | **出口筛查数据支持** | L1 | SKU `hs_code`/两用物项标志字段 + 待审订单导出筛查表 | 2-3 天 | E1 比对规则（可后补字段先行） | 字段可编辑 + 导出 CSV 含必填列 | open |
| DEV-11 | **分析接入** | L3 | GA4 或自托管 Plausible | 1 天 | 账号（外部小依赖） | 生产页面可见分析脚本 + 后台收到 PV | open |
| DEV-12 | **大陆 CDN 接入** | L4 | 决策（P6）后：CDN 配置/备案/多地域 | 决策后 2-5 天 | 🟠G P6 | 大陆方向速度复测显著改善 | open（决策门控） |

## P2 · 上线后迭代（不影响 GO-1/GO-2）

| ID | 工作项 | 层 | 范围 | 量级 | 依赖 | 状态 |
|---|---|---|---|---|---|---|
| DEV-13 | 自助取消（客户订单详情 + po_received/confirmed 可取消） | L1 | 端点权限放开 + UI 按钮 + 流水 | 2-3 天 | 无 | open |
| DEV-14 | 退款 + 发票红冲（credit note） | L1 | 退款模型/流程 + 红冲发票生成 | 1-2 周 | 财务规则确认 | open |
| DEV-15 | 信用额度管理 | L1 | 机构 credit_limit + 超额拦截 | 3-5 天 | 商业规则确认 | open |
| DEV-16 | RMA 退换货 | L1 | 独立子系统（申请/审核/回库） | 1-2 周 | 售后 SOP | open |
| DEV-17 | 机构内审批流 | L1 | 机构管理员审批组员订单 | 1-2 周 | 商业确认 | open |
| DEV-18 | EDM cron 落地 | L3 | Mailgun key + cron 配置 | 1 天 | 🟠G 决策 | open（门控） |
| DEV-19 | a11y/响应式/跨浏览器**跑测并修** | L4 | 执行既有 spec，修发现项 | 修多少算多少 | 无 | open |

## 验证类（code-only → P-verified，并入 DEV-6 执行）

`/basket` 全流程 · confirm-quote 端到端 · COA/SDS 生产下载 · 续期 cron 真实周期 · a11y/响应式 spec 实跑

---

## 明确排除（非开发范围 —— 见 v4.1 §0.1/§12）

🟠G 决策：商品数据上线方式 · 大陆访问方案 · EDM 决策 · 知识质量目标 · 备份 RPO
外部依赖：两用物项比对 · ICP 认定 · GDPR 代表权 · nexus 逐州 · 爬虫授权 · IP 归属 · CFC/GILTI 存量申报
运营流程：履约 SOP · 上架审核流程 · 售后通道 · 数据授权

## 变更记录

| 日期 | 变更 |
|---|---|
| 2026-10-15 | v1 创建（19 项；源自 v4.1 框架审计） |
