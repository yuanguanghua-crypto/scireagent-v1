# 研究员工作台 E2E 全功能覆盖计划（COVERAGE PLAN）

> 目标：以"人类测试工程师全手动完整测试"为标准，用 Playwright 真实浏览器驱动，覆盖工作台**每一个按钮、每一个弹窗/状态、每一个字段的正/负/边界**，且不留下孤儿数据。
> 标准：所有用例确定性可复现（主理人独立复跑为交付依据，不采信 QA 自报）。
> 基础：本计划全部条目均来自对真实前端组件 + 后端端点的代码探查（非假设）。

---

## 0. 环境与登录

- 前端 `localhost:5173`、后端 `127.0.0.1:8000`（SQLite dev 库，`DB_ENGINE=sqlite`）须同时运行；Chromium 已装。
- 登录凭证：`admin / admin123`（不重置库）。
- 测试数据卫生：所有新建产品 catalog_no 带 `E2E_TEST_` 前缀；`finally` 中 `cleanupE2EProduct` 双兜底（UI 删 → 失败回退带 token `DELETE /api/v1/products/<id>/`），杜绝孤儿。
- 统一响应信封：`{ success, data, meta:{error:{code,message}} }`。

---

## 1. 外部依赖与 Mock 策略（已代码核实）

| 端点（UI 触发点） | 网络依赖 | 测试手法 |
|---|---|---|
| `POST /products/enrich/`（**AI AUTO MATCH 按钮**） | 出网 PubChem/ChEMBL/Bioz/PubMed（免费，无 key） | **Mock**（用户拍板：全 Mock）。构造 单命中 / 多候选 / 未命中 / 错误 四种返回 |
| `POST /products/<id>/generate-seo/`（**Auto-generate SEO 按钮**） | 纯本地模板 | **真跑**。注意：响应是 `ProductListSerializer`，**不含 seo 字段** → 点完后再 `GET /products/<id>/` 详情断言 |
| `POST /products/parse-word/`（**Word 导入**） | 纯本地（解析 .docx） | **真跑**（准备测试用 .docx） |
| `StructureViewer → POST /products/render-structure/` | 纯本地 RDKit | **真跑**。填合法 SMILES 出 SVG；填非法 SMILES 出 `.structure-error` |
| `POST /products/<id>/validate/` 等 | 出网 PubChem | **无 UI 按钮**（见 §5 缺口）→ 不经 UI 覆盖 |
| `recommend-protocols` / `recommend-literature` | 本地 / 出网 | **无独立 UI 按钮**（enrich 已内联返回）→ 不经 UI 覆盖 |

**Mock 关键响应结构（真实字段，照抄后端）：**
- enrich 成功（单命中）：`data.chemical.{found:true, cid, resolved_name, cas_resolved, properties:{molecular_formula, molecular_weight, canonical_smiles, inchi,...}, lipinski:{passed, violations, details}}`；`data.jena.{matched, normalized:{purity, storage_condition, shipping_condition, shelf_life, concentration, category_l1}}`；`data.bioz.{queried, equivalence, total, references:[{article_title, authors, journal, impact_factor, pmid, doi, pub_date, techniques}]}`；`data.literature.{applications, methods, references, matched_apps, matched_methods}`；`data.protocols:[{id, title, abstract, steps}]}`。
- enrich 多候选：`data.chemical.candidates:[{cid, iupac_name, molecular_formula, molecular_weight, cas}]`（非空）。
- enrich 未命中：`data.chemical.{found:false, search_hint:"...not found in PubChem or ChEMBL..."}`；`data.jena.{matched:false}`；`data.bioz.{queried:false}`。
- enrich 错误：`{success:false, data:null, meta:{error:{code:"error", message:"enrich failed"}}}`。

> Mock 用 `page.route('**/api/v1/products/enrich/', route => route.fulfill({json: {...}}))`，每个 AI 子用例前设置对应 fixture。

---

## 2. 完整功能点 × 测试流程

### 2.1 认证与导航（A 组）
- **A1 未登录访问 `/workspace`** → 重定向 `/login`（断言 URL 含 login）。
- **A2 登录字段校验**：用户名为空提交 → `.form-error` "Please enter your username"；密码为空同理。
- **A3 错误凭证**：`admin / wrong` → `.auth-error-banner` "Incorrect username or password..."。
- **A4 正确登录** → 落 Dashboard，`.stat-card` 首卡出现且数值匹配 `\d+`。
- **A5 侧边栏导航**：Overview / Products / Goals / Applications / Methods / Protocols / References / Back to Site 逐项点击可达（断言 URL 与各页标题）。

### 2.2 Dashboard（D 组）
- **D1** 4 张统计卡（Total Products / Active / Incomplete / CAS Coverage）数值渲染且为数字。
- **D2** Data Health 三项（CAS / SMILES / Knowledge Link）渲染 `with_cas / total` 与百分比。
- **D3** Knowledge Graph 四项（Goals / Applications / Methods / Protocols）计数渲染。
- **D4** Recently Updated 行点击 → 跳 `/workspace/products/<id>/edit`。
- **D5** Quick action `+ New Product` → 跳 `/workspace/products/new`。

### 2.3 Products 列表（P 组，最复杂）
- **P1** 列表加载 → `.products-table` 渲染真实行（≈109）。
- **P2** 错误态（route mock `**/api/v1/products/` 返 500）→ `.error` "Failed to load products"。
- **P3** 空态（过滤无结果）→ `p.empty-text` "No products match the current filters."。
- **P4** 排序：点 `Catalog No` 表头 → 首行 catalog_no 最小；再点 → 最大（▲/▼ 图标切换）。同样覆盖 Name/CAS/Status/Category 列。
- **P5** 状态筛选 `Active` → `.filter-count` 计数更新且均为 active。
- **P6** 完整度筛选 `No CAS` → 计数更新且行均无 CAS。
- **P7** 双筛选组合（状态×完整度）→ 计数与行一致。
- **P8** 行多选（勾选 2 行）→ 批量按钮（Batch Link / 批量下架 / 批量删除）出现。
- **P9** Batch Link 弹窗：选 Research Goal / Application 联动 → 选必填 Method → `Preview` → 断言 "Will link N products, skip M" → `Confirm` → 关联成功 toast。
- **P10** 下架确认（单条，行菜单"下架"）→ 弹窗显示产品名 → `确认下架` → 该行状态变 `archived`。
- **P11** 重新上架（archived 行菜单"重新上架"）→ 状态回 `active`（验证显隐逻辑：仅 archived 才显示"重新上架"）。
- **P12** 删除确认：未勾 `.confirm-check` → `永久删除` 按钮 disabled；勾选后 → 点击 → 行消失 + 库减少。
- **P13** 批量下架 / 批量删除（多选后弹窗，逻辑同 P10/P12）。
- **P14** 行菜单显隐：非 archived 显示"下架"不显示"重新上架"；archived 反之。
- **P15** 整行点击 → 跳编辑页。
- **P16** `+ New Product` → 跳 `/workspace/products/new`。

### 2.4 知识实体列表（E 组：Goals / Apps / Methods / Protocols / References）
每页覆盖：
- **E1** 加载态 `.loading` "Loading..." / 错误态 `.error` "Failed to load" / 空态 `No <x> yet.`（References 错误文案为 "Failed to load references"，唯一不同）。
- **E2** `+ New <X>` → 行内 modal 编辑器打开（标题 `New <X>`）。
- **E3** 必填填写（Name 必填；References 额外 URL/DOI/Source Type）→ `Save` → 列表出现新行。
- **E4** `Edit` → 改 Name → `Save` → 列表更新。
- **E5** `Save` 防重：保存中按钮 disabled 且文字 `Saving...`。
- **E6** `Cancel` 关闭 modal 不落库。
- **E7** Status 标签渲染（active/draft 配色）。

### 2.5 ProductEdit（PE 组，核心：字段 + 按钮 + 弹窗 + 状态）

**字段与校验：**
- **PE1** 必填不阻断：清空 name / catalog_no / cas / smiles / category / 无 default SKU → 点 Save Draft 仍可保存（标红 + warn toast），验证"研究员最终决定权"。
- **PE2** 必填标红 + `span.field-error` "⚠ 必填字段未填写"（name/catalog_no/smiles/category/default_sku）。
- **PE3** CAS 格式错（如 `123-45-6`）→ `field-error` "Invalid CAS format (e.g. 1927-31-7)"。
- **PE4** SMILES 含 `<` → `field-error` "SMILES contains invalid characters"。
- **PE5** Formula 含 `@` → `field-error` "Formula contains invalid characters"。
- **PE6** Molecular Weight 输 `-1` → `field-error` "Molecular weight must be a positive number"。
- **PE7** 正确填写全部必填 + 若干可选（synonyms / formula / molecular_weight / purity / storage / overview / seo 两字段手动）→ Save Draft → 跳编辑页；`GET /products/<id>/` 详情**逐字段断言持久化**（name/cas/smiles/category/sku/formula/mw/overview 等）。
- **PE8** "这次少填"：仅填必填（不填 formula/mw/purity 等）→ 保存成功，详情中这些字段为空。
- **PE9** "下次多填"：在 PE8 产品上补填 purity/storage/shipping/shelf_life/synonyms/overview → 再 Save → 详情断言更新（覆盖"少→多"增量场景）。
- **PE10** SKU 重复：两行相同 pack_size+concentration → 行加 `.sku-duplicate` + `.sku-warning` "⚠ Duplicate pack size..."。
- **PE11** SKU 默认单选互斥（选第 2 行为 default → 第 1 行取消）。
- **PE12** Category 级联选择器选择 → 必填标红消除。
- **PE13** Status select 切换 Draft/Active/Deprecated/Archived。

**保存 vs 发布：**
- **PE14** Save Draft（新建态）→ `router.replace('/workspace/products/<id>/edit')`；编辑态 → PUT 成功。
- **PE15** Publish 弹窗（字段完整）→ `div.dialog-warn` 不渲染；点 `Confirm Publish` → 状态变 `active`。
- **PE16** Publish 弹窗（不完整）→ `div.dialog-warn` 列出缺失项 + `div.dialog-suggest` 列出建议改进；**仍点 Confirm Publish** → 发布成功 + 顶部 `.incomplete-banner` 出现。
- **PE17** Publish `Cancel` → 弹窗关闭，未发布。

**Word 导入：**
- **PE18** 上传合法 .docx → `.word-status.word-ok` "✓ N fields extracted" + 表单字段被预填。
- **PE19** 上传非法/损坏文件 → `.word-status.word-err` 报错，不预填。

**AI AUTO MATCH（mock enrich）：**
- **PE20** 单命中 fixture → 预览表渲染（Resolved Name/CID/CAS/SMILES/Formula/MW）+ Lipinski 区；点 `Apply All to Form` → 字段填入 + `.word-status.word-ok` "✓ All results applied to form"。
- **PE21** 多候选 fixture → `.word-warn` "⚠ Multiple candidates (n)" + `.candidate-item` 列表。
- **PE22** 未命中 fixture → `.word-warn` "✗ Not found in PubChem or ChEMBL"。
- **PE23** 错误 fixture → `.word-err` 显示错误文案。
- **PE24** Jena 命中 → `仅填空字段 Apply` 按钮 → 仅填入空字段（不覆盖已填），断言 purity/storage 等被补。
- **PE25** Bioz 命中（编辑态）→ 单篇 `Adopt` 落库标记 `✓ 已落库`；`Adopt all (n)` 批量落库。
- **PE26** Bioz `canAdopt` 守卫：新建态（!isEdit）→ Adopt 按钮 disabled + `.bioz-nosave-hint` "先保存产品后再 Adopt 文献"。
- **PE27** CAS 冲突：`casConflict` → 表单 CAS 与 enrich CAS 不一致时 `.cas-conflict` 横幅出现。

**SEO 自动生成：**
- **PE28** 新建态点 `Auto-generate SEO` → disabled + 提示 "Save product first to enable SEO auto-gen"。
- **PE29** 编辑态点 `Auto-generate SEO` → 生成 → `GET /products/<id>/` 详情断言 `seo_title` 以 `" | SciReAgent"` 结尾、`seo_description` 含 `"Buy <name>"` 与 `"High purity research reagent"`。

**知识关联：**
- **PE30** Link existing Method（下拉选 + `Link`）→ chip 出现 + `a.chip-link` 跳转。
- **PE31** `+ New Method` 行内弹窗 → 填 Name → `Save & Link` → chip 出现 + loadKnowledge 刷新。
- **PE32** Link existing Protocol / `+ New Protocol` 同理。
- **PE33** Knowledge Chain `km-link-btn` 关联 Method。
- **PE34** Protocol 卡 `🔽 Import to Knowledge Base` → 导入成功 toast + method chip 增加。

**结构预览：**
- **PE35** 填合法 SMILES → `StructureViewer` 调 render-structure → `.structure-svg` 渲染；填非法 SMILES → `.structure-error`。

---

## 3. 测试用例总表（约 60 条）

| 组 | 用例数 | 覆盖 |
|---|---|---|
| A 认证/导航 | 5 | 重定向/字段校验/401/登录/Dashboard 落位/侧栏 |
| D Dashboard | 5 | 4 卡/Data Health/Knowledge Graph/Recent/Quick action |
| P Products 列表 | 16 | 加载/错误/空/排序/双筛选/多选/批量/下架/重新上架/删除门禁/显隐/整行/新建 |
| E 实体列表×5 | 35（每页 7） | 加载/错误/空/新建/编辑/防重/Cancel/Status |
| PE ProductEdit | 35 | 字段校验×6/持久化×3(SHU少→多)/SKU×2/category/status/保存/发布×3/Word×2/AI×8/SEO×2/知识关联×5/结构×1 |

> 合计约 **111 个断言点 / ~56 个 test 用例**（部分用例内含多断言）。

---

## 4. 已知缺口 / 需你确认

1. **KnowledgeIntake.vue 孤儿页**：组件存在但**未注册路由、无 URL 入口** → 无法经 UI 覆盖。是否补 `/workspace/knowledge-intake` 路由？（属开发任务，超出 E2E 范围）
2. **KetcherEditor.vue 未接入**：画结构式编辑器从没被引用，ProductEdit 仅用只读 `StructureViewer` → "手绘结构式"能力未真正可用。
3. **Apps/Methods/Protocols 编辑器缺 FK 下拉**：`form` 含 `research_goal_id`/`application_id`/`method_id`，但 UI 未渲染这些关联下拉 → 无法经 UI 测试实体间关联选择（疑似缺陷，建议回归开发确认）。
4. **独立 AI 端点无 UI 按钮**：`/validate/`、`/recommend-protocols/`、`/recommend-literature/` 在 workspace 无触发按钮（enrich 已内联返回 literature/protocols）。UI 层 AI 覆盖 = enrich + SEO + Word + render-structure。若要单独覆盖这三者，需先加 UI 按钮。

---

## 5. 实现与复跑

- 在现有 `src_claude/e2e/` 基础上扩展：`tests/workspace-e2e.spec.js`（既有 9 条保留）+ 新增 `tests/product-edit-e2e.spec.js`、`tests/products-list-e2e.spec.js`、`tests/entity-list-e2e.spec.js`，helpers.js 增加 `mockEnrich(page, fixture)` / `uploadWord(page, file)` / `getProductDetail(page, id, token)` 等。
- 复跑：`cd src_claude/e2e && npx playwright test`（前后端 + Chromium 就绪）。
- 交付判定：主理人独立复跑 **全部 passed、库干净（PRODUCT_TOTAL 回到基线、E2E_RESIDUE 为空）** 方算完成。

---

*本计划全部条目均来自对 `ProductEditPage.vue`(1601 行)、6 个列表页、router、LoginPage、DashboardPage、以及后端 `ai_views.py`/`seo_generator.py`/`rdkit_renderer.py`/`protocol_recommender.py`/`literature_recommender.py` 的真实代码探查。*
