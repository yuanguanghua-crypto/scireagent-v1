# Phase 3 TDD Test Plan — Knowledge Graph

**Approach:** Test-Driven Development
**Rule:** Write tests first → Run (expect fail) → Implement → Run (expect pass)

---

## Week 7 (P0): KG API — Graph Traversal Endpoint

### Test File: `apps/knowledge/tests/test_graph_api.py`

| ID | Test | Assert |
|----|------|--------|
| T7-01 | Graph endpoint returns 200 | `GET /api/v1/graph/?type=product&id=1` → 200 |
| T7-02 | Graph response has nodes key | `data['nodes']` is list |
| T7-03 | Graph response has edges key | `data['edges']` is list |
| T7-04 | Graph uses Envelope format | `data['success'] == True` |
| T7-05 | Graph from product includes product node | Node with `type='product'` exists |
| T7-06 | Graph from product includes method nodes | Nodes with `type='method'` exist (via ProductMethod) |
| T7-07 | Graph from product includes application nodes | Nodes with `type='application'` exist |
| T7-08 | Graph edges connect product to method | Edge `source=product_id, target=method_id` |
| T7-09 | Graph edges connect method to application | Edge `source=method_id, target=app_id` |
| T7-10 | Node has required fields | `id, type, label` present |
| T7-11 | Edge has required fields | `id, source, target, relationship` present |
| T7-12 | Graph respects max_nodes limit | `len(nodes) <= 50` |
| T7-13 | Graph respects max_edges limit | `len(edges) <= 100` |
| T7-14 | Graph respects depth parameter | `?depth=1` returns only direct neighbors |
| T7-15 | Graph default depth is 3 | Without param, traverses 3 levels |
| T7-16 | Graph from application works | `?type=application&id=1` returns graph |
| T7-17 | Graph from method works | `?type=method&id=1` returns graph |
| T7-18 | Graph missing params returns 400 | `?type=product` (no id) → 400 |
| T7-19 | Graph invalid type returns 400 | `?type=invalid&id=1` → 400 |
| T7-20 | Graph nonexistent id returns 404 | `?type=product&id=99999` → 404 |

### Test File: `apps/knowledge/tests/test_graph_service.py`

| ID | Test | Assert |
|----|------|--------|
| T7-21 | Service: product with method returns 2 nodes | Traverse depth=1 |
| T7-22 | Service: product with method+app returns 3 nodes | Traverse depth=2 |
| T7-23 | Service: product with reference adds ref node | ProductReference edge |
| T7-24 | Service: max_nodes truncates | Set max_nodes=2, verify truncation |
| T7-25 | Service: no duplicates | Same entity visited twice → single node |
| T7-26 | Service: cycle detection | Circular reference doesn't loop |
| T7-27 | Service: empty graph | Product with no relations → only self node |

---

## Week 8 (P1): Homepage KG Preview + Product KG Widget

### Test File: `apps/knowledge/tests/test_graph_api.py` (continued)

| ID | Test | Assert |
|----|------|--------|
| T8-01 | Homepage graph_preview is no longer null | `data['graph_preview']` has nodes/edges |
| T8-02 | Homepage graph_preview limited to 20 nodes | `len(nodes) <= 20` |
| T8-03 | Homepage graph_preview has central node | A node with `type='application'` exists |

---

## Test Summary

| Week | Category | Count |
|------|----------|-------|
| 7 | Graph API | 20 |
| 7 | Graph Service | 7 |
| 8 | Homepage KG Preview | 3 |
| **Total** | | **30** |

---

## Entity Relationship Map (for traversal)

```
ResearchGoal
    ↓ (FK)
Application ← display_priority
    ↓ (FK)
Method
    ↓ (MethodProtocol bridge)
Protocol
    ↑ (ProductMethod bridge)
Product ← display_priority
    ↓ (FK)
SKU

Product ←→ Reference (ProductReference bridge)
Product ←→ Product (ProductProduct bridge)
Product ←→ Compatibility (ProductCompatibility bridge)
```

## Traversal Rules

| From | Via | To | Edge Relationship |
|------|-----|-----|-------------------|
| Product | ProductMethod | Method | `used_in` |
| Method | FK (reverse) | Application | `belongs_to` |
| Application | FK (reverse) | ResearchGoal | `part_of` |
| Method | MethodProtocol | Protocol | `has_protocol` |
| Product | ProductReference | Reference | `cited_in` |
| Product | ProductProduct | Product | `related_to` |
