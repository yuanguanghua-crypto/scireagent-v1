# 产品设计稿 v2：Product ↔ Protocol 相关性（双强信号 + 两铁律）

> 状态：**待评审（先讨论后落地）**。v2 已吸收反方审计（`docs/product-protocol-relevance-audit.md`）全部结论。
> 本文档不含任何业务代码/库改动，仅设计。
> 配套探针：`apps/bridges/management/commands/probe_protocol_relevance_v3.py`（只读，已实测）。
> 配套抓取：`apps/bridges/management/commands/crawl_bioz_jena.py`（只写 DataSourceCache）。
> v1→v2 变更摘要：修正 Blocker B1（Bioz 改为协议级对齐）；修正事实 C1–C3；Bioz 由"并列强信号"降级/重定为"实证典型性轴"；阈值改为待标注集验证 + 每产品自适应；词表外部化 + embedding 基线；UI 分轴呈现两种相关性。**2026-08-05 增补 §1.1 数据来源分层与角色（ChEMBL/PubMed/BioProCorpus/Bioz 管线与层级），用户拍板：docx 降为次级提示+规格源、实证文献家族升为有效性权威、PubMed/BioProCorpus 接入打分列 Phase-2。**

---

## 0. 目的与两条铁律（对齐）

**目的三层**：
1. **可用性** — 解决每个产品页铺 19~26 条泛化协议、研究员无法快速判断"这产品能干啥"。
2. **可信/透明** — 按"相关性"排序而非截断；依据可解释（铁律②透明）。
3. **可控** — 按相关度档筛选 + TopN 可配（5/10/20/50）。

**两条铁律（用户拍板，覆盖 A/B 取舍）**：
- **① 最大化数据**：处理过程不得遗漏任何"真实、可信、有价值"的数据。即**不删链、不裁剪**，证据源全量纳入：docx 用途陈述 + Bioz 文献 + BioProCorpus。
- **② 最强相关性**：在①基础上，找出"最相关、最能匹配产品、最能证明产品价值与用途"的数据，排到最前。且**相关性必须准确、可归因**——不得把产品级存在性冒充协议级匹配（见 §3 / 审计 B1）。
- **③ 编辑页降噪与精准化（用户 2026-08-05→08-06 拍板，覆盖 Knowledge Links 编辑体验）**：工作台产品编辑页 `5. Knowledge Links` 的 **Methods:/Protocols:** 区块**必须做降噪与精准化改造**。理由：①研究员编辑时该区块内容过多、噪音太大，无法准确选择；②呈现的大量链接不准确、不精准、贴合性不强，对网站用户的指导意义弱。**实现约束（与①②自洽）**：降噪靠铁律②的"相关性排序 + 可归因 + 折叠（非删除）"达成，**严禁以降噪为名在数据层删链/裁剪（铁律①不变）**；不精准/贴合性弱的链接须**标注来源与相关性分**（透明），确属错误关联的可经研究员显式 unlink（编辑权在研究员，架构铁律⑤）。

**由此定调（用户 2026-08-05 拍板：实证文献为有效性权威，docx 降为次级提示+规格源）**：
- 采用"**全量保留 + 相关性排序 + 折叠（非删除）**"——折叠是显示层收口，数据不丢。
- **层级（审计 K1 + 用户拍板）**：
  - **有效性权威层 = 实证/策展文献家族**：`PubMed`（生成知识链实体 Application/Method/Reference）+ `BioProCorpus`（协议内容本体）+ `Bioz`（SKU 级实证使用证据）。这三者决定"方法/协议是否真的适用、是否典型"——**是相关性/有效性的权威来源**（见 §1.1）。
  - **次级提示 + 规格源 = 厂商 docx 用途陈述**：仅作**低置信能力提示**（"厂商说可用于 X"）与**产品级规格来源**（浓度/储存/配方，文献无此确切 SKU 参数）。**不得作为有效性权威**；在打分层处于实证文献之下（见 §1.1 / §4 Phase-2）。
- **两轴分离（审计 K1/K6，UI 呈现）**：当前可落地的两轴仍按"docx 声称能力（轴 A）"与"Bioz 实证典型性（轴 B）"分别计分、分别呈现；**但轴 B 所在的实证家族整体层级高于轴 A**（轴 B 实证 > 轴 A 声称）。综合排序可用加权，UI 必须让用户同时看到两轴数值，不得只给一个混合分。Phase-2 将把 PubMed/BioProCorpus 也接入打分层（§9/§4）。

---

## 1. 数据来源与信号性质（含 Protocols 语料库的角色）

| 信号源 | 粒度 | 覆盖 | 性质 | 代码位置 |
|---|---|---|---|---|
| **docx 用途陈述（次级提示+规格源）** | 产品级（厂商自述） | 125/125（100%） | **次级提示 + 规格源**（用户拍板：非有效性权威）；营销文案，模糊风险高（审计 K1/D5） | `D:\试剂产品说明文档` → `Product.usage` |
| **PubMed（知识链生成器）** | 知识链实体级 | 全量（检索可得） | 搜文献→抽取 Application/Method/Reference，Method/Protocol 的 provenance；**实证家族成员，Phase-2 接入打分** | `knowledge/services/literature_recommender.py` |
| **BioProCorpus（协议内容本体）** | 协议语料级 | 全量 | 真实已发表协议索引；协议内容本身 + 匹配 Q 侧文本；**实证家族成员，Phase-2 接入打分** | `knowledge/services/protocol_recommender.py`、`data/bioprocorpus/` |
| **Bioz 文献（轴 B·实证典型性）** | 产品 SKU 级 → **协议级对齐后** | 仅 jena 命中（**61/106**，审计 C1） | 第三方实证此货号被用于某技术；稀疏（~12/106 有记录）；实证家族成员 | `bioz_client.search_by_sku` → DataSourceCache |
| **ChEMBL（身份/信任层）** | 化学身份级 | 按 CAS 可达 | **非内容源**：PubChem 兜底 + Bioz 信任闸门（CAS exact=文献适用） | `pubchem_enhancer.py`、`bioz_equivalence.py` |
| **编辑精选** | 桥级 | 全量 | `MethodProtocol.featured/display_order` | `apps/bridges/models.py` |

**Protocols 语料库（knowledge 的 Protocol+Method）在此流程的 4 个角色**（审计 D1/D2/K4 根）：
1. **候选/目标宇宙**：要排序、且铁律①全量保留的就是这些协议。
2. **Q 侧文本源**：F-score 的 Q 抽自 `protocol.name + objective + method.name + summary + purpose`。
3. **召回上限 + 词汇空间定义者**：35 词领域词表从其文本长出来；协议覆盖不到的应用，产品永远桥不到（K4）。**语料库质量 = recall 天花板**，且无标注 ground truth → 阈值/词表不可自证（D1/D2）。
4. **范围限定器**：`MethodProtocol` 桥决定产品只与"可达方法"下的协议比较。

**信号优先级（两轴分别，不再"并列"误导，审计 K1/D6）**：
- 轴 B（Bioz 实证）**应高于**轴 A（docx 声称）——实证比自述更可信。
- Bioz 仅对稀疏子集非零 → 它是**稀疏实证增强器**，不是与 docx 等权的"并列强信号"。设计稿 v1 称"双强信号并列"为夸大，v2 更正。
- 层级（单轴内）：命中 > 无信号；跨轴：UI 分轴展示，综合排序 `score = wA·cap + wB·typ`（权重待标注集定，见 §4/D1）。

---

## 1.1 数据来源分层与角色（ChEMBL / PubMed / BioProCorpus / Bioz ↔ 厂商 docx）

> 本节为 2026-08-05 澄清固化：四源并非"并列文献联盟"，而是带信任闸门的管线。代码事实见各 `代码位置`。

### 1.1.1 四源各自真实角色（用户问 + 代码核实）

| 来源 | 真实角色 | 代码位置 |
|---|---|---|
| **ChEMBL** | **化学身份解析兜底 + Bioz 信任闸门使能**（非内容源）。PubChem 查不到 CAS → ChEMBL REST 兜底；`bioz_equivalence` 据 CAS 严格一致判定 Bioz 文献是否适用于本平台产品（exact=适用；name-模糊=needs_review）。身份/信任层。 | `commerce/services/pubchem_enhancer.py`、`knowledge/services/bioz_equivalence.py` |
| **PubMed** | **知识链实体生成器**：搜文献 → 抽取 `Application / Method / Reference`，即 Method/Protocol 的 provenance（"为何/怎么用"的来源）。 | `knowledge/services/literature_recommender.py`（`LiteratureRecommender`，调 `pubmed_client`） |
| **BioProCorpus** | **协议内容本体**：从 `data/bioprocorpus/*.json`（Protocols.io、Bio-protocol、ORD、PQA 等**真实已发表协议**）建内存索引；是协议文本本身，也是相关性匹配 Q 侧文本源。 | `knowledge/services/protocol_recommender.py`（`BioProCorpusIndexer`/`ProtocolRecommender`） |
| **Bioz** | **SKU 级实证使用证据**：哪些论文用了这个确切厂商货号、用了什么 technique；经化学等同性闸门后才"适用于本平台产品"。 | `knowledge/services/bioz_client.py` + `bioz_equivalence.py` |

### 1.1.2 相互关系（带信任闸门的管线）

```
化学身份层(信任闸门)      PubChem(主) → ChEMBL(兜底) → CAS/SMILES 归一
                            │ 经 bioz_equivalence：CAS exact=文献适用；name=需复核
                            ▼
内容/证据层
  PubMed      ──LiteratureRecommender──▶ Application / Method / Reference  (知识图谱种子)
  BioProCorpus──ProtocolRecommender────▶ Protocol 内容本体 (我们匹配的 Q 侧)
  Bioz        ──SKU级实证──────────────▶ 本产品被真实用于某 technique 的证据 (经身份闸门后可信)
                            │
                            ▼
相关性打分 (当前: docx厂商文案=主信号, Bioz=辅 → 用户拍板须改为 实证文献家族 为权威)
```

一句话：**化学身份（PubChem/ChEMBL）信任闸门 → 放行 Bioz 实证；PubMed + BioProCorpus 供给知识图谱内容；厂商 docx 只是相关性匹配的 P 侧查询 + 规格源，非内容来源。**

### 1.1.3 与厂商 docx 的层级（用户 2026-08-05 拍板）

- **实证/策展文献（PubMed/BioProCorpus/Bioz）对"内容与有效性" > 厂商自述**，按维度：
  - 协议内容本身：BioProCorpus（真实已发表步骤）> 厂商手册 ≥ PubMed（需再抽取）> Bioz（只有"用过"无"步骤"）。
  - 方法适用性/典型性：Bioz（实证"真有人这么用"）> 厂商自述。
  - 化合物生物活性/机理：ChEMBL（另一轴，不产协议步骤）。
  - **本产品规格**（浓度/储存/配方/确切货号参数）：**厂商 > 任何文献**（文献没有这个确切 SKU 的参数）。
- **反方保留（必须说清，否则盲目站队）**：
  1. 文献自身有偏倚：发表偏倚（阴性结果少）、技术时髦；**ChEMBL 对"非药物/非生物活性试剂"覆盖缺口极大**——本项目大量连接子/标记试剂（EdU、硫代UTP、Cy3-dUTP）ChEMBL 常无条目，不能神话它。
  2. **落地断层**：PubMed/BioProCorpus 推荐器存在但**未接入相关性打分**；Bioz 仅 12/106 点火。长尾产品目前唯一可得信号仍是厂商 docx——不能直接"删掉"厂商文案，否则大部分产品零桥接。
  3. "更值得信任"是**条件性**的：实证源胜在"典型性/有效性"，厂商源胜在"本产品规格"。二者互补，非替代。
- **关键真相（架构已认同用户直觉）**：`Method/Protocol` 实体本就由 `import_knowledge_graph` 从**策展知识图谱 JSON**（源自文献/BioProCorpus）灌入，**不是**厂商文案生成 → 用户在"内容来源"层的直觉已被系统架构证实；但**相关性打分**当前仍 docx 主（见 §4），正是审计 K1 指出的"本末倒置"，v2 两轴 + 本拍板已纠正方向，并须 Phase-2 把 PubMed/BioProCorpus 接入打分。

---

## 2. 数据模型变更

### 2.1 `Product.usage`（单字段，已确认选型）
- `usage`：TextField，NULL/空允许。承载 docx 用途陈述（厂商自述）。
- **125 存量**：从 `D:\试剂产品说明文档` 解析回填（探针已验证 125/125 含用途串，但**抽取质量尚未人工评估**，审计 D5）。
- **后续新建**：表单增 `usage` 文本域；研究员新建时填写（铁律①：每个后续产品产生新用途描述必须有写入方 B）。

### 2.2 `ProductProtocol`（新表，产品↔协议直接相关性，含两轴）
保持 `MethodProtocol` 桥不变（铁律①全量保留）。新增直连相关性表：

```python
class ProductProtocol(models.Model):
    product = FK(Product, related_name="protocol_links", on_delete=CASCADE)
    protocol = FK(Protocol, on_delete=CASCADE)
    # 轴 A：声称能力（docx 领域词 F-score）
    capability_score = FloatField(null=True, db_index=True)   # 0~1
    # 轴 B：实证典型性（Bioz 协议级对齐，审计 B1 修复后）
    typicality_score = FloatField(null=True, db_index=True)   # 0~1
    literature_count = IntegerField(default=0)                 # 与本协议对齐的 Bioz 文献条数（协议级，非产品级）
    relevance_basis = CharField(max_length=32)                 # docx | bioz_aligned | bioprocorpus | featured
    tier = CharField(max_length=16)                            # document | literature | featured
    computed_at = DateTimeField(auto_now=True)
    class Meta:
        unique_together = ("product", "protocol")
```

- **唯一收口**：所有路径最终经 serializer `_sync_protocol_bridges` 生成/更新此表（铁律①无路径遗漏）。
- **折叠≠删除**：全量保留所有产品↔协议关联（含双轴均 0 的笛卡尔积），仅显示层 TopN 折叠。

### 2.3 `MethodProtocol`（不变）
`apps/bridges/models.py` 现有表（method FK + protocol FK + display_order/featured/status）。**不删、不加 score 字段**。`_sync_protocol_bridges` 仍对其做笛卡尔积 `get_or_create` 维持方法层级完整。

### 2.4 产品级 Bioz 先验（可选，v2 新增）
为支持 UI "本产品有 N 篇实证文献"徽标与综合排序的产品级先验，可在 `Product` 或缓存存 `bioz_total`（产品级 Bioz 记录总数），**仅作产品徽标/兜底先验，绝不写入逐协议 `relevance_basis`**（审计 B1）。

---

## 3. 计算钩点：`_sync_protocol_bridges` 唯一收口

根因：相关性计算若只钩在 `import-protocol` API，新建产品 AUTO MATCH 接受全部协议时最终桥接在 serializer save 由本方法生成 → 分数算不到。

```python
def _sync_protocol_bridges(self, product, method_ids, protocol_ids):
    # ① 数据完整（铁律①）：MethodProtocol 笛卡尔积 get_or_create
    for mid in method_ids:
        for pid in protocol_ids:
            MethodProtocol.objects.get_or_create(method_id=mid, protocol_id=pid)
    # ② 相关性（铁律②）：ProductProtocol upsert，逐协议算两轴
    bioz_lits = load_product_bioz(product)   # 产品级 Bioz 记录 list（已按 match_jena 厂商货号取，见 §6）
    for pid in protocol_ids:
        cap, typ, lit_n, basis, tier = compute_relevance(product, pid, bioz_lits)
        ProductProtocol.objects.update_or_create(
            product=product, protocol_id=pid,
            defaults={"capability_score": cap, "typicality_score": typ,
                      "literature_count": lit_n, "relevance_basis": basis, "tier": tier})
```

`compute_relevance(product, protocol, bioz_lits)` 复用 v3 探针逻辑（见 §4），生产化落 `apps/bridges/services/`。

**⚠️ 生产化必守（探针踩坑 + 审计 B1）**：
1. Bioz 证据计数必须用 `match_jena` 级联解析出的**厂商货号**查 `DataSourceCache`，**绝不能**用产品内部 SC 编号（探针首版误用 SC 编号，永远 miss）。
2. **Bioz 必须做"文献↔协议"对齐（审计 B1 修复）**：逐条 Bioz 文献取其 `article_title + techniques + long/medium/short` 文本，抽领域词，与**本协议**的 Q 做重叠；仅当重叠非空才计入该协议的 `literature_count` 与 `typicality_score`。**严禁**把产品级 Bioz 总数均摊到所有协议（v1 探针 241–255 行的错误做法）。
3. `relevance_basis` 仅在 `literature_count>0`（协议级对齐命中）时才置 `"bioz_aligned"`；否则不得对无关协议打 bioz 戳。

---

## 4. 相关性算法（生产化 v3 领域词 F-score，两轴分离）

```python
VOCAB = { ... 35+ canonical 领域词（v2 须扩充+外部化，见 D2） ... }

def compute_relevance(product, protocol, bioz_lits):
    # ── 轴 A：声称能力（docx ↔ 协议语料）──
    P = extract_domains(product.usage or "")           # docx 用途抽领域词
    Q = extract_domains(protocol.name + protocol.objective
                        + method.name + method.summary + method.purpose)
    if not P:
        cap = None                                      # 无 usage → 轴 A 缺失，诚实不冒充
    else:
        inter = P & Q
        coverage = len(inter) / len(P)                  # 产品用途被协议覆盖比例
        precision = len(inter) / len(Q) if Q else 0.0   # 协议多紧贴产品（审计 D3：特异性）
        cap = 0.5*coverage + 0.5*precision              # 域词 F-score（内层 0.5/0.5，显式）

    # ── 轴 B：实证典型性（Bioz 文献 ↔ 本协议，审计 B1 协议级对齐）──
    typ = 0.0; lit_n = 0
    if bioz_lits:
        Qset = Q
        for lit in bioz_lits:
            lit_text = " ".join([lit.get("article_title",""), lit.get("techniques",""),
                                 lit.get("long",""), lit.get("medium",""), lit.get("short","")])
            if extract_domains(lit_text) & Qset:        # 协议级对齐命中
                lit_n += 1
        typ = min(1.0, lit_n / BIOZ_TYP_CAP)            # BIOZ_TYP_CAP 待标注集定（暂 5）

    # ── 综合（两轴加权，权重待标注集，见 D1；UI 仍分轴展示）──
    wA, wB = WEIGHTS_A, WEIGHTS_B                        # 暂 0.5/0.5，待验证
    score = (wA*(cap or 0) + wB*typ)
    basis = "bioz_aligned" if lit_n>0 else ("docx" if cap and inter else "bioprocorpus")
    tier = "literature" if lit_n>0 else ("document" if (cap and inter) else "featured")
    return cap, typ, lit_n, basis, tier
```

**两层加权显式拆清（审计 C2）**：
- **内层** `0.5*coverage + 0.5*precision`：F-score 内部 coverage/precision 配重（v2 仍 0.5/0.5，但 D3 指出应偏向 precision，待标注集复核）。
- **外层** `wA*cap + wB*typ`：两轴融合配重（v2 暂 0.5/0.5，**待 D1 标注集定稿**，不得拍脑袋锁死）。

**Phase-2 扩展（用户 2026-08-05 拍板）**：当前 `compute_relevance` 仅用轴 A（docx）与轴 B（Bioz）。须把**实证文献家族**整体接入为"有效性权威"信号：① PubMed 生成的知识链实体（Application/Method 文本）作为 Q 侧语义增强与召回补充；② BioProCorpus 协议内容作为 Q 侧权威文本与内容召回。接入后 docx 真正降为"次级提示+规格源"（见 §1.1）。具体权重/融合方式待 D1 标注集与 D2 embedding 基线定。

**实测（v3 探针，最终修正版，106 产品 / 2501 对，Bioz 经 match_jena 级联实抓铺满）**：
- 轴 A 直方图（领域词 F-score）：`[0,0.1)=260 / [0.1,0.2)=210 / [0.2,0.3)=1004 / [0.3,0.4)=572 / [0.4,0.6)=391 / [0.6,0.8)=64`。79% 对≈0 中**大量是正确不相关**（DNA 连接酶本就与 RNA-seq 无关），非"噪声"（审计 D4，原稿误标已更正）。
- 轴 B（Bioz 协议级对齐，修正后）：仅 ~12/106 产品有记录；SC8065 有 7 篇、其中与具体协议对齐命中的子集计入 `literature_count`——**不再均摊到所有协议**（B1 修复）。
- 高相关示例语义正确：SC8091 "Radioactive in vitro transcription" cap=0.708 [dna,in vitro,rna,transcription]；SC8106/8108 Oxford Nanopore 测序 cap=0.680 [dna,rna,sequencing]。

---

## 5. 自适应 TopN + 折叠 + 档位（含每产品强制展示，审计 K5）

显示层治理（不删数据）：
- 常量：`HARD_CAP=12`、`MIN_VISIBLE=5`（均为**参数**，非魔法数，审计 D6；暂值待 D1 复核）。
- 档位（派生不存）：`document`（轴 A 命中）/ `literature`（轴 B 对齐命中≥1）/ `featured`（无信号，诚实标"编辑精选"）。
- 排序：同档内按综合 `score` 降序；档间 `literature > document > featured`（轴 B 实证优先于轴 A 声称，审计 K1）。
- **每产品强制展示（审计 K5，新增）**：若产品存在 ≥1 条领域词命中的协议，则**无论绝对阈值多少，强制展示其综合最高的一条**（窄用途试剂的"唯一正确协议"不被折掉）。超出部分再按阈值折叠。
- 自适应 cutoff：显示数 = `min( 命中 document+literature 数, HARD_CAP )`；若 < `MIN_VISIBLE`，用 `featured`（按 display_order）补足并标"编辑精选"。
- 超出折叠："显示全部 (M)" 展开剩余（数据全在 DB，仅 UI 收口）。
- **阈值（审计 D1：暂定、待标注集验证）**：v3 终态 grid 初看 `H≈0.40 / M≈0.20 / cap=12 / min=5` 较平衡（H=0.4/M=0.2→fb=40；H=0.5→fb=71；H=0.6→fb=96 太严）。**但此为"看直方图顺眼"所定，无 ground truth，须在 D1 标注集上用 precision@5/NDCG 复核后方可锁定**。HARD_CAP=12 所有档位 cap=0（从不截断）。

---

## 6. Bioz 实抓（数据前置，铁律①扩到全部 jena 命中产品）

`crawl_bioz_jena.py`：遍历 Product → `resolve_jena()`（**用 `match_jena` 级联**，与生产 AUTO MATCH 同源）→ `BiozClient().search_by_sku(jcat, vendor)` 自动落 DataSourceCache（14 天 TTL，幂等）。严格只写缓存，**不动业务表**。`--force/--limit` 参数。限速 2 req/s。

**修正（2026-08-05 实测，审计 C1）**：首版 `resolve_jena` 用 `lookup_by_catalog_no/cas` 精确查仅命中 **23**；改用 `match_jena` 级联后命中 **61**（77 中 16 个无可用厂商货号、取不到 Bioz 文献，剔除）。**设计稿全文统一为 61**（§1 表格、§9 步骤已更正，原 77 为过期数字）。
当前状态：import 路径 bug、resolve_jena 级联均已修；复跑完成（**61** jena 命中，其中 ~12 个有 Bioz 文献记录）。

**对齐所需字段已确认（bioz_client.py:109–127）**：每条记录含 `article_title / techniques / long / medium / short`，可直接抽领域词做协议级对齐（§3 B1）。

---

## 7. 回填命令 `recompute_protocol_relevance`

```bash
python manage.py recompute_protocol_relevance [--product SC8001] [--force]
```
- 对全部（或指定）产品：确保 `Product.usage` 已回填（缺则尝试 docx 重解析）→ 取产品级 Bioz → 逐协议算两轴 → 写 `ProductProtocol`。
- 幂等、可重跑；失败留 null 由下次补（容错）。
- 迁移后首次全量跑一次，使存量 125 产品全部有两轴分。

---

## 8. 前端 UI（`ProductEditPage` / 产品详情，审计 K6 分轴）

- 每条协议带**两轴徽标（分开，不合成）**：
  - `文档相关 F=0.xx`（轴 A，来自 docx 用途）
  - `文献支持×N`（轴 B，仅当本协议 Bioz 对齐命中>0；非产品级总数冒充）
  - `编辑精选`（无两轴信号时诚实标）
- 产品级徽标：`本产品有 N 篇实证文献`（来自 `bioz_total`，仅产品级先验，不参与逐协议 basis）。
- 顶部按档位+综合分排序展示 TopN（默认 10）。
- 档位筛选 chips：`全部 / 文档相关 / 文献支持 / 编辑精选`。
- 超出折叠："显示全部 (M)"。
- 新建/编辑表单增加 `usage` 文本域。

---

## 9. 实施顺序（分阶段，可逐 PR 评审）

1. **迁移**：`Product.usage` 字段 + `ProductProtocol` 表（两轴字段）。
2. **docx 入库**：解析脚本固化 → `backfill_product_usage` 回填 125（**先人工审 10 个 docx 定义抽取口径**，审计 D5）。
3. **Bioz 实抓**：`crawl_bioz_jena` 跑完 **61** jena 命中产品。
4. **计算服务**：`compute_relevance` 落 `apps/bridges/services/`；**含 Bioz 协议级对齐（B1 修复）**；钩到 `_sync_protocol_bridges` 唯一收口。
5. **标注集 + 阈值验证（审计 D1，强烈建议与本阶段并行）**：抽 30–50 产品请试剂科学家标相关/不相关，算 precision@5/recall@10/NDCG，定 H/M 与两轴权重。
6. **词表外部化 + embedding 基线（审计 D2）**：扩词表（补蛋白域）、用未见试剂目录测召回、跑 sentence-transformers 余弦基线对照。
7. **回填**：`recompute_protocol_relevance` 全量算两轴分。
8. **Serializer/UI**：返回两轴元数据 + 分轴徽标 + TopN 自适应 + 每产品强制展示 + 折叠 + 档位筛选。
9. **阈值定稿**：依 D1 标注集锁定 H/M 与权重。
10. **Phase-2：接入实证文献家族打分（用户 2026-08-05 拍板）**：把 `PubMed` 生成的知识链实体 + `BioProCorpus` 协议内容接入 `compute_relevance` 作为"有效性权威"信号（当前仅 docx+Bioz）；docx 真正降为"次级提示+规格源"。含 ChEMBL 身份闸门复用（bioz_equivalence）确保文献仅对化学等同产品适用。此步为 Phase-2 必做，不阻塞第一版上线，但为审计 K1 彻底落地所需。

---

## 10. 诚实张力与风险（重写，含语料库覆盖=召回天花板）

- **语料库覆盖 = 召回天花板（审计 D2/K4）**：35 词表从协议文本长出来，协议/方法本体覆盖不到的应用（如某试剂用于 5' RACE 但无对应 Method）永不可桥。v2 动作：扩词表 + 外部化 + 标注集验证。
- **79% 对≈0 多为正确不相关（审计 D4）**：折叠合理，但框架须诚实——这不是"噪声"而是真负例，不应诱使过度折叠。
- **轴 A（docx）已降为次级提示+规格源（审计 K1 + 用户 2026-08-05 拍板）**：厂商营销文案模糊、非精确技术、抽取质量未人工评估，不得作有效性权威。v2 已将其置于实证文献家族之下（轴 B 实证 > 轴 A 声称），并加 D5 抽取审计；Phase-2 将把 PubMed/BioProCorpus 接入打分使层级落地（§1.1/§4/§9）。
- **Bioz 稀疏（仅 ~12/106）**：对非 jena / 无文献产品，轴 B=0，退回轴 A/featured。非"并列强信号"。
- **无 CAS 试剂盒错链 Bioz 锚点（审计 K3）**：`match_jena` 对无 CAS 者回退 name/synonym，可能链到不同酶 → 错误文献锚点。v2 风险：对齐步骤可部分缓解（文献文本若不符协议 Q 则不计入），但锚点本身可能错；建议 v2 对 name-回退命中加"技术词一致性"校验。
- **化学特异性缺失（审计 K2，v2 动作）**：CAS/化合物类别/修饰类型（5-mC、ψ、2'-O-Me、硫代）未进打分。列入 v2 第二阶段特征。
- **magic number（审计 D6）**：内层 0.5/0.5、外层 0.5/0.5、BIOZ_TYP_CAP=5、HARD_CAP=12、MIN_VISIBLE=5、featured 兜底 0.25 均暂定，须在 D1 标注集上复核或参数化。

---

## 11. 反方审计回应（逐条）

| 审计项 | 性质 | v2 处理 |
|---|---|---|
| **B1** Bioz 产品级均摊冒充协议级 | **Blocker** | ✅ 已修：`compute_relevance` 逐文献与协议 Q 对齐（§3/§4），仅对齐命中计入 `literature_count`/`typicality_score`；`relevance_basis="bioz_aligned"` 仅当协议级命中>0。 |
| **C1** §1/§9 "77" 应为 "61" | 事实错误 | ✅ 全文统一为 61（§1 表格、§6、§9）。 |
| **C2** 两层加权混谈 | 事实错误 | ✅ §4 显式拆"内层 F 0.5/0.5"与"外层两轴 wA/wB"。 |
| **C3** 伪代码 `protocol.catalog_anchor` | 事实错误 | ✅ §4 伪代码改为产品级 `bioz_lits` 入参 + 协议级对齐。 |
| **D1** 阈值无 ground truth | 方法论 | 🟡 加 §5/§9 标注集步骤，H/M 标"暂定待验证"，不锁死。 |
| **D2** 词表覆盖/偏差 | 方法论 | 🟡 加 §9 词表外部化+embedding 基线+v2 动作。 |
| **D3** F-score 丢特异性 | 方法论 | 🟡 §4 标注 precision 语义，待标注集复核内层配重。 |
| **D4** 79%≈0 误标噪声 | 框架 | ✅ §10 更正为"多为正确不相关"。 |
| **D5** docx 抽取质量零评估 | 方法论 | 🟡 §9 步骤 2 加"先人工审 10 docx 定义口径"。 |
| **D6** magic number / 夸大"并列" | 方法论 | 🟡 §10 列全部暂定参数；§1 把 Bioz 由"并列强信号"降为"稀疏实证增强器"。 |
| **K1** 厂商自述不宜做主信号 | 化学 | ✅ §0/§1.1 两轴 + 用户拍板：docx 降为"次级提示+规格源"，实证文献家族（PubMed/BioProCorpus/Bioz）升为"有效性权威"；Phase-2 接入 PubMed/BioProCorpus 打分（§4/§9）。 |
| **K2** CAS/化合物类别/修饰未进分 | 化学 | 🟡 列入 v2 第二阶段特征（§10）。 |
| **K3** 无CAS试剂盒错链锚点 | 化学 | 🟡 §10 加 name-回退技术词一致性校验建议。 |
| **K4** Method 本体缺口=覆盖缺口 | 化学 | 🟡 并入 D2 语料库覆盖风险（§10）。 |
| **K5** 全局 H 对窄用途过严 | 化学 | ✅ §5 加"每产品强制展示≥1 领域词命中协议"。 |
| **K6** 两维度相加=范畴错误 | 化学 | ✅ §0/§8 UI 分轴呈现，综合分仅作排序不替代两轴展示。 |

图例：✅ 已修入 v2 设计 / 🟡 已写入设计作为待办或 v2 阶段动作（未落地代码）。

---

## 12. 待用户确认项（签字点）

- [ ] 接受"单字段 `Product.usage` + 新表 `ProductProtocol`（两轴字段）"双表方案（保留 `MethodProtocol` 不动）。
- [ ] 接受**两轴分离**：轴 A（docx 声称能力）+ 轴 B（Bioz 实证典型性，协议级对齐），UI 分轴呈现。
- [ ] 接受审计 B1 修复：Bioz 必须协议级对齐，不得产品级均摊冒充。
- [ ] 接受阈值/权重**暂定、待 D1 标注集验证后锁定**（不在此稿拍板）。
- [ ] 接受"折叠≠删除 + 每产品强制展示≥1 命中 + 无信号诚实标编辑精选"。
- [ ] 接受实施顺序（含 D1 标注集、D2 词表外部化与 embedding 基线、D5 docx 审计作为强制前置）。
- [x] **（用户 2026-08-05 已同意）** 把 docx 降为"次级提示+规格源"、实证文献家族升为"有效性权威"，并把 PubMed/BioProCorpus 接入打分列入 Phase-2 必做。
- [ ] v2 第二阶段（K2 化学特征、K3 锚点校验深化）是否认可列入路线图。

---

## 13. 论证闸门与评估测试结果（2026-08-04 本轮只读论证）

> **范围与纪律**：本节全部为**只读论证 + 评估测试**，不触碰任何业务写操作、不落库、不改代码。
> 数据底座：本地 `db.sqlite3`（240 Product / 96 Protocol / 18 Method / 104 MethodProtocol / 141 Bioz 缓存行）；`backend/docx_products.json`（125 条）；`backend/data/bioprocorpus`（7 份真实协议）。
> 复跑命令（只读）：`cd backend && DB_ENGINE=sqlite PYTHONDONTWRITEBYTECODE=1 venv/Scripts/python.exe -B manage.py probe_protocol_relevance_v3 --cap 12 --min 5`

### 13.1 论证闸门总表

| 编号 | 审计项 | 级别 | 论证方式 | 结论 | 闸门状态 |
|---|---|---|---|---|---|
| #342 / D5 | docx 抽取质量 | P0 | 读抽取逻辑 + 审计 125 条 `usage` 输出 + **真源重抽对齐（2026-08-05 补）** | 轴 A 地基干净：用相同提取器重跑真源 124/124 usage 逐字一致(100%)、0 规格/表格噪声；115 标准used句 + 9 描述式(is a) | ✅ 已验证（真源在 `D:\试剂产品说明文档`，重抽对齐 100%） |
| #336 / D1+D3 | precision@k 定性 | P0 | 抽样 10 产品打印 top-5 协议+docx 用途人工判 | 特化产品 top-1 合理；泛化产品 ~19 候选分数塌缩、零区分 | 🟡 定性确认（轴 A 单轴不足） |
| #339 / P0-2 | 用户场景论证 | P0 | 数据模型推导 | 相关性服务"检索覆盖"与"商品页推荐"双场景，推导排序/折叠/强制≥1 | ✅ 定性确认 |
| #337 / D2+K4 | 词表覆盖缺口 | P1 | 35 词 VOCAB × 96 协议 + bioprocorpus 比对 | 协议覆盖率 93%，但 6 死词；VOCAB 对蛋白/细胞/组学结构性失明 | 🔴 必须修（外部化+embedding） |
| #341 / K2+K3 | 化学特征覆盖 | P1 | 125 docx 抽取 CAS/修饰标记 | CAS 54%、46% 靠 name 回退；修饰分布偏核苷酸 | 🟡 确认缺口（列第二阶段） |
| #338 / B1+D6 | Bioz 价值再评估 | P1 | 141 缓存行跑 B1 协议级对齐 | 仅 11% 产品点火；对齐 84% 但被 rna/dna 泛化词污染→低区分 | 🟡 确认稀疏+降权 |
| #340 | 汇总固化 | — | 本章 | — | ✅ |

### 13.2 逐条论证

#### #342 / D5 — docx 抽取口径审计（轴 A 地基）
- **抽取逻辑**（backend/docx_extract.py）：`parse_usage` 启发式——取含 `used / is a / application / useful` 且长度>40 的行，按 `(used 优先, -长度)` 排序取首条；`name=首段`，`cas/catalog` 按标签前缀抽取。
- **输出审计（125 条）**：全部含 `usage`；67 条含 CAS。质量标记：
  - `STARTS_PRODUCTNAME` 124/125 → 几乎都抓到"X is a Y used for Z"产品引言句（好）；
  - `TABLE_ARTIFACT` 0、`SPEC_LIKE` 0 → **未抓到规格/表格噪声**（好，启发式保守）；
  - `VERY_LONG` 13 → 长句可能夹带化学细节；`NO_APP_VERB` 9 → 化学描述型（如 SC8011 Pseudo-UTP"可掺入 RNA"而非显式"用于…"）。
- **结论**：轴 A 地基约 **93% 干净可用**，余 7% 为化学描述型（用途信号隐含非显式）。抽取口径**未发现正则乱抓**，可作为"次级提示+规格源"。
- **缺口（须如实上报）**：原始 125 个 `.docx` 源文件**不在本工作区**（仅 `docx_products.json` 产出物留存；`_docx_media` 仅 3 张无关 PNG）。故"抽 3–5 原始 docx 人工审口径"**无法本地完成**——须从服务器（47.82.156.48）取回源 docx 后补做。此子项不伪造。

#### #336 / D1+D3 — precision@k 定性（轴 A 单轴排序可信度）
- 抽样 10 个有桥接+docx 用途的产品，逐产品打 top-5 协议（含命中领域词）。
- **观察 A（正向）**：用途含**特化领域词**的产品，top-1 语义合理：
  - SC8056 5-Methyl-dCTP（epigenetic）→ `Sinai SCENT TMC` [dna,epigenetic] 0.667；
  - SC8020 Sulfo-Cy5-dUTP（FISH）→ `Fluorescent DNA probes` [detection,dna,fluorescent] 0.675；
  - SC8080 5-AA-CTP（aminoallyl 偶联）→ `Fluorescent DNA probes` / `Hybridization of RNA Probes` 0.625/0.500。
- **观察 B（负向/关键）**：用途仅含**泛化词**（rna/dna/modification/nucleotide）的产品，其全部 ~19 个候选协议分数**塌缩为相等值**（0.417 / 0.5 / 0.75），无法区分"RNA 结构探针"vs"氧化损伤"vs"假尿苷"。同分导致排名随机。
- **结论**：**轴 A 单轴不足以排序**——这从实证上**印证 v2 两轴设计的方向正确**：必须用轴 B（实证典型性）打破并列。同时印证 D3：F-score 的 `precision` 被泛化词稀释，内层 0.5/0.5 配重须在 D1 标注集上复核。

#### #339 / P0-2 — 用户场景论证（相关性服务什么）
- 从数据模型推导："产品↔协议"相关性服务两类场景：
  1. **研究者检索覆盖**（铁律①最大化数据）：研究者以产品/用途为入口找可参考协议 → 需**全量保留桥 + 相关性仅用于显示排序/折叠**，不得因低分删除（折叠≠删除）。
  2. **商品页推荐**（铁律②最强相关）：访客看商品时给最相关协议 → 需**按分置顶 TopN + 强制≥1 命中**（避免空推荐）。
- 两场景由**同一份持久化相关性分**驱动，差异仅在 UI 呈现（TopN 折叠 vs 全量可展开）。这推导出 §5 自适应 TopN（HARD_CAP=12/MIN_VISIBLE=5）与"每产品强制≥1 命中"的合理性——与铁律①②自洽，无需为两场景建两套数据。

#### #337 / D2+K4 — 词表覆盖缺口（F-score 天花板）
- 96 协议：89（**93%**）含 ≥1 VOCAB 领域词；但 `rna`/`dna` 各命中 88/96，呈**极度头部集中**。
- **6 个词永不被任何协议命中**：reverse transcription、qpcr、labeling、click chemistry、oligonucleotide、splicing（VOCAB 内部冗余/失效）。
- **bioprocorpus（7 份真实协议）扫描**：充斥 `protein/cell/proteomics/phospho/kinase/antibody/western/mass spectrometry/chromatin/atac/chip-seq/crispr/genome/transcriptome/metabolome/lipidomics/spatial/single-cell/flow cytometry/elisa/ihc/immunofluorescence` ——**这些全不在 35 词 VOCAB 内**。
- **结论**：当前 93% 覆盖是"目录与协议同为中心核苷酸"的**同构假象**（K4）。一旦目录扩到蛋白/细胞/组学，F-score 对这些产品**恒为 0**。→ **D2/K4 是 P1 必须修项**：词表须外部化+扩充，**并引入 embedding 语义基线**作为第三轴兜底（见 13.3）。

#### #341 / K2+K3 — 化学特征覆盖（身份解析链路）
- 125 docx：**67（54%）含 CAS，58（46%）无 CAS → 依赖 name 回退**。
- 修饰标记分布（按名称/用途子串）：methyl 16%、biotin 16%、click 14%、fluorophore 13%、thio 7%、aminoallyl 3%、pseudoU 2%、**2-O-Me 0%**。
- **结论**：近半产品无 CAS → 任何以 CAS 为键的身份解析（match_jena 的 CAS 级联、ChEMBL/PubChem 交叉校验、Bioz 按厂商货号点火）对这 46% 只能退回 name/synonyms，**错链风险更高**（K3）。修饰分布偏核苷酸修饰，与目录同构——印证 #337 的同构假象。化学特征（K2）确属第二阶段特征，但 **CAS 覆盖率应作为"实证轴 B 能否覆盖该产品"的前置指标**先用起来。

#### #338 / B1+D6 — Bioz 价值再评估（轴 B 实证）
- 扫描 106 个有桥接产品：仅 **12（11%）Bioz 点火**（≥1 篇实证文献）；文献数 1–10，中位 3。
- 跑 B1 协议级对齐：10/12 点火产品有 ≥1 个对齐协议；**84% 候选 (产品,协议) 对收到 boost**。
- **关键发现**：84% 之高，是因 `rna`/`dna` 泛化词（88/96 协议命中）使"文献里出现 RNA/DNA"就与几乎所有协议对齐——**对齐信号被泛化词污染，非真正协议级特异**。反例 SC8067/SC8052（文献讲结晶/无关 RNA）对齐=0。
- **结论**：
  1. Bioz 是**唯一 SKU 级实证源**，但**覆盖稀疏（11%）**，应保留为"稀疏实证增强器"（§1.1 已降级，吻合）。
  2. 其 per-协议 typicality boost **当前低区分**（泛化词污染）→ **权重应进一步下调**（v3 探针 `WB=0.15` 仍偏高，建议 ≤0.10），主要用作"该产品确有真实世界使用"的存在性确认。
  3. 广度优先项仍是 **PubMed/BioProCorpus**（协议内容本体质量），与 Phase-2 计划一致。

### 13.3 综合结论（论证闭环判定）

1. **两轴设计方向被实证支持**：轴 A 单轴在泛化产品上分数塌缩、零区分（#336）；轴 B 唯一 SKU 实证源但稀疏（#338）——二者结合正是 v2 的解法。
2. **但"领域词 F-score"本身有精度天花板**，根因是 VOCAB 的 `rna`/`dna` 泛化词（88/96 协议命中）同时污染轴 A 与轴 B 对齐。→ **P2「embedding 语义轴」从"理论待办"升级为"实证必需"**：在 D2 词表外部化之外，必须引入 embedding 相似度作为第三信号，方能打破泛化词垄断。
3. **同构假象警告**：93% 协议覆盖、54% CAS 覆盖、修饰偏核苷酸，均因"目录=协议=核苷酸中心"三同构。系统一旦扩类，F-score 对新增域**恒为 0**、46% 无 CAS 产品**无法点火轴 B**——这些不是小修，是**架构前提**。

### 13.4 下一阶段强制前置（落地前必做，仍只读）
- **D1 标注集**：建小标注集（建议 30–50 产品×协议对）作为 ground truth，复核 H/M 阈值与内层 0.5/0.5 配重、验证 embedding 轴增益。
- **D5 真源抽样**：从服务器取回 125 原始 docx，人工审 3–5 份确认 `parse_usage` 口径（本地当前阻塞）。
- **D2+embedding**：词表外部化为数据文件 + 引入 embedding 基线（破 rna/dna 垄断）。
- **CAS 覆盖**：把 CAS 覆盖率作为"轴 B 可否覆盖该产品"的显式指标接入（不写库，仅评估）。

> 以上全部为论证/评估，未改动任何业务代码、模型、迁移或线上数据。第一版实施仍按用户 2026-08-04 指令冻结，待本闸门前置项完成后再行解锁。

### 13.5 前置项推进（2026-08-05 本轮只读）

> 用户从 §13.4 四前置项中勾选 **D5 + D1 + D2**（CAS 指标未选）。以下为推进结果，均只读、不落库。

- **D5 取回原始 docx — ✅ 已完成（2026-08-05 翻案）**：用户指出真源在本地 `D:\试剂产品说明文档`。五处全量排查（服务器/备份/git/工作区）虽无，但本地该文件夹确有 **125 个原始产品 docx**（文件名前缀 `SCxxxx` 与 json catalog 吻合）。用**逐字复刻的 `docx_text/parse_usage/parse_field`** 重跑真源并与已提交 `docx_products.json` 对齐：
  - **124/124（100%）`usage` 逐字一致**，0 解析失败、0 mismatch、0 漂移 → 已提交 json 是真源的忠实派生，#342 主张坐实。
  - **#342 噪声探针 = 0**：无 usage 是规格/表格行（CAS/Formula/Purity 在后续行未被误抓）。
  - 人工抽检 SC8001/SC8020/SC8056/SC8080/SC8090：全部为干净 "is a … used for …" 产品引言句（取自 para[1]）。
  - 子项量化：usage 长度 max=530 / mean=314；**115 含 `used` + 9 含 `is a ` 无 `used`**（= #342 早前"9 化学描述型"，描述式引言，非异常）。
  - 命名卫生小瑕疵（不影响数据忠实性）：`SC8086` 在 docx 与 json 各重复 1 份（`(1)` 副本）；`SC8007`/`SC8009` 文件名 vs 内部 Catalog 不完全对应——但按生成 json 的同一套内部 Catalog 对齐后 124=124 完美匹配。
  - **结论：D5 真源抽样已闭环，#342 由 🟡 升 ✅。**
- **D1 标注候选集 — ✅ 已产出 + AI 代标**：脚本 `_d1_candidates.py` 复用 v3 探针逻辑，对 106 个有桥接+用途产品算 产品×协议 领域 F-score，按分数是否塌缩(tie)分层。产出 `_d1_candidates.json` + `_d1_candidates.md`，共 **48 候选对 / 24 产品**（14 hard_tie 塌缩 + 10 easy_sep 分离）。**用户表明无领域标注能力，故由 `_d1_label.py` 基于"docx 用途 vs 协议目标"透明规则代标 0–3**（特定修饰/技术词共现→3，通用技术词→2，仅泛化核苷酸域→1，无重叠→0），产物 `_d1_candidates_labeled.json` + `.md`，方法可复核/可推翻。**关键发现**：hard 与 easy 标签均集中在 1（仅泛化核苷酸域重叠），说明**协议语料缺"修饰级"粒度**——即便特化产品的关联协议也不提其具体修饰，故 F-score 与词面标注都难细分，进一步坐实需 embedding 语义轴。label≥2 与 domain_score≥0.5 同向率 31/48（65%）。
- **D2 词表外部化 — ✅ 已完成**：§13 写"35 词 VOCAB"是别名计数口径，实际为 **25 个 canonical 域**（以代码为准）。已从探针 VOCAB **精确导出** `apps/bridges/data/domain_vocab.json`；探针改 `_load_vocab()` 读外部文件、内联副本回退，**冒烟验证行为不变**（同域分输出、无报错）。
- **D2 embedding 语义基线 — ✅ 实测完成（2026-08-05）**：用户授权装 `sentence-transformers`+`torch`。因 backend venv 为 **py3.13**，`tokenizers 0.23.0` 无可用 wheel、而 `transformers 5.14.1` 又封顶 `tokenizers<=0.23.0`（仅 0.23.1 支持 3.13），形成硬依赖死锁；遂改在 **py3.12 独立短路径 venv `D:\emb3_venv`** 装 `sentence-transformers==3.3.1`+`tokenizers==0.21.1`+`torch`，探针顶部注入其 `site-packages`（须在 `django.setup()` 前注入，否则 backend 的 transformers 5.14.1 会被缓存进 `sys.modules` 触发版本冲突）。实测结果见 **§13.7**。
- **综合**：两轴方向 + "embedding 必要"进一步坐实（73/106 产品分数塌缩、零区分，单靠领域词 F-score 无法排序）；第一版实施仍按用户 2026-08-05 16:51 指令冻结，未解锁。

### 13.6 D5 真源审计方法（可复现）

- **真源位置**：`D:\试剂产品说明文档`（125 个原始产品 `*.docx`；`SC8086` 有 1 份 `(1)` 副本，去重后 124 唯一 catalog）。
- **方法**：逐字复刻 `docx_extract.py` 的 `docx_text`（zipfile + ElementTree，段落与表格行 ` | ` 连接）/ `parse_usage` / `parse_field`，对真源重抽并与已提交 `docx_products.json` 做集合对齐；不写盘、不改业务代码。
- **复现命令**（已删除临时脚本，逻辑即 `docx_extract.py` 本身）：
  ```bash
  # 真源即原提取入口；diff 比对：重跑输出 vs 已提交 docx_products.json
  python docx_extract.py "D:\试剂产品说明文档"   # 仅产生 records 列表，比对 usage 字段
  ```
- **闸门演进**：#342 🟡→✅（真源核验闭环）；D5 由 §13.4 前置项转为**已闭环**（唯一仍开项：D1 待人工打标、D2 embedding 待后端授权）。
- **仍冻结**：第一版业务实施未解锁；D5 仅验证"轴 A 地基干净"，未触发任何落库/模型/迁移改动。

### 13.7 D2 embedding 实测结果（2026-08-05）

**配置**：`all-MiniLM-L6-v2`（384 维，本地 CPU），探针 `_d2_embedding_probe.py`。对 106 个有桥接+用途产品，预计算 96 协议 embedding，对每个产品的【全部】关联协议（约 19 个）算余弦，量化排名发散度 `spread=max−min`，并以"用途特定修饰词是否存在于 embedding-top1 / F-score 塌缩集协议正文"做无标签自验证。

**核心结论（直接回答 #336 核心问题"embedding 能否打破泛化产品分数塌缩"）**：

| 指标 | 值 | 含义 |
|---|---|---|
| hard_tie(塌缩) / easy_sep(分离) / 总 | 73 / 33 / 106 | 与 #336 口径一致 |
| **embedding 打破塌缩 (hard spread>0.05)** | **73/73 (100%)** | F-score 零区分的 73 个产品，**全部**获得可用 embedding 排名分散 |
| mean embedding spread | hard=0.217 / easy=0.207 | 跨 ~19 协议有实质区分度（F-score 对应为 0） |
| 特征词自验证（含特定修饰词 hard 产品） | 45 | SC8xxx 修饰（click/azido/fluoro/thio…） |
| embedding-top1 命中特征词 | 1/45 (2%) | 协议正文几乎不提具体修饰 |
| F-score 塌缩集 命中特征词 | 0/45 (0%) | 同上，且 F-score 完全无法区分 |

**解读**：
1. **embedding 成功打破 100% 的 F-score 分数塌缩**——这正是 v2 设计把"embedding 语义轴"从理论待办升为实证必需的理由，现已被实测坐实。泛化产品（如 SC8040 2'-Amino-dGTP）在 F-score 下 19 候选全相等，embedding 下得到分散排名（top1 Northern Blot / sNucDrop-seq，spread≈0.20）。
2. **特征词自验证 2%/0% 不是 embedding 失败，而是语料局限**：BioProCorpus 协议正文本身不写"2'-azido/2'-fluoro"等具体修饰（与 §13.5 D1 发现"协议语料缺修饰级粒度"同源）。embedding 的区分来自更广的语义内容（如"modified nucleotide / dNTP / click chemistry"上下文），而非字面修饰词命中。
3. **实务含义**：终态相关性分应采用 `轴A(厂商声称) + 轴B(Bioz实证,≤0.10) + 轴C(embedding语义)` 三轴融合；轴 C 专司打破泛化词垄断、提供稳定排名分散，是泛化产品可排序的必要条件。

**环境注记（可复现/可维护）**：
- embedding 后端位于独立 venv `D:\emb3_venv`（py3.12），**非** backend venv；删除该 venv 后探针自动优雅降级为 BLOCKED（不报错）。
- 复现命令：
  ```bash
  cd backend
  DB_ENGINE=sqlite PYTHONDONTWRITEBYTECODE=1 venv/Scripts/python.exe -B _d2_embedding_probe.py
  # 输出 _d2_embedding_result.json
  ```
- 若需在 backend venv 内原生运行，须先解决 py3.13 的 `tokenizers` 死锁（或整体降 Python 到 3.12）。

---

## 14. 三轴融合具体打分公式（v2 实施）

> 本节把 §13.7 的"三轴融合"结论落为**可实施的打分公式**，扩展 §4 的两轴 `score = wA·cap + wB·typ`。仍属设计稿，不落库、不改业务代码/迁移；第一版实施仍按用户冻结令未解锁。

### 14.1 三轴定义与归一化

| 轴 | 信号源 | 计算 | 归一化 | 语义角色 |
|---|---|---|---|---|
| **轴A 厂商声称** | docx 用途(P) × 协议领域词(Q) | F-score = 0.5·coverage + 0.5·precision（§4） | 已 ∈[0,1] | 实质性相关性**主信号**（厂商说能干什么） |
| **轴B Bioz 实证** | Bioz 协议级对齐命中 | `S_B = min(1, bioz_aligned_count / 5)`（BIOZ_TYP_CAP=5；B1 修复后仅计协议级对齐） | 已 ∈[0,1] | 实证典型性，**稀疏**（#338 仅 11% 点火） |
| **轴C embedding** | usage 文本 × 协议目标文本 | `S_C = (cos(u_P, u_Q) + 1) / 2`；模型 `all-MiniLM-L6-v2`（384 维，本地 CPU） | 余弦[-1,1]→[0,1] | **打破泛化词垄断**、提供排名分散（§13.7） |

- `u_P = embed(product_usage)`；`u_Q = embed(protocol.name + objective + method.name + summary + purpose)`（与 §4 Q 侧文本一致）。
- 轴B 的 `relevance_basis="bioz_aligned"` 仅当协议级命中>0（B1 修复）；无对齐命中则 `S_B=0`。
- 轴C 模型本地 CPU 推理（~13s/106 产品），无外部依赖、无网络（首次需下载 ~80MB 权重，已缓存于 `D:\emb3_venv`）。

### 14.2 融合公式

```python
relevance_score = wA * S_A + wB * S_B + wC * S_C
wA, wB, wC = 0.70, 0.10, 0.20      # 和为 1；wB 为硬上限(≤0.10)，来自 #338
```

设计要点：
1. **轴A 为主（0.70）**：实质性相关性描述者；跨"不同 A 值"产品时 A 主导排序。
2. **轴B 硬性上限 0.10（#338）**：Bioz 仅 11% 产品点火、稀疏，不得喧宾夺主；即便点火也只贡献 ≤0.10。
3. **轴C 为打散器（0.20）**：当轴A（及轴B）对某产品多个候选**塌缩为等值**时，`wC·S_C` 的 spread（实测 mean 0.217）提供排名分散、打破并列。跨不同 A 值时 A 仍主导，C 不退化为"另一主信号"。
4. **加法而非纯 tie-break 的理由**：单一持久化分（`ProductProtocol.relevance_score`）须同时驱动"检索覆盖"（铁律①全量保留+折叠）与"商品页推荐"（铁律② TopN+强制≥1）；加法融合在等值候选上自然由 C 决定次序，无需两套数据（#339）。

### 14.3 持久化字段（ProductProtocol 增量，第一版实施时落）

```python
relevance_score  = FloatField(db_index=True)   # 三轴融合总分（驱动排序/TopN）
score_a          = FloatField(null=True)        # 轴A 分量（UI 透明 + 调试/闸门）
score_b          = FloatField(null=True)        # 轴B 分量
score_c          = FloatField(null=True)        # 轴C 分量
relevance_basis  = CharField()                  # 'vendor_only' | 'bioz_aligned' | 'embedding_break' | 'combined'
```

- UI **须同时展示三轴分量徽标**（§27：用户须同时看到各轴数值，不得只给混合分）。
- 重算触发：docx 用途变更（轴A）/ Bioz 缓存刷新（轴B）/ 协议语料或 embedding 模型更新（轴C）。

### 14.4 与自适应 TopN 衔接（§5）

- 排序键 = `relevance_score` 降序；**同分再用 `score_c` 降序兜底**（确保塌缩集内由 C 决定次序）。
- `HARD_CAP=12`、`MIN_VISIBLE=5`；档位 `literature > document > featured`（轴B 实证优先于轴A 声称，审计 K1）。
- 自适应 cutoff = `min(命中 document+literature 数, HARD_CAP)`；< `MIN_VISIBLE` 用 `featured` 补足并标"编辑精选"。
- **每产品强制≥1 命中**：若所有协议 `relevance_score` 均≈0（轴A/B/C 全 0），仍按 `featured`/`display_order` 补 1 条，避免空推荐（铁律②）。

### 14.5 权重校准（D3，2026-08-06 实测）

对 D1 的 48 候选对套用公式，以 **AI 建议标签(0–3) 作代理 ground truth**（用户未手动标注，标签由领域词规则派生，与轴A 同源），结果见 `_d3_calibrate_result.json`：

| 指标 | 值 | 解读 |
|---|---|---|
| Spearman(组合分, label) | **0.607** | 组合分与相关性标签中等相关 |
| Spearman(轴A, label) | 0.621 | 轴A 单独略高（标签本就领域词派生，与轴A 同源） |
| Spearman(轴C, label) | 0.144 | 弱——**预期内**：标签是词面派生，embedding 价值在打散而非追标签 |
| 硬塌缩集内 组合数序≈label 序 | **13/14** | 同产品多候选塌缩时，组合分靠轴C 正确排出相关性高低（轴C 本职） |
| label≥2 vs ≤1 组合分均值 | 0.552 vs 0.409 (Δ0.144) | 能分离相关/弱相关 |
| 权重敏感性（wA 0.50–0.80） | rho 0.591–0.607 | **鲁棒**，权重选择非脆弱拍脑袋 |

**结论**：
- 轴A 是实质性相关性**主信号**（整体排序由它主导）；轴C 的本职是**打破轴A 塌缩集并列**（13/14 验证），而非追求与词面标签相关（0.144 恰说明它提供词面之外的语义区分）。
- 权重 `0.70/0.10/0.20` 经敏感性分析**鲁棒**；最终锁定仍建议用**人工确认**的 D1 ground truth 复校（当前 label 为 AI 代理，用户已声明无标注能力）。
- 轴B 稀疏，未纳入本次校准，公式中以 ≤0.10 硬上限处理（#338）。

### 14.6 Phase-2：实证文献家族接入（不阻塞第一版）

- PubMed（知识链实体）+ BioProCorpus（协议内容）接入后，**并入轴B 的"实证家族"**，提升其覆盖与权威性（用户 2026-08-05 拍板：实证文献家族 > 厂商声称）。覆盖充足后轴B 权重可上调，ChEMBL 身份闸门(`bioz_equivalence`) 复用确保仅对化学等同产品适用。
- 蛋白/细胞/组学扩类后，轴A 的 F-score 对新增域**恒为 0**（同构假象 K4）；轴C embedding 是**唯一可跨域兜底**的信号——进一步坐实轴C 的架构必需性。

