# 02 Information Architecture Specification

## Homepage Structure

```text
Header
↓
Hero Search
↓
Research Goals
↓
Featured Solutions
↓
Featured Products
↓
Knowledge Graph Preview
↓
Publications
↓
Custom Synthesis CTA
↓
Footer
```

---

## Homepage Component Tree

```text
src/
  views/
    HomeView.vue
  components/home/
    HeroSearch.vue
    ResearchGoals.vue
    FeaturedSolutions.vue
    FeaturedProducts.vue
    KnowledgeGraphPreview.vue
    PublicationsSection.vue
    CustomSynthesisCTA.vue
```

---

## Product Page Structure

```text
ProductHero
↓
Applications
↓
Compatibility
↓
KnowledgeGraph
↓
Protocols
↓
References
↓
FAQ
↓
RelatedProducts
↓
SKU
↓
RequestQuote
```

---

## Product Component Tree

```text
views/
  ProductDetailView.vue
components/product/
  ProductHero.vue
  ProductApplications.vue
  ProductCompatibility.vue
  ProductKnowledgeGraph.vue
  ProductProtocols.vue
  ProductReferences.vue
  ProductFAQ.vue
  RelatedProducts.vue
  ProductSKU.vue
  RequestQuote.vue
```

---

## Scientific Entity Model

```text
Research Goal → Application → Method → Protocol → Product → SKU
```

---

## Knowledge Graph Model

```text
Application ↔ Method ↔ Protocol ↔ Product ↔ SKU
```

Relationships are many-to-many. No redesign needed.

---

## Homepage Wireframe

```text
┌────────────────────┐
│ Header             │
└────────────────────┘
┌────────────────────┐
│ Hero Search        │
└────────────────────┘
┌────────────────────┐
│ Research Goals     │
└────────────────────┘
┌────────────────────┐
│ Featured Solutions │
└────────────────────┘
┌────────────────────┐
│ Featured Products  │
└────────────────────┘
┌────────────────────┐
│ Knowledge Graph    │
└────────────────────┘
┌────────────────────┐
│ Publications       │
└────────────────────┘
┌────────────────────┐
│ Custom Synthesis   │
└────────────────────┘
```
