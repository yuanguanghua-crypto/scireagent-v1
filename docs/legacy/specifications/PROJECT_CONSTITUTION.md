# SciReagent Project Constitution

**Status:** Frozen — Supreme Authority
**Priority:** Overrides ALL prior documents
**Effective:** V1.2 FINAL and beyond

---

# North Star

> 在不推翻现有 Django5.1 + DRF + Vue3 + Vite 架构、不重构核心数据库的前提下，将网站从产品目录网站升级为面向未来AI生态下、以研究场景驱动（Research Intent Driven）、以科研知识赋能（Knowledge-Enabled）、最终促进科研试剂实质性销售（Scientific Commerce）的平台。

## Vision

> Build an AI-Native, Research Intent Driven, Knowledge-Enabled Scientific Commerce Platform.

## Mission

> Transform scientific knowledge and research workflows into product discovery, trust building, and commercial conversion.

---

# Project Identity

## We Are NOT

- ❌ 科研百科网站
- ❌ 知识图谱平台
- ❌ Neo4j 项目
- ❌ AI Agent 项目
- ❌ SEO 内容农场
- ❌ 电商重构项目

## We ARE

> **Research Knowledge-Enabled Scientific Commerce Platform**

```
Research Intent
      ↓
Application
      ↓
Method
      ↓
Protocol
      ↓
Product
      ↓
SKU
      ↓
RFQ / Order
```

**Knowledge 是手段；Commerce 是目的。**

---

# Three Supreme Principles (Constitution)

## Principle 1: Knowledge Serves Commerce

任何新功能必须回答：

> 它是否提升：
> - 产品发现率（Discovery）
> - 信任建立（Trust）
> - RFQ 率（Conversion）

否则：**禁止进入 Phase 1。**

## Principle 2: Evolution, Not Revolution

**禁止：**
- 重构核心数据库
- 更换技术栈
- 重写前后端

**允许：**
- 增量 API
- 增量字段
- 增量组件
- 增量 Service

## Principle 3: Agent-Ready, Not Agent-Building

**Phase 1 只要求：**
- 结构化数据
- API 可消费
- JSON-LD 预留
- 实体关系清晰

**禁止：**
- Neo4j
- GraphRAG
- Agent Orchestration
- 动态图谱

---

# Phase 1 Scope (Frozen)

## Objective 1: Homepage Upgrade

**从：**
```
Hero → Featured Products
```

**升级为：**
```
Hero → Research Goals → Featured Solutions → Featured Products → References → Custom Synthesis CTA → Knowledge Preview (static)
```

**目的：** 增加 Research Discovery

## Objective 2: Product Page Upgrade

**从：**
```
Product → SKU
```

**升级为：**
```
Product → Applications → Methods → Protocols → References → FAQ → Related Products → Compatibility
```

**目的：** 建立 Scientific Trust

## Objective 3: API Upgrade

**新增：**
```
GET /api/v1/products/<id>/detail/
```

**扩展：**
```
GET /api/v1/site/home/
```

**目的：** 统一数据聚合

## Objective 4: Data Organization Upgrade

**建立：**
```
Application → Method → Protocol → Product
```

**导航关系。**

**目的：** 支持 AI Discovery

---

# Out of Scope (Explicitly Forbidden in Phase 1)

## Graph
- ❌ Neo4j
- ❌ Cytoscape.js
- ❌ Dynamic Graph API

## Search
- ❌ ElasticSearch
- ❌ Vector DB
- ❌ RAG

## Frontend
- ❌ Nuxt
- ❌ SSR 重构
- ❌ 微前端

## Backend
- ❌ FastAPI 迁移
- ❌ DDD 重构
- ❌ Event Sourcing

## Commerce
- ❌ 重写 Basket
- ❌ 重写 Order
- ❌ 完整电商系统

---

# Phase 1 Deliverables

## Backend

### Models (New)
- `display_priority` (Product, Application)
- `QuoteRequest`
- `QuoteRequestItem`

### Services (New)
- `apps/commerce/services/faq_service.py`
- `apps/commerce/services/product_relationship_service.py`

### Serializers (New)
- `ApplicationBriefSerializer`
- `MethodBriefSerializer`
- `ProtocolBriefSerializer`
- `ProductBriefSerializer`
- `RelatedProductSerializer`
- `ReferenceBriefSerializer`
- `FAQSerializer`
- `GraphNodeSerializer`
- `GraphEdgeSerializer`
- `ProductFullSerializer`

### APIs (New/Extended)
- `GET /api/v1/site/home/` (extended with 4 new sections)
- `GET /api/v1/products/<id>/detail/` (new aggregated endpoint)

## Frontend

### Homepage Components (7)
- `HeroSearch.vue`
- `ResearchGoals.vue`
- `FeaturedSolutions.vue`
- `FeaturedProducts.vue`
- `KnowledgeGraphPreview.vue` (static SVG)
- `ReferencesSection.vue`
- `CustomSynthesisCTA.vue`

### Product Components (10)
- `ProductHero.vue`
- `ProductApplications.vue`
- `ProductCompatibility.vue`
- `ProductKnowledgeGraph.vue` (textual)
- `ProductProtocols.vue`
- `ProductReferences.vue`
- `ProductFAQ.vue`
- `RelatedProducts.vue`
- `ProductSKU.vue`
- `RequestQuote.vue`

### API Functions
- `getProductDetail(id)` → `/api/v1/products/${id}/detail/`

---

# Phase 1 Success Metrics (North Star Funnel KPIs)

## Funnel

```
AI Search → Research Intent → Application → Method → Protocol → Product Discovery → RFQ → Order
```

## KPI Layer 1: Discovery

- Research Page PV ↑
- Application → Product CTR ↑
- Organic Landing Pages ↑

## KPI Layer 2: Trust

- Protocol View Rate ↑
- Reference View Rate ↑
- FAQ Expansion Rate ↑

## KPI Layer 3: Conversion

- Product → RFQ Rate ↑
- RFQ → Order Rate ↑
- Revenue / Session ↑

---

# Scope Freeze Declaration

**Date:** 2026-06-14
**Status:** FROZEN

## Architecture Status: 🟢 Stable
## Constitution Status: 🟢 Frozen
## Scope Status: 🟢 Frozen
## Codebase Alignment: 🟢 Acceptable
## Remaining Work: 🟡 Pure Implementation

## Freeze Rules

1. No new architecture concepts
2. No new technology introductions
3. No scope expansion beyond Phase 1 deliverables
4. All decisions must reference this Constitution
5. Any scope change requires explicit approval

---

# Phase 1 Implementation Priority

## P0 (Week 1) — Research Discovery

1. `display_priority` migration + Admin
2. Homepage API extension (`/api/v1/site/home/`)
3. Homepage 7 components

## P1 (Week 2-3) — Scientific Trust

4. 10 Serializers
5. Product Detail Endpoint (`/api/v1/products/<id>/detail/`)
6. 2 Service files (faq_service, product_relationship_service)
7. `getProductDetail()` frontend function

## P2 (Week 4) — Commercial Conversion

8. Product 10 components
9. QuoteRequest model + API

---

# Phase 1 Timeline

| Week | Priority | Tasks |
|------|----------|-------|
| 1 | P0 | `display_priority` migration + Admin. Extend `/api/v1/site/home/`. Homepage components (HeroSearch, FeaturedProducts, FeaturedSolutions). |
| 2 | P0 | Homepage continued: ResearchGoals, References, CustomSynthesisCTA, KnowledgePreview (static). Progressive loading. |
| 3 | P1 | `/api/v1/products/<id>/detail/` + serializers + services. Refactor ProductDetail.vue into 10 sections. |
| 4 | P2 | QuoteRequest model + API. Testing + bug fixes. |

---

# Document Priority Chain

```
PROJECT_CONSTITUTION.md (this file)
    ↓
V1.2_FINAL.md
    ↓
V1.2_RC2_Codebase_Aligned.md
    ↓
V1.2_RC1_Rebaselined.md
    ↓
11_RC2_Clarifications.md
    ↓
10_Amendments_V1.1.md
    ↓
01-09 original specs
```

**When conflicts exist, the higher document takes precedence.**
