# 测试执行卡

> **1 页。执行只看这张。**
> 为什么这么做的依据 → `docs/TEST_STRATEGY.md`（参考手册，遇到具体问题再查）
> 更新：2026-10-20 ｜ 与 STRATEGY V1.2 配套
>
> ⚠️ **本卡命令里的路径是本机专用**（`/e/Users/yuankaifeng/...`）。他人使用请把这段替换成自己的 `<repo>` 路径。

---

## 0. 一句话

**不是"测得多"，是"测对地方" + "每条测试都能红"。**

判断任何一条测试有没有用，只问一句：**这段代码明天坏了，它会红吗？**

---

## 1. 这周做这两件（S1 / S2，当天可见效）

> ⚠️ **这两件是待办，不是"照这张卡就能做完"** —— 卡里只给验收标准；
> 具体操作要单独动手（S1 改 `ci.yml`、S2 写两份文档），完成后回来对验收。

| # | 做什么 | 怎么验做完 |
|---|---|---|
| **S1** | 把 `test:e2e:readonly` 接进 CI（**操作**：`ci.yml` 加一个 job → 装依赖 → `npx playwright install chromium` → `npm run test:e2e:readonly`） | CI 多一个 job，push 后能看到它跑 |
| **S2** | `CLAUDE.md` 加「可运行检查命令」段 + 新建 `REVIEW.md`（**怎么写**见 STRATEGY §8.8） | AI 接手任务时知道该跑什么；review 时有"什么叫失败"的定义 |

> 依据：STRATEGY §9.2 路线图。这两条零重构、零风险，且立刻提升"每次改动都有人看"的密度。

---

## 2. 每次提交前（照抄，5 条命令）

```bash
# 1) 后端（改了哪个 app 先跑哪个，快）
cd backend && venv/Scripts/python.exe -m pytest apps/<app>/tests/ -q

# 2) 后端全量（最终）
venv/Scripts/python.exe -m pytest -q
#    ⚠️ 汇总行可能消失，用这个判读：
python scripts/test_result_summary.py <输出文件>

# 3) 前端构建（★ 必须 E: 物理路径，C: 会报 vite:build-html 错）
cd /e/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/frontend
npx vite build --outDir .build_check && rm -rf .build_check
#   ↑ 只验证「能构建成功」，产物不留（真正的产物由部署脚本在生产构建）

# 4) E2E（只在你改了页面时）
#    ⚠️ 前置：test:e2e:local 需要「后端 localhost:8000 + 前端 Vite localhost:5173」都在跑
#        （否则连不上，见 e2e/GATE.md）。test:e2e:readonly 若跑生产则需口令（见 §3 说明）
npm run test:e2e:local        # 或 test:e2e:readonly

# 5) 判测试是否变摆设（只在你改了核心逻辑时）
python scripts/mutation_check.py
```

### 提交前问自己三句（30 秒）

1. 我改的属于哪一层？（L1 逻辑 / L2 API / L3 数据 / L4 并发 / L5 契约 / L6 页面）
2. 对应层的用例**加了吗**？
3. 答不上"**如果它坏了，哪条测试会红**" ⇒ **测试还没写**。

---

## 3. 每次发布前（6 项门禁，任一不过不许发）

| # | 检查 | 命令 |
|---|---|---|
| 1 | 后端全量绿 | `pytest -q`，判读标准 **0 failed**（通过数会随用例增减，不写死） |
| 2 | CI 全绿 | GitHub Actions |
| 3 | 前端构建成功 | 从 **E: 物理路径** 构建 |
| 4 | **四地一致 + 产物 commit 正确** | `python scripts/check_deploy_consistency.py` |
| 5 | 匿名写探针 401/403 | 带 Basic Auth **穿透 nginx** |
| 6 | 关键路径 E2E | `npm run test:e2e:prod` |

### 部署时绝对不要做（今天踩过）

```
❌ mv dist dist_prev && mv new dist      → 换 inode，容器看不到，部署假成功
❌ 读宿主机 dist 判断是否上线            → 假绿，要读容器内 /usr/share/nginx/html
❌ 手工 chmod 已入库的文件               → mode 进 git，merge 冲突
❌ 手工 scp 未入库的文件到生产           → untracked 挡住后续 merge
✅ 一律用 scripts/deploy_frontend.sh    → 内含 inode 校验 + 容器内 md5 校验
```

---

## 4. 修 bug 时（3 步，别只修完就算）

1. **先写一条能复现的测试**（红）
2. 修到它变绿
3. **留着这条测试**（bug 变成回归用例）—— 不删，不进 skip

> 没有第 3 步，同一个 bug 会在半年后再来一次。

---

## 5. 写 E2E 时的七条铁律（浓缩版）

| # | 铁律 |
|---|---|
| 1 | **像用户一样操作** —— 从菜单点进去，不用 `goto()` 直达 |
| 2 | **不绕过页面打接口** —— 被测路径必走 UI，只有前置数据能走 API |
| 3 | **不用 JS 塞值** —— 用 `fill()`，让验证器跑一遍 |
| 4 | **"成功"提示不算通过** —— 列表要刷新、DB 要查到 |
| 5 | **验效果，不看返回值** —— `click()` 不报错 ≠ 点到了（节点可能已被换掉） |
| 6 | **测试数据打标** `TEST-YYYYMMDD-NNN` |
| 7 | **不赌登录态** —— 每条用例前探会话，多页签守先后 |

### 定位器与等待（两条最容易犯的）

```
✅ getByRole('button', { name: '加入购物车' })     ← 用户视角
❌ div.list > div:nth-child(1) > button          ← 一改版全灭

✅ expect(locator).toBeVisible()                  ← Web-first 自动重试
❌ waitForTimeout(3000)                           ← 赌运气
```

---

## 6. 遇到问题查哪

| 你现在的问题 | 翻哪 |
|---|---|
| 这个模块该测多深？ | STRATEGY §2.1 风险四问 + 附录 A |
| 测到多少算够？ | STRATEGY §2.5 量化线 |
| 这一层具体怎么写？ | STRATEGY §3（L1–L7 逐层规范） |
| 页面/按钮怎么点才"像人"？ | STRATEGY §4.3–§4.9 |
| 改了东西该测什么？ | STRATEGY §2.3（含"真能拦吗"一列） |
| 流程怎么串（计划→用例→执行→报告）？ | STRATEGY §8 |
| flaky / mock / Schema 怎么定？ | STRATEGY §8.9 三张速查 |
| 命令忘了 | 本卡 §2 + STRATEGY 附录 D |

---

## 7. 现在**还做不到**的事（别为难自己）

| 做不到 | 为什么 | 什么时候能 |
|---|---|---|
| 并发测试（超卖/重复提交） | 测试跑 sqlite，`select_for_update` 是 no-op | PG 环境建成后（S3） |
| 新增模型自动拦截"没写测试" | pre-commit 不检查这个（只查删除和变异） | 暂无计划，靠 review 勾选 |
| AI 自动生成用例 | 没有测试计划层和知识库，生成的是通用货 | S1/S2 之后再谈 |
| AI 审查代码 | 没有 REVIEW.md，AI 不知道"什么叫失败" | S2 完成后可试 |

⚠️ **把"还做不到"写清楚，是为了不让它变成"假装做到了"。**
