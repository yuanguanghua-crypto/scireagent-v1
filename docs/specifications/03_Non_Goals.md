# 03 Non-Goals (Forbidden Changes)

## Database

Forbidden:
- DROP TABLE
- RENAME TABLE
- ALTER TABLE redesign

Forbidden entities:
- WorkflowTable
- GraphNode
- ApplicationV2
- ProductNode

---

## Framework Migration

Forbidden:
- FastAPI
- Next.js
- Nuxt
- GraphQL
- Microservices

---

## Search Replacement

Forbidden:
- ElasticSearch
- OpenSearch
- Vector DB
- Haystack

Phase 1 search remains:
- PostgreSQL Full Text Search
- Trigram Similarity
- GIN Index

---

## Admin System

Do not rewrite:
- CMS
- CRUD
- Existing URLs

---

## Existing URLs remain

```text
/applications/
/methods/
/protocols/
/products/
/products/:slug/
```
