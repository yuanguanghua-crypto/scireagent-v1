# 10 Amendments V1.1

**Status:** Approved
**Priority:** Overrides original spec where conflicts exist

---

## Amendment 1: SSR Not Mandatory

**Original:** "Entity pages must be SSR or prerendered. CSR-only is prohibited."

**Revised:**

Entity pages must be:

1. Static prerender (Preferred — `vite-plugin-prerender`)
2. Django server-rendered shell
3. SSR (Nuxt — NOT recommended, cost/benefit unfavorable)

CSR-only is discouraged but **allowed in Phase 1**.

**Rationale:**
- Nuxt migration: 20% SEO gain, 300% complexity increase — not worth it
- `vite-plugin-prerender` covers SEO/AEO/LLM needs with minimal architecture change
- Phase 1 focuses on IA/UX, SEO enhancement is Phase 2

---

## Amendment 2: FAQ Generated Dynamically

**Original:** "FAQ model required. Minimum 4 questions. Must generate FAQPage JSON-LD."

**Revised:**

- **No FAQ table** in V1.1
- FAQ generated **dynamically at runtime** from existing entities
- New FAQ table is **prohibited** in V1.1

**Data sources:**
```text
Product → Applications → Methods → Protocols → Storage → Description
```

**Auto-generated FAQ example (2'-Azido-dATP):**
```text
Q: What is 2'-Azido-dATP used for?
A: [from Product.applications]

Q: Which methods use 2'-Azido-dATP?
A: [from Product → Method relationships]

Q: How should 2'-Azido-dATP be stored?
A: [from Product.storage]

Q: Which protocols require 2'-Azido-dATP?
A: [from Product → Protocol relationships]
```

**API:**
```
GET /api/products/:slug/faq/
```

Returns:
```json
[
  { "question": "...", "answer": "..." }
]
```

Runtime generation. No database storage.

---

## Amendment 3: Publication → Reference

**Original:** "PublicationsSection", "Publications", "/api/home/publications/"

**Revised:**

Unify on **Reference** model (already exists).

- `PublicationsSection` → `ReferencesSection`
- `/api/home/publications/` → `/api/home/references/`
- `/api/products/:slug/references/` (unchanged)

**Rationale:**
- Reference is broader: Journal Article, DOI, Patent, Protocol Paper, White Paper, Preprint, Documentation
- No new model needed
- Avoids data redundancy

---

## Amendment 4: Homepage Progressive Loading

**Original:** "7 components, all blocking"

**Revised:**

**Blocking (首屏, must load immediately):**
- HeroSearch
- ResearchGoals
- FeaturedProducts

**Lazy Load (below fold, load on demand):**
- FeaturedSolutions
- KnowledgeGraphPreview
- ReferencesSection
- CustomSynthesisCTA

**Implementation:**
```javascript
// Vue 3 defineAsyncComponent
const FeaturedSolutions = defineAsyncComponent(() =>
  import('@/components/home/FeaturedSolutions.vue')
)

// Or IntersectionObserver
const observer = new IntersectionObserver((entries) => {
  if (entries[0].isIntersecting) {
    // Load component
  }
})
```

**API Strategy:**
```
GET /api/home/           → hero, goals, featuredProducts (blocking)
GET /api/home/explore/   → solutions, graph, references (lazy)
```

Not 7 separate API calls.

---

## Amendment 5: PostgreSQL FTS Returns Grouped Entities

**Original concern:** "How does FTS return {applications, methods, protocols, products}?"

**Revised:**

PostgreSQL FTS **absolutely can** return grouped results.

**Implementation (4 separate queries):**
```python
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank

q = SearchQuery(request.GET['q'])

applications = Application.objects.annotate(
    rank=SearchRank(SearchVector('name', 'description'), q)
).filter(rank__gt=0).order_by('-rank')[:10]

methods = Method.objects.annotate(
    rank=SearchRank(SearchVector('name', 'description'), q)
).filter(rank__gt=0).order_by('-rank')[:10]

protocols = Protocol.objects.annotate(
    rank=SearchRank(SearchVector('name', 'description'), q)
).filter(rank__gt=0).order_by('-rank')[:10]

products = Product.objects.annotate(
    rank=SearchRank(SearchVector('name', 'cas', 'formula', 'overview'), q)
).filter(rank__gt=0).order_by('-rank')[:20]
```

**Response:**
```json
{
  "applications": [...],
  "methods": [...],
  "protocols": [...],
  "products": [...]
}
```

**Performance:** Entity counts are hundreds to thousands. 4 queries complete in <50ms. No ElasticSearch needed.

---

## Amendment 6: Commerce Scope — Inquiry Cart + Quote Request

**Original concern:** "Add to Cart and Request Quote need user system, cart model, etc."

**Revised:**

V1.1 scope is **NOT full e-commerce**. It's:

### Anonymous Inquiry Cart
- Storage: **localStorage only** (no backend cart table)
- Label: **"Add to Inquiry List"** (not "Add to Cart")
- Purpose: Collect products of interest for later quote request

### Quote Request (new model)
```python
class QuoteRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RESPONDED = 'responded', 'Responded'
        CLOSED = 'closed', 'Closed'

    # Contact info (no user auth required)
    contact_name = models.CharField(max_length=200)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=30, blank=True)
    organization = models.CharField(max_length=200, blank=True)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

class QuoteRequestItem(models.Model):
    quote_request = models.ForeignKey(QuoteRequest, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('commerce.Product', on_delete=models.CASCADE)
    sku = models.ForeignKey('commerce.SKU', on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.IntegerField(default=1)
    notes = models.TextField(blank=True)
```

### API
```
POST /api/quote-requests/
GET /api/quote-requests/:id/
```

### Button Behavior
- "Add to Inquiry List" → localStorage
- "Request Quote" → Collect inquiry items → Submit Quote Request form → Backend saves

**No user authentication required for V1.1.** Full user system (login/register/cart) is V2.0 scope.

---

## Summary of Amendments

| # | Amendment | Impact |
|---|-----------|--------|
| 1 | SSR → Prerender (Phase 1 CSR OK) | Reduces Phase 1 complexity significantly |
| 2 | No FAQ table, runtime generation | Eliminates new model, reduces DB changes |
| 3 | Publication → Reference | Eliminates naming confusion, reuses existing model |
| 4 | Homepage progressive loading | Improves performance, reduces blocking requests |
| 5 | PostgreSQL FTS confirmed sufficient | No external search engine needed |
| 6 | Inquiry Cart + Quote Request (no auth) | Simplified commerce scope for V1.1 |

---

## V1.1 Final Scope Confirmation

| Metric | Target | Status |
|--------|--------|--------|
| Database changes | ~0% (only QuoteRequest table) | ✅ Achievable |
| URL changes | 0% | ✅ Achievable |
| Framework migration | 0% | ✅ Achievable |
| Backend changes | 10-15% | ✅ Achievable |
| Frontend changes | 20-30% | ✅ Achievable |
| New dependencies | Cytoscape.js, vite-plugin-prerender | ✅ Minimal |
