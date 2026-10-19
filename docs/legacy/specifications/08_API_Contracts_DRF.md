# 08 API Contracts (DRF)

## Home APIs

```text
GET /api/home/research-goals/
GET /api/home/featured-solutions/
GET /api/home/featured-products/
GET /api/home/publications/
GET /api/home/knowledge-graph/
```

---

## Product APIs

```text
GET /api/products/:slug/applications/
GET /api/products/:slug/compatibility/
GET /api/products/:slug/protocols/
GET /api/products/:slug/references/
GET /api/products/:slug/graph/
```

---

## Search API

```text
GET /api/search/?q=
```

Returns:
```json
{
  "applications": [],
  "methods": [],
  "protocols": [],
  "products": []
}
```

---

## DRF Structure

```text
apps/
  api/
    home/
    products/
    search/
```

---

## Home Views

```python
ResearchGoalsAPIView
FeaturedSolutionsAPIView
FeaturedProductsAPIView
PublicationsAPIView
KnowledgeGraphAPIView
```

---

## Search Implementation (Phase 1)

- SearchVector
- SearchQuery
- SearchRank
- TrigramSimilarity
- GinIndex

No ElasticSearch.
