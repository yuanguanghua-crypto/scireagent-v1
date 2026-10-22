# 全站全局测试方案 V3（以《角色与功能操作说明书》为索引）

**版本** V3.0 · 2026-10-22 · **索引源** `SITE_ROLE_OPERATION_MANUAL.md` V2.0（8 身份 / 52 页面 / 41 流程 / 336 端点）
**配套** `PERSONA_TEST_PLAN.md`（拟人化脚本）、`GLOBAL_TEST_DEFINITION.md`（什么算测过）、`FAILURE_MODES.md`（缺陷台账）

---

## 0. 这份方案是什么、不是什么

| | 内容 |
|---|---|
| **是** | 把说明书里每一条「角色 × 页面 × 流程 × 端点」变成**可执行的测试条目**，并核算**现在到底覆盖到什么深度** |
| **不是** | 不重新定义"什么算测过"——那是 `GLOBAL_TEST_DEFINITION.md` 的事（A/B/C 归属 + 不许有"没人知道没测"的格子） |
| **不是** | 不维护缺陷台账——那是 `FAILURE_MODES.md`（48 行）与说明书第 11 章 |
| **不是** | 不替代既有 spec——它是在 78 个 spec 之上做**覆盖盘点 + 缺口补齐计划** |

> 与旧版的关系：`FULL_SITE_E2E_PLAN.md`（52KB）是按阶段推进的施工计划；`ROLE_TEST_PLAN.md` 是按角色的四层设计；
> 本 V3 的特点是**以说明书为唯一索引**——说明书里有的格子，这里必须有覆盖结论；说明书里没有的，不在这里测。

---

## 1. 覆盖模型：4 个维度 + 2 个横切

| 维度 | 说明书里的索引 | 测试手段 | 当前规模 |
|---|---|---|---|
| **角色** | 第 1–8 章（8 种身份） | persona 脚本（见 `PERSONA_TEST_PLAN.md`）+ 权限矩阵 | 8/8 有章节；**E2E 只覆盖 3 个**（匿名/客户/staff） |
| **页面** | 第 12 章（52 页逐页） | Playwright 加载级 + 交互级 | **52/52 有访问**，深度分级见 §2 |
| **流程** | 各章 `F*-*`（41 条） | 端到端脚本 | **FULL 20 / PART 10 / LOAD 5 / NONE 6** |
| **端点** | 附录 B（336 个 path×method） | 后端单测 + 真实 HTTP 探测 | 单测 1017 文件；HTTP 实测 199 |
| **横切 1：权限边界** | §0.4 + §10.1（8 类判据 × 8 身份） | 权限矩阵快照 + 越权探测 | 求值 336×8，HTTP 校核 1393 格（一致 99.7%） |
| **横切 2：状态机** | 附录 A（Order/CoA/SDS/verified/Quote） | 状态流转用例 + 非法流转拒绝 | Order 15 态全覆盖；CoA/SDS 门控已测 |

**为什么必须四个维度一起看**：只看页面会得出"52/52 全覆盖"的假象——页面能打开但**业务流程可能是断的**（例：`/f3-11` 下载中心页面正常，但从没测过"能不能真下到文件"）。

---

## 2. 现状核算（机械脚本，可复跑）

| 指标 | 值 | 核算脚本 | 说明 |
|---|---|---|---|
| 页面有 E2E 访问 | **52/52** | `scan_e2e_coverage.py` | "访问过" ≠ "断言过"，深度见 §4 |
| 流程 FULL | **20/41** | `flow_coverage_matrix.py` | 主路径走通且断言了业务结果 |
| 流程 PART | 10/41 | 同上 | 部分字段/分支/角色 |
| 流程 LOAD | 5/41 | 同上 | 只有"加载不崩" |
| 流程 NONE | **6/41** | 同上 | **零针对性用例** |
| 后端测试文件 | 1017 | `find backend -name "test_*.py"` | 收集 2630 用例 / 189 文件（含 skip 常量项） |
| E2E spec | 78 | `ls frontend/e2e/*.spec.cjs` | 含本次新增的 4 个事实/页面核验 spec |

**一句话结论**：**广度基本铺满（页面 52/52），深度只到 49%（FULL 20/41）**。
剩下的 21 条里，有 **6 条是零覆盖**——这是本方案要解决的核心。

---

## 3. 五层分工（每层回答不同问题，不能互相替代）

| 层 | 回答什么 | 手段 | 规模 | 典型 |
|---|---|---|---|---|
| **L1 单元/领域** | 这段逻辑在孤立情况下对不对 | pytest | 2630 用例 | 状态机、序列号、金额计算 |
| **L2 API 契约** | 端点对每个身份的准入与响应形状 | 后端 API 测试 + `http_role_probe.py` | 336 端点 × 8 身份 | 403/401 边界、信封结构 |
| **L3 页面功能** | 页面上的动作能不能达到业务结果 | Playwright + 侧证（查 API/DB） | 78 spec | 加购→下单、PO 提交 |
| **L4 拟人化流程** | **一个真人从进入到完成目标的完整路径** | persona 脚本 | 8 persona | 采购一早上审批+发货+开票 |
| **L5 非功能** | 并发/性能/跨浏览器/视觉/可访问性 | PG 用例、perf_gate、3 引擎、a11y | 分散 | 10 并发入库 +10、三浏览器一致 |

**L3 与 L4 的区别**（最容易混）：
- L3 是**单页/单功能**验证（"PO 提交页能提交成功"）
- L4 是**跨页跨角色的一条真人任务链**（"客户提 PO → 采购审批 → 发货 → 开票 → 客户下载发票"），**必须验证交接处的数据一致**

---

## 4. 41 条流程覆盖矩阵

> 图例：🟩 FULL = 主路径走通并断言业务结果｜🟨 PART = 部分｜🟦 LOAD = 只有加载级｜🟥 NONE = 零覆盖
> 本表由 `python scripts/flow_coverage_matrix.py --md` 生成，映射关系写在脚本里，可 diff 复核。

| 流程 | 名称 | 深度 | 现有用例 | 缺口 |
|---|---|---|---|---|
| `F1-1` | 浏览首页 | 🟨 PART | homepage, home-pills-cta, public-smoke | 分类胶囊点击、知识区展开未断言 |
| `F1-2` | 产品列表与筛选 | 🟨 PART | public-smoke | 三级分类/排序/搜索联动、L3 子分类不生效(已知缺陷)未锁 |
| `F1-3` | 查看产品详情 | 🟩 FULL | product-detail-fields, product-detail-structure-image, product-detail-verified-methods | — |
| `F1-4` | 搜索 | 🟨 PART | search-result-docs | `/search/suggest` 建议接口、按类型 Tab 过滤未单独测 |
| `F1-5` | 浏览知识实体 | 🟦 LOAD | public-smoke, responsive | 方法/方案列表的状态 chips **点击不筛数据**(已知缺陷)**无用例锁定** |
| `F1-6` | 加入购物车 | 🟩 FULL | cart-button-regression, cart-page-interactions, basket-local-merge-prune, basket-merge-over-limit | — |
| `F1-7` | 提交询价单（RFQ） | 🟥 NONE | （仅 responsive 的加载级） | **整条链路无功能用例**：匿名提交、必填校验、失败提示缺失 |
| `F1-8` | 注册（三步向导） | 🟩 FULL | register-wizard | — |
| `F1-9` | 邮箱验证 | 🟨 PART | verify-improvements, verify-field-normalize | 链接过期/无 token 分支、失败态无重发入口未测 |
| `F1-10` | 静态页与 404 | 🟦 LOAD | manual-pages-smoke | 只验渲染，无内容断言（三份法务文案） |
| `F2-1` | 未验证登录被拒 + 重发 | 🟥 NONE | （manual-facts F-06 只记录现象，无断言） | **登录 403 分支 + 重发按钮死链无回归用例**（已知缺陷） |
| `F2-2` | 重走验证链接 | 🟨 PART | verify-improvements | 过期 token 路径未覆盖 |
| `F3-1` | 登录 | 🟩 FULL | permission-matrix, 以及全部 spec 的 login helper | — |
| `F3-2` | 管理个人资料（5 Tab） | 🟨 PART | settings-save-banner | Shipping/Contact 两个 Tab 的保存、**改密码假成功**未锁定 |
| `F3-3` | 购物车（登录态） | 🟩 FULL | cart-page-interactions, cart-checkout-regression | — |
| `F3-4` | 结账下单 | 🟩 FULL | checkout-validation, checkout-progressive-sections, cart-checkout-regression | — |
| `F3-5` | 查看订单列表 | 🟩 FULL | orders-pagination, order-status-filters | — |
| `F3-6` | 订单详情 + 报价应答 | 🟨 PART | order-error-paths, state-branches-commerce | `quoted` 状态下 Accept/Reject 报价的**成功路径**未单独测 |
| `F3-7` | 提交 PO | 🟩 FULL | po-lifecycle.api, po-lifecycle.fullflow, po-prod-sweep | — |
| `F3-8` | 查看 PO 单列表 | 🟩 FULL | order-status-filters, po-lifecycle.ui | — |
| `F3-9` | PO 单详情与下载 | 🟨 PART | po-lifecycle.ui, state-branches-po | 发票 PDF / PO 附件下载的**权限与内容**未断言 |
| `F3-10` | 地址簿 CRUD | 🟩 FULL | po-addresses-crud | — |
| `F3-11` | 下载中心 | 🟦 LOAD | manual-pages-smoke | **零功能用例**：只渲染过，没有"能下载到文件"的断言 |
| `F3-12` | 再次订购 | 🟦 LOAD | manual-pages-smoke | **零功能用例**：Re-order 跳转与预填未测 |
| `F3-13` | 收藏夹 | 🟦 LOAD | manual-pages-smoke | **零功能用例**：收藏/取消/清空、未登录提示均未测 |
| `F4-1` | 确认机构管理员徽章 | 🟥 NONE | — | **"is_org_admin 零影响"没有任何用例锁定**；将来有人给它加权限也不会报警 |
| `F5-1` | 审批 PO | 🟩 FULL | po-lifecycle.fullflow, po-lifecycle.ui, ops-po-desk-gaps | — |
| `F5-2` | 发货 | 🟩 FULL | po-lifecycle.fullflow, ops-po-desk-gaps | — |
| `F5-3` | 开票与收款 | 🟩 FULL | po-invoicing-queue, po-lifecycle.fullflow, ops-po-desk-gaps | — |
| `F5-4` | 看应收账龄 | 🟨 PART | ops-po-desk-gaps | 分桶金额计算未断言（只验了页面出现） |
| `F5-5` | 机构管理 | 🟨 PART | ops-po-desk-gaps | 按机构查单的**过滤正确性**未断言 |
| `F5-6` | 库存管理 | 🟩 FULL | ops-inventory | 并发正确性另由 PG 用例覆盖（run_pg_tests.py） |
| `F6-1` | 指派销售 | 🟥 NONE | （manual-facts 只测了 403 与 500 现象） | **成功路径无用例**；且"填用户名 → 500"这个缺陷无回归 |
| `7.3` | 产品新建（含导入/AI/SKU/合规/SEO） | 🟩 FULL | product-new-*, product-edit-*, product-compliance-lifecycle, product-seo-publish | — |
| `7.4` | 产品管理（上下架/回收站/批量） | 🟩 FULL | product-list-*, product-batch-ai, product-save-keeps-links | — |
| `7.5` | 知识实体 CRUD | 🟩 FULL | workspace-entity-crud, cascader-workflow | — |
| `7.6` | Verified 审核 | 🟩 FULL | workspace-verified-review, verify-dialog-a11y, verify-dialog-style | — |
| `7.7` | 知识录入 | 🟩 FULL | knowledge-intake, workspace-entry-intake | — |
| `7.8` | 订单与 PO 八个台 | 🟩 FULL | po-lifecycle.*, ops-*, order-* | — |
| `F8-1` | 物理删除产品（无 UI） | 🟥 NONE | — | **无端点级用例**；超管专属能力，误删不可逆 |
| `F8-3` | Django admin 角色分配 | 🟥 NONE | — | 无自动化（此前判定为 C 类）；但"改完要重登"这条**完全没有验证过** |

**合计 41 条流程：FULL 20、PART 10、LOAD 5、NONE 6**

---

## 5. 缺口与优先级

> ⚠️ **唯一清单在 [`GAP_REGISTER.md`](./GAP_REGISTER.md)（23 条，去重，机读版 `GAP_REGISTER.json`）。**
> 本节只是**摘要**，不要在两处各维护一份——第一版就出现过重复登记（F8-1 / F8-3 各被列两次）。
> 缺口来源：`flow_coverage_matrix.py` 的 `FLOWS` 表里深度 ≠ FULL 的 21 条 + 2 条非流程项（金额快照、邮件）。

### 5.1 P0：六条零覆盖（🟥 NONE）——按"出事概率 × 不可逆性"排

| 序 | 流程 | 为什么是 P0 | 要补什么 |
|---|---|---|---|
| **P0-1** | `F1-7` 提交询价单（RFQ） | **匿名即可提交**（唯一未声明权限的端点），是获客入口；整条链路**零用例** | 匿名提交成功 + 必填校验 + 邮箱格式 + 失败无提示（已知缺陷） |
| **P0-2** | `F2-1` 未验证登录被拒 + 重发 | 已知**重发按钮是死链**，却没有任何回归用例；客服会反复踩 | 断言 403 分支、断言点击后无网络请求（锁定缺陷） |
| **P0-3** | `F6-1` 指派销售 | 是 `admin(role)` **唯一独有能力**；且"填用户名 → 500"无回归 | 数字 id 成功路径 + 非数字返回 400（当前 500） |
| **P0-4** | `F3-11` 下载中心 | 客户**拿发票/PO 附件**的唯一集散页，零功能用例 | 有发票的订单能下到 PDF、无权限时被挡 |
| **P0-5** | `F3-12` 再次订购 | 复购入口，零用例；`Re-order` 跳转与预填未测 | 从已完成订单 → 预填的 PO 提交页 |
| **P0-6** | `F3-13` 收藏夹 | 零用例；未登录提示已知 | 收藏/取消/清空 + 未登录引导 |

### 5.2 P1：五条只有加载级（🟦 LOAD）

| 流程 | 现状 | 补什么 |
|---|---|---|
| `F1-5` 浏览知识实体 | 只验加载 | **锁定"状态 chips 点击不筛数据"这个已知缺陷**（Method/Protocol 两页） |
| `F1-10` 静态页与 404 | 只验渲染 | 三份法务文案的存在性（改文案时能报警） |
| `F3-11/12/13` | 同上（已在 P0 提） | — |

### 5.3 P2：十条 PART 需要补深

| 流程 | 缺的那一半 |
|---|---|
| `F1-1` 首页 | 分类胶囊点击、知识区展开 |
| `F1-2` 产品列表 | 三级分类/排序/搜索联动；**锁定 L3 子分类不生效** |
| `F1-4` 搜索 | `/search/suggest`、按类型 Tab |
| `F1-9` 邮箱验证 | 链接过期、无 token、失败态无重发入口 |
| `F2-2` 重走验证链接 | 过期 token 路径 |
| `F3-2` 个人资料 | Shipping/Contact 保存；**锁定改密码假成功** |
| `F3-6` 报价应答 | `quoted` 状态下 Accept/Reject 成功路径 |
| `F3-9` PO 单下载 | 发票 PDF / 附件下载的**权限与内容** |
| `F5-4` AR 账龄 | 分桶金额计算 |
| `F5-5` 机构管理 | 按机构查单的过滤正确性 |

### 5.4 明确不自动化的（C 类，不装样子）

| 项 | 理由 | 替代承担 |
|---|---|---|
| `F8-3` Django admin 角色分配 | 无产品面 UI/API；自动化成本 >> 收益 | 运营手册 + 季度人工冒烟 |
| `F8-1` 物理删除（无 UI） | 只能 curl；不可逆 | 上线前人工演练一次 + 端点级单测 |
| 像素级视觉回归 | 仓库无基线截图 | 设计令牌校验（已有 `visual-tokens`） |

---

## 6. 闸门与归属（沿用 A/B/C，ratchet 口径）

| 层 | 归属 | 跑在哪 | 变了怎么办 |
|---|---|---|---|
| L1 单测 | **A** | CI | 红即阻 |
| L2 权限矩阵快照 | **A** | CI（0 次 HTTP，秒级） | 改 golden 必须写明"为什么改权限" |
| L3 页面功能 | **A** | CI（`@local-only` 子集） | 红即阻 |
| L4 拟人化 | **A**（关键 3 条 persona）/ **B**（其余） | 本地 + 发版前 | B 类必须有可执行兜底动作 |
| L5 非功能 | **A**（PG 并发、三浏览器）/ **B**（生产只读） | 手动/定时 | — |

**ratchet 规则（只拦新增）**：CI 只对**新增的**红灯与**新增的** golden 差异失败；
不要求一次性把 21 条 PART/LOAD/NONE 清零——否则会催生"假签名"（`GLOBAL_TEST_DEFINITION.md §4.1` 明令禁止）。

---

## 7. 执行批次

| 批次 | 范围 | 产出 | 验收线 |
|---|---|---|---|
| **Batch 1** | P0 六条零覆盖 | 3 个新 spec（`rfq-flow`、`customer-download-reorder-wishlist`、`assign-rep`）+ 1 个缺陷锁定 spec（`unverified-login`） | 六条从 🟥 变 🟩/🟨；且**每条都有侧证**（查 API 或 DB），不是只看 UI |
| **Batch 2** | P1 五条 + P2 十条 | 在既有 spec 上补断言，不新开文件 | FULL 从 20 → ≥35 |
| **Batch 3** | L4 拟人化 8 persona | 按 `PERSONA_TEST_PLAN.md` 落地 | 8 个 persona 各有 1 条可跑通的脚本 |
| **持续** | L5 非功能 | PG 并发（已有）、跨浏览器（已有）、生产只读（已有） | 不退化 |

> Batch 1 的六条**必须优先**：它们都是"客户或运营每天会碰、但一次都没被自动验证过"的路径。

---

## 8. 这套方案不覆盖什么（边界）

1. **生产环境的写操作**——会污染真实数据，主动不做（只读已覆盖）
2. **像素级视觉**——无基线截图机制
3. **性能承诺**——`perf_gate` 只测进程内 p95，不替代真实压测
4. **Django admin**——见 §5.4
5. **邮件真实投递**——当前 `EmailTemplate` 表 0 条、outbox 全 pending，**没有可投递的内容可测**；
   已作为缺陷记录，等补齐模板后再加用例

---

## 9. 复跑与维护

```bash
cd src_claude
python scripts/scan_e2e_coverage.py        # 页面级 E2E 覆盖（52/52？）
python scripts/flow_coverage_matrix.py     # 流程级覆盖（FULL/PART/LOAD/NONE）
python scripts/flow_coverage_matrix.py --md > 表格.md   # 生成 §4 的矩阵
python scripts/gap_register.py             # 重新生成唯一 backlog（GAP_REGISTER.md/.json）
python scripts/audit_manual_delivery.py    # 说明书自身是否与代码一致
```

**维护约定**：新增/改流程时，先改 `flow_coverage_matrix.py` 里的 `FLOWS` 表，再跑一遍看缺口变化；
**不要手改 §4 的表格**——它是脚本产物。

---

## 10. 统一执行入口（答"能否统一到一个测试任务"）

**已落地** `scripts/run_all_tests.py`，一条命令串起 L1–L5：

```bash
python scripts/run_all_tests.py --profile fast      # 无需起服务（config + 权限矩阵 + 单测）
python scripts/run_all_tests.py --profile full      # + HTTP 权限 / 对象级 / 三类 E2E / PG 并发
python scripts/run_all_tests.py --profile nightly   # + 跨浏览器 / 生产只读
```

实测（2026-10-22 本机）：`config` 0.6s / `perm-matrix` 2.0s / `perm-http` 15.5s /
`e2e-smoke` 79.9s（129 用例）全部 PASS；前端停掉时该 suite 报 **SKIP 且退出码 2**（不假装通过）。

> **统一的是入口与报告，不是框架**：pytest（Django 测试库）、python 探测（直连 DB 侧证）、
> playwright（浏览器）、外部只读（线上域名）四类载体无法塞进同一个 Playwright 任务。
> 设计细节与"为什么不做成一个大 spec"见 [`UNIFIED_TEST_ENTRY.md`](./UNIFIED_TEST_ENTRY.md)。

**当前未接 CI**：CI 仍是 12 个独立 job；把 `--profile full` 接进去是待办。
