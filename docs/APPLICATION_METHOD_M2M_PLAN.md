# B 方案：把「应用↔方法」从 1:N 修正为 M:N

> 状态：**方案待确认，未动代码**
> 依据：2026-10-30 生产库实测 + 全仓引用扫描
> 前置结论：`Method.application` FK 是建模错误；`canonical_by_name` 是运行时补丁；
> 47,761 行 draft 是错误建模的数据代价。

---

## 1. 目标态

### 现在（错误建模）

```
Application 1 ────N Method
                     ↑
                47,761 行副本（83 个名字 × 22,213 个应用各一份）
                + 83 个 canonical（application=None，无归属）
                + 运行时靠 canonical_by_name() 把副本翻译成 canonical
```

### 目标（正确建模）

```
Application M ────N Method
                     ↑
              ApplicationMethod 桥（约 47,754 条）
              Method 表只剩 83 个真实实体（+ 若干 archived）
              不再需要 canonical_by_name 补丁
```

### 关键理由（语义）

方法与应用本质是多对多：PCR 用于基因分型、病原检测、克隆、qPCR 定量；
「病原检测」这个应用也用 PCR、LAMP、测序。1:N 的 FK 强行规定「一个方法只属于一个应用」，
必然产生副本。

---

## 2. 现状数据（迁移前必读）

| 项 | 数字 | 说明 |
|---|---|---|
| Method 总行数 | 47,935 | — |
| 其中 draft | 47,761 | **只涉及 83 个名字**，22,213 个应用各 1~3 行 |
| 其中 active | 93 | 83 个无 application（canonical 池）+ 10 个有 application |
| 其中 archived | 81 | 含 73 个重指向后归档的重复版 + 7 个 `__e2e_methods_*` + 1 个协议标题误当方法名 |
| 孤儿（无 method_protocol 引用） | 47,852 | draft 47,761 + archived 81 + active 10 |
| **一个方法都没挂的应用** | **6,344（22.2%）** | 迁移后仍是 0，这是数据问题不是结构问题 |
| 平均每个应用挂几个方法 | **1.68** | — |
| Method 表体积 | 52 MB | — |

**必须承认的事实**：迁移完成后，22,213 个应用页的 methods 列表仍平均 1.68 个、
6,344 个仍为空。**B 修的是结构，不是内容。**

---

## 3. 新表设计

```python
# apps/knowledge/models.py
class ApplicationMethod(TimeStampedModel):
    """应用 ↔ 方法（M:N）。

    为什么需要它：`Method.application` 这个 FK 假设「一个方法只属于一个应用」，
    与领域事实矛盾（PCR 同时服务基因分型/病原检测/克隆）。历史实现把 M:N 塞进
    1:N，结果是给 22,213 个应用各存了一份方法清单（47,761 行），再靠
    `canonical_by_name()` 在运行时翻译回 83 个全局方法。本表取代那套做法。

    迁移来源：47,761 行 draft Method 的 (application, name)，
    经 canonical_by_name 映射到 83 个无归属 active Method 后去重写入。
    """
    application = models.ForeignKey(
        'knowledge.Application', on_delete=models.CASCADE,
        related_name='application_methods', verbose_name='应用场景',
    )
    method = models.ForeignKey(
        'Method', on_delete=models.CASCADE,
        related_name='application_methods', verbose_name='科研方法',
    )
    display_order = models.IntegerField(default=0, verbose_name='展示顺序')
    source = models.CharField(
        max_length=32, blank=True, default='', verbose_name='来源',
        help_text='migrated_t2 = 从 T2 补链的 draft 行迁移而来；空 = 人工维护',
    )

    class Meta:
        db_table = 'application_method'
        ordering = ['application', 'display_order', 'id']
        unique_together = [('application', 'method')]
        indexes = [models.Index(fields=['method', 'application'])]
```

**设计取舍**：

| 决策 | 理由 |
|---|---|
| 用 M:N 桥而不是 `Method.applications` M2M 字段 | 桥要带 `display_order` / `source`，且将来可能加 `confidence` |
| `unique_together (application, method)` | 幂等键；迁移重跑不会重复插 |
| `on_delete=CASCADE` 双向 | 与应用/方法同生共死；协议删除已用同样策略 |

---

## 4. 五个阶段（每阶段独立可验证、可回滚）

### 阶段 0：备份与基线（**必做，否则后面没法对照**）

```bash
# 1) 全量备份 method 表
python manage.py dumpdata knowledge.Method --indent 1 > _corpus_backup/method_all_<ts>.json

# 2) 记录基线：每个应用的 canonical 方法数（迁移后必须逐一相等）
python manage.py shell -c "
from apps.knowledge.models import Application
from apps.knowledge.services.canonical_methods import canonical_by_name
import json
out = {}
for a in Application.objects.only('id','name'):
    names = list(a.methods.values_list('name', flat=True))
    canon = canonical_by_name(names)
    out[a.id] = sorted(canon.keys())
json.dump(out, open('_corpus_backup/baseline_app_methods.json','w'))
"
```

**基线文件是后面唯一的对照依据**，它把「迁移前每个应用看到哪几个方法」固化成可比对的事实。

### 阶段 1：建表 + 迁移数据（不动任何读路径）

- migration `knowledge/0027_application_method`（纯 CreateModel）
- 新命令 `migrate_application_methods`：

```
--dry-run   打印：可映射行数 / 映射不到的名字 / 去重后桥行数 / 受影响应用数
--apply     写入 ApplicationMethod（source='migrated_t2'）
--verify    对照阶段 0 的基线，逐应用比对
```

**迁移映射规则**（必须与 `canonical_by_name` 完全一致，否则前后台不一致）：

| 情形 | 处理 |
|---|---|
| draft 行，名字能在 canonical 池找到（83 个） | 写 (application_id, canonical_id)，source='migrated_t2' |
| draft 行，名字找不到（7 个 `__e2e_methods_*`） | **丢弃并计数**，不写桥 |
| draft 行，名字是那句话（1 条协议标题误当方法名） | 丢弃 |
| 同一 (application, canonical) 由多行映射而来 | 按唯一约束去重，只留 1 条 |
| **10 个有 application 的 active Method** | 也写一条桥（保住它们的归属），随后 application_id 置 NULL |
| 81 个 archived | **不写桥**（archived 不应出现在应用页） |

预期结果：桥约 **47,754 条**，覆盖 22,213 个应用。

**验证**：`--verify` 必须 100% 匹配基线——每个应用的方法名集合完全相同。
这是本阶段唯一放行条件，任一应用不一致就停下查映射。

### 阶段 2：切读（改代码，FK 仍保留）★ 最关键

逐处改造，**每改一处跑一次对照**：

| # | 位置 | 现在 | 改成 |
|---|---|---|---|
| 1 | `serializers.py:218` `ApplicationDetail.get_methods` | `obj.methods.all()` + `canonical_by_name()` | `obj.application_methods.select_related('method').values(...)`，**删掉 canonical 调用** |
| 2 | `serializers.py:239` `get_protocols` | `obj.methods.values_list('id')` | `obj.application_methods.values_list('method_id')` |
| 3 | `serializers.py:250` `get_products` | 同上 | 同上 |
| 4 | `serializers.py:421-455` 协议页 `get_methods` 的 researchPath 上溯 | `mp.method.application` | `mp.method.application_methods.first().application`（或取 display_order 最小者） |
| 5 | `selectors.py:5` `get_methods_by_application` | `filter(application_id=...)` | `filter(application_methods__application_id=...)` |
| 6 | `graph_service.py:70-75` RG→AP→Method 边 | `method.application` | `method.application_methods.first()` |
| 7 | `graph_service.py:112` | `filter(application_id=aid, status='active')` | `filter(application_methods__application_id=aid, status='active')` |
| 8 | `commerce/selectors.py:112` | `product_methods__method__application_id=` | `product_methods__method__application_methods__application_id=` |
| 9 | `commerce/services/product_relationship_service.py` | `method__application__id__in=app_ids` | `method__application_methods__application_id__in=app_ids` |
| 10 | `site_views.py:80-86` 首页聚合 | `methods__status='active'` + `methods__product_methods__...` | 经桥改写 |
| 11 | `method_remap.py` | 整个 service 围绕 FK | **标注废弃**，不再调用（T2 补链不该再跑） |

**风险点**：#8/#9 是 commerce 的产品筛选，改错会让「按应用筛产品」失效；
#4 是协议页的研究路径面包屑，改错会让路径断裂。这两处必须单独验证。

### 阶段 3：停写 + 清数据

- 所有写路径（`MethodViewSet` 的 create/update、`import_*` 命令）不再写 `Method.application`
- 删除 47,761 行 draft（**先备份**，用现有 `purge_protocols` 的模式做 `purge_orphan_methods`）
- 清理 81 个 archived（含 7 个 e2e）
- `Method.application` 字段 `null=True` 保留，加注释 `# 已废弃：语义由 ApplicationMethod 承载，新代码禁止写入/读取`

### 阶段 4（可选，独立决定）：RemoveField

真正删掉 `Method.application`。

**不建议现在做**：RemoveField 不可逆、要过迁移闸门，且保留一个 null 字段不影响正确性。
等阶段 2/3 稳定运行一段时间后再单独做一次小 migration。

---

## 5. 验收判据（量化，缺一不放行）

| # | 判据 | 通过线 |
|---|---|---|
| 1 | 阶段 1 `--verify`：逐应用方法名集合 vs 基线 | **100% 一致** |
| 2 | 应用详情页 `methods` 字段：抽 50 个应用对比改造前后 | 完全一致 |
| 3 | 协议页 researchPath 覆盖数（有 application 上溯的协议数） | 改造前后相等 |
| 4 | 知识图谱边数（RG→AP→Method 三类边的总数） | 改造前后相等 |
| 5 | 「按应用筛产品」`?application_id=X` 命中数：抽 10 个应用 | 改造前后相等 |
| 6 | 首页按 application 聚合的方法数 | 改造前后相等 |
| 7 | `ApplicationMethod` 行数 | 47,754 ± 0，且 `SELECT count(DISTINCT application_id)` = 22,213 |
| 8 | 迁移后 Method 表行数 | 174 行左右（83 canonical + 10 有归属 active + 81 archived） |
| 9 | 8 表行数变化仅限预期范围（method / application_method） | Δ0 其余 |
| 10 | 全量后端测试 | 无新增失败 |
| 11 | 匿名写探针（PATCH /protocols、PATCH /methods） | 401/403 |

---

## 6. 风险清单与对策

| 风险 | 概率 | 影响 | 对策 |
|---|---|---|---|
| 映射遗漏（某名字找不到 canonical） | 低（83/91 已验证） | 该应用少一个方法 | `--verify` 逐应用比对会立刻暴露 |
| `commerce/selectors` 改错 | 中 | 按应用筛产品失效 | 判据 #5 专项验证 |
| 协议页 researchPath 断 | 中 | 面包屑少一层 | 判据 #3 专项验证 |
| `graph_service` 改错 | 中 | 知识图谱断边 | 判据 #4 专项验证 |
| 删 47,761 行后无法恢复 | — | 不可逆 | 阶段 3 前 dumpdata 全量备份；`purge_orphan_methods` 必须先备份再删 |
| FK 保留但有人误用 | 中 | 新代码又写回旧字段 | Model 注释 + `KNOWLEDGE_ASSETS.md` + 记忆三处标记 |

---

## 7. 工作量拆解

| 阶段 | 内容 | 估时 |
|---|---|---|
| 0 | 备份 + 基线固化 | 0.5h |
| 1 | 建表 + `migrate_application_methods` 命令 + 测试 | 3h |
| 2 | 11 处读路径改造 + 逐处对照验证 | **6h（最重）** |
| 3 | 停写 + `purge_orphan_methods` + 清 81 个 archived | 2h |
| 4 | （可选）RemoveField | 0.5h |
| — | 部署 + 生产验收 11 条判据 | 2h |
| **合计** | 到阶段 3 完成为止 | **约 2 天** |

---

## 8. 建议的执行顺序（重要）

**不要按 0→4 线性做。** 建议：

```
阶段 0（备份+基线）
  ↓
阶段 1（建表+迁移+verify 100% 对齐基线）  ← 此时前台行为完全没变，可安全停在
  ↓
阶段 2 逐处切换，每处一次对照  ← 可分批上，每批可回滚（把代码改回读 FK 即可）
  ↓
阶段 3（清数据）  ← 只有在阶段 2 全部验证通过后才做
```

**关键停点**：阶段 1 结束时，新表已建好、数据已迁、前台仍走旧路径 —— 这是一个
**零风险的中间态**。如果 Phase 2 中途发现问题，随时可以停在阶段 1 并回滚代码。

---

## 9. 明确不做的事

| 不做 | 理由 |
|---|---|
| 重建那 6,344 个空应用的「应用→方法」关系 | 是内容缺失，不是结构问题；需要领域判断 |
| 顺手补 83 个 canonical Method 的描述字段 | 是独立的内容工作，不该混进结构迁移（但建议紧接着做，见下） |
| 动 `facet` 的 method 维度（60 个值） | 它与 Method 表用途不同（标签 vs 实体），不冲突 |
| 让 `Method.application` 与桥双写 | 双写会造成两份真相，比现状更糟 |

---

## 10. 与后续工作的衔接

B 完成后，83 个 canonical Method 成为**唯一的方法实体**。这时补它们的
`purpose / advantages / limitations / timeline / cost_band`（目前各只有 10 条有值）
才有意义 —— 一份描述只维护一次，被 22,213 个应用共享。

**所以 B 的真正价值不在「结构干净」，而在「方法的描述只需要写一遍」。**
这是它值得做的核心理由，也是排在这个时点的理由。

---

# 执行记录（2026-10-30，阶段 0~1 已完成并上线）

## 生产实测

| 步骤 | 结果 |
|---|---|
| `baseline` | **22,219 个应用 / 47,844 对**（每应用：1 个 6,966｜2 个 4,906｜3 个 10,339｜4~12 个 8） |
| `rescue-bridges` | PMR **159**｜MRC **39**｜ProductMethod **19**（另 3 条无处可去，指向那句协议标题名，保留不动） |
| `merge-active` | 10 个「带 application 的 active」，**10 个全部可合并**，重指向 `method_protocol` **647** 条，删 10 行 |
| `migrate-drafts` | 待迁 47,835（draft + archived），**仅 1 个名字无法映射**（`__e2e_methods_*`），写入桥 **47,834** 条 |
| `verify` | **22,219 = 22,219，不一致 0** |

## 当前状态（零风险中间态）

```
Method 行数          47,925   （47,935 - 10 合并）
ApplicationMethod    47,844
前台行为              完全不变（读路径仍是 obj.methods + canonical_by_name）
抽样 5 个应用         API methods 与桥 100% 一致  ← 说明阶段 2 切换是安全的
```

## 执行中改掉的四处设计（都已进 commit message）

1. **顺序**：rescue 必须在 merge 之前 —— `ProductMethodRelation.method` 是 PROTECT，
   先 merge 会被 `ProtectedError` 挡住（数据库在保护数据）。
2. **promote 分支**：本地实测有一例（id=36 `Random Primer Method`）active 带 application
   但 canonical 池无同名 —— 不是重复品，而是「还没转正」，应清 FK + 写桥，不能跳过。
   生产恰好没有这种情况（10/10 都能合并）。
3. **基线算法**：原用 `canonical_by_name()` 自算，漏了两个分支（active 直接输出 /
   archived 也走映射），本地 verify 报 30 个不一致。⇒ 抽出
   `services/application_methods.resolve_application_methods`，序列化器与基线共用。
4. **迁移范围**：原只查 `status='draft'`，漏 archived。

## 备份

`_corpus_backup/appmethod_20261030/`（1.6MB）

| 文件 | 内容 |
|---|---|
| `baseline_app_methods.json` | 22,219 个应用改造前的方法名集合（**verify 的唯一对照依据**） |
| `merge_active_snapshot.json` | 被合并的 10 个 Method 全字段 + 647 条 method_protocol |
| `rescue_snapshot.json` | 159 PMR + 39 MRC + 19 ProductMethod 重指向前的方法 id |

## 下一步（阶段 2 未开始）

阶段 2 要改 13 处读路径，是本方案唯一有风险的部分。当前状态可以长期停留 ——
桥已建好且与基线完全一致，随时可以切。

**切换前必须复跑一次 `--step verify`**，确认基线仍匹配（因为期间数据可能变动）。

---

# 执行记录（2026-10-30，阶段 2 已完成并上线，提交 `b1c0f1f`）

## 改了 14 处

| # | 位置 | 改法 |
|---|---|---|
| 1 | `services/application_methods.resolve_from_bridge` | 新主路径：读桥，一次查询，无需 canonical 翻译 |
| 2 | 同文件 `resolve_from_legacy_fk` | 旧逻辑保留为**回滚路径** |
| 3 | 同文件 `application_of_method` | M:N 下取 display_order 最小者（researchPath/图谱需单值） |
| 4 | `ApplicationDetailSerializer.get_methods` | 走 service（受开关控制） |
| 5 | `get_protocols` / `get_products` | 方法 id 改从桥取 |
| 6 | 协议页 researchPath 上溯 | `method.application` → `application_of_method()` |
| 7 | `selectors.get_methods_by_application` | filter 桥 |
| 8-9 | `graph_service` 2 处 | Method→AP 边 + 按 AP 取方法 |
| 10 | `commerce/selectors` | `method__application_id` → `method__application_methods__application_id` |
| 11 | `product_relationship_service` | 同上（`__in` 多应用，靠 set 去重） |
| 12 | `site_views` 首页聚合 | `methods__*` → `application_methods__method__*` |
| 13 | `MethodViewSet.filterset_fields` | 移除 `application_id` 自动筛选，改 get_queryset 手工查桥（参数名不变） |
| 14 | `MethodDetailSerializer.application_id/name` | 经 `application_of_method` 取 |

## 灰度开关

`APP_METHOD_READ_FROM_BRIDGE`（默认 `1`）。设 `0` 即回滚到旧 FK 路径，**不必重新部署**。

## 生产验证

| 判据 | 结果 |
|---|---|
| **逐应用对照基线** | **22,219 个应用，不一致 0** |
| `methods?application_id=33` | 200，count 1（桥筛选生效） |
| 协议 201 的 methods | 3 个，**带 application_name**（researchPath 上溯正常） |
| 图谱 `?type=application&id=33` | 50 节点，含 1 个 method（边正常） |
| knowledge 全量测试 | 0 失败 |
| commerce + bridges 全量测试 | 0 失败 |

## 过程中修掉的三个问题

1. **`baseline` 不能用当前读路径算** —— 它固化的是「改造前用户看到什么」。
   加开关后若用桥算，在桥未建时得到空基线，verify 变成空转（本地实测
   `test_verify_detects_missing_bridge` 因此未报错）。⇒ 强制用 `resolve_from_legacy_fk`。
2. **`application_of_method` 也要受开关控制** —— 否则回滚路径下 draft 方法上溯不到
   应用（协议页面包屑会空）。
3. **测试工厂必须同步建桥** —— `MethodFactory(application=app)` 若只建 FK 不建桥，
   19 个既有测试会失败。改为：默认 `status='active'`（对齐生产 canonical）+ 带
   application 时自动建桥；draft 不建桥（对应「应用页不显示 draft」的既有断言）。

## ⚠️ 阶段 3 尚未执行（不可回滚点）

删 47,835 行 draft + 81 个 archived + 停用 `remap_method_applications`。
现在的状态是**可回滚**的（开关切 0 即回旧路径），建议观察一段时间再做阶段 3。

**做阶段 3 前必须注意**：
- 基线文件在容器 `/tmp`，**容器重建即丢** —— 已取回 `_corpus_backup/appmethod_20261030/`，
  重跑 verify 前要先 `docker cp` 回去
- 阶段 3 之后 legacy 回滚路径失效（draft 行没了），开关实际上只剩 `1`
