# 库存管理工具（F3）· 设计稿 v1

> 状态：**待确认**（确认后按 §8 顺序实施）｜ 依据：v4.1 框架 F3 节点 ｜ 2026-10-15
> 设计原则：**只补 API 层 + 变动审计 + UI，不重写现有原子操作** —— `InventoryService` 的
> `select_for_update` 并发模型与不变量已生产验证（allocate 端到端 paid 实测），必须复用。

---

## 1. 背景与目标

- v4.1 框架 L1 唯一 `missing` 的工具类节点：库存管理无 UI、无 API（`inventory/` app 只有 models/services/serializers）
- 使用者：**内部**（procurement/admin）—— 商品数据灰度结束后，入库/盘点全靠它
- 目标：入库、盘点调整、库存查询、变动流水（审计）四件事

## 2. 现状盘点（2026-10-15 读码核实）

| 已有 | 缺 |
|---|---|
| `Inventory` 模型（sku+batch+location 唯一，available/allocated，`allocate()/release()` 带不变量） | **API 层**（无 `api/` 目录、无 urls） |
| `Allocation` 模型（RESERVED/SHIPPED/RELEASED） | **变动审计**（入库/调整/占用/释放全部静默改数，无流水） |
| `InventoryService`（`select_for_update` 原子：allocate/allocate_for_order/release/release_quantity/available_for_sku） | **前端页面**（全仓 grep 无 inventory 页面） |
| `InventorySerializer`/`AllocationSerializer`（只读展示用，可直接复用） | 入库/盘点两个业务动作（模型只有 allocate/release，没有"纯加库存"操作） |

## 3. 数据模型改动（1 个新模型 + 1 个 migration）

### `InventoryMovement`（变动流水 —— 审计台账）

```python
class InventoryMovement(TimeStampedModel):
    class Kind(models.TextChoices):
        RECEIPT  = 'receipt',  '入库'
        ADJUST   = 'adjust',   '盘点调整'
        ALLOCATE = 'allocate', '订单占用'
        RELEASE  = 'release',  '占用释放'
        SHIP     = 'ship',     '发货出库'
    inventory = FK(Inventory, related_name='movements')
    kind      = CharField(choices=Kind)
    delta_available = IntegerField()   # 对 available 的净变化（可负）
    delta_allocated = IntegerField()   # 对 allocated 的净变化（可负）
    quantity  = IntegerField()         # 操作数量（正数）
    reason    = CharField(200, blank)  # 入库/调整必填；占用/释放填订单号
    order     = FK(transactions.Order, null=True, blank=True)
    created_by = FK(User, null=True)   # 系统触发可为空
```

- `0002` migration；**不动** `Inventory`/`Allocation` 现有字段
- 存量数据**不回填**（migration 只建表）

## 4. 服务层改动（复用 + 新增）

| 改动 | 说明 |
|---|---|
| 新增 `InventoryService.receipt(sku_id, location, batch_id, qty, user, note)` | `(sku,batch,location)` 存在则 `available+=qty`，否则建行；写流水 RECEIPT；`select_for_update` |
| 新增 `InventoryService.adjust(inventory_id, delta, user, reason)` | `available+=delta`，结果 `<0` 抛 `InsufficientInventoryError`；写流水 ADJUST |
| **改造** `allocate()/release()` | 在现有原子块**末尾**各加一行 movement 写入（ALLOCATE/RELEASE/SHIP）——同一事务，零额外风险；这是唯一触碰存量代码的点 |

## 5. API 设计（全部 `IsProcurementOrAdmin`；Envelope `{success,data,meta}`）

| 端点 | 方法 | 入参 | 出参 | 说明 |
|---|---|---|---|---|
| `/api/v1/inventory/` | GET | `?search=<sku_code>&location=&low_stock=<阈值>` | 分页列表（含 product_name） | 列表+筛选 |
| `/api/v1/inventory/{id}/` | GET | — | 详情 + `movements`（最近 50）+ `active_allocations` | 详情抽屉 |
| `/api/v1/inventory/receipt/` | POST | `{sku_id, location, quantity≥1, batch_id?, reason*}` | 更新后的 Inventory 行 | 入库（新建或累加） |
| `/api/v1/inventory/{id}/adjust/` | POST | `{delta≠0, reason*}` | 更新后的 Inventory 行 | 盘点调整；`available+delta<0` → 400 |

- **权限**：`IsProcurementOrAdmin`（list/retrieve 亦同 —— 内部工具不对外）
- **并发**：全部经 `InventoryService`（`select_for_update`），**禁止** view 直接改字段
- **校验**：quantity≥1；adjust `reason` 必填、`delta≠0`；不变量 `available≥0 / allocated≥0` 由模型方法保证

## 6. 前端设计

| 项 | 值 |
|---|---|
| 路由 | `/ops/inventory`（`requiresAdmin` —— 现守卫已允许 procurement/admin 进入） |
| 组件 | `src/views/admin/InventoryDesk.vue`（与 PoShipmentDesk 等同层） |
| API 模块 | `src/api/inventory.js`（getInventory/receipt/adjust） |
| 页面结构 | ① 筛选栏（SKU 搜索 + 库位下拉 + 低库存开关）② 主表（SKU/产品/批号/库位/可分配/已占用/在库/操作）③ 行操作：入库弹窗、调整弹窗（delta+reason）④ 行展开：变动流水 + 当前占用（Allocation 列表） |
| 交互约定 | 弹窗提交后原地刷新该行；reason 输入框必填校验；低库存行着色（复用 po-row 风格） |

## 7. 测试计划（TDD，先红后绿）

| 用例 | 断言 |
|---|---|
| 匿名/客户/procurement/admin 四角色 × 4 端点 | 匿名 401；客户 403；procurement/admin 200 |
| 入库到新 (sku,location) | 创建行 + available=qty + 流水 RECEIPT |
| 入库到已有行 | available 累加，不建新行 |
| 调整 delta=-N 超过 available | 400 + **不落库**（断言无行创建/无流水） |
| 调整 reason 缺失 | 400 |
| allocate（订单路径） | 行为不变（回归）+ 新增流水 ALLOCATE |
| release/ship | 行为不变（回归）+ 新增流水 |
| 并发：同时 adjust 与 allocate | `select_for_update` 下无超卖（沿用现有测试模式） |

## 8. 实施顺序（确认后执行）

1. migration `0002_inventorymovement` + 模型
2. 服务层：receipt/adjust + allocate/release 加流水（带回归测试：`test_allocate.py` 必须全绿）
3. API 层（urls/views/serializers）+ 权限测试
4. 前端 api 模块 + 路由 + `InventoryDesk.vue`
5. E2E：`ops-inventory.spec.cjs`（procurement 登录→入库→调整→流水可见）
6. 部署（随下次发版）

## 9. 明确不做（范围外）

- 批次管理 UI（Batch 归 documents app，另议）
- 多仓调拨（EU/US 仓间转移）
- 供应商采购单（PO to supplier）
- 最低库存告警的通知推送（先做低库存筛选，告警列入监控项 §P0-5 一并考虑）
