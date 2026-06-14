# 11 RC2 Clarifications

**Status:** Approved — Overrides all prior documents where conflicts exist
**Priority:** 10_Amendments_V1.1.md > 11_RC2_Clarifications.md > 01-09 original specs

---

## 1. Database Changes: "0%" → "0% Core Schema + Business Tables Allowed"

**Original:** "Database redesign: 0%"

**Revised:**

```md
Core entity schema changes: 0%.

The following supporting tables are allowed:

- QuoteRequest
- QuoteRequestItem
- InquiryList

provided that they do NOT modify:

- Application
- Method
- Protocol
- Product
- SKU
- or their relationships.
```

**Rationale:** QuoteRequest belongs to Business Transaction Domain, not Knowledge Graph Domain. Core scientific schema remains untouched.

---

## 2. URL Breaking Changes: "Slug Optional"

**Original:** "Breaking URL changes: 0%" + "/products/:slug/"

**Revised:**

```md
No URL migration is required.

Slug routes are optional — implement only if the current project already supports slugs.

If current routes use /products/<id> or /products/<catalog_number>, they must remain unchanged.

Backward compatibility is mandatory.
```

**Current state:** Frontend uses `/products/:id`. This remains authoritative.

**If slug support is added later:** Must implement 301 redirect from old URLs.

---

## 3. Search API: "No Breaking Changes" + "New Grouped Endpoint"

**Original:** "No breaking changes" + replace search response format

**Revised:**

```md
Existing search APIs must remain unchanged.

Grouped search responses must be exposed via a NEW endpoint:

GET /api/search/grouped/

Response:
{
  "applications": [],
  "methods": [],
  "protocols": [],
  "products": []
}

No existing search response formats may be modified.
```

**Implementation:** Keep `/api/search/` as-is. Add `/api/search/grouped/` with PostgreSQL FTS.

---

## 4. Featured Solutions: "Not an Entity — Application-Level Aggregation"

**Original:** Featured Solutions as homepage component (15% weight) with no definition

**Revised:**

Featured Solution is **NOT a new entity**. It is an **aggregation view** over existing data.

**Data source:** Application-level aggregation

```python
class FeaturedSolutionDTO:
    application_id: int
    name: str
    methods_count: int
    protocols_count: int
    products_count: int
    references_count: int
```

**Example:**
```json
{
  "application_id": 1,
  "name": "RNA Labeling",
  "methods_count": 2,
  "protocols_count": 8,
  "products_count": 15,
  "references_count": 23
}
```

**V1.1 restriction:** Only Application-based solutions allowed. Method-level solutions deferred.

**API:**
```
GET /api/home/featured-solutions/
```

**Forbidden:** SolutionTable, WorkflowTable, or any new entity.

---

## 5. Knowledge Graph API: "Nodes + Edges Schema Fixed"

**Original:** No API format defined

**Revised:**

```json
{
  "nodes": [
    {
      "id": "app_1",
      "type": "application",
      "label": "RNA Labeling",
      "slug": "rna-labeling"
    }
  ],
  "edges": [
    {
      "id": "edge_1",
      "source": "app_1",
      "target": "method_2",
      "relationship": "USES_METHOD"
    }
  ]
}
```

**Node Schema:**
```typescript
interface GraphNode {
  id: string
  type: 'application' | 'method' | 'protocol' | 'product' | 'sku'
  label: string
  slug?: string
  metadata?: Record<string, any>
}
```

**Edge Schema:**
```typescript
interface GraphEdge {
  id: string
  source: string
  target: string
  relationship: string
}
```

**Compatible with:** Cytoscape.js, Vue Flow, Neo4j (future), Agent API, GraphRAG

---

## 6. TypeScript: "Optional in V1.1, Target for V2.0"

**Original:** TypeScript listed as technology lock

**Revised:**

```md
TypeScript is recommended but not mandatory in V1.1.

Existing JavaScript modules may remain unchanged.

All newly created modules should prefer TypeScript.

Full TypeScript migration is deferred to V2.0.
```

---

## Summary of Resolutions

| # | Contradiction | Resolution |
|---|---------------|------------|
| 1 | 0% DB changes vs new tables | "0% Core Schema" + "Business Tables Allowed" |
| 2 | 0% URL breaking vs slug routes | "Existing routes authoritative. Slug optional." |
| 3 | No breaking changes vs search format | "Keep existing. New grouped endpoint." |
| 4 | Featured Solutions undefined | "Application-level aggregation view, not entity" |
| 5 | KG API format missing | "nodes + edges schema defined" |
| 6 | TypeScript mandatory vs no plan | "Optional V1.1. Target V2.0." |
