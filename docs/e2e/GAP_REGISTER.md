# 缺口总账（唯一 backlog）

**生成** 2026-10-22 · **事实源** `scripts/flow_coverage_matrix.py` 的 FLOWS 表
**用途** 两份测试方案（V3 / PERSONA）的缺口**只有这一份清单**，不要在别处再列一遍。

> 合计 **23** 条：P0 5 / P1 7 / P2 11

| 序 | ID | 缺口 | 现深度 | 优先级 | 归属 | 现状 | 缺什么 |
|---|---|---|---|---|---|---|---|
| 1 | `F1-7` | 提交询价单（RFQ） | 🟥 NONE | **P0** | A | （仅 responsive 的加载级） | **整条链路无功能用例**：匿名提交、必填校验、失败提示缺失 |
| 2 | `F2-1` | 未验证登录被拒 + 重发 | 🟥 NONE | **P0** | A | （manual-facts F-06 只记录现象，无断言） | **登录 403 分支 + 重发按钮死链无回归用例**（已知缺陷） |
| 3 | `F4-1` | 确认机构管理员徽章 | 🟥 NONE | **P0** | A | — | **"is_org_admin 零影响"没有任何用例锁定**；将来有人给它加权限也不会报警 |
| 4 | `F6-1` | 指派销售 | 🟥 NONE | **P0** | A | （manual-facts 只测了 403 与 500 现象） | **成功路径无用例**；且"填用户名 → 500"这个缺陷无回归 |
| 5 | `X-3` | 金额快照不被改价影响 | 🟥 NONE | **P0** | A | 跨角色接力 | P3 下单后内部改 SKU 价，历史订单金额必须不变（当前无用例） |
| 6 | `F1-10` | 静态页与 404 | 🟦 LOAD | **P1** | A | manual-pages-smoke | 只验渲染，无内容断言（三份法务文案） |
| 7 | `F1-5` | 浏览知识实体 | 🟦 LOAD | **P1** | A | public-smoke, responsive | 方法/方案列表的状态 chips **点击不筛数据**(已知缺陷)**无用例锁定** |
| 8 | `F3-11` | 下载中心 | 🟦 LOAD | **P1** | A | manual-pages-smoke | **零功能用例**：只渲染过，没有"能下载到文件"的断言 |
| 9 | `F3-12` | 再次订购 | 🟦 LOAD | **P1** | A | manual-pages-smoke | **零功能用例**：Re-order 跳转与预填未测 |
| 10 | `F3-13` | 收藏夹 | 🟦 LOAD | **P1** | A | manual-pages-smoke | **零功能用例**：收藏/取消/清空、未登录提示均未测 |
| 11 | `F8-1` | 物理删除产品（无 UI） | 🟥 NONE | **P1** | A | — | **无端点级用例**；超管专属能力，误删不可逆 |
| 12 | `X-4` | 邮件可投递性 | 🟥 NONE | **P1** | B | §11.3 | 模板表 0 条、outbox 全 pending ⇒ 没有可投递内容，暂无法测；补齐模板后再加 |
| 13 | `F1-1` | 浏览首页 | 🟨 PART | **P2** | A | homepage, home-pills-cta, public-smoke | 分类胶囊点击、知识区展开未断言 |
| 14 | `F1-2` | 产品列表与筛选 | 🟨 PART | **P2** | A | public-smoke | 三级分类/排序/搜索联动、L3 子分类不生效(已知缺陷)未锁 |
| 15 | `F1-4` | 搜索 | 🟨 PART | **P2** | A | search-result-docs | `/search/suggest` 建议接口、按类型 Tab 过滤未单独测 |
| 16 | `F1-9` | 邮箱验证 | 🟨 PART | **P2** | A | verify-improvements, verify-field-normal | 链接过期/无 token 分支、失败态无重发入口未测 |
| 17 | `F2-2` | 重走验证链接 | 🟨 PART | **P2** | A | verify-improvements | 过期 token 路径未覆盖 |
| 18 | `F3-2` | 管理个人资料（5 Tab） | 🟨 PART | **P2** | A | settings-save-banner | Shipping/Contact 两个 Tab 的保存、**改密码假成功**未锁定 |
| 19 | `F3-6` | 订单详情 + 报价应答 | 🟨 PART | **P2** | A | order-error-paths, state-branches-commer | `quoted` 状态下 Accept/Reject 报价的**成功路径**未单独测 |
| 20 | `F3-9` | PO 单详情与下载 | 🟨 PART | **P2** | A | po-lifecycle.ui, state-branches-po | 发票 PDF / PO 附件下载的**权限与内容**未断言 |
| 21 | `F5-4` | 看应收账龄 | 🟨 PART | **P2** | A | ops-po-desk-gaps | 分桶金额计算未断言（只验了页面出现） |
| 22 | `F5-5` | 机构管理 | 🟨 PART | **P2** | A | ops-po-desk-gaps | 按机构查单的**过滤正确性**未断言 |
| 23 | `F8-3` | Django admin 角色分配 | 🟥 NONE | **P2** | C | — | 无自动化（C 类）；另外"改完权限必须重登才看到菜单"这条**从未验证** |

## 归属口径（沿用 GLOBAL_TEST_DEFINITION）

- **A**：该由自动化承担，且已经能跑（或本轮就该补上）
- **B**：已知未测，但有**可执行的兜底动作**（如"改这些路径时必须手跑某个脚本"）
- **C**：产品面不适用（如 Django admin），用运营手册 + 周期人工冒烟承担

> ⚠️ 这份清单**不包含"没人知道没测"的格子**——那是定义里的红线。
