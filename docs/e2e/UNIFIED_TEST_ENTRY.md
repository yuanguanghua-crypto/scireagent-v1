# 两份测试方案：覆盖现状与统一入口

**日期** 2026-10-22 · **被问** ① 是否已全部覆盖 ② 能否统一到同一个测试任务
**结论**（2026-10-22 Batch 1~3 执行后更新）
① 覆盖：**42 条流程里 40 条 FULL**，缺口从 23 降到 **2 条**（1 条 C 类人工 + 1 条 PART）
② 统一：`run_all_tests.py` 已落地，`fixtures + e2e-probe` **两次连跑各 47/47 通过**（幂等自证）

---

## 0. 先给两个字的答案

| 问题 | 答案 | 一句话理由 |
|---|---|---|
| 全部覆盖了吗？ | **没有** | 页面维度 **53/53** 均有浏览器访问；流程维度 **40/42 FULL**；仍有 **2 条缺口**（见 `GAP_REGISTER.md`） |
| 能统一到一个测试任务吗？ | **能，已实现** | `python scripts/run_all_tests.py --profile full` 一条命令串起 L1–L5；已实测 4 类 suite 跑通 |

---

## 1. 覆盖现状：为什么不能说"全覆盖"

### 1.1 三个维度、三个数（都来自脚本，不是估的）

| 维度 | 覆盖 | 脚本 |
|---|---|---|
| **页面**（53） | **53/53 有 E2E 访问** | `scan_e2e_coverage.py` |
| **流程**（42） | **FULL 40 / PART 1 / LOAD 0 / NONE 1** | `flow_coverage_matrix.py` |
| **缺口**（去重后） | **2 条**：P0 **0** / P1 **0** / P2 2 | `gap_register.py` |

> ⚠️ **只看页面会得出假结论**。53/53 只说明"每个页面至少被打开过一次"，
> 而 `F3-11 下载中心` 就是典型：页面能开（LOAD），但**从来没验证过"能不能真下到发票 PDF"**。

### 1.2 剩余 2 条缺口（唯一清单，不要在别处再列）

见 **[`GAP_REGISTER.md`](./GAP_REGISTER.md)**。全部为 P2（P0/P1 已清零）：

| ID | 缺口 | 现状 |
|---|---|---|
| `F1-5` | 浏览知识实体（PART） | chips 不筛数据已锁死；**实体详情的 Tab/展开仍只有加载级** |
| `F8-3` | Django admin 角色分配（C 类） | 不自动化；改为 `PERSONA_TEST_PLAN.md` 的 **P8 人工冒烟清单（6 步）** |

> `F3-11` 下载中心**已修复**（2026-10-22）：列表序列化器补 `invoice`/`attachments` + 预取防 N+1，
> 用例从"锁缺陷"改为"验功能"，覆盖契约字段 / 发票号渲染 / 下载请求 / PO 附件 / 无数据空态。

### 1.3 现在的准确表述

> **广度铺满、深度基本补齐**：53/53 页有浏览器访问；42 条流程 40 条 FULL。
> 剩下 2 条不是"忘了测"，而是**有明确原因**：1 条 C 类（Django admin，人工冒烟承担）、
> 1 条 PART（知识实体只剩详情页交互未覆盖）。

### 1.4 Batch 1~3 执行结果（2026-10-22）

| 批次 | 内容 | 产出 | 结果 |
|---|---|---|---|
| **Batch 1** | P0 五条 | `p0-rfq` / `p0-auth-orgadmin` / `p0-assign-rep` / `test_price_snapshot.py` | **10 passed**（浏览器）+ **3 passed**（后端） |
| **Batch 2** | P1 七条 | `p1-public-pages` / `p1-customer-pages` / `test_hard_delete.py` / `test_email_outbox_contract.py` | **11 passed** + **9 passed** |
| **Batch 3** | P2 十二条 | `p2-public-interactions` / `p2-auth-verify` / `p2-customer-flows` / `p2-ops-desk` + P8 人工清单 | **21 passed** |
| 合计 | 23 条缺口 | 9 个新 spec / 3 个后端测试 / 1 个人工清单 | `fixtures + e2e-probe` **42/42 × 连跑两次** |

**过程中新发现 3 个真缺陷（现已全部修复）**：
1. ✅ **已修**：`/po/downloads` 永远空态（列表序列化器缺 `invoice`/`attachments`）
   —— 修法与回归见说明书 附录 D.5.1
2. ✅ **已修**：`/verify-email?token=<非UUID>` → 原 500 + HTML；现 **400 + `Invalid or expired verification token.`**
   根因是 `UUIDField` 抛 `django.core.exceptions.ValidationError` 而代码只捕 `ValueError`。
   回归：`apps/accounts/tests/test_verify_email_token_tolerance.py`（5 条）+ `p2-auth-verify`
3. ✅ **已修**：RFQ 原只有创建入口、无查询入口（详情按邮箱过滤，连 staff 也 404）。
   现补 `GET /quote-requests/manage/`（`IsProcurementOrAdmin`）+ 新运营台页面 `/ops/rfq`。
   回归：`apps/quotes/tests/test_rfq_inbox.py`（10 条）+ `p3-rfq-inbox.spec.cjs`（3 条）

---

## 2. 统一入口：已落地，不是设想

### 2.1 一条命令

```bash
python scripts/run_all_tests.py --profile fast      # 无需起服务：config + 权限矩阵 + 单测
python scripts/run_all_tests.py --profile full      # 加：HTTP 权限 / 对象级 / 三类 E2E / PG 并发
python scripts/run_all_tests.py --profile nightly   # 加：跨浏览器 / 生产只读
python scripts/run_all_tests.py --only perm-http,e2e-smoke   # 只跑指定
```

### 2.2 实测证据（2026-10-22 本机）

| suite | 载体 | 实测 | 耗时 |
|---|---|---|---|
| `config` | python 脚本 | **PASS** | 0.6s |
| `perm-matrix` | python 脚本（0 请求） | **PASS** | 2.0s |
| `perm-http` | python 脚本（真实 HTTP） | **PASS**（8 身份 × 199 端点） | 15.5s |
| `e2e-smoke` | **Playwright** | **PASS**（129 用例） | 79.9s |
| `e2e-smoke`（前端停掉后） | — | **SKIP**，且**退出码 2** | 0s |

→ 说明两件事：① 跨载体（python / playwright）确实串起来了；
② **环境缺失时不会假装通过**——SKIP 单独计，且"全 SKIP"时退出码为 2。

### 2.3 三个设计决定（都是为了不骗人）

| 决定 | 理由 |
|---|---|
| **SKIP ≠ PASS**，且全 SKIP 退出码 2 | 否则 CI 里"服务没起来"会变成绿灯 |
| **前置检查先跑**：每个 suite 声明它需要什么（探测栈/前端/PG/外网），缺了提前说 | 避免跑到第 5 个 suite 才炸，日志难读 |
| **每个 suite 独立日志 + 统一 summary.json** | 失败时能直接看那一条，不用翻几万字 |

### 2.4 但**不做**成"一个 Playwright 任务"——四类载体本质不同

| 载体 | 例子 | 为什么塞不进 Playwright |
|---|---|---|
| `pytest` | 2630 个单测 | 在 Django 测试库里跑，和浏览器无关 |
| Python 探测 | 权限矩阵、HTTP 探测、PG 并发 | 需要 8 个账号轮换 + 直连 DB 侧证 |
| Playwright | 78 个 spec | 它本来的地盘 |
| 外部只读 | 生产匿名探测 | 打的是线上域名，与本地栈无关 |

**统一在"入口 + 报告 + 分级"，不统一在"框架"**——强行合并只会得到一个又慢又脆的巨型命令。

---

## 3. 三份文档怎么咬合（避免各自为政）

```
① SITE_ROLE_OPERATION_MANUAL.md   ← 事实底座：8 角色 / 53 页 / 42 流程 / 336 端点
        │  （提供"该测什么"的坐标）
        ▼
② GLOBAL_TEST_PLAN_V3.md          ← 全局方案：4 维覆盖模型 + L1–L5 分层 + 42 流程矩阵
   PERSONA_TEST_PLAN.md           ← 拟人化：8 个角色的真人任务链
        │  （两份方案的缺口汇总到一处）
        ▼
③ GAP_REGISTER.md / .json         ← **唯一 backlog**（现有 2 条；原始 23 条已处置 21 条）
        │  （backlog 的执行载体）
        ▼
④ scripts/run_all_tests.py        ← **统一入口**（fast/full/nightly + 统一报告）
```

**四条约定**（写进各文档）：
1. **缺口只在 `GAP_REGISTER.md` 列一次** —— V3 与 PERSONA 只放摘要 + 链接，不各维护一份（第一版就重复登记了 F8-1/F8-3，已修）
2. **事实只在说明书里定义** —— 测试方案引用章节号（如"见 §F5-1"），不复制事实
3. **深度口径只有一套** —— `flow_coverage_matrix.py` 的 `FLOWS` 表是唯一事实源
4. **矩阵表不手写** —— `inject_flow_matrix.py` 从脚本生成，改流程先改表再重生成

---

## 4. 现在这套东西能回答什么问题

| 你问 | 去哪 | 能不能答 |
|---|---|---|
| 某个功能能不能用？ | 说明书第 12 章 + `GAP_REGISTER` | ✅ 能（且标了证据等级） |
| 全站测试过不过？ | `run_all_tests.py --profile full` | ✅ 能（一条命令一份报告） |
| 还差多少？ | `GAP_REGISTER.md` | ✅ 能（2 条，均 P2） |
| 某个角色能不能完成他的工作？ | `PERSONA_TEST_PLAN.md` 对应 persona | ⚠️ **部分**：脚本还没落地（Batch 1–3） |
| 生产环境正常吗？ | `--profile nightly` 的 `prod-readonly` | ⚠️ 只能答"匿名边界"（写操作主动不测） |

---

## 5. 下一步（没做的，明确列出来）

| 批次 | 内容 | 状态 |
|---|---|---|
| ~~Batch 1~~ | P0 五条 | ✅ 已完成 |
| ~~Batch 2~~ | P1 七条 | ✅ 已完成 |
| ~~Batch 3~~ | P2 十二条 | ✅ 已完成 |
| ✅ | **RFQ 收件箱**（`/ops/rfq`）：新端点 + 新页面 + 后端 10 条 + E2E 3 条 | ✅ 2026-10-22 |
| ✅ | **CI 已接**：新增 job `e2e-probe`（第 13 个），跑 `run_all_tests.py --only fixtures,e2e-probe` | ✅ 2026-10-22 |
| ~~待修~~ | ~~`F3-11` 下载中心~~ | ✅ **已修**（序列化器补字段 + 预取） |
| 待办 | `F1-5` 知识实体详情页交互（PART，仅加载级） | ⬜ 低优先 |
| ~~待办~~ | ~~两个已锁定的缺陷待产品决定是否修~~ | ✅ **均已修**（400 + RFQ 收件箱）|

> **现在的说法**：`GAP_REGISTER` 里 **P0/P1 已清零**，42 条流程 40 条 FULL。
> 仍不能宣称"100% 覆盖"，因为还有 2 条有明确原因的缺口 —— 但它们都在台账上，
> 不是"没人知道没测"。这正是 `GLOBAL_TEST_DEFINITION` 要求的终态。
