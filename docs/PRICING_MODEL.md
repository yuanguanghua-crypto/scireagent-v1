# 定价口径（PRICING MODEL）

> 最后更新：**2026-10-29**（阶梯价上线）。文中数字与代码位置均为当日实测。

---

## 1. 一句话

**单价只有一个出口：`apps/commerce/services/pricing.resolve_unit_price()`。**
任何地方都不要再直接读 `sku.price` —— 否则会出现「前端显示 $90、实际扣 $100」，
而且两边都不报错，只在客户对账时爆出来。

优先级（2026-10-29 产品确认）：

```
报价单价  >  阶梯价（按数量）  >  SKU 目录价
```

---

## 2. 为什么是「价目表」而不是 django-oscar 那种规则引擎

我读了 oscar 的 `offer/abstract_models.py` 源码，结论是**它自己也做不了阶梯价**：

- `AbstractBenefit.value` 是**单一 Decimal**（`max_digits=12`），一个 Benefit 只能表达一个值；
- `MULTIBUY` 的语义是「买 3 送 1」（最便宜一件免费），**不是**分段单价；
- `FIXED_PRICE` 是「满足条件享某个固定价」，也是单一价；
- 要做 1/5/10 分档单价，必须**自定义 Benefit 代理类**（自己写 `apply()`）。

而试剂行业（阿拉丁、Medchemexpress）实际做法就是一张分段价目表。
用 Range + Condition + Benefit + Offer 四张表 + 优先级互斥去表达三档价，是过度设计。

⇒ **建一张 `SkuPriceTier` 表，取价函数按数量查表。**

### 顺便验证到的一件事

oscar 的库存三动作和我们**完全等价**，说明 2026-10-28 做的锁库语义是行业标准，不是野路子：

| oscar `StockRecord` | 我们 |
|---|---|
| `allocate()`：`num_allocated += q` | `Inventory.allocate`：`available -= q, allocated += q` |
| `consume_allocation()`（发货）：`allocated -= q, num_in_stock -= q` | `release()`：`allocated -= q` |
| `cancel_allocation()`（取消）：`allocated -= q` | `release_reservation()`：`available += q, allocated -= q` |

---

## 3. 模型

```python
SkuPriceTier(sku, min_qty, unit_price)
  unique_together (sku, min_qty)
  CheckConstraint min_qty >= 1
  CheckConstraint unit_price >= 0
```

**取价语义**：
- 按**单个 SKU 的购买数量**匹配（**不是**订单内所有产品合计）；
- 取 `min_qty <= 数量` 中**最大**的那一档；
- 一档都不命中 ⇒ 回落 `SKU.price`。

**为什么必须保留 `SKU.price`**：它是「1 件基准价」和兜底价。删了它，
所有还没配阶梯价的 SKU 就没价格了，整站无法下单。

### 默认档位

新 SKU 不自动建档位（表为空 ⇒ 行为与改造前**逐字节一致**，这是上线当天不改价的前提）。
运营配置时通常从 **10 件**起一档，档位数量与门槛都**可调**，不写死。

---

## 4. 六处取价点（已全部收敛）

| 位置 | 作用 |
|---|---|
| `transactions/api/v1/basket_serializers.py` | 购物车行单价 + 小计（随本行数量变） |
| `transactions/api/v1/checkout_views.py:76` 附近 | 结账 subtotal |
| `transactions/api/v1/checkout_views.py:133` 附近 | `OrderItem.unit_price` 落库（**必须与上一处同值**） |
| `transactions/services.py:141` | PO 提交时的单价覆盖（服务端强制，不信客户端） |
| `commerce/api/v1/serializers.py` `get_sku_summary` | 产品列表价格区间（min 已含最低档） |
| `knowledge/api/v1/site_views.py:266` | 首页「起价」 |

**N+1 防护**：批量场景用 `build_tier_map(skus)` 一次查库；`ProductViewSet` 的 queryset
已 `prefetch_related('skus__price_tiers')`。

---

## 5. 不影响历史订单（这是在线改价的前提）

`OrderItem.unit_price` 是**下单那一刻的快照**，`subtotal = unit_price × quantity`。
改阶梯价、改目录价都**不会**让已有订单金额变化。

测试固定了这一条：`test_price_tiers.py::OrderSnapshotTest`。

---

## 6. 运营怎么维护

**方式一（推荐，整表替换，不会留中间态）**
```
PUT /api/v1/skus/<id>/price-tiers/
body: {"tiers": [{"min_qty": 1, "unit_price": "100.00"},
                 {"min_qty": 5, "unit_price": "90.00"},
                 {"min_qty": 10, "unit_price": "80.00"}]}
空数组 = 清空（该 SKU 回到单一目录价）
```
权限 `IsAdmin`；每次写入都会写 `AuditLog`（`snapshot.scope='price_tiers'`，
含 before/after）—— 价格是敏感数据，不留痕就查不出「谁把价改成 1 元」。

两条硬校验：
- `min_qty` 不能重复；
- 按 `min_qty` 升序后 `unit_price` 必须**递减或持平**（买得多反而更贵一定是录错了）。

**方式二（临时）**：Django admin → SKU 阶梯价（支持按 `sku_code` 搜、按产品筛）。
⚠️ 在 admin 里逐条增删可能留下「只有 10+ 档、没有 1-4 档」的中间态，那会让
1 件时回落目录价。要改整组请用方式一。

---

## 7. 已知限制（未做，别当已实现）

| 限制 | 影响 |
|---|---|
| **报价单没有逐行报价** | `QuoteRequest` 只有整单 `quoted_total`，`QuoteRequestItem` **无 `quoted_unit_price`**。所以「报价单价优先」这一层**只能传参、还不能自动取**。`resolve_unit_price(..., quote_unit_price=...)` 形参已留好。**后果**：报价单转订单时，行单价仍按阶梯价/目录价重算，报价金额不会逐行落到订单上（总额也可能对不上）。 |
| **产品编辑页没有内联编辑档位** | 目前走 API 或 admin。原因是 Django admin 不支持 inline 套 inline，产品编辑页要自己写弹窗。 |
| **低库存阈值仍是前端全局常量** | `InventoryDesk.vue` 里 `lowStockThreshold = 10`。专业做法是 SKU 级字段（oscar 就是放在 `StockRecord` 上）。 |
| **阶梯价不分币种** | 跟随 `SKU.currency`，不单独设（产品确认）。 |
| **无有效期 / 客户组价** | 需要时再加，避免现在过度设计。 |

---

## 8. 相关文件

- 模型 `backend/apps/commerce/models.py::SkuPriceTier`
- 取价 `backend/apps/commerce/services/pricing.py`
- 端点 `backend/apps/commerce/api/v1/views.py::SkuPriceTierView`
- 测试 `backend/apps/commerce/tests/test_price_tiers.py`（19 例）
- 前端 `frontend/src/views/ProductDetail.vue`（SKU 表格 Price 列的分段展示）
