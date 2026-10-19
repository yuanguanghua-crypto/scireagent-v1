# 后端端点 → 前端入口 分诊表

> **本文档解决什么**：后端有 138 个 URL，并非每个都该有前端入口。
> 但"该不该有"不能靠工具自动判定 —— 本文记录**逐条人工判定**的结果与依据。

---

## ⚠️ 先看这里：为什么不能直接用工具的数字

`scripts/capability_guard.py --map` 会输出「零前端入口 N 条」。**这个数字不能用**，实测有误判：

| 口径 | 数量 | 问题 |
|---|---|---|
| `capability_guard --map` | **51** | 把 `/admin/orders/{X}/confirm/`、`/admin/invoices/{X}/verify-payment/` 等**前端明明有调用**的端点数成零入口 |
| 修正多行匹配 + 前缀归一化后 | **25** | 目前最可信 |

**误判的三个来源**（复现方式都写在这里，便于下次改工具）：

1. **多行链式调用漏抓**
   ```js
   return http
     .get(`/invoices/${invoiceId}/pdf/`, { responseType: 'blob' })   // ← 换行分开，正则抓不到
   ```
2. **URL 前缀未归一化** —— 后端是 `/api/v1/admin/...`，前端写 `/admin/...`，直接比对必然不匹配
3. **`window.open` / `<a href>` / 动态拼接** —— 不是 `http.get` 形式

⇒ ★ **结论：这个清单只能当"候选集"，每条都要人工确认。**

---

## 判定标准（四类）

| 分类 | 含义 | 处置 |
|---|---|---|
| **A 不该有 UI** | 机器接口、运维、危险操作。**有 UI 反而有害** | 保持无 UI，在本文标注理由 |
| **B 有替代路径** | 功能已通过别的端点实现。**不是缺失** | 保持无 UI，标注"由谁替代" |
| **C 真缺 UI** | 功能存在、用户需要、**无任何入口** | 排期补 |
| **D 待确认** | 静态分析无法判断，需人工/产品确认 | 逐条确认后归入 A/B/C |

---

## 分诊结果（2026-10-19）

### A 类：不该有 UI（保持现状）

| 端点 | 理由 |
|---|---|
| `GET/POST /pubchem-cache/`、`/pubchem-cache/{X}/` | 缓存运维，业务用户不应直接操作 |
| `POST /products/{X}/hard-delete` | **物理删除**，危险操作，故意不给 UI（软删走正常流程） |
| `ANY /verified/{X}/` | 桥接校验，供内部/批量流程使用 |
| `GET /robots.txt`、`/sitemap.xml` | SEO 机器接口 |
| `GET /api/docs/`、`/api/schema/` | 开发者文档 |

### B 类：有替代路径，不是缺失（保持现状）

| 端点 | 由谁替代（已核实） |
|---|---|
| `ANY /orders/{X}/allocate/` | PO 流程走 `InventoryService.allocate_for_order`（`po_views.py:209`）**自动分配**，不需要独立 UI。该端点疑为遗留/备用 |
| `DELETE/GET/PATCH/PUT /coas/{X}/` | COA 用列表数据 + 子端点（`approve` / `withdraw` / `qc-results` / `download`），不需要单独取详情 |
| `GET/POST /skus/`、`/skus/{X}/` | SKU 在 `ProductEditPage.vue` 内作为**嵌套数组**编辑，无需独立端点 |

### C 类：★ 真缺 UI（建议排期）

| 端点 | 现状 | 影响面 |
|---|---|---|
| ★★ `GET/POST /wishlist/`、`DELETE/GET/PATCH/PUT /wishlist/{X}/` | **全域 0 前端命中**（`grep -r wishlist frontend/src` = 0），后端 CRUD 完整 | ★ **用户完全无法使用收藏功能**。这是最确定的一条 |

### D 类：待确认（需产品/人工判断）

| 端点 | 疑问 |
|---|---|
| `DELETE/GET/PATCH/PUT /sds-revisions/{X}/` | SDS 修订详情/审核是否有台面？目前只有 `download` 被调用 |
| `ANY /quote-requests/{X}/` | 匿名询价的**详情页**是否有？列表已有 |
| `DELETE/GET/PATCH/PUT /quotes/{X}/` | 报价详情 |
| `DELETE/GET/PATCH/PUT /batches/{X}/` | 批次详情 |
| `GET/POST /documents/`、`/documents/{X}/` | 产品文档列表（`/documents/{X}/` 有调用，列表无） |
| `GET/POST /pdf-files/`、`/pdf-files/{X}/` | PDF 文件管理 |
| `GET/POST /catalog-groups/`、`/catalog-groups/{X}/` | 目录分组 |
| `GET/PUT /product-classes/{X}/` | 产品分类详情 |
| `GET/POST /compatibility/`、`/compatibility/{X}/` | 兼容性管理 |
| `ANY /products/{X}/faq/` | 产品 FAQ |
| `ANY /products/{X}/related/` | 相关产品推荐 |
| `ANY /methods/{X}/products/` | 某方法下的产品列表 |

---

## 维护方式

1. **不要相信自动统计的数字**，它只能缩小候选范围
2. 新增端点时，确认它属于哪一类，写进本表
3. **判定"真缺 UI"前必须先验证"有无替代路径"** —— `/orders/{X}/allocate` 就是典型反例：
   看着像漏了 PO 关键步骤，实际由 `allocate_for_order` 在别处自动完成
4. 若工具修复了上述三个误判来源，可重跑并与本表对账 —— **以本表为准**
