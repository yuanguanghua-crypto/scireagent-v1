# 库存模型与口径（INVENTORY MODEL）

> 最后实测：**2026-10-28**。文中的数字全部是当天现测的，不要凭记忆引用。
> 本文只讲**模型与口径**；操作手册见第 6 节。

---

## 1. 一句话口径

**`Inventory.available` 的单位是「包装件数」，不是质量、不是体积、不是"份数"以外的任何东西。**

- SKU 的 `pack_size` 是 `10 μL` ⇒ `available = 100` 表示**100 支 10 μL 装**；
- SKU 的 `pack_size` 是 `100 mg` ⇒ `available = 100` 表示**100 瓶 100 mg 装**；
- 客户在购物车买 3 个 ⇒ 需要 3 件，不是 3 mg。

⚠️ 这条必须在任何录入界面/导入模板上写明。否则研究员看到 "Quantity" 会填成 `100`（心想 100 mg），
实际含义是 100 件 —— 差 100 倍，而且**没有任何校验能发现**。

---

## 2. 四个概念，别混

| 对象 | 位置 | 语义 | 谁写 |
|---|---|---|---|
| `SKU.is_stock_tracked` | `commerce/models.py` | **这个 SKU 是否纳入库存管理**（显式开关） | 入库自动置 `True`；运营可手工开关 |
| `Inventory.available` | `inventory/models.py` | 该 (SKU, 批次, 库位) 行**还能卖几件** | `receipt` / `adjust` / `allocate` / `release` |
| `Inventory.allocated` | 同上 | 已被订单行锁定、还没出库的件数 | `allocate` / `release` |
| `Allocation` | 同上 | 「哪一条订单行占用了哪一行库存、占了几件」 | `allocate_for_order`（**目前只有运营手动端点**） |

`on_hand = available + allocated`（在库总量）。

### 2.1 `is_stock_tracked` 为什么必须存在

改造前，判「有没有纳管」用的是 `Inventory.objects.filter(sku_id=...).exists()` —— 即
**有没有库存行**。这个判据有两个致命缺陷：

1. **它是副作用**：加一行就纳管、删一行就脱管，误点一次系统行为就变，界面上还看不见；
2. **它无法区分两件业务含义相反的事**：
   - 这个 SKU **按需生产、本来就不设库存** ⇒ 应永远不拦；
   - **忘了给这个 SKU 建库存行** ⇒ 应视为 0、必须拦；
   两者在数据上完全一样。

所以引入显式字段。语义：

| `is_stock_tracked` | 下单时行为 |
|---|---|
| `True` | 按 `Inventory.available` 之和校验；**没有库存行 = 可用 0 = 拦** |
| `False` | 视为不限量 / 按需生产，**跳过缺货校验** |

`inventory_status == 'out_of_stock'` 这个人工枚举**不受开关影响**，一律拦。

---

## 3. 缺货拦截的判定链（`StockShortageService.is_short`）

```
① sku is None                → 不缺货（交给上层报参数错误）
② inventory_status==out_of_stock → 拦（reason=out_of_stock）
③ is_stock_tracked == False  → 放行（reason=''，不判定）
④ sum(available) < quantity  → 拦（reason=insufficient）
⑤ 否则                        → 放行
```

拦截时不建订单，但**落一条 `StockShortageAlert`**（谁、什么时候、想买什么、要几件）。
运营在 `/ops/shortage-alerts` 看到，决定补货还是联系客户换货。

被拦发生在**事务之外**（`PoSubmitView` / `CheckoutView` 在 `transaction.atomic()` 之前），
否则告警行会跟着回滚，运营什么都看不到。

---

## 4. 数据入口（只有两条）

| 入口 | 端点 | 权限 | 副作用 |
|---|---|---|---|
| 入库 | `POST /api/v1/inventory/receipt/` | `IsProcurementOrAdmin` | `available += n`；写 `InventoryMovement(RECEIPT)`；**自动置 `is_stock_tracked=True`** |
| 纳管开关 | `POST /api/v1/inventory/track/` | `IsProcurementOrAdmin` | 改 `is_stock_tracked`；**关闭时硬校验**：`available==0` 且 `allocated==0` 且无 RESERVED 占用，否则 400 `STOCK_NOT_EMPTY` |

**为什么研究员不能填库存**：库存是资产数据，`receipt` 的语义是"仓库确认实物到仓"。
研究员知道"我做了多少"，不等于"仓库收到了多少"。研究员建 SKU 不等于建库存。
（这一条是 2026-10-28 与产品负责人确认的边界，不要为了省事放开。）

**入库即纳管**是唯一自动置位路径。理由：入库是唯一能证明"这个 SKU 真的要管库存"的事件。

---

## 5. 当前状态与已知缺口（2026-10-28 实测）

| 项目 | 生产 | 本地开发库 |
|---|---|---|
| `inventory` 行数 | **0** | 3（同一 SKU 1675 的三个库位，合计 available=1004） |
| `allocation` 行数 | **0** | 5 |
| SKU 总数 | 36（全部 `inventory_status='in_stock'`） | 596 |
| `is_stock_tracked=True` | **0** | 1（= 1675，由迁移回填，与库存行精确一致） |

⇒ **缺货拦截在生产是 100% 空转的**：没有纳管 SKU ⇒ 判定链走到 ③ 就放行。
这不是 bug，是"还没有库存数据"。等产品上架、SKU + COA/SDS 齐备、盘点完成后录库存，
拦截才会真正生效。

### 5.1 缺口 A：下单不占用库存 ⇒ 会累计超卖

**这是当前最大的库存风险，尚未解决。**

- 下单全程不碰 `inventory`：`PoSubmissionService.submit` / `CheckoutView` 只做**只读**校验；
- `InventoryService.allocate_for_order` 的**唯一调用点**是运营手点的
  `POST /orders/{id}/allocate/`（`po_views.py:238`）；
- ⇒ 库存 100 件时，A 客户下单 100、B 客户再下单 100，**两单都能通过**。
  等运营去点 Allocate，第二单才会 `InsufficientInventoryError` —— 而那时订单已经收了、款可能已付。

"下单即预占"需要配套完整的**释放闭环**（取消 / 拒单 / 超时 / 作废），
漏一个就是库存永久泄漏。该项**未立项**，等库存数据就绪后再评估。

### 5.2 缺口 B：纳管但无库存行的 SKU 会拦掉所有下单

由 `is_stock_tracked=True` + 0 行库存造成。它们在库存台上**不会出现**（库存台只列库存行），
所以单独提供 `GET /api/v1/inventory/tracked-gaps/` + 库存台顶部红色提示条。
这是 4a 引入显式开关后**唯一新增的失效模式**，必须与开关同轮交付。

### 5.3 缺口 C：低库存阈值是前端全局常量

`InventoryDesk.vue` 里 `lowStockThreshold = 10`，对所有 SKU 一视同仁。
不同 SKU 的合理阈值差 2~3 个数量级。应改为 SKU 级字段（未做）。

---

## 6. 运维操作手册

**要给某个 SKU 建库存**
`/ops/inventory` → `+ New Stock Row` → 搜产品 → 选 SKU → 选库位 → 填**件数** → 填原因 → Confirm。
该 SKU 自动纳管。

**要停止管理某个 SKU 的库存**（改成按需生产）
`/ops/inventory` → 该行 `Stop tracking`。
要求该 SKU 当前 `available=0`、`allocated=0`、无未出库占用，否则会被拒（先把库存调 0 / 释放占用）。

**要查"纳管了但没库存"的 SKU**
`/ops/inventory` 顶部红条；或 `GET /api/v1/inventory/tracked-gaps/`。

**要改数量（盘点）**
该行 `Adjust` → 填 `delta`（可正可负）→ 填原因。结果不可为负。
