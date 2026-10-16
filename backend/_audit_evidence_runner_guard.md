# pytest runner 统一改造 —— 实测取证

日期：2026-10-17
基线 commit：`cab93ab`
命令口径：`backend/venv/Scripts/python.exe`，工作目录 `backend/`

---

## 一、核心事实（实测，纠正立项文档的偏差）

| 项 | 立项文档说法 | **实测结果** |
|---|---|---|
| `manage.py test` 行为 | 完全收集不到，报 `Ran 0 tests` | **收到 1984 个测试**（`Found 1984 test(s).`） |
| pytest 收集规模 | 28 文件 / 约 284 用例 | **176 文件 / 2438 用例** |
| 隐形文件数 | 28 个 | **34 个**（静态扫描）/ 其中 26 个实测 unittest 收 0 |

### 关键纠正：`manage.py test` 不是「Ran 0 tests」

实测 `manage.py test`（后台跑，落盘 `_mpt_test_out.txt`）开头：

```
Creating test database for alias 'default'...
Found 1984 test(s).
System check identified no issues (0 silenced).
```

⇒ 立项文档「`Ran 0 tests`」的结论**只在"指定某个纯 pytest 风格文件/目录"时成立**，
全量 `manage.py test` 会收到 1984 个 unittest 风格用例。

### 但「假通过」的风险**依然真实**，且性质更隐蔽

真实危害不是"报 0 个"，而是：
`manage.py test` 跑完它能看见的 1984 个用例后**返回 exit 0**，
而 pytest 风格的用例**从未运行** —— 人看到"测试通过"就以为验证过了。

⇒ 拦截守卫的**必要性成立**，但理由和数字要按实测改写。

### 隐形用例的实测口径

- unittest 加载器逐文件实测（`unittest.defaultTestLoader`）：
  27 个纯 pytest 风格文件 **全部收 0 个用例**
- pytest 收集：其中 26 个文件合计 **251 个用例**（`test_order_flow.py` 当时被另一位
  工程师占用未纳入该次统计）
- 静态 AST 扫描共列出 **34 个** 含 pytest 风格用例的文件
- 差值来源：其中 6 个是**混风格**文件（既有 `TestCase` 子类又有模块级 pytest
  函数），unittest 能收到其`TestCase` 部分（实收 5~21 个），被守卫保守列入

---

## 二、守卫实现

### 位置

- 新增：`backend/config/guard_manage_py_test.py`
- 接入：`backend/manage.py` 的 `main()`，**在 `os.environ.setdefault(...settings...)`
  与 `execute_from_command_line` 之前** —— 即Django 初始化之前，误用立刻失败，
  不值得为它先建测试库。

### 为什么用静态 AST 而不是"跑 pytest collect 比对"

用户建议的参考方向是"在 manage.py 里比对 pytest 收集数与 unittest 收集数"。
实测开销对比：

| 方案 | 耗时 | 依赖 |
|---|---|---|
| **静态 AST 扫描（采用）** | **0.42 s** | 仅标准库 |
| 实跑 `pytest --collect-only` | 3.58 s | pytest + 插件 + settings |
| 参照：`manage.py check`（仅初始化 Django） | 1.66 s | Django |

结论：静态扫描快 **8.5 倍**，且不碰数据库、不加载 Django、不依赖 pytest 插件。
守卫只在"真的要跑 `manage.py test`"时触发，而那条命令本身要建测试库 + 跑 1984 个
用例（分钟级），0.42 s 相对可忽略。

**但静态方案有代价，已在守卫输出与 docstring 里写明**：它判的是"文件里有没有
`test_` 开头的定义"，不是"unittest 到底收几个用例"，因此对混风格文件偏严
（可能多拦一次本可运行的调用）。方向是安全的 —— 只会误拦，不会漏放，不会假通过。

### 守卫能力（逐条实测验证）

| 场景 | 期望 | 实测 |
|---|---|---|
| `manage.py test`（无参数） | 拦截 exit 1 | exit 1 + 指引 |
| `manage.py test apps/accounts` | 拦截 exit 1 | exit 1 + 指引 |
| `manage.py check` | 放行 | exit 0，`System check identified no issues` |
| `manage.py migrate` / `runserver` / 无子命令 | 放行 | 全部放行 |
| `SCIREAGENT_ALLOW_MANAGE_TEST=1` | 放行 | 放行 |

### 已知局限（守卫**覆盖不到**的情况）

1. **「两条命令都收集不到」的文件 ⇒ 守卫放行。**
   守卫靠 `sys.argv[1] == 'test'` 触发，不比对收集数，因此这类文件它**根本不会看到**。
   静态扫描会把它们识别为"无 `test_` 定义"并**单独归类为"非测试"**（输出里会列出），
   这只是让统计更准，**并不能拦住它们**。
   ⇒ 解法是给这类文件改名去掉 `test_` 前缀，不指望守卫。

2. **守卫只拦 `manage.py test`。** 直接 `python -m unittest ...` 绕过 `manage.py`
   不在覆盖范围。

3. **偏严的假阳性**：混风格文件被一并列入（见上）。

4. AST 只认**直接**继承 unittest `TestCase` 家族的类，且只数**类体内直接定义**的
   `test` 方法。间接基类（`class T(BaseTestCase)`）会漏判成隐形 ⇒ 偏严。

5. 扫描按 `python_files`（`test_*.py` / `*_tests.py` / `tests.py`）匹配文件。

### 交叉验证（守卫 vs unittest 真实行为）

把静态判定与 `unittest.defaultTestLoader.loadTestsFromModule().countTestCases()`
逐文件比对：

- 34 个被列入文件中，**28 个实测 unittest 收 0 个** ⇒ 判定正确
- 6 个混风格文件 unittest 实收 5~21 个 ⇒ 守卫的已知偏严假阳性（见局限 3）

落盘：`_crossvalidate_out.txt`

---

## 三、`manage.py test` 调用点清单与处理

全仓扫描（排除 `.git/`、`node_modules/`、`venv/`）共**11 处**命中，
分布在 **3 个文件**，其中 9 处是立项文档自身在**描述**这个命令（非调用点）。

### 已修改（1 处）

| 文件 | 位置 | 处理 |
|---|---|---|
| `.claude/commands/django.md` | 第 14-15 行 | 改为 pytest 命令 + 标注禁用 `manage.py test` 及原因 |

原文：
```
- 测试用 Django TestCase + factory_boy
- 运行测试：cd backend && python -B manage.py test --settings=config.settings.development
```
现为：
```
- 测试用 Django TestCase + factory_boy；也可用 pytest 风格（模块级 def test_xxx + 裸 assert）
- **运行测试一律用 pytest**（两种风格都能收集）：cd backend && venv/Scripts/python.exe -B -m pytest -p no:cacheprovider
- ⚠️禁用 `manage.py test`：它走 unittest 发现器，看不到 pytest 风格用例，会静默少跑后返回 exit 0（假通过）。已加拦截守卫，误用会直接报错退出。
```

### 无需修改（已核实为 pytest 或非调用点）

| 文件 | 核实结论 |
|---|---|
| `backend/scripts/run_tests.sh` | Step 5 已是 `python -m pytest apps/ -v --tb=short` ⇒ **本来就是 pytest** |
| `backend/scripts/run_tests.bat` | 同上，已是 `python -m pytest apps/ -v --tb=short` |
| `backend/CLAUDE.md` | 团队规范早已确立 pytest（多处 `-m pytest`），无 `manage.py test` |
| `_audit_tmp/立项_pytest隐形测试_*.md` (9 处) | 立项文档在**描述**该命令，非调用点 |
| `_audit_evidence/01_full_inventory.md` | 取证表格的表头，非调用点 |

### 无 CI 配置（实测确认）

`.github/`、`.gitlab-ci.yml`、`Jenkinsfile`、`.circleci/`、`azure-pipelines.yml`
**全部不存在** ⇒ 不存在"CI 用哪条命令"的既成约束，无需处理。

### 未改动、需你确认的文档清单

以下 `.md` 记录了立项时的**旧数字**（"28 文件 / 284 用例 / `Ran 0 tests`"），
现已与实测不符。属历史立项/取证文档，**我未改动**（它们是决策过程的留痕）：

- `_audit_tmp/立项_pytest隐形测试_2026-10-17.md`
- `_audit_evidence/01_full_inventory.md`
- `_audit_evidence/03_planA_cost.md`

⇒ 建议：若这些文档要作为团队规范长期保留，应加一行"实测纠正"批注；
若只是过程留痕，可保持原样。请指示是否要我补批注。

---

## 四、pytest 全量基线

落盘：**`backend/_pytest_full_baseline.txt`**

命令：
```
DB_ENGINE=sqlite venv/Scripts/python.exe -B -m pytest -p no:cacheprovider --tb=line -rf
```

### 关键数字

```
5 failed, 2424 passed, 10 skipped, 6 warnings in 278.72s (0:04:38)
```

| 指标 | 数值 |
|---|---|
| 总用例 | **2439**（2438 收集 + 1 parametrize 展开差） |
| passed | **2424** |
| failed | **5** |
| skipped | **10** |
| error | **0** |
| 耗时 | **278.72 s** |
| 测试文件 | **176** |

`skipped` 的 10 条与 `backend/CLAUDE.md` 记载一致：「10 skipped 为 PostgreSQL 专用」。

### 5 条失败分类 —— **全部与本次改造无关，且非外网依赖**

| # | 用例 | 断言 |
|---|---|---|
| 1 | `test_product_validator.py::BioProCorpusValidatorTest::test_bioprocorpus_lookup_returns_results_for_real_keyword` | `0 not greater than 0` |
| 2-5 | `test_pubchem_enhancer.py::ProtocolEnrichContentTest::test_search_with_content_returns_{equipment,reagents,steps}` + `test_search_without_content_does_not_return_extra_fields` | `0 not greater than 0` |

**根因（实测确认）**：本地 BioProCorpus 语料**未下载**。

- `apps/knowledge/services/protocol_recommender.py:19-22` 的 `BIOPROCORPUS_DIR`
  解析为 `backend/data/bioprocorpus`，该目录**存在但为空**（仅含 `.cache/` 子目录，
  0 个数据文件）
- ⇒ `get_shared_retriever()` 构建出 `0 entries` 的索引（早期日志实测：
  `BioProCorpus shared index ready: 0 entries`）
- ⇒ 两个测试类都断言"检索应返回非空"，实际返回空 ⇒ 失败

**分类**：属于**本地数据缺失导致的既有环境问题**，既非外网依赖（走本地索引，
`get_shared_retriever()` 不联网），也非真实代码缺陷，更与本次 runner 改造无关。

⚠️ 立项文档提到"除 1 条失败，该失败由另一位工程师修"—— **实测是 5 条**，
不是 1 条。这 5 条全部集中在 `apps/commerce`，请确认是否已知。

---

## 五、关于 `test_bioz_cache_roundtrip.py` 是否改名（待你确认，**未改**）

### 实测结论

- 文件内容：`class Command(BaseCommand)`，`help = "Diagnose Bioz cache persistence..."`，
  docstring 写明「诊断：本地 sqlite 能否持久化 Bioz缓存写」⇒ **确为诊断脚本，非测试**
- 全仓引用：除立项/取证文档外，**零引用**
- 静态扫描将它归类为「非测试（无 `test_` 定义）」，与真实性质一致

### 守卫能覆盖它吗？—— **不能**

守卫靠 `sys.argv[1] == 'test'` 触发，对这个文件无感知。它落在守卫的已知局限 1
（"两条命令都收集不到 ⇒ 守卫放行"）之内。**实测确认**：pytest 的收集清单里
（`_collect_pytest.txt`）不含此文件，两条命令都不收它 —— **这是正确行为，不是缺陷**。

### 建议改名，但有一个反对理由

**建议**：改名为 `diag_bioz_cache_roundtrip.py`。
理由：它的存在正是「靠命名约定发现测试」会误导人的实证—— 任何人扫 `test_*.py`
都会误判。改名成本极低（零引用），收益是消除这个持续的误导源。

**反对理由（请你权衡）**：改名会让它**不再被 pytest 尝试收集**。
目前 pytest 尝试收集它、收集到 0 个用例，属于"无害的噪音"。
一旦改名，它连"被尝试"都不会发生 —— 这当然是好事，但反过来说，
**当前状态下它对测试结果没有任何影响**，属于纯文档整洁性问题，优先级低。
且若将来有人想给它加真实测试用例，`diag_` 前缀反而会挡住 pytest 的 `test_*.py` 匹配。

⇒ 我的判断：**改名是对的，但不紧急**，且如果你希望保留"未来可转成真测试"的可能，
可以放到 `scripts/` 下而保留诊断语义。**等你确认后再动。**

---

## 六、结论：对立项判断的纠正

| 立项判断 | 评价 |
|---|---|
| 需要统一到 pytest | ✅ **成立**（pytest 能收全部 2438，unittest 只收 1984） |
| `manage.py test` 会假通过 | ✅ **成立**，但机制是"静默少跑 + exit 0"，**不是** `Ran 0 tests` |
| 需要加拦截守卫 | ✅ **成立**（0.42 s 开销可忽略） |
| 28 文件 / 284 用例 | ❌ **实测为 176 文件 / 2438 用例**；隐形部分为 34 文件 |
| 全量仅 1 条失败 | ❌ **实测 5 条失败**（同一根因：本地 BioProCorpus 语料为空） |
| 需要迁移大量调用点 | ⚠️ **不成立**：全仓仅 **1 处**真实调用点（`.claude/commands/django.md`），
且两个测试脚本**本来就已经是 pytest** |
| 无 CI 配置 | ✅ **确认成立** |