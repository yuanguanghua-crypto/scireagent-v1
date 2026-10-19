# 后端端点 → 前端入口 分诊表

> **本文档解决什么**：后端有 138 个 URL，并非每个都该有前端入口。
> 本文记录**逐条判定**的结果与依据。

---

## ⚠️ 阅读前必看：一个我犯过并已纠正的错误

2026-10-19 我曾在此文档中断言「`capability_guard --map` 的 51 条是误判，真实约 25 条」。
**这个指控是错的，已撤销。** 记录经过，因为它本身就是一次有价值的教训：

| 我的主张 | 实际 |
|---|---|
| 「工具把 `/admin/orders/{X}/confirm/` 判成零入口，但前端明明有调用」 | ❌ **我错了**。`api/orders.js:74` 有 `export function confirmOrder`，但**全仓零引用**（`grep -rn confirmOrder frontend/src` 只命中定义处）⇒ 用户**无法触达**，工具判它是**真孤儿**，正确 |
| 「我的脚本算出 25 条才是真相」 | ❌ 我的脚本只看「URL 字面量是否出现」，把**写了但没人调用的 API 封装**误当成"有入口"，**低估**了孤儿 |

**两套口径的本质差异**：

| 口径 | 判定标准 | 结论 |
|---|---|---|
| 我用的（URL 字面量） | 前端代码里出现过这个 URL 字符串 | ❌ **太弱**：API 封装写了但无人调用也算"有入口" |
| **`capability_guard` 用的（符号级追踪）** | api 层 `export` → 被组件 `import` 且实际调用 | ✅ **更接近"用户能否触达"** |

反例佐证（工具判对的一侧）：`/invoices/{X}/pdf/` 被工具判为 **`[T] ← 2 入口`**，
因为 `downloadInvoicePdf`（`api/poPortal.js:83`）确实被 `PoDownloadCenter.vue:53` 与 `PoOrderDetail.vue:122` 调用。

⇒ ★ **结论：`capability_guard` 的符号级追踪可信，51 这个数字可用。不要用 URL 字面量自算。**

---

## 判定标准（四类）

| 分类 | 含义 | 处置 |
|---|---|---|
| **A 不该有 UI** | 机器接口、运维、危险操作。**有 UI 反而有害** | 保持无 UI，标注理由 |
| **B 有替代路径** | 功能已通过别的端点实现。**不是缺失** | 标注"由谁替代" |
| **C 真缺 UI** | 功能存在、用户需要、**无任何入口** | 排期补 |
| **D 待确认** | 需产品/人工判断 | 逐条确认后归类 |

---

## 分诊结果

### A 类：不该有 UI（6 项，保持现状）

| 端点 | 理由 |
|---|---|
| `GET/POST /pubchem-cache/`、`/pubchem-cache/{X}/` | 缓存运维，业务用户不应直接操作 |
| `POST /products/{X}/hard-delete` | **物理删除**，危险操作，故意不给 UI |
| `ANY /verified/{X}/` | 桥接校验，供内部/批量流程使用 |
| `GET /robots.txt`、`/sitemap.xml` | SEO 机器接口 |
| `GET /api/docs/`、`GET /api/schema/` | 开发者文档 |

### B 类：有替代路径（3 项，已核实，不是缺失）

| 端点 | 由谁替代（已核实） |
|---|---|
| `ANY /orders/{X}/allocate/` | PO 流程走 `InventoryService.allocate_for_order`（`po_views.py:209`）**自动分配**，无需独立 UI |
| `DELETE/GET/PATCH/PUT /coas/{X}/` | COA 用列表数据 + 子端点（`approve`/`withdraw`/`qc-results`/`download`），不需单独取详情 |
| `GET/POST /skus/`、`/skus/{X}/` | SKU 在 `ProductEditPage.vue` 内作为**嵌套数组**编辑，无需独立端点 |

### C 类：★ 真缺 UI

| 端点 | 现状 | 状态 |
|---|---|---|
| ★★ `GET/POST /wishlist/`、`DELETE/GET/PATCH/PUT /wishlist/{X}/` | 全域 0 前端命中；**且后端 serializer 原本不暴露 `products`**，前端即使做按钮也调不通 | **后端契约已补**（`7b7f50b`：`products` 只读嵌套 + `product_ids` 整体替换）；**前端待做** |
| `POST /admin/orders/{X}/confirm/` | `confirmOrder`（`api/orders.js:74`）**有定义、零调用** | 待确认：是废弃流程还是漏接按钮 |
| `POST /admin/invoices/{X}/verify-payment/` | `api/orders.js:109` 有定义，零引用 | 待确认 |

### D 类：待确认（需产品判断）

`sds-revisions/{X}`、`quote-requests/{X}`、`quotes/{X}`、`batches/{X}`、`documents`、`pdf-files`、`catalog-groups`、`product-classes/{X}`、`compatibility`、`products/{X}/faq`、`products/{X}/related`、`methods/{X}/products`

> ⚠️ D 类每一条都要先回答：**是不是已有替代路径**（参考 B 类的三个反例）。
> 不要因为"端点无调用"就判定"功能缺失" —— `/orders/{X}/allocate` 就是这样被误判的。

---

## ⚠️ 已知误判（工具看不到，必须人工修正）

### 第 3 类盲区：API 层「返回 URL 字符串」的函数

工具只把 `http.get(...)` / `fetch(...)` 这类调用识别为"端点入口"。
但有两处写法是**函数返回 URL 字符串**，再由 `window.open()` 使用：

```js
// frontend/src/api/documents.js:66-72
export function downloadSdsUrl(id) { return `/api/v1/sds-revisions/${id}/download/` }
export function downloadCoaUrl(id) { return `/api/v1/coas/${id}/download/` }

// 使用处（4 个）
ProductDetail.vue:404   window.open(documentsApi.downloadSdsUrl(...))
ProductDetail.vue:410   window.open(documentsApi.downloadCoaUrl(coa.id), '_blank')
ProductEditPage.vue:1386 / :1408  同上
```

⇒ **功能完全可用，但 `capability_map` 把它们标成 `⚠️` 零入口。**

**所以这两个端点的真实状态是「有入口」**：

| 端点 | 工具显示 | 真实 |
|---|---|---|
| `GET /api/v1/coas/{X}/download/` | ⚠️ 零入口 | **有入口**（2 处 window.open） |
| `GET /api/v1/sds-revisions/{X}/download/` | ⚠️ 零入口 | **有入口**（2 处 window.open） |

⇒ ★ **零入口的真实数字是 49 − 2 = 47**（2026-10-19 实测）。

**为什么不修工具**：
全仓只有这 2 个这种写法（`grep -rn "return \`/api/v1/" frontend/src/api/` 只命中它们）。
改符号提取逻辑（让"返回 URL 的函数"也算端点符号）会影响全部 140 个端点的判断，
风险大于收益 ⇒ 记录在案，人工扣减。

⚠️ 若将来这类写法变多（>5 处），再考虑修工具。

---

## 维护方式

1. **用 `capability_guard --map`，不要自算 URL 字面量**（差异见本文开头的教训）
2. 新增端点时确认归类并写进本表
3. 判定"真缺 UI"前，**先验证有无替代路径**
4. 判定"有 UI"时，确认是**组件真的调用**，而不只是 api 层写了封装
