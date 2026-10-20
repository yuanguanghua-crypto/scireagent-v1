# docs/CURRENT/ — 当前有效文档索引

> **这里只放索引，不放文件本体。**
>
> 原因：下列活文档**被代码按路径引用**（形如 `docs/某个文档.md` 的路径出现在 `backend/apps/**/*.py` 的注释里），
> 一旦移动就会断链。所以它们留在 `docs/` 根目录，本文件负责**指路**。

## 判据（比"我觉得哪篇还准"可靠）

```bash
# 统计某篇文档被代码/核心文档引用多少次
grep -r "DATASOURCE_RELIABILITY.md" backend/ frontend/src/ scripts/ CLAUDE.md README.md | wc -l
```

**被引用的才是活文档。** 零引用的，默认当作已冻结（见 `docs/legacy/`）。

2026-10-19 实测（扫描 1016 个文件 / 740 万字符）：

| 引用数 | 文档 | 用途 |
|---|---|---|
| **18** | `docs/DATASOURCE_RELIABILITY.md` | 数据源可靠性与健壮性（缓存/容错/降级/三种数据放置策略） |
| **11** | `docs/COA_SDS_PRD.md` | COA/SDS 文档生成规格。★ **被用作测试判据**（`test_sds_download_gate.py` 引用其 `:80` 行） |
| **9** | `docs/FIVE_DATASOURCES.md` | 六数据源权威叙事（含 §8「历程与坑」—— 全仓最有价值的一种文档形态） |
| **4** | `docs/CLAIMS.md` | 结论登记表：相信什么 + 依据 + **失效条件** |
| **4** | `docs/DECISIONS.md` | 决策记录（ADR）：**只记"为什么"** |
| 2 | `docs/AI_AUTO_MATCH.md` | AUTO MATCH 接口契约（⚠️ jena/bioz 部分已被 `FIVE_DATASOURCES` 取代） |
| 2 | `docs/KNOWLEDGE_ROADMAP.md` | 知识图谱优化待办（P0/P1/P2） |
| 2 | `docs/jena_scraper_spec.md` | jena 爬虫产出物规格 |
| 2 | `docs/ROADMAP.md` | 产品路线图 |
| 1 | `docs/COA_SDS.md` | COA/SDS 工作流（`COA_SDS_PRD.md` 的简版） |
| 1 | `docs/KNOWLEDGE_ASSETS.md` | 知识图谱体系（⚠️ 缺 4 张桥接表 + 3 个 facet 类） |
| 1 | `docs/DESIGN_STANDARDS.md` | 设计规范 |

### 子系统文档（未被代码引用，但内容是新的）

| 路径 | 内容 |
|---|---|
| `docs/po-portal/`（8 篇） | PO 采购门户 + 库存台（2026-10-14/15）—— 覆盖当前最大子系统 |
| `docs/e2e/`（3 篇） | E2E 计划与流程教训（`INTERACTION_INVENTORY.md` 被 42 处引用） |
| `docs/ORPHAN_ENDPOINTS.md` | 后端端点 → 前端入口分诊表 |
| `docs/design/DESIGN_SYSTEM.md` | 设计系统 |

## 零引用的 30 篇（默认已冻结）

包括 `s6_test_playbook.md`、`product-protocol-relevance-*.md`、`月度工作汇报_202606.md` 等。
它们仍然留在 `docs/` 根目录（未搬移，避免一次性大改），但**默认不再维护**。
若你确认某篇其实还要用，请在被引用处引用它 —— 有了引用它就自动变成活文档。

## 生成物怎么保持新鲜（②）

`deliverables/capability_map.txt` 是 `capability_guard.py --map` 的**生成物**，
记录「后端端点 → 前端入口 → 是否有测试」的真实映射。

**问题**：生成物没人主动重跑 ⇒ 会长期停在"看起来有完整映射、实际与代码脱节"的状态。
这正是本文档要防的那类问题，只是发生在生成物上。

**解法：检测漂移，不自动重写。**

```bash
# 校验：已提交的映射表是否与当前代码一致
python scripts/capability_guard.py --verify-map

# 不一致时它会打印 unified diff、给出修复命令，并以退出码 1 失败
# 修复：
python scripts/capability_guard.py --map && git add deliverables/capability_map.txt
```

**已接入 pre-commit hook**（`scripts/hooks/pre-commit-capability-guard`）：
在**删除文件**的提交里会自动跑 `--verify-map`，过时就拦住提交。

⚠️ 为什么只在删文件时跑：`--verify-map` 要重建索引约 30s。
而最高风险场景恰好是"删了端点/文件但映射表没更新" —— 那个 hook 本来只在删文件时触发，
触达面正好对口。新增端点导致的过时风险较低，不值得拖慢所有提交。

⚠️ 为什么"检测"而不是"自动 --map"：自动重写会在 commit 中途静默改文件、
需要二次 add，且可能与人的手改冲突。检测则明确告诉人跑哪条命令。

⚠️ **那个 `[耗时]` 行是故意归一化掉的**：生成物末尾有
`[耗时] 索引构建 X.XXs｜总计 Y.YYs`，每次运行都不同。
不做归一化的话，**内容完全相同的两份也会被判"不一致"** ⇒ 检测永远假红。
（这条有 4 个单元测试钉着：`apps/core/tests/test_capability_guard.py` 的 `VerifyMapDiffTests`）

## 怎么验证「测试真的有效」（③）

**测试变绿不等于测试有效。** 一个永远通过的测试和没有测试一样。

```bash
python scripts/mutation_check.py            # 跑全部变异（约 1 分钟）
python scripts/mutation_check.py --list     # 看有哪些变异
python scripts/mutation_check.py --changed  # 只跑本次改动涉及的（hook 用的就是这个）
```

做法：对每个关键守卫注入一个**已知会破坏行为**的变异，跑它的测试，断言必须变红。

| 结果 | 含义 |
|---|---|
| 变红 | ✅ 测试真的在测这件事 |
| 仍绿 | ❌ 测试是摆设（退出码 1） |

当前覆盖 4 个守卫：IDOR 跨用户隔离、`--verify-map` 耗时归一化、URL 常量展开、`@action` 尾斜杠。

**已接进 pre-commit hook**：改动这些文件时会自动跑（平时零成本，成功静默、失败才出声）。

⚠️ 两个实现细节值得记住：
1. **还原时恢复 mtime** —— 否则 git stat 缓存失效，`git status` 显示 M 而 `git diff` 为空，会被误认为"脚本留了残留"（实测踩到）
2. **自检用 `git diff --quiet` 而不是 `git status`** —— 本仓库工作区是 CRLF、仓库内是 LF，`git status` 会误报

⚠️ 这个脚本自己也被验证过：把 `expect_failed_min` 调到 999（不可能达到），
它会返回 1 并报"无效测试" —— 证明它不是永远报 ✅ 的摆设。

## 一句话

- 想知道**现在怎么运行** → 读代码（`models.py` / `urls.py` / `vite.config.js`）
- 想知道**为什么这么做** → `docs/DECISIONS.md`
- 想知道**某结论还能不能信** → `docs/CLAIMS.md`
- 想知道**某个功能该不该有** → `docs/ORPHAN_ENDPOINTS.md`
- 想知道**历史怎么想的** → `docs/legacy/`（**别照着写代码**）
