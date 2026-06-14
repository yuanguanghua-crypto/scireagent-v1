# 09 Technical Constraints (Vue + Django)

## Technology Lock

**Backend:**
- Django 5.1
- Django REST Framework
- PostgreSQL

**Frontend:**
- Vue 3
- Vite
- TypeScript
- Pinia
- Vue Router

**Graph:**
- Preferred: Cytoscape.js
- Fallback: Vue Flow

---

## Deployment
- Docker
- Gunicorn
- Nginx

---

## Forbidden

Do not introduce:
- FastAPI
- Next.js
- Nuxt migration
- GraphQL
- Microservices
- ElasticSearch / OpenSearch
- Neo4j service
- Celery
- Vector DB

unless explicitly requested.

---

## SEO Strategy

Scientific entity pages must be SSR or prerendered:

```text
/
/applications/*
/methods/*
/protocols/*
/products/*
```

CSR-only implementation is prohibited.

Recommended: `vite-plugin-prerender`

---

## Future AI APIs (Reserve)

```text
/api/ai/search/
/api/entities/
/api/graph/
```

Must remain DRF APIs. No GraphQL.
