# Phase 1 TDD Test Plan

**Approach:** Test-Driven Development
**Rule:** Write tests first → Run (expect fail) → Implement → Run (expect pass)

---

## Week 1 (P0): display_priority + Homepage API

### Test File: `apps/commerce/tests/test_display_priority.py`

| ID | Test | Assert |
|----|------|--------|
| T1-01 | Product has display_priority field | `product.display_priority == 0` (default) |
| T1-02 | Product display_priority is indexed | Field has `db_index=True` |
| T1-03 | Product can set display_priority | `product.display_priority = 100; product.save()` |
| T1-04 | Product filter by display_priority | `Product.objects.filter(display_priority__gt=0).count() == 2` |

### Test File: `apps/knowledge/tests/test_display_priority.py`

| ID | Test | Assert |
|----|------|--------|
| T1-05 | Application has display_priority field | `app.display_priority == 0` (default) |
| T1-06 | Application filter by display_priority | `Application.objects.filter(display_priority__gt=0).count() == 1` |

### Test File: `apps/knowledge/tests/test_homepage_api.py`

| ID | Test | Assert |
|----|------|--------|
| T1-07 | Homepage returns hero.suggested_searches | `data['hero']['suggested_searches']` is list |
| T1-08 | Homepage returns featured_solutions | `data['featured_solutions']` is list |
| T1-09 | Featured solution has methods_count | `data['featured_solutions'][0]['methods_count']` is int |
| T1-10 | Featured solution has products_count | `data['featured_solutions'][0]['products_count']` is int |
| T1-11 | Featured solution does NOT have references_count | `'references_count' not in data['featured_solutions'][0]` |
| T1-12 | Homepage returns research_goals | `data['research_goals']` is list |
| T1-13 | Research goal has applications_count | `data['research_goals'][0]['applications_count']` is int |
| T1-14 | Homepage returns references | `data['references']` is list |
| T1-15 | Reference has title/journal/year/doi | All fields present |
| T1-16 | Homepage returns graph_preview as null | `data['graph_preview'] is None` |
| T1-17 | Featured products use display_priority | Products with `display_priority > 0` appear first |
| T1-18 | Featured products exclude draft status | No `status='draft'` products in featured |
| T1-19 | Featured applications use display_priority | Applications with `display_priority > 0` appear first |
| T1-20 | Featured methods have products_count | `data['featured_methods'][0]['products_count']` is int |

---

## Week 2 (P0): Homepage API Completeness

### Test File: `apps/knowledge/tests/test_homepage_api.py` (continued)

| ID | Test | Assert |
|----|------|--------|
| T2-01 | Homepage response has all 9 sections | hero, stats, featured_applications, featured_methods, featured_products, featured_solutions, research_goals, references, graph_preview |
| T2-02 | Homepage response uses Envelope format | `data['success'] == True`, `data['data']` exists, `data['meta']` exists |
| T2-03 | Featured products have catalog_no | `data['featured_products'][0]['catalog_no']` is str |
| T2-04 | Featured products have formula | `data['featured_products'][0]['formula']` is str |
| T2-05 | Featured products have price | `data['featured_products'][0]['price']` is str |
| T2-06 | Featured products have structure_svg | `data['featured_products'][0]['structure_svg']` is str or null |
| T2-07 | Featured applications have summary | `data['featured_applications'][0]['summary']` is str |
| T2-08 | Featured applications have products_count | `data['featured_applications'][0]['products_count']` is int |
| T2-09 | Empty database returns empty lists | All lists are `[]`, not errors |
| T2-10 | Homepage limits featured_products to 8 | `len(data['featured_products']) <= 8` |

---

## Week 3 (P1): Serializers + Product Detail Endpoint + Services

### Test File: `apps/commerce/tests/test_serializers_v2.py`

| ID | Test | Assert |
|----|------|--------|
| T3-01 | ApplicationBriefSerializer fields | `['id', 'name', 'slug', 'summary']` |
| T3-02 | ApplicationBriefSerializer uses summary (not description) | `'summary' in serializer.data`, `'description' not in serializer.data` |
| T3-03 | MethodBriefSerializer fields | `['id', 'name', 'slug', 'purpose']` |
| T3-04 | ProtocolBriefSerializer fields | `['id', 'name', 'slug', 'objective', 'estimated_time_minutes']` |
| T3-05 | ProtocolBriefSerializer estimated_time_minutes is computed | `serializer.data['estimated_time_minutes'] == 2` (for 120s step) |
| T3-06 | ProtocolBriefSerializer estimated_time_minutes with no steps | `serializer.data['estimated_time_minutes'] == 0` |
| T3-07 | ProtocolBriefSerializer estimated_time_minutes with null duration | `serializer.data['estimated_time_minutes'] == 0` |
| T3-08 | ProductBriefSerializer fields | `['id', 'name', 'slug', 'catalog_no', 'cas']` |
| T3-09 | ReferenceBriefSerializer fields | `['id', 'title', 'journal', 'year', 'doi']` |
| T3-10 | RelatedProductSerializer fields | `['id', 'name', 'catalog_no', 'cas', 'match_reason']` |
| T3-11 | FAQSerializer fields | `['question', 'answer']` |
| T3-12 | ProductFullSerializer has all product fields | Includes catalog_no, formula, molecular_weight, etc. |
| T3-13 | ProductFullSerializer has product_class_name | Computed field |
| T3-14 | ProductFullSerializer has product_class_path | Computed field (list) |
| T3-15 | ProductFullSerializer includes nested skus | `serializer.data['skus']` is list |
| T3-16 | ProductFullSerializer includes nested documents | `serializer.data['documents']` is list |

### Test File: `apps/commerce/tests/test_product_detail_api.py`

| ID | Test | Assert |
|----|------|--------|
| T3-17 | Product detail endpoint returns 200 | `GET /api/v1/products/{id}/detail/` → 200 |
| T3-18 | Product detail has product section | `data['product']` is dict |
| T3-19 | Product detail has applications section | `data['applications']` is list |
| T3-20 | Product detail has protocols section | `data['protocols']` is list |
| T3-21 | Product detail has references section | `data['references']` is list |
| T3-22 | Product detail has related_products section | `data['related_products']` is list |
| T3-23 | Product detail has faq section | `data['faq']` is list |
| T3-24 | Product detail has compatibility section | `data['compatibility']` is dict |
| T3-25 | Product detail has graph section (null) | `data['graph'] is None` |
| T3-26 | Product detail 404 for nonexistent | `GET /api/v1/products/99999/detail/` → 404 |
| T3-27 | Product detail uses Envelope format | `data['success'] == True` |
| T3-28 | Product detail applications have name | `data['applications'][0]['name']` is str |
| T3-29 | Product detail protocols have estimated_time_minutes | `data['protocols'][0]['estimated_time_minutes']` is int |
| T3-30 | Product detail compatibility has methods/protocols/products | All three keys exist |

### Test File: `apps/commerce/tests/test_faq_service.py`

| ID | Test | Assert |
|----|------|--------|
| T3-31 | FAQ with applications | Returns "What is X used for?" |
| T3-32 | FAQ with methods | Returns "Which methods use X?" |
| T3-33 | FAQ with storage | Returns "How should X be stored?" |
| T3-34 | FAQ with protocols | Returns "Which protocols use X?" |
| T3-35 | FAQ with all data | Returns 4 items |
| T3-36 | FAQ with no data | Returns empty list |
| T3-37 | FAQ with only storage | Returns 1 item |

### Test File: `apps/commerce/tests/test_product_relationship_service.py`

| ID | Test | Assert |
|----|------|--------|
| T3-38 | Related products: same application (score 100) | Product in same app appears first |
| T3-39 | Related products: same method (score 50) | Product in same method appears |
| T3-40 | Related products: same category (score 10) | Product in same class appears |
| T3-41 | Related products: limit=4 | Returns at most 4 |
| T3-42 | Related products: excludes self | Product not in results |
| T3-43 | Related products: empty when no relations | Returns empty list |
| T3-44 | Related products: match_reason field | Each result has match_reason |

---

## Week 4 (P2): QuoteRequest

### Test File: `apps/quotes/tests/test_models.py`

| ID | Test | Assert |
|----|------|--------|
| T4-01 | QuoteRequest creation | `qr.contact_name == 'Dr. Smith'` |
| T4-02 | QuoteRequest default status | `qr.status == 'pending'` |
| T4-03 | QuoteRequestItem creation | `item.quantity == 5` |
| T4-04 | QuoteRequestItem FK to product | `item.product_id == product.id` |
| T4-05 | QuoteRequestItem FK to sku (nullable) | `item.sku is None` |
| T4-06 | QuoteRequest cascade delete items | Delete QR → items deleted |
| T4-07 | QuoteRequest ordering | Newest first |

### Test File: `apps/quotes/tests/test_api.py`

| ID | Test | Assert |
|----|------|--------|
| T4-08 | Create quote request | POST → 201 |
| T4-09 | Create quote request with items | items count matches |
| T4-10 | Create quote request validation: empty items | 400 |
| T4-11 | Create quote request validation: invalid email | 400 |
| T4-12 | Retrieve quote request | GET → 200 |
| T4-13 | Retrieve quote request includes items | `data['items']` is list |
| T4-14 | Quote request no auth required | Anonymous POST → 201 |
| T4-15 | Quote request uses Envelope format | `data['success'] == True` |

---

## Test Summary

| Week | Category | Count |
|------|----------|-------|
| 1 | display_priority | 6 |
| 1 | Homepage API (new sections) | 14 |
| 2 | Homepage API (completeness) | 10 |
| 3 | Serializers | 16 |
| 3 | Product Detail API | 14 |
| 3 | FAQ Service | 7 |
| 3 | Product Relationship Service | 7 |
| 4 | QuoteRequest Models | 7 |
| 4 | QuoteRequest API | 8 |
| **Total** | | **89** |

---

## TDD Execution Order

### Week 1
1. Write T1-01 ~ T1-06 (display_priority tests)
2. Run → expect fail
3. Add `display_priority` field to Product + Application models
4. Run migration
5. Run → expect pass ✅
6. Write T1-07 ~ T1-20 (homepage API tests)
7. Run → expect fail
8. Extend `site_home()` view
9. Run → expect pass ✅

### Week 2
1. Write T2-01 ~ T2-10 (homepage completeness tests)
2. Run → expect fail
3. Complete homepage API response
4. Run → expect pass ✅

### Week 3
1. Write T3-01 ~ T3-16 (serializer tests)
2. Run → expect fail
3. Create all 10 serializers
4. Run → expect pass ✅
5. Write T3-17 ~ T3-30 (product detail API tests)
6. Run → expect fail
7. Create ProductDetailAPIView + services
8. Run → expect pass ✅
9. Write T3-31 ~ T3-44 (service tests)
10. Run → expect fail
11. Implement faq_service + product_relationship_service
12. Run → expect pass ✅

### Week 4
1. Write T4-01 ~ T4-15 (QuoteRequest tests)
2. Run → expect fail
3. Create QuoteRequest model + API
4. Run → expect pass ✅
