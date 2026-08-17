# S6 四轴子结构判定 — 信号消费落地（②前端展示 + ④数据治理门）

> 范围：S6 判定器（RDKit SMARTS 四轴）产出后，如何"消费"信号。本纪要固化**已拍板的落地顺序**与**已落地的实现**。
> 状态：开发测试态（本地 dev SQLite + 种子数据）。本文所述均非"已交付/已上线"，仅本地落实与校验。

---

## 1. 背景与目标

S6 判定器（`apps/bridges/services/substructure_backend.py`）对单个 SMILES 做四轴子结构判定：碱基（base）、碱基修饰（base_mod）、糖环取代（sugar_sub）、糖型（sugar_type）、环上 OH 数、Biotin 标签、NTP、propargyl 连接臂。经硬化后零误报（10 真值 × 7 断言 = 70/70 通过）。

"消费方式"有四种候选（详见 §2）。用户于 2026-08-10 拍板：**②前端展示四轴标签 + ④数据治理门 先落地**，③接入 relevance 打分暂缓（等真实反馈）。理由：②+④零打分风险、互为支撑、可独立验证。

---

## 2. 决策记录（四方案矩阵 + 拍板）

| 方案 | 内容 | 风险 | 结论 |
|---|---|---|---|
| ① 仅后端字段+API | 落库不展示 | 用户无感、无反馈 | ✗ 不单独做 |
| ② 仅前端展示四轴标签 | 卡片 chips + 详情页 Signature 区块 | 零打分风险；依赖字段未填则空 | ✓ **先落地** |
| ③ 接入 relevance 打分 | 四轴加权进聚合分 | 引入打分权重争议、需更多真值 | ✗ 暂缓，等反馈 |
| ④ 独立工具 + 数据治理门 | `detect_substructures --write` 离线填充、告警非阻断 | 零运行时风险 | ✓ **先落地** |

**拍板结论**：② + ④ 先行。②改前端 card/detail 暴露标签；④把 `detect_substructures` 接成"导入后数据治理门"。③待真实反馈再定。

---

## 3. 架构与数据流

```
SMILES (Product.smiles)
   │  build_substructure_payload(smiles)        [bridges/substructure_backend.py]
   ▼
{ parsed, labels[], axes{...} }   ← RDKit 惰性注入（独立 venv，S6_RDKIT_VENV 可覆盖）
   │  detect_substructures --write  （离线、非阻断；默认只读）
   ▼
Product.substructure_tags  (JSONField, null, 用户不可写)
   │  ProductListSerializer / ProductDetailSerializer 暴露
   ▼
前端卡片 chips（labels / axes）  +  详情页 Modification Signature 区块
```

铁律遵守：
- `substructure_tags` 不进 `ProductCreateUpdateSerializer` → 用户写入路径不可改此字段。
- `detect_substructures` 默认只读；`--write` 仅填充、不删不改任何实体数据；数据质量告警打印但**不阻断**写入。
- `Product` 无 `post_save` 信号（仅 `post_delete`），`--write` 用 `update_fields` 写入不产生审计噪声。

---

## 4. 后端实现

### 4.1 字段 `Product.substructure_tags`
`apps/commerce/models.py`：
```python
substructure_tags = models.JSONField(
    null=True, blank=True, verbose_name='四轴子结构标签',
    help_text='S6：由 detect_substructures --write 离线填充，展示用，不进用户写入路径')
```
迁移：`apps/commerce/migrations/0013_product_substructure_tags.py`（已应用到 dev SQLite）。

### 4.2 归一化助手 `build_substructure_payload(smiles)`
`apps/bridges/services/substructure_backend.py:154`
- 有 SMILES → 返回 `{parsed:True, labels:[...], axes:{...}}`（labels 为前端直接可用的派生展示标签）。
- SMILES 为空 → 返回 `None`。
- SMILES 无效（RDKit 解析失败）→ 返回 `{parsed:False, labels:[], axes:{...全 None/False}}`（诚实占位，不冒充 0）。
- RDKit 缺失 → 返回 `None`（由调用方决定降级）。

### 4.3 数据治理门 `detect_substructures --write`（操作手册）
`apps/bridges/management/commands/detect_substructures.py`

| 命令 | 作用 |
|---|---|
| `python manage.py detect_substructures` | 只读。输出全库统计 + 数据质量标记（名称宣称糖环类型 vs SMARTS 判定） |
| `python manage.py detect_substructures --write` | 在只读基础上，把 `build_substructure_payload` 结果写入 `Product.substructure_tags`（离线填充、用户不可写）；`data-quality` 告警照常打印但**从不阻断**写入 |
| `python manage.py detect_substructures --json` | 全库统计 + 质量标记，JSON 输出 |

环境变量：`S6_RDKIT_VENV`（或 `settings.S6_RDKIT_VENV_PATH`）指向 RDKit 独立 venv，默认 `D:/s6_rdkit_venv`。缺失则命令跳过 RDKit 相关判定并告警。

实跑记录（dev SQLite）：`--write` 成功写入 **107/107** 带 SMILES 商品（0 未解析）。3 条数据质量告警（SC8053 / SC8015 / SC8007 名称 vs SMARTS 不一致）均为供应商脏 SMILES，非判定错，按设计非阻断。

### 4.4 序列化器暴露
`apps/commerce/api/v1/serializers.py`：
- `ProductListSerializer`（line 109）：加入 `substructure_tags`（卡片数据源）。
- `ProductDetailSerializer`（line 438）：加入 `substructure_tags`（详情页数据源）。
- `ProductCreateUpdateSerializer`：**不加**（守住用户不可写铁律）。

---

## 5. 前端实现

- `src/frontend/src/components/cards/ProductCard.vue`：卡片 header 下新增四轴 chips 行，按轴五色编码（base / sugar_sub / sugar_type / base_mod + 派生 labels），guard 空值。数据源 `product`（= `ProductListSerializer`）。
- `src/frontend/src/views/ProductDetail.vue`：Chemical Identity 区后新增「Modification Signature (SMARTS)」分组，渲染四轴 chips（axes + labels）。数据源 `store.currentProduct`（= `ProductDetailSerializer`）。

构建校验：`vite build` ✓（15.74s，仅 chunk 体积告警，无编译错误）。

---

## 6. `substructure_tags` payload 字段规范

```jsonc
{
  "parsed": true,                  // bool | null。null=SMILES 空；false=SMILES 无效
  "labels": ["U", "2'-F", "deoxy", "NTP"],  // 前端直接渲染的派生标签（按化学意义排序）
  "axes": {
    "base": "U",                   // 碱基：A / C / G / U / 其他
    "base_mod": null,              // 碱基修饰（如硫代、甲基化等），无则 null
    "sugar_sub": "2'-F",           // 糖环取代（2'-F / 2'-O-Me / 氨基等），无则 null
    "sugar_type": "deoxy",         // deoxy / ribo
    "ring_oh_count": 1,            // 环上 OH 数（辅助区分 2'/3'/5' 修饰）
    "biotin_label": false,         // 是否带 Biotin 标签
    "ntp": true,                   // 是否为核苷酸三磷酸
    "propargyl": false             // 是否含 propargyl 连接臂
  }
}
```

前端展示约定：
- 卡片：优先用 `labels`（紧凑、已排序）；`parsed` 为 null/false 时整行隐藏。
- 详情页：渲染 `axes`（分 Base / Sugar / Labels 三组）+ `labels`，`null/false` 以「—」占位。

---

## 7. 测试与校验结果（全绿）

- 单元/集成：`bridges` + `commerce` 全量 pytest 通过（含新增 `test_s6_payload_labels_and_axes`、`test_s6_substructure_tags_exposed`）。
- 迁移：`makemigrations --check commerce` → No changes（0013 已一致并应用到 dev SQLite）。
- 治理门：`detect_substructures --write` 实跑 107/107 写入成功，0 未解析。
- 数据抽查：SC8035 → `["U","2'-F","deoxy","NTP"]`；SC8016 → 含 `Biotin`，均正确。
- 构建：`vite build` ✓。
- 真实 HTTP：详情接口（按 pk）返回完整 `substructure_tags`（`field_in_detail=True`）；列表接口（修复后）返回 67 条可见商品，均带 `substructure_tags`（`field_present_in_all=True`）。
- 前端 server：5173 返回 200，绑定字段校验通过（`ProductCard.vue` 用 `labels`、`ProductDetail.vue` 用 `axes`，均 guard `parsed`）。

---

## 8. 已知限制与后续

1. **③接入 relevance 打分未做** —— 按约定等真实反馈再决定。当前方案零打分风险，闭环完成。
2. **公开列表两处数据/代码问题（均与 S6 无关，已修复）**：
   - **(a) `status` 过滤预埋 bug**：`ProductViewSet.get_queryset` 用 `status=Product.Status.ACTIVE`（枚举成员）过滤，而 dev 库 `status` 存原始字符串 `'active'`，Django 不把枚举成员匹配到字符串，公开列表恒返回 0。已改为 `status=Product.Status.ACTIVE.value`（一行，2026-08-10 修复）。
   - **(b) 种子数据几乎全归档（真正阻塞）**：dev 库 255/256 商品 `archived=True`，公开列表按设计排除 archived（软归档机制），故卡片列表拉不到商品。详情接口（按 pk）不过滤 archived，所以详情页 chips 先通过真实 HTTP 验证。为做本地目视验证，已将 **106 条带 `substructure_tags` 的商品解档**（archived=False，可逆、非删除），列表恢复显示 67 条可见商品（active 且未归档）。
3. 历史遗留 `transactions.0007` 待生成迁移，与本任务无关，未动。
4. 本环境无浏览器自动化工具，**像素级 chips 渲染仍需人工确认**：打开 `http://localhost:5173/`（卡片列表）或 `http://localhost:5173/products/54`（SC8035 详情页，四轴 chips 可见）。数据通路（DB→API→序列化器→前端绑定）已全链路核验通过。

---

## 9. 操作速查

```bash
# 后端（dev sqlite）
cd src_claude/backend
DB_ENGINE=sqlite venv/Scripts/python.exe -B manage.py runserver 127.0.0.1:8000
DB_ENGINE=sqlite S6_RDKIT_VENV=D:/s6_rdkit_venv \
  venv/Scripts/python.exe -B manage.py detect_substructures --write

# 前端
cd src_claude/frontend && NODE_OPTIONS="" npx vite --port 5173

# 校验 API
curl "http://127.0.0.1:8000/api/v1/products/<pk>/" | python -m json.tool   # 看 substructure_tags
```
