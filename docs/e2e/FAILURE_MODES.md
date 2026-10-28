# 失效模式清单（归属台账）

> 定义见 `GLOBAL_TEST_DEFINITION.md`。本文是它要求的**载体**。
> 规则：**每一行必须有归属状态，不允许空白。**
> 状态：**A 自动化**（改坏会红）/ **B 已知不测**（有理由 + 人工兜底）/ **C 不适用**（不存在）

更新时间：2026-10-21

## 总览

| 状态 | 条数 | 含义 |
|---|---|---|
| **A 自动化** | 28 | 有闸门能拦退化（且经变异验证或状态码/字段断言校准） |
| **B 已知不测** | 18 | 明确不测，**且有可执行的人工兜底**（见 §4.1） |
| **C 不适用** | 2 | 本系统不存在该类风险 |
| **空白** | **0** | ✅ 无盲区（7.2/7.3 由 #430、9.1 由 #431、5.5 由 #432 消除） |

**广度 = 1 − 0/48 = 100%**（48 条全部有归属）
**深度 = 28 条 A 类中，10 条经过变异验证**（其余靠字段/状态码断言校准）——
⚠️ 这次报的 100% 与之前那次不同：之前是把「兜底=无」算进 B 类换来的假 100%，
这次每条 A 都有真载体（闸门/测试/变异验证记录）。**深度仍是短板，见 §12 的 L3**。

---

## 1. 功能正确性（做什么会错）

| # | 失效模式 | 状态 | 载体 / 理由 |
|---|---|---|---|
| 1.1 | 前端读后端不返回的字段（D3、D6 的原型） | **A** | `check_api_contract.py`（20 端点，CI `contract-check`） |
| 1.2 | 状态判断恒真/恒假（D6 RUO 声明恒显示） | **A** | E2E 反向断言（"B 状态下必须不出现"） |
| 1.3 | 空态/边界渲染错（空态对比度 2.94:1） | **A** | E2E a11y 37 条 + 空态用例 |
| 1.4 | 表单校验被绕过（弱密码、非法枚举） | **A** | 序列化器单测 + 注册密码策略用例 |
| 1.5 | 计算错（价格/总额/税额） | **A** | 领域单测；`unit_price` 服务端覆盖有专项用例 |
| 1.6 | **库存纳管口径与判定不一致**（谁算"纳管"、纳管了没库存行算什么） | **A** | `SKU.is_stock_tracked` 显式开关 + `apps/inventory/tests/test_stock_shortage.py` 32 例（含「纳管但无行必须拦」「脱管但有行必须放行」两条新语义）；**3 个变异验证全部变红**（判据改回隐式、`receipt` 不自动纳管、脱管前置校验去掉）；「纳管但无库存行」的可见性由 `/inventory/tracked-gaps/` + 库存台红条承载。口径全文 `docs/INVENTORY_MODEL.md` |
| 1.7 | **累计超卖**（两客户各买光同一批货，两单都能提交） | **A** | 已修（2026-10-28 第二轮）：**承诺即锁库** —— 购物车下单锁、PO 上传不锁（意向单）、运营 Approve 时锁；释放闭环 = 取消/拒单 `release_for_order` + 超时命令 `release_expired_reservations` + 发货 `release`（**发货与取消是两种语义，用错会让库存凭空增减且不报错**）。`apps/inventory/tests/test_stock_reservation.py` 21 例；**6 个变异全部变红**（结账不锁库 / 审核不锁库 / 取消不释放 / 释放用错语义 / 手动 Allocate 不拦 / 超时碰 in_production）。E2E 同步更新：`po-lifecycle.api` 与 `ops-inventory` 原假设「手点 Allocate 成功」已失效，改为验证自动锁库 + `ALREADY_ALLOCATED` 保护。口径全文 `docs/INVENTORY_MODEL.md` §5.1 |

## 2. 权限与数据隔离

| # | 失效模式 | 状态 | 载体 / 理由 |
|---|---|---|---|
| 2.1 | 越权读写他人资源（IDOR） | **A** | `permission_audit.py`（332 端点全分类）+ `test_address_write_permission` 等 |
| 2.2 | 匿名可写（`AllowAny` 漏声明） | **A** | `permission_audit` P0 逐条核对 + 匿名写探针（部署后实测全 401） |
| 2.3 | 匿名端点泄露 PII（D13） | **A** | `test_org_search_privacy`（字段集 `==` 断言） |
| 2.4 | 对象级授权缺失（发票/附件下载） | **A** | `_is_order_viewer` 用例 |
| 2.5 | **角色能力矩阵**（每个角色"能做什么"的声明式清单） | **B** | 无声明式矩阵，能力散落在各端点权限类。**兜底**：改动权限时跑 `permission_audit --check` 看严重度变化 |
| 2.6 | 注册/加入机构时提权（D16） | **A** | `test_membership_guard.py` 11 例 |

## 3. 状态与流转

| # | 失效模式 | 状态 | 载体 / 理由 |
|---|---|---|---|
| 3.1 | 订单状态机非法跃迁 | **A** | `OrderStateMachine` 单测 + PO 流程 E2E |
| 3.2 | 并发改同一订单导致状态错乱 | **B** | 未测。**理由**：需真实并发 + 多事务；已有行锁但只有取号/库存做过并发验证。**兜底**：改状态机时人工 review `select_for_update` 覆盖 |
| 3.3 | 软删后仍可见 / 恢复失败 | **A** | 产品回收站 E2E + `retrieve` 的 archived 分支用例 |
| 3.4 | 删除产生级联孤儿 | **B** | 未系统覆盖。**兜底**：删除前跑 `capability_guard --check`（能力侧），数据侧靠 FK 约束 |
| 3.5 | 跨日/跨月结边界（单号重置、账龄） | **A** | `test_order_sequence` 跨日重置 + `test_ar_assign` |
| 3.6 | 时区/夏令时导致日期错 | **B** | 仅 `test_business_timezone` 部分覆盖；生产固定 `Asia/Shanghai` 无夏令时。**兜底**：新增日期逻辑时必须写 `business_today()` 用例 |

## 4. 数据契约

| # | 失效模式 | 状态 | 载体 / 理由 |
|---|---|---|---|
| 4.1 | 字段消失（前端依赖它） | **A** | 契约检查：少字段 = FAIL |
| 4.2 | 字段类型变化 | **A** | 同上 |
| 4.3 | 分页/信封形状变化 | **A** | E2E + 前端 store 单测（D2 的原型） |
| 4.4 | 枚举值新增/删除导致前端崩 | **B** | 无专门闸门。**兜底**：枚举改动的 PR 需人工检查前端映射（如 `poConstants.js`） |

## 5. 并发与事务

| # | 失效模式 | 状态 | 载体 / 理由 |
|---|---|---|---|
| 5.1 | 订单号重复（并发取号） | **A** | PG 并发测试 + **变异验证**（摘锁 ⇒ 重复） |
| 5.2 | 发票号重复 | **A** | 同上（`TestInvoiceSequenceConcurrencyOnPostgres`） |
| 5.3 | 库存超卖 / 读-改-写丢更新 | **A** | PG 并发测试 3 例 + **变异验证**（实测超卖 2 件、丢 1 次） |
| 5.4 | 其余 14 处 `select_for_update` 失效 | **B** | 全仓 23 处，实测 3 处（覆盖钱与库存）。**兜底**：改动这些路径时跑 `run_pg_tests.py` 并人工确认锁点 |
| 5.5 | 死锁（多行加锁顺序不一致） | **A** | **审查结论：全仓 0 处处理 40P01/40001** —— PG 杀事务后用户直接 500。已加 `core/db_retry.py`（只重试 `40P01`/`40001`，最多 3 次、退避封顶 200ms）并装饰 4 个入口（checkout / PO 提交 / 开票 / 收款，均包在 `transaction.atomic` **外层**）；`apps/core/tests/test_db_retry.py` **14 例**；变异验证：把判据改成 `return False` ⇒ 5 条变红 |

## 6. 环境与配置（横切面 A —— **本清单新增，旧框架完全没有**）

| # | 失效模式 | 状态 | 载体 / 理由 |
|---|---|---|---|
| 6.1 | `DEBUG` 在生产被打开（泄露 traceback/settings） | **A** | `config_parity.py` 检查 production 硬写 `DEBUG=False` 且 base 默认值不得为 True |
| 6.2 | `ALLOWED_HOSTS` 漏配（全部端点 400） | **A** | 同上（production 必须由环境提供且非空） |
| 6.3 | 安全响应头缺失（nosniff / secure cookie） | **A** | 同上 + nginx.conf 检查 |
| 6.4 | **容器单文件 bind mount 不跟随 inode** | **B** | 无自动检测（本轮实测踩到：宿主机改了、容器内没变）。**兜底**：改配置后**必须进容器内 grep 验证**，不能只看宿主机 |
| 6.5 | 依赖版本在 dev/镜像/CI 不一致 | **A** | `config_parity.py` 比对 `requirements.txt` 与 Dockerfile 安装源 |
| 6.6 | 时区/locale 三套不一致 | **A** | 同上（TIME_ZONE / USE_TZ / LANGUAGE_CODE） |
| 6.7 | `.env` 被打进镜像（密钥外泄） | **A** | 同上（检查 `.dockerignore`） |
| 6.8 | 前端产物依赖外网（字体 CDN） | **A** | `e2e/preflight.cjs` + 部署后 `grep fonts.googleapis dist/index.html` |

## 7. 依赖与降级

| # | 失效模式 | 状态 | 载体 / 理由 |
|---|---|---|---|
| 7.1 | 外部 API 不可达 ⇒ 页面报错而非降级 | **A** | **实测原状：视图无任何 try/except ⇒ 生产直接 500**。已修：单产品模式外层兜 **503 + `DATASOURCE_UNAVAILABLE`**、**批量模式逐条降级**（失败项 `found=False, error=source_unavailable`，不拖垮整批）；`apps/commerce/tests/test_enrich_degradation.py` **6 例**；变异验证：把 `except Exception` 换成永不匹配的异常类 ⇒ 2 条变红。⚠️ 不用 cassette：PubChem 主路径走 `pubchempy`（urllib），绕过了统一客户端 |
| 7.2 | DB 不可用 ⇒ 500 而非友好错误 | **A** | `GET /api/v1/health/` 在 DB 不可用时返回 **503 + `checks.db=error`**；`apps/core/tests/test_health.py` 8 例（含「检查函数自己抛异常也不 500」） |
| 7.3 | 磁盘满 / 内存不足 | **A** | 同一端点的 `disk` 检查（余量 < 1GB 判 degraded）；测试里用 mock 覆盖低磁盘分支 |
| 7.4 | 缓存不可用 ⇒ 回退 LocMem | **A** | cache-aside 降级有单测 |

## 8. 演化与迁移

| # | 失效模式 | 状态 | 载体 / 理由 |
|---|---|---|---|
| 8.1 | 迁移无法执行 / 无法回滚 | **A** | `migration_drill.py`（10 app / 74 迁移，CI） |
| 8.2 | **模型与迁移不一致** | **A** | CI `migration-state-check`（PostgreSQL 下 `makemigrations --check --dry-run`，自动、非人工）。★ 2026-10-28 更正：原写「当前生产就带着这个问题」**已不成立** —— 同日实测 PG 下返回 `No changes detected`，且 2026-10-21 已用 state-only 迁移对齐过。守卫见 8.5 |
| 8.3 | 数据迁移后数据不对（能跑但结果错） | **B** | 演练只验证"能执行"。**兜底**：数据迁移需人工抽样比对 |
| 8.4 | 破坏性 API 变更 | **A** | 契约检查（少字段 FAIL） |
| 8.5 | **迁移删掉生产在用的检索对象**（`search_vector` / 5 GIN / 4 trgm / 5 触发器+函数） | **A** | `scripts/check_migrations_safe.py`：AST 扫所有迁移文件，覆盖 `RemoveField`/`RemoveIndex`/`DeleteModel`/`SeparateDatabaseAndState` 子列表/`RunSQL` 里的 `DROP INDEX\|TRIGGER\|FUNCTION\|COLUMN` + 「地基迁移文件是否还在」；**12 种破坏形态变异验证全部变红**（含位置参数、跨行、侧门）。单测 `backend/core/tests/test_migration_guard.py` 19 例（含「清单完整性」：迁移里每个 `GinIndex` 都必须已登记，防新增索引漏保护）。CI 里是 `migration-state-check` 的**第一步**（纯静态、不装依赖、毫秒级）。⚠️ 为什么 `--check` 抓不到这一类：那是「模型 ↔ 迁移是否漂移」，若有人**有意**下线检索方案并同步改模型，`--check` 会绿 |

## 9. 可观测性（横切面 B —— 新增）

| # | 失效模式 | 状态 | 载体 / 理由 |
|---|---|---|---|
| 9.1 | 关键路径无日志 ⇒ 出问题无法定位 | **A** | 4 条核心路径已加带业务标识的日志（checkout / PO提交 / 开票 / 收款）；`apps/transactions/tests/test_core_path_logging.py` 4 例用 `assertLogs` 断言日志**含单号**；变异验证：把 `logger.info` 降级为 `debug` ⇒ 测试变红。⚠️ 更正：本条原写「有 logger 调用但未断言」是错的 —— 实际是**一条日志都没有** |
| 9.2 | 错误无 traceback 关联（无 request id） | **C** | 单机部署、无分布式链路，暂不适用；改为纵向扩展后需重评 |
| 9.3 | 无告警 ⇒ 故障靠用户投诉发现 | **C** | 当前无告警系统，属运维缺失而非测试缺失（已记入待办） |

## 10. 非功能

| # | 失效模式 | 状态 | 载体 / 理由 |
|---|---|---|---|
| 10.1 | 性能退化（某端点变慢 10 倍） | **A** | `perf_gate.py`（9 端点，**发版前手动跑 `--strict`**；刻意不进 CI 见 §3.15.1） |
| 10.2 | 数据量 10 倍后崩（查询无索引/全表扫） | **A** | 新增 `scripts/seed_volume.py`（bulk_create，1x=5s / 10x=37s；**库名必须含 "vol"** 防误伤）+ 实测报告 `docs/e2e/VOLUME_BENCHMARK.md`。**实测结论：10x 后 2 个端点超限** —— `search/grouped` **7.5s**（FTS 查询时现算 tsvector，索引完全没用上）、`sitemap.xml` **7.6s 且响应 16.6MB**（超线性 25.5x，匿名可触发的带宽放大）。⚠️ 状态 A 指「能复现并量化」，**不是已优化**：两个瓶颈仍在，修法（sitemap 分片 / tsvector 加 trigger）另立任务 |
| 10.3 | 可访问性回归 | **A** | E2E axe（37 条，全站 0 critical/serious） |
| 10.4 | 跨浏览器差异 | **A** | Playwright 三引擎（chromium/firefox/webkit） |

---

## 10.1 契约特例：健康检查返回**裸 JSON**（不套统一信封）
`GET /api/v1/health/` 显式指定 `@renderer_classes([JSONRenderer])`，绕开全局
`EnvelopeRenderer`（项目其他端点都套 `{success,data,meta}`）。

理由：它是**机器接口**（LB / k8s probe / 监控轮询）。若套信封，503 时
`{status, checks}` 会被塞进 `meta.error`，监控端取不到 `status` 字段。

⚠️ 实现上踩过两次：
1. 第一版用纯 Django `JsonResponse` 绕信封 ⇒ **`force_authenticate`（DRF 机制）对它无效**，
   staff 判定永远 False（测试 7 passed / 1 failed 才发现）
2. 正解是**保留 DRF 视图（认证走 DRF）、只替换 renderer**

## 11. 本轮已升级的条目

| 条目 | 之前 | 现在 | 靠什么升级 |
|---|---|---|---|
| 6.1 / 6.2 / 6.3 / 6.5 / 6.6 / 6.7 | 空白（无归属） | **A** | 新增 `scripts/config_parity.py` |
| 5.2 发票号重复 | 空白 | **A** | 新增 `TestInvoiceSequenceConcurrencyOnPostgres` |
| 4.x 契约覆盖 | A（但仅 4 端点） | **A（20 端点）** | 契约扩容 |
| 1.1 / 2.3 | 空白 | **A** | D3/D6/D13 修复时补的用例 |
| 8.2 模型与迁移不一致 | B（"当前生产就带着"） | **A** | CI `migration-state-check` 自动执行；同日实测无漂移 |
| 8.5 迁移删掉检索对象 | 空白（无归属） | **A** | 新增 `scripts/check_migrations_safe.py` + 19 例单测 + 12 形态变异验证 |

## 12. 按"归属状态"排出的下一步优先级

**B 类里风险最高的三条**（不是条数最多，是后果最重）：

1. ~~**8.2 模型与迁移不一致**~~ → **2026-10-28 已升级为 A**：CI `migration-state-check` 自动执行（不再靠人工），且同日实测 PG 下 `No changes detected`，原「当前生产就带着这个问题」的描述已不成立
2. **7.1 依赖失效的降级行为** —— 外部 API 是核心链路（AUTO MATCH / enrich / COA），挂掉的概率不低
3. **10.2 数据量级** —— 决定架构能否支撑增长，且成本随时增长而上升

**明确不值得投入的**：把 5.4 的 14 处锁全部补并发测试（成本极高，且那 14 处多在低并发路径）。
