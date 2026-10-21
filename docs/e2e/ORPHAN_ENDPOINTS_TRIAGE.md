# 孤儿端点分诊台账（2026-10-21）

> 数据来源：`scripts/capability_guard.py --map` → `deliverables/capability_map.txt`
> 生成口径：后端存活端点中，**没有任何 frontend/src 调用方**的 URL。

## 0. ⚠️ 先看这一节：这个数字不等于"可以删"

`--map` 报 **49 条**零前端入口。但**独立复核发现其中 5 条是误报**——
前端明确调过，guard 没识别出来：

| 被误报的 URL | 前端实际调用位置（可直接核对） |
|---|---|
| `/api/v1/search` | `frontend/src/api/search.js:4` → `http.get('/search', {params})` |
| `/api/v1/search/suggest` | `frontend/src/api/search.js:8` |
| `/api/v1/convergence-classes` | `frontend/src/api/convergence.js:10` |
| `/api/v1/inventory/movements` | `frontend/src/api/inventory.js:29` |
| `/api/v1/products/enrich-from-pubchem` | `frontend/src/api/aiTools.js:30` |

**复核方法**（不依赖 guard，自己数一遍）：
```python
import re, pathlib
pat = re.compile(r"""https?\.(?:get|post|put|patch|delete)\(\s*[`'"]([^`'"]+)[`'""]""")
def norm(s): return '/' + s.strip().strip('/')
found = set()
for f in pathlib.Path('frontend/src').rglob('*'):
    if f.suffix in ('.js', '.vue'):
        for m in pat.finditer(f.read_text(encoding='utf-8', errors='ignore')):
            raw = m.group(1).split('?')[0]
            if '${' in raw:      # ★ 模板拼接（'/documents/${id}'）不能当列表端点
                continue
            found.add(norm(raw))
```

> ⚠️ **这段复核脚本自己也踩过一次坑**：第一版对模板字符串只做 `.split('${')[0]`，
> 于是 `http.delete('/documents/${docId}')` 被截成 `/documents`，害我一度把
> `/api/v1/documents`（列表，确实没前端调用）误判成"guard 误报"。
> 所以误报数从 6 修正为 **5**。**验证工具本身也要验证** —— 这是同一个教训连着踩两次。

### 为什么这件事很严重
`capability_guard` 是**删文件闸门**。它的误报方向是"把还在用的能力说成零引用"
⇒ 会直接导致误删。这个方向比漏报危险得多。

### 待办（本轮未做）
- [ ] 定位 guard 的提取漏检原因（猜：`FETCH_CALL` 对"URL 字面量后跟 `, {参数}`"或
      "同一文件多个导出函数"的处理不完整）
- [ ] 修完补自测：这 6 条必须能被识别为"有入口"
- [ ] **在此之前，任何"零引用"结论都要用上面的独立方法复核过**

---

## 1. 修正后的真实孤儿：约 44 条

按处置方式分四类。**A 类是合理设计（不需要 UI）**，B/C/D 需要判断。

### A. 设计如此，本来就不该有前端入口（10 条）

| URL | 说明 |
|---|---|
| `/api/v1/` | DRF 的 `APIRootView`，自动生成 |
| `/api/v1/admin/` | Django admin 前缀 |
| `/api/v1/api/docs/`、`/api/v1/api/schema/` | OpenAPI 文档（路径前缀重复是另一个小瑕疵） |
| `/api/v1/robots.txt`、`/api/v1/sitemap.xml` | 给爬虫的；根路径 `robots.txt`/`sitemap.xml` 才是对外入口 |
| `/api/v1/products/{id}/json-ld/` | 结构化数据，给搜索引擎 |
| `/api/v1/methods/{id}/json-ld/` | 同上 |
| `/api/v1/protocols/{id}/json-ld/` | 同上 |

**处置建议**：在 guard 里加白名单（`EXPECTED_NO_UI`），不算孤儿。**本轮未做** —— 改 guard 的判定逻辑要连带改它的 15 个自测，风险大于本轮收益。

### B. 后台 CRUD，由 Django admin 承担（约 18 条）

`catalog-groups`、`product-classes`、`skus`、`batches`、`documents`、`pdf-files`、
`pubchem-cache`、`compatibility`、`coas`、`sds-revisions`、`convergence-classes`、
`inventory/{id}`、`quotes/{id}`、`verified/{id}`、`quote-requests/{id}` 等
（含各自的 `{id}` 详情路由）。

**判断**：这些是标准 ModelViewSet，Django admin 里已能管。前端工作台只暴露了其中一部分。
**处置**：**不补 UI**，但要在文档里写明"这些靠 Django admin 维护"。

### C. ⚠️ 真漏 UI 的高概率项（约 9 条）—— 需要产品判断

| URL | 为什么可疑 |
|---|---|
| `/api/v1/admin/dashboard/` | 运维台首页，没入口很奇怪 |
| `/api/v1/admin/orders/{id}/confirm/` | 订单确认（审批流起点） |
| `/api/v1/admin/orders/{id}/invoice/` | 管理端开票 |
| `/api/v1/admin/invoices/{id}/verify-payment/` | 收款核销 |
| `/api/v1/admin/knowledge-import/` | 知识导入 |
| `/api/v1/orders/{id}/allocate/` | 备货台锁库存 |
| `/api/v1/coas/{id}/download/` | COA 下载（合规必需！） |
| `/api/v1/sds-revisions/{id}/download/` | SDS 下载（合规必需！） |
| `/api/v1/products/{id}/hard-delete/`、`/restore/` | 回收站彻底删除/恢复 |

**这 9 条不是我能单方面决定的**——补 UI 是产品范围，标废弃可能是错的
（比如 COA/SDS 下载是法规要求的能力）。**处置：列出清单交产品评审，本轮不动代码。**

### D. 需要逐条确认（约 6 条）

`products/{id}/faq/`、`products/{id}/related/`、`products/{id}/documents/`、
`methods/{id}/products/`、`inventory/movements/`、`products/enrich-from-pubchem/`

**判断**：这些看起来"前端应该有"，但可能通过别的路径（如详情页内嵌聚合接口）间接使用。
**处置**：逐条查证后再定，不在本轮做。

---

## 2. 结论

| 分类 | 条数 | 处置 |
|---|---|---|
| 误报（前端其实在用） | **5** | 修 guard；修好前"零引用"结论必须独立复核 |
| A 设计如此 | 10 | 建议加白名单（本轮未做，避免动 1398 行的 guard） |
| B 后台 CRUD | ~18 | 不补 UI，文档标注 |
| C 疑似真漏 UI | ~9 | **交产品评审**，本轮不动 |
| D 待确认 | ~6 | 逐条查证 |

**本轮只做了一件事：把这个数字从"49 条待处理"变成"5 错报 + 10 合理 + 18 后台 + 9 待评审 + 6 待查"。**
没有删任何代码，也没有补任何 UI —— 因为在 guard 的误报修好之前，
"这条没入口"本身不是一个可以据以动手的结论。
