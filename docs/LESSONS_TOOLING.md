# 事故教训固化：可执行工具集

本目录的每个脚本都对应一条**真实付出代价换来的教训**。
目的：让教训在会话结束后依然生效，而不是只留在某个人的记忆里。

| 脚本 | 固化的教训 | 事故形态 |
|---|---|---|
| `hooks/pre-commit-capability-guard` + `install_git_hooks.py` | 闸门必须**自动接入**，否则等于没有 | 闸门 1398 行已落地，但 `.git/hooks/` 0 个 hook、`.github/workflows/` 0 个 workflow ⇒ 只能靠人记得手动跑；当天因此丢失批量 AI + goals/apps UI 两项能力 |
| `migration_drill.py` | migration 必须在**独立实例**上全链路演练 | `documents/0006` 漏 commerce 跨 app 依赖 ⇒ 新环境/回滚/分库抛 `FieldError: Cannot resolve keyword 'current_sds_id'`；`manage.py check` 查不出 |
| `prod_schema_tables.py` | 生产表名**要查不要猜** | 按本地习惯猜 `productmethod`，实际是 `product_method` ⇒ SQL 直接报错 |
| `find_stale_duplicates.py` | 改名后必须清理旧副本 | `deletion_guard.py`（有 P0 漏洞）残留磁盘且从未进 git ⇒ 跑它会得到「可以删」的**假安全信号** |
| `test_result_summary.py` | pytest 汇总行不可信 | 汇总行被 `ValueError: I/O operation on closed file` 吞掉；`grep -oE '[.FEsxX]'` 被路径字母污染（实测 `s`：1 vs 30） |

全部**纯标准库**，全部**只读/报告型**（唯一例外是 `migration_drill.py`，
但它只在自建的临时 sqlite 实例上操作，绝不碰项目 DB）。

---

## 1. 删除前置闸门（★ 最高优先级）

### 安装

```bash
# 方式 A（推荐）：安装脚本。会先检查 core.hooksPath 是否已被占用
backend/venv/Scripts/python.exe scripts/install_git_hooks.py

# 只看状态，不改任何东西
backend/venv/Scripts/python.exe scripts/install_git_hooks.py --status

# 卸载
backend/venv/Scripts/python.exe scripts/install_git_hooks.py --uninstall
```

方式 B（手工）：

```bash
cp scripts/hooks/pre-commit-capability-guard .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit          # Git Bash 下必须
```

> ⚠️ **换机器后要重装**。`.git/hooks/` 不入库（每个 clone 都是空的），
> 所以新 clone 必须跑一次安装脚本。模板在 `scripts/hooks/` 里，随仓库分发。

### 为什么必须用 `.gitattributes`

本仓库 `core.autocrlf=true`。这意味着模板检出后可能是 CRLF，
而 CRLF 的 bash hook 在 Git Bash 下会报 `$'\r': command not found`。
仓库根的 `.gitattributes` 对 `scripts/hooks/*` 强制 `eol=lf`，
让这条约束**跟着文件进仓库**，而不是靠每个人的机器配置。

### 触发条件

只在**暂存区有文件被删**时才跑闸门：

```bash
git diff --cached --name-only --diff-filter=D
```

实测：日常提交（无删除）hook 耗时 **0.64s** 且完全不启动闸门；
有删除时约 **2~4s**。若每次提交都跑，必然会被关掉 —— 那等于没装。

### 绕过方式（三条，都会留下痕迹）

```bash
git commit --no-verify                          # git 原生
SKIP_CAPABILITY_GUARD=1 git commit             # 显式环境变量
CAPABILITY_GUARD_FORCE=1 git commit            # 放行但保留 BLOCK 告警
```

### 失败提示里最关键的一条

> **孤儿模块不算入口。**
> 路由注册了但没有任何页面引用它 ⇒ 不许用它来过闸门。
> 用孤儿入口骗过闸门，等于把「删掉了」换成「看不见了」，事故只是从显性变成隐性。

### 设计取舍：fail-closed

闸门自身出错（找不到解释器、git 取不回内容、甚至 Python 崩栈）时**也拦**。
理由：只读工具报错时如果默默放行，等于给了一个假的「已检查」信号。

⚠️ 特别注意：Python 未捕获异常的退出码**也是 1**，与 BLOCK 完全相同。
所以 hook 靠输出里的 `Traceback` 区分两者 —— 否则「崩栈」会被误报成
「失去了能力入口」，人以为「那就是要删的」就绕过了，崩栈反而成了放行通道。

---

## 2. migration 演练

```bash
# 完整演练 documents 的 0006（今天的重点）
backend/venv/Scripts/python.exe scripts/migration_drill.py --app documents --target 0006

# 只做静态跨 app 依赖审计（最快，秒级）
backend/venv/Scripts/python.exe scripts/migration_drill.py --app documents --audit-only
```

演练链路：静态依赖审计 → 迁移到前节点 → 造存量数据 → 应用目标迁移
→ 幂等重跑 → 反向回滚。

### 实测：它真的能抓到今天的 bug

把 `documents/0006` 的 `('commerce', '0006_product_current_sds')` 依赖删掉后：

```
🛑 静态依赖审计（manage.py check 查不到的部分）
      1 处可疑：documents/0006_sdsrevision_status：数据迁移引用了 app 'commerce' 的模型，
      但 dependencies 未声明 ⇒ 若 commerce 尚未迁到含所需字段的版本，
      回填会抛 FieldError: Cannot resolve keyword
🛑 ③ 应用目标迁移 documents/0006_sdsrevision_status
      ❌ 跨 app 依赖缺失：FieldError: Cannot resolve keyword 'current_sds_id'。
         ⇒ 生产当前进度可能刚好掩盖了它，但**新环境 / 回滚 / 分库会炸**。
```

### 两个容易踩的实现坑

1. **造数必须用「历史模型」，不能用当前模型。**
   第①步把库迁到目标的前一个节点，此时 schema 是**旧的**。
   用当前模型插入会报 `table product has no column named catalog_no`。
   正确做法：`MigrationExecutor(connections['default']).loader.project_state((app, node))`。

2. **造数失败必须标红。**
   实测中造数脚本曾因模型名写错而静默退出，演练却报「全链路通过」——
   那是**假绿灯**，比红灯危险得多（数据没造出来时，迁移「成功」只证明了空库能迁）。

### 数据形态

造数贴近生产真实形态，重点是**序号版单 + uuid 版单并存**：

- 序号版：`ORD-YYYYMMDD-NNN`（`next_checkout_order_no()`，计数器口径）
- uuid 版：`ORD-{hex8}`（`PoSubmissionService.submit()` 直接 `uuid4`）

迁移若假设了单一形态，回填/统计就会口径错。

### DB_ENGINE 必须是 `sqlite`（不是全路径）

这是实测踩到的隐蔽坑：

- `config/settings/development.py` 用 `os.getenv('DB_ENGINE') == 'sqlite'` 判断，
  只有**恰好**是 `'sqlite'` 时才会换成 sqlite3 后端并摘掉 `django.contrib.postgres`。
- 各 app 的 `models.py` 用 `!= 'sqlite'` 判断 `_USE_POSTGRES`。
- 若写成 `django.db.backends.sqlite3`：models 以为在 Postgres ⇒ 声明了
  `SearchVectorField`，而 sqlite 迁移没建该列 ⇒ 建库序列化直接炸
  （`no such column: application.search_vector`）。

同理，跑 pytest 时也必须用 `DB_ENGINE=sqlite`，而非
`DB_ENGINE=django.db.backends.sqlite3`（后者会让整个测试套件在 setup 阶段失败）。

---

## 3. 生产表清单（只读）

```bash
# 生产（docker exec 进 postgres 容器）
backend/venv/Scripts/python.exe scripts/prod_schema_tables.py
backend/venv/Scripts/python.exe scripts/prod_schema_tables.py --grep method --rows

# 本地退化（不需要 docker）
backend/venv/Scripts/python.exe scripts/prod_schema_tables.py --sqlite backend/db.sqlite3 --grep method --rows
```

实测输出（本地 sqlite）：

```
过滤：表名含 'method'（共 5 / 5 张表）

  表名                       行数
  -----------------------  ----
  method                    67,091
  method_protocol           15,036
  method_reagent_class      39
  product_method            146
  product_method_relation   159
```

`product_method` 而不是 `productmethod` —— 这就是今天的坑。

### 只读是硬约束，写在代码里

`_assert_readonly()` 对每条要发送的 SQL 做词边界匹配，出现
`INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/GRANT…` 就**在本地拒绝**，
根本不会发到生产。

用**词边界**而非朴素子串，是为了不误杀 `WHERE updated_at > NOW()`
（`updated_at` 里含 `update` 子串）。字符串字面量与注释里的关键字也会先剥掉。

⚠️ 只读脚本最大的风险不是「写错了」，而是「某天有人加了个功能」。
所以约束写进代码，而不是写进注释。

---

## 4. 残留副本检测

```bash
backend/venv/Scripts/python.exe scripts/find_stale_duplicates.py
backend/venv/Scripts/python.exe scripts/find_stale_duplicates.py --threshold 0.98
backend/venv/Scripts/python.exe scripts/find_stale_duplicates.py scripts/
```

**只报告，不删除。**

### 为什么阈值定在 0.95（宁可漏报也不要误报）

误报的代价是**信任崩塌**：工具一旦开始喊狼来了，大家就会学会忽略它。
实测在真实仓库（1162 个文件）上跑，默认阈值给出 **0 条**报告。

脚本里有一处值得说明的实现：前端 `frontend/` 下同时留着
`_d2` `_d3` `_d4` `_d5` `dist_new` 等多份历史构建输出，
它们是同一版本 bundle 的重复，相似度轻松 0.95+。
目录名会变（`_d6`、`dist_2024`…），写死目录名堵不住，
所以改为**按内容特征**识别 —— 实测 bundle 平均 **12587 字符/行**，
而正常源码约 **31~38 字符/行**，差三个数量级，阈值取 1000 有极大余量。

另外还排除了 `foo.py` 与 `foo/__init__.py` 这类正常共存结构。

### 它抓不到什么

- 「改了名字但逻辑已分叉」的副本（需要读代码语义，超出相似度判断范围）。
- 实测真实分叉样本 `fill_missing_data.py` vs `_v2.py` 相似度仅 **0.357**，
  远低于 0.95 ⇒ 不会误报。

---

## 5. pytest 输出判读

```bash
backend/venv/Scripts/python.exe scripts/test_result_summary.py _fb_after_commerce.txt
backend/venv/Scripts/python.exe scripts/test_result_summary.py out.txt --expect-failed 5
backend/venv/Scripts/python.exe scripts/test_result_summary.py out.txt --json
```

### 为什么不能用 `grep -oE '[.FEsxX]'`

它对**整行**做字符提取，于是路径里的每个 `s`、`e`、`x` 都变成一个「跳过的测试」。
实测对照（同一份输出）：

| 做法 | passed | failed | skipped |
|---|---|---|---|
| `grep -oE '[.FEsxX]'`（错误） | 11 | 2 | **30** |
| 本脚本（行首锚定） | 8 | 1 | **1** |

做法：进度点图**只认行首** `^[.FEsxX]+[ \t]*\[`。

### 汇总行缺失时不编数字

输出会显式标注「数字来源：进度点图反推（汇总行不可用）」，
并给出疑似原因（`ValueError: I/O operation on closed file`）。
两个来源都在且不一致时，会警告「通常意味着输出被截断」。

### 与基线比对

`--expect-failed N`：失败数 **≤ N** 时退出 0（基线内的既有失败是预期状态），
超过才判回归。否则基线里的 5 条外网失败会让这个命令天天误报。

---

## 测试与 mutation 验证

测试放在 `backend/apps/core/tests/`（pytest rootdir 是 `backend`，
放 `scripts/tests/` 不会被收集）。

```bash
cd backend
DB_ENGINE=sqlite SECRET_KEY=x venv/Scripts/python.exe -B -m pytest \
  apps/core/tests/test_test_result_summary.py \
  apps/core/tests/test_find_stale_duplicates.py \
  apps/core/tests/test_prod_schema_tables.py \
  apps/core/tests/test_capability_guard_hook.py \
  apps/core/tests/test_migration_drill.py \
  -q --tb=short -p no:cacheprovider
```

每个脚本都做过 **mutation 验证**（破坏实现 → 确认测试变红），
记录见提交历史。摘要：

| 脚本 | 变异 | 结果 |
|---|---|---|
| `test_result_summary` | 去掉进度点图行首锚定 | 4 条测试红 |
| `test_result_summary` | 反转「汇总行丢失」判定条件 | 2 条测试红 |
| `find_stale_duplicates` | 关闭压缩产物识别 | 2 条红（含真实仓库零误报门禁） |
| `find_stale_duplicates` | 关闭注释降噪 | 2 条红 |
| `prod_schema_tables` | 让只读守卫完全失效 | 2 条红 |
| `prod_schema_tables` | 词边界改朴素子串（引入误报） | 1 条红 |
| `migration_drill` | 删除 `documents/0006` 的 commerce 依赖 | 报出 FieldError + EXIT=1 |