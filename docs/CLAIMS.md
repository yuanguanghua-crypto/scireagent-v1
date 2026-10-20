# 结论登记表（CLAIMS）

> **用途**：记录"我们相信什么"+"凭什么"+"什么时候会失效"。
>
> **铁律**：**没有「失效条件」的结论，等于没有结论。**
>
> **为什么需要这张表**（2026-10-19 立的规矩）：
> 本项目的翻车方式不是"文档过时"，而是**"结论记得住、它依赖什么没人记"**。
> 实例：`basket.js` 的注释与 toast 文案都声称"被跳过的行留在 localStorage 可重试"，
> 代码注释写得很认真、toast 也说得很清楚 —— 但**那个前提在真实链路从不成立**
> （`saveLocalBasket()` 只在 API 失败降级时调用，成功路径从不写 localStorage）。
> 文档和代码**同步地错**，所以"检查文档是否过时"这个方法查不出来。

---

## 新增结论前必答四问

> 这四问是本项目的**强制闸门**。凡是涉及**资金 / 库存 / 权限 / 数据可见性**的改动，
> 合并前必须由一个**没有参与实现**的人回答。

1. **这个结论依赖的前置状态，在真实路径上「谁会生产它」？**
   - 找不到生产者的状态，就是不存在。（A5 就是这样暴露的）
2. **如果这个状态不产生，用户会看到什么？**
   - 这一问能直接暴露"用户以为商品还在、实际已消失"这类问题。
3. **有没有一个最小反例能推翻这个结论？**
   - 找不到反例只能说"未发现反例"，**不能说"证明为真"**。
4. **哪条测试能证伪它？**（2026-10-20 新增，登记表最后一列）

   必须写出**具体的测试文件（用例名）**，或者一条**任何人重跑都能得到同样结果的命令**。

   - ⚠️ **「我验证过了」不是判据。** 判据的标准是：**别人不需要问你就能够推翻它。**
   - 两种合格形态：
     - **自动化（最优）**：故意破坏这条结论，那条测试会变红。这种能进 CI，
       不依赖任何人的记忆 —— 参考 `scripts/mutation_check.py` 做过的 4 次变异验证。
     - **可复现命令（次优）**：一条 SQL / curl / 脚本，输出可判定。
   - **填「无」是允许的**，但要如实写明为什么设不了判据。
     这比编一个测试名诚实 —— 编造会让后来的人以为"有人在看"，
     而实际没有，比空白更危险。
   - 自检一句：**如果这条结论明天悄悄失效了，谁会知道？**
     答不上来，就说明它还没有判据。

---

## 登记

状态图例：`有效` / `已失效` / `时效性`（需每次核对）/ `风险已知未处理`

| # | 结论 | 依据（可复现） | **失效条件** | 状态 | **证伪判据（测试 / 命令）** |
|---|---|---|---|---|---|
| C1 | `POST /basket/merge` 的"叠加超 999"走**跳过**（200 + `skipped_items`），不发 400 | `basket_views.py:303-338`；实测 5 件中 1 件超限 → 200 / `merged:1` / `skipped:1` / 其余 4 件落库 | 若 `max_line_quantity` 语义改为"整单上限"而非"单行上限" | 有效 | `tests/test_basket_merge_overflow_skip.py`（19 例）+ e2e `basket-merge-over-limit.spec.cjs` |
| C2 | 被跳过的行**不会**保留在 localStorage 待重试 | `saveLocalBasket()` 仅 3 处 catch 调用（`basket.js:111/137/154`），`loadBasket():43` 成功路径不写；实测主流程 `localStorage=null` | 若 `loadBasket()` 增加写 localStorage，或新增"合并失败落本地"逻辑 | **已失效** ⚠️ 旧注释与 toast 曾如此声称（已于 `7c2a0f2` 修正文案） | e2e `basket-local-merge-prune.spec.cjs` |
| C3 | `pruneMergedLocalItems()` **只在「匿名 + 加购 API 失败」的降级路径上生效**；正常网络下 `localStorage` 为空，走不到它 | `saveLocalBasket()` 仅 3 处 catch 调用（`basket.js:111/137/154`）；`addItem` 降级条件 `if (!token)`（`:99`）⇒ 只有匿名且 API 失败才写副本；登录时 `auth.js:58` 的 `filter(_guest \|\| _local)` 能读到它 ⇒ 该路径上 prune **确实在工作** | 若正常路径也开始写 localStorage（那会把"降级专用代码"变成主流程代码，**须重新评估二次合并翻倍风险**） | **有效，但仅限降级路径** ⚠️ 本表曾误标为「死代码」，因为只验证了主流程不可达，**没验证降级路径可达** | e2e `basket-local-merge-prune.spec.cjs` |
| C4 | 库存 `available`/`allocated` 写库前有 **int4 上界**检查，且对**累加结果**判定 | `services.py:11-25` 守卫；`receipt:148` / `adjust:167` / `allocate:47` 三处；实测 `available=INT4_MAX-1000` + receipt 1001 → 400 | 若 DB 列类型从 `int4` 改 `bigint` | 有效（含 `cac4d79` 修复的"先查后加"顺序） | `inventory/tests/test_int4_overflow.py` |
| C5 | 所有累加守卫必须**先查后加**，不可在 `+=` 之后调用 | `allocate` 曾在 `allocated += qty` 之后守卫 ⇒ 多算一次 quantity ⇒ **合法下单被误拒**（`allocated=INT4_MAX-100` + 60 应成功却 400）。已修为 `:47` guard → `:48` allocate | — | 有效（根因是顺序，不是数值） | `inventory/tests/test_int4_overflow.py` |
| C6 | 数据库层禁止负库存（`ck_inv_available_nonneg` / `ck_inv_allocated_nonneg`） | `models.py:43-53` + `inventory/0005`；生产 `pg_constraint` 实测 `convalidated=t`；本地 2026-10-19 已 migrate 并实测 `available=-5` 被 `IntegrityError` 拦 | 若绕过 ORM 用 raw SQL 且 `SET session_replication_role=replica` | 有效 | `inventory/tests/test_int4_overflow.py` + 迁移 0005 |
| C7 | 生产代码 = GitHub = 本地 HEAD | 四值全等（2026-10-19 09:30 时为 `7c2a0f2`） | **任何一次本地提交后立即失效** | **时效性** —— 每次部署前后必须重新核对 | **未设自动化判据** —— 靠人工四地核对（见本表「维护」） |
| C8 | 生产前端产物与 HEAD 源码一致 | `dist/` 143 资产 mtime 与构建时间一致；判别串 `kept for retry`=0 / `not merged`>0；经 nginx 取回 md5 == 磁盘 md5 | 同 C7；另：**前端 dist 不在 git 里，四地一致 ≠ 前端上线** | **时效性** | **未设自动化判据** —— 靠人工 md5 核对（见本表「维护」） |
| C9 | 匿名写端点是**设计允许**（游客购物车 / 匿名 RFQ），非漏洞 | `basket_views.py:73/88/136/171` 均 `AllowAny`；`quotes` 视图 `permission_classes=[]`；`AllowAny` 次数与上一版相同（6=6） | 若产品决定关闭匿名购物车 | **风险已知未处理** ⚠️ 见 C10 | `transactions/tests/test_api_permission_hardening.py` |
| C10 | 匿名写入**无实质上限**：`quote-requests` 的 `items` 无 `max_length` 且 `{}` 是合法 item | `quotes/api/v1/serializers.py:16`；实测 `items=[{}]×50000` 通过校验（0.26s）；20MB 请求正文理论可塞约 520 万条 | 若加上 `max_length` | **风险已知未处理**（建议 `max_length=50`，见 `docs/DECISIONS.md` D5） | **未设判据** ⚠️ 这是「缺失上限」的断言，没有测试能证明"永远没有" |
| C11 | 匿名写探针必须**穿透 nginx** 才有意义 | 不带 Basic Auth 的 401 来自 nginx（`WWW-Authenticate: Basic`），根本没到 Django；只有带 Basic Auth 后仍 401（`WWW-Authenticate: Token`）才是应用层判据 | 若移除 nginx Basic Auth | 有效（方法论） | 非可测断言（方法论）—— 无判据 |
| C12 | 不能用 `OPTIONS` 探测"匿名可写" | DRF `SAFE_METHODS=('GET','HEAD','OPTIONS')`，`IsAdminOrReadOnly` 对 OPTIONS 放行 ⇒ 会得出**完全相反**的结论 | DRF 改 `SAFE_METHODS` | 有效（方法论） | 非可测断言（方法论）—— 无判据 |
| C13 | ★ **「叠加后超单行上限 999」在真实数据中几乎不可能发生**：`basket` 175 行 **max=8** / p95=3；`order_item` 954 行 **max=9** / p95=2；两表 **≥100 的行数均为 0**。上限 999 与真实峰值 9 相差**两个数量级** | `select max(quantity)` / 分位数（2026-10-19 本地库实测） | 若出现批发型大单（单行 ≥ 100），需重新评估上限是否合理 | 有效 —— ★ 这条是「**不做** basket 合并超限可重试」的决定依据（见 `DECISIONS.md` D8） | 可复现 SQL（见「依据」列），非自动化 |

---

## 已确认失效的旧结论（保留作为教训，勿再引用）

| 旧结论 | 曾出现在 | 实际问题 | 纠正 |
|---|---|---|---|
| 「被跳过的商品保留在 localStorage，用户可自行调小后重试」 | `basket.js` 注释、toast 文案 | localStorage 恒为 null，该路径不存在 | `7c2a0f2` 删除文案，改为"请手动重新加购" |
| 「整条 400 会让用户陷入重试死循环、且商品全部丢失」 | 我本人 2026-10-19 的判断 | 前半句对（确实 400），后半句**错**：400 时 catch 在轮换 session key **之前** return，老 key 保留，用户登出后仍能看到全部商品 | `5463633` 改为跳过；但"可找回"这一优势也随之失去 |

---

## 维护

- 每次部署后：核对 C7 / C8（**必做**，属时效性结论）
- 每次改动涉及资金/库存/权限/可见性：新增一行，并回答**四问**
- ★ **新增行必须填「证伪判据」列**（2026-10-20 起）。填「无」可以，但要写清原因。
  ⚠️ C1~C13 的判据列是**补填**的，其中 C7/C8/C10/C11/C12 明确标了"无自动化判据" ——
  这不是偷懒，是如实标注它们**目前只能靠人或靠方法**，没有测试能替你看着。
- 发现某条失效：**不要删**，移到「已确认失效」，写明曾被谁依赖

## 为什么要有「证伪判据」这一列（2026-10-20）

文档治理解决不了"文档与代码同步错"—— 因为**它们是一起错的**。

`FIVE_DATASOURCES.md` 就是实例：它写「核心命题：平台的数据由**五**数据源获取」，
**同一句话里却列了 6 个名字**（PubChem / ChEMBL / PubMed / BioProCorpus / jena / Bioz）。
文档 3 个月没人动，代码引用它 18 处，照样没人发现 —— 因为**没有任何东西会因此变红**。

对比 `COA_SDS_PRD.md:80`（"审批即发布 → status=PUBLISHED"）：它也 3 个月没更新，
但它是**准的** —— 因为 `test_sds_download_gate.py` 按它当判据，写错了测试就红。

⇒ **文档不会因为被"维护"而准确，只会因为被"引用/被执行"而准确。**
「证伪判据」这一列就是把"断言"往"测试判据"上逼：填不出判据的结论，
至少让读的人知道它**目前无人看守**。

