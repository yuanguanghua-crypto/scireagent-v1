# 协议语料回灌方案（L0 溯源层 + L1 材料条目化）

> 状态：**方案待确认，未动代码**
> 依据：2026-10-29/30 对本地语料全量 + 生产库全表的实测结果
> 关联：`docs/KNOWLEDGE_ENTITIES_BRIEF.md`（现状问题）、`docs/KNOWLEDGE_ROADMAP.md`（BIO-P1-1 / BIO-P1-2）

---

## 0. 一句话结论

语料里被丢弃的两类信息（**来源链接**和**材料清单**）可以用纯本地解析抢救回来，
但**只覆盖库内 14,128 条协议的 34.6%（4,890 条）**，其余 65.4% 语料本身就没有这两个字段。

---

## 1. 覆盖范围：必须先讲清楚的边界

| 语料源 | 库内协议数 | 占比 | `input` 字段（材料清单）情况 | L0 来源链接 | L1 材料条目化 |
|---|---|---|---|---|---|
| **Bio-protocol** | 4,194 | 29.7% | 4,048/4,157 非空（97.4%），编号列表结构 | ✅ 100% 有 DOI | ✅ 4,045 条可解析 |
| **Protocol-exchange** | 930 | 6.6% | 845/933 非空，**空行分隔无编号**，需独立规则 | ✅ 99.4% 有 DOI | ⚠️ 845 条可解析，质量较低 |
| **Protocol-io** | 8,821 | 62.4% | **字段根本不存在**（原始 JSON 无 `input`） | ❌ 无 DOI，只有 protocols.io URL | ❌ **0 条** |
| 无法归属语料 | 178 | 1.3% | — | ❌ | ❌ |

> **关键事实**：`Protocol-io` 占库内 62.4%，但它的原始 JSON 里**没有 `input` 字段**
> （字段仅 `id/url/title/keywords/abstract/hierarchical_protocol/length/description/problem/method/innovation/application/classification`）。
> 这些协议的材料信息只存在于步骤正文，**不是"导入丢了"，是语料本身没有**。
> 从步骤正文抽取材料属于另一量级的工程（需 NLP 抽取 + 人审），**本方案不做**。

**因此本方案的实际交付面**：

| 能力 | 覆盖 | 占全库 |
|---|---|---|
| 协议挂原文链接 | 13,945 条 | **98.7%** |
| 协议挂 DOI | 5,127 条 | 36.3% |
| 协议挂结构化材料清单 | 4,890 条 | **34.6%** |

---

## 2. 已验证的事实基础（解析器原型实测）

原型脚本：`_corpus_audit/parse_v2.py`（Bio-protocol）、`_corpus_audit/parse_px.py`（Protocol-exchange）。
**未写库，仅评估。**

### 2.1 Bio-protocol 解析结果

| 指标 | 实测值 |
|---|---|
| 记录数 | 4,157 |
| 解析出条目的记录 | **4,045（97.3%）** |
| 解析不出（`input` 为空） | 112（2.7%） |
| **条目总数** | **163,413** |
| 每记录条目数 | 中位 35｜均值 39.3｜P90 70｜最大 268 |
| 条目含 vendor | 58.9% |
| 条目含 catalog_no | 52.9% |
| 疑似该有货号但没抽到 | 3.7%（原型 v2 已从 v1 的 13.2% 降下来） |
| 条目切分漏检（同一物理行塞多个编号） | **1.9%**（3,085 项，影响 926 条记录） |

类别分布（8 类）：

| kind | 条目数 | 占比 |
|---|---|---|
| `reagent` | 73,330 | 44.9% |
| `equipment` | 42,792 | 26.2% |
| `consumable` | 15,261 | 9.3% |
| `biological_material` | 13,925 | 8.5% |
| `material_or_reagent`（前导区未细分） | 8,059 | 4.9% |
| `software` | 5,163 | 3.2% |
| `solution_recipe` | 3,452 | 2.1% |
| `note` | 1,431 | 0.9% |

### 2.2 人工判读（放行前必做的抽样）

对 `Bio-protocol-1`（34 条）和 `Bio-protocol-2290`（30 条）逐条判读，**条目切分与 vendor/货号抽取全部正确**：

```
Bio-protocol-2290  #9   reagent  JBS DNA-Shuffling Kit      vendor=Jena Bioscience  cat=PP-103
Bio-protocol-2290  #10  reagent  DNase I, RNase-free (1 U/uI) vendor=Thermo Fisher   cat=EN0521
Bio-protocol-1     #4   reagent  Sodium chloride (NaCl)    vendor=J.T. Baker       cat=3624-19
Bio-protocol-1     #3   equipment Glass alcohol burner      vendor=Everglass        cat=EVG1381
```

### 2.3 一处自我纠错（必须记录）

评估「同一行塞多个编号」的影响面时，第一版正则用 `\s` 做前导分隔，
`\s` 会跨换行，把**行首编号重复计了一次**，得出「43% 条目被吞」的错误结论。
改为 `[ \t]` 后真实值是 **1.9%**。

> 教训复用：统计"漏检率"时，分隔符必须用 `[ \t]` 而不是 `\s`，否则行首项会被重复计数。

### 2.4 Protocol-exchange 解析结果

| 指标 | 实测值 |
|---|---|
| 记录数 | 933 |
| 解析出条目 | 845（90.6%） |
| 条目总数 | 5,182 |
| 条目含 vendor | 31.9% |
| 条目含 catalog_no | 19.2% |

质量明显低于 Bio-protocol：它的 `input` 是**空行分隔的无编号行**（`NaClO (Honeywell)`），
括号里只有供应商没有货号时容易串味。**建议 P2 再做，或只做 vendor 不做 catalog。**

---

## 3. L0 溯源层（建议先做，与 L1 同一批）

### 3.1 表结构变更

`Protocol` 新增 4 个字段（migration `knowledge/0025_protocol_provenance.py`）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `doi` | `CharField(100, blank, db_index=True)` | 如 `10.21769/BioProtoc.2841`，**不设 unique**（语料有 2 条重复） |
| `source_url` | `URLField(500, blank)` | DOI 链接或 protocols.io 页面地址 |
| `corpus_id` | `CharField(64, blank, db_index=True)` | 如 `Bio-protocol-2290`，用于对回原文 |
| `corpus_source` | `CharField(32, blank, db_index=True)` | `bioprotocol` / `protocol_io` / `protocol_exchange` / `unknown` |

> 为什么不放 `reference` 表：`reference` 是**引文**（论文），协议本身的出处是**协议原文地址**，两者语义不同。
> 混用会让"某协议引用了哪篇论文"和"这份协议从哪抄的"无法区分。

### 3.2 回填方式

按 `Protocol.name` **精确匹配**语料 `title`（实测逐字相等，非模糊匹配）：

```python
# 伪代码
for corpus_row in load_corpus():            # 14,675 条
    key = normalize(corpus_row.title)        # 小写 + 非字母数字折叠
    idx[key].append(corpus_row)
for p in Protocol.objects.all():
    hits = idx.get(normalize(p.name))
    if len(hits) == 1:                       # 跨源同名 5 条跳过，人工处理
        p.doi, p.source_url, p.corpus_id, p.corpus_source = ...
```

匹配结果（双向全量实测）：

| 方向 | 结果 |
|---|---|
| Bio-protocol 标题 → 库内 | 4,157 / 4,157 = **100%** |
| Protocol-exchange 标题 → 库内 | 933 / 933 = **100%** |
| Protocol-io 标题 → 库内 | 9,302 / 9,585 = 97.0% |
| 库内 14,128 行归属 | PI 8,821｜BP 4,194｜PX 930｜**无法归属 178**｜跨源同名 5 |

### 3.3 L0 验收判据

| # | 判据 | 阈值 |
|---|---|---|
| 1 | `doi` 非空条数 | ≥ 5,000（预估 5,127） |
| 2 | `source_url` 非空条数 | ≥ 13,900（预估 13,945） |
| 3 | 抽 5 条 DOI 实际访问 `https://doi.org/<doi>` | 5/5 返回 302 且落地页标题含协议名关键词 |
| 4 | 协议详情页出现 "View original protocol" 链接，点击可达 | 人工 3 条 |
| 5 | 幂等：连跑两次，`doi` 非空条数不变 | 必须 |
| 6 | 部署闸门：8 表 Δ0 + 匿名写探针必须 401/403 | 必须 |

---

## 4. L1 材料条目化（核心改造）

### 4.1 为什么必须建表，不能塞 TextField

现有 `Protocol.materials / reagents / equipment` 是 `TextField`，语料是**条目化清单**（每项带 vendor + catalog number）。
如果塞成文本，客户看到的是 2,779 字符的一坨，**无法用于**：

- 生成"一键采购清单"（ROADMAP `BIO-P1-2` 的原始诉求）
- 反查"这份协议到底用了哪些试剂"（这是重建 `ProductProtocol` 唯一的可靠依据）
- 按 vendor/货号做检索

### 4.2 新表设计（migration `knowledge/0026_protocol_material.py`）

```python
class ProtocolMaterial(TimeStampedModel):
    class Kind(models.TextChoices):
        REAGENT             = 'reagent',              '试剂'
        EQUIPMENT           = 'equipment',            '设备'
        CONSUMABLE          = 'consumable',           '耗材'
        BIOLOGICAL_MATERIAL = 'biological_material',  '生物材料'
        SOLUTION_RECIPE     = 'solution_recipe',      '溶液/配方'
        SOFTWARE            = 'software',             '软件'
        MATERIAL_OR_REAGENT = 'material_or_reagent',  '材料或试剂（未细分）'
        NOTE                = 'note',                 '说明'

    protocol   = FK(Protocol, CASCADE, related_name='materials_items')
    seq        = PositiveIntegerField()          # 解析时生成的全局递增序号（幂等键）
    kind       = CharField(24, choices=Kind.choices, db_index=True)
    ordinal    = PositiveIntegerField(null=True) # 原文编号（可能重复，仅展示用）
    name       = CharField(500)                  # 条目名
    vendor     = CharField(200, blank, db_index=True)
    catalog_no = CharField(100, blank, db_index=True)
    model_no   = CharField(100, blank)
    section_heading = CharField(200, blank)      # 原始 `#` 标题，保留语料原貌
    raw_line   = TextField()                     # ★ 原文整行，保真，不许改写

    class Meta:
        db_table = 'protocol_material'
        ordering = ['protocol', 'seq']
        unique_together = [('protocol', 'seq')]
        indexes = [
            Index(fields=['protocol', 'kind']),
            Index(fields=['kind', 'vendor']),
        ]
```

**设计取舍**：

| 决策 | 理由 |
|---|---|
| 用 `seq` 而非 `(kind, ordinal)` 做幂等键 | 原文编号在同一份协议里跨分节重复（`# Solutions` 和 `# Recipes` 都从 1 开始），不唯一 |
| 保留 `raw_line` | 解析器可能出错，原文必须可回溯；也是验收判据 4 的检查对象 |
| 保留 `section_heading` | 1,800 种标题不可穷举，"未细分"是诚实状态，不能强行归一类 |
| `kind` 只有 8 类 | 不做更细粒度（如区分 antibody / enzyme / dye），那是 ReagentClass 的职责，不是材料清单的职责 |
| 不存 quantity | 语料里用量表述极不规整（`5.5% (w/v)`、`1 U/uI`、`2~g~`），塞一个字段只会产生错误数据。要做得单独设计 |

### 4.3 解析规则（已用原型验证）

**步骤 1｜分节**：按 `^#\s*(.+)$` 切；第一个 `#` 之前的部分是**前导裸列表**（85.5% 的记录有，这是材料/试剂主清单）。

**步骤 2｜切条目**：行首 `^\s*(\d{1,3})[\.\)]\s+`；续行并入上一条。

**步骤 3｜标题归一化**（1,800 种 → 8 类）：去 `a.` / `1.` 编号前缀 → 小写 → 去符号 → 关键词匹配，优先级 `equipment > software > consumable > biological_material > reagent > solution_recipe`。

**步骤 4｜前导区条目内容级分类**：前导区没有标题，按条目名关键词判别（`tube/plate/tip → consumable`；`centrifuge/microscope → equipment`；`cell line/plasmid/antibody → biological_material`；其余 → `reagent`）。无法判别时落 `material_or_reagent`。

**步骤 5｜vendor / catalog 抽取**：遍历条目内所有括号，取第一个含 `catalog`/`model` 的括号；name = 该括号之前的部分。**括号后允许有 `, store at RT` 等尾巴**（v1 因为要求括号在行末，漏了 13.2%）。

**步骤 6｜保真校验**：每条 `raw_line` 必须是原 `input` 的 **substring**，否则报错不写库。

### 4.4 导入命令

`backend/apps/knowledge/management/commands/import_protocol_materials.py`

```
--corpus-dir  <BioProCorpus 目录>   # 默认 E:\scireagent-tencent\backend\data\bioprocorpus
--source      bioprotocol|protocol_exchange|all
--dry-run     # 只解析不写库，输出统计
--purge       # 删除该 protocol 的已有条目后重灌（幂等）
--limit N
```

**必须**在 `transaction.atomic()` 内（management command 无 `ATOMIC_REQUESTS`）。

### 4.5 前台展示变更

`frontend/src/views/ProtocolDetail.vue` → Materials tab：

- **优先读新表**（`protocol.materials_items`），按 kind 分组，分组顺序：
  `biological_material → reagent → solution_recipe → consumable → equipment → software → material_or_reagent`
- 每条渲染：**name 粗体** + `vendor · catalog_no` 灰色小字
- **空分组不渲染**（沿用 2026-10-29 `f20c97a` 已确立的"空就整块不显示"原则）
- **旧 TextField 作为 fallback**：新表无条目且旧字段有值时，仍按原样渲染（保护现有 53 条有 equipment 的 curated 协议）
- 页面顶部（Objective 上方）增加 `View original protocol ↗`，仅当 `source_url` 非空时显示

API：`ProtocolDetailSerializer` 增 `materials_items`（嵌套只读）；列表页**不返回**该字段（避免 N+1 与体积膨胀）。
`site_views` 若也返回协议详情，同样要 `prefetch_related('materials_items')`。

### 4.6 L1 验收判据

| # | 判据 | 阈值 |
|---|---|---|
| 1 | `ProtocolMaterial` 总条目数（Bio-protocol） | ≥ 160,000（原型 163,413） |
| 2 | 有材料的协议数 | ≥ 4,800（BP 4,045 + PX 845） |
| 3 | **`raw_line` 全部是原 `input` 的 substring** | **100%**，任一失败即中止 |
| 4 | 抽 20 条协议人眼判读条目切分与 vendor/货号 | 正确率 ≥ 95% |
| 5 | 幂等：`--purge` 重跑两次，条目数完全一致 | 必须 |
| 6 | 详情页 Materials tab 首屏渲染 | ≤ 300ms，且查询数 ≤ 45（当前基线） |
| 7 | 8 表 Δ0 + 匿名写探针 401/403 | 必须 |
| 8 | 抽查 `Protocol-io` 来源的协议 | 材料清单为空，且**页面不显示空态抱怨**，只显示 "This protocol does not list materials" |

---

## 5. 明确不做的事

| 不做 | 理由 |
|---|---|
| 从 `Protocol-io` 步骤正文抽材料 | 8,821 条，需 NLP 抽取 + 人审，准确率无法保证；投入产出比最差 |
| 用 LLM 改写/补全任何字段 | 违反保真原则。`raw_line` 必须原文 |
| 填 `expected_results` | 语料无该字段；信息在图注（80.2%）里，但属定性描述，需 LLM + 人审。**另立项** |
| 填 `principle` / `troubleshooting` | 语料无对应字段（`protocol` 正文里的 Notes 可抽，价值低） |
| 修 `Method` 47,935 → 91 去重 | L3 结构性重构，破坏性，需独立迁移方案。**本方案不碰** |
| 修 `ProductProtocol` 23,431 条 | 依赖 L1 落地后才能用材料清单重建，顺序必须是 L1 先行 |

---

## 6. 需要你决策的三点

| # | 决策 | 我的建议 |
|---|---|---|
| 1 | **旧 `materials/reagents/equipment` TextField 保留还是废弃** | **保留**，作为 fallback。废弃会导致现有 53 条 curated 协议的前台内容消失 |
| 2 | **Protocol-exchange 是否与 Bio-protocol 同批做** | **同批做但降级**：只写 `name`，`vendor` 保留、`catalog_no` 只在括号内明确带 `catalog number` 时才填。它的 930 条不值得再迭代一轮 |
| 3 | **`ProtocolMaterial` 是否现在就接 `Product`（做采购清单）** | **不接**。先把材料清单本身做对，`ProductRouter`（材料名 → 我们 SKU 的映射）是**独立的一张人工维护映射表**，属下一步 |

---

## 7. 实施顺序与回滚

```
① knowledge/0025_protocol_provenance   （加 4 字段，不写数据）      ← 零风险
② 回填命令 backfill_protocol_provenance                             ← 可回滚：UPDATE ... SET doi='' 按 created_at 区间
③ 详情页 + 序列化器：展示 source_url                                ← 纯前端 + 只读字段
④ knowledge/0026_protocol_material     （建空表）                   ← 零风险
⑤ import_protocol_materials --dry-run → 统计核对                    ← 不写库
⑥ import_protocol_materials --source bioprotocol                   ← 可回滚：DELETE FROM protocol_material
⑦ 详情页 Materials tab 改读新表                                     ← 纯前端
⑧ import_protocol_materials --source protocol_exchange             ← 同上
```

每一步独立可验证、独立可回滚。①–③ 与 ④–⑧ 之间可以停，不影响线上。

---

## 附：本次实测数据出处

| 数据 | 来源 |
|---|---|
| 语料字段覆盖率、1,800 种标题、85.5% 前导列表 | `Bio-protocol.json` 4,157 条全量遍历 |
| 库内 14,128 行字段完整度 | `psql SELECT count(*) FILTER (WHERE length(trim(x))>0)` |
| 双向标题匹配 | `/tmp/match.py` / `/tmp/match3.py`（语料 14,675 签名 ↔ 库 14,128 名） |
| DOI 唯一性 | 4,157 个 BP DOI 全部 `10.21769/BioProtoc.NNNN`，零重复 |
| 解析器原型 | `_corpus_audit/parse_v2.py`、`_corpus_audit/parse_px.py` |
| 人工判读样本 | `_corpus_audit/eyeball.py` 输出（Bio-protocol-1 / -2290） |
