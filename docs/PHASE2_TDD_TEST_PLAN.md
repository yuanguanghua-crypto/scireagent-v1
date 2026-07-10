# Phase 2 TDD Test Plan — Search + SEO

**Approach:** Test-Driven Development
**Rule:** Write tests first → Run (expect fail) → Implement → Run (expect pass)

---

## Week 5 (P0): PostgreSQL FTS + Grouped Search

### Test File: `apps/knowledge/tests/test_fts.py`

| ID | Test | Assert |
|----|------|--------|
| T5-01 | Product has search_vector field | `field exists on model` |
| T5-02 | Application has search_vector field | `field exists on model` |
| T5-03 | Method has search_vector field | `field exists on model` |
| T5-04 | Protocol has search_vector field | `field exists on model` |
| T5-05 | Reference has search_vector field | `field exists on model` |
| T5-06 | Product search_vector is populated on save | `product.search_vector is not None` |
| T5-07 | Product FTS finds by name | `SearchQuery('rna') matches product` |
| T5-08 | Product FTS finds by cas | `SearchQuery('12345-67-8') matches product` |
| T5-09 | Product FTS ranks by relevance | `ranked results order correct` |

### Test File: `apps/knowledge/tests/test_search_grouped.py`

| ID | Test | Assert |
|----|------|--------|
| T5-10 | Grouped search returns 200 | `GET /api/v1/search/grouped/?q=rna` → 200 |
| T5-11 | Grouped search has products key | `data['products']` is list |
| T5-12 | Grouped search has applications key | `data['applications']` is list |
| T5-13 | Grouped search has methods key | `data['methods']` is list |
| T5-14 | Grouped search has protocols key | `data['protocols']` is list |
| T5-15 | Grouped search has references key | `data['references']` is list |
| T5-16 | Grouped search uses Envelope format | `data['success'] == True` |
| T5-17 | Grouped search returns empty for no match | All lists are `[]` |
| T5-18 | Grouped search limits products to 10 | `len(data['products']) <= 10` |
| T5-19 | Grouped search limits other types to 5 | `len(data['applications']) <= 5` |
| T5-20 | Grouped search empty query returns empty | `q=''` → all `[]` |
| T5-21 | Grouped search with type filter | `?type=product` → only products |
| T5-22 | Grouped search product has catalog_no | `data['products'][0]['catalog_no']` |
| T5-23 | Grouped search product has score | `data['products'][0]['score']` is float |
| T5-24 | Trigram similarity for typo tolerance | `SearchQuery('rnalabeling') finds 'RNA labeling'` |

---

## Week 6 (P1): SEO Enhancements

### Test File: `apps/knowledge/tests/test_seo_api.py`

| ID | Test | Assert |
|----|------|--------|
| T6-01 | Product detail has seo_title | `data['product']['seo_title']` |
| T6-02 | Product detail has seo_description | `data['product']['seo_description']` |
| T6-03 | Homepage API has seo section | `data['seo']` is dict |
| T6-04 | Homepage seo has title | `data['seo']['title']` is str |
| T6-05 | Homepage seo has description | `data['seo']['description']` is str |
| T6-06 | Homepage seo has og_image | `data['seo']['og_image']` is str or null |
| T6-07 | Application detail has seo fields | `data['seo']` section exists |
| T6-08 | robots.txt endpoint returns 200 | `GET /robots.txt` → 200 |
| T6-09 | robots.txt contains User-agent | Body contains `User-agent:` |
| T6-10 | robots.txt contains Sitemap | Body contains `Sitemap:` |
| T6-11 | Sitemap XML returns 200 | `GET /sitemap.xml` → 200 |
| T6-12 | Sitemap contains product URLs | Body contains `/products/` |
| T6-13 | JSON-LD Product schema in detail API | `data['product']['jsonld']` exists |
| T6-14 | JSON-LD has @type Product | `jsonld['@type'] == 'Product'` |
| T6-15 | JSON-LD has name, description | Both fields present |

---

## Test Summary

| Week | Category | Count |
|------|----------|-------|
| 5 | FTS Models | 9 |
| 5 | Grouped Search API | 15 |
| 6 | SEO API | 15 |
| **Total** | | **39** |

---

## TDD Execution Order

### Week 5
1. Write T5-01 ~ T5-09 (FTS model tests)
2. Run → expect fail
3. Add SearchVector fields + GIN indexes + migration
4. Run → expect pass ✅
5. Write T5-10 ~ T5-24 (grouped search API tests)
6. Run → expect fail
7. Create `/api/v1/search/grouped/` endpoint with PostgreSQL FTS
8. Run → expect pass ✅

### Week 6
1. Write T6-01 ~ T6-15 (SEO tests)
2. Run → expect fail
3. Implement SEO endpoints + JSON-LD + robots.txt + sitemap
4. Run → expect pass ✅
