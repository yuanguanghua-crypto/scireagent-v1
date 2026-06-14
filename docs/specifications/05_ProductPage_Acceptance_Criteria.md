# 05 Product Page Acceptance Criteria

## Required Section Order (Cannot Change)

```text
ProductHero
Applications
Compatibility
KnowledgeGraph
Protocols
References
FAQ
RelatedProducts
SKU
RequestQuote
```

---

## ProductHero

Must include:
- Structure Image
- Product Name
- CAS
- Purity
- Storage
- Purchase Box (sticky on scroll)

---

## Applications

Minimum: 1 application. Must be clickable. Route: `/applications/:slug`

---

## Compatibility

Must support:
- Methods
- Protocols
- Products
- Publications
- Dyes
- Enzymes

---

## Knowledge Graph

Must be interactive. Static image is prohibited.

---

## Protocols

Display:
- Protocol Name
- Difficulty
- Estimated Time
- Related Methods

---

## References

Display:
- Title
- Journal
- Year
- DOI
- Related Application

Support: PubMed URL, DOI URL

---

## FAQ

Minimum: 4 questions. Must generate FAQPage JSON-LD for SEO.

---

## Related Products Priority

```text
Same Application > Same Method > Same Protocol > Same Category
```

Display: 4 products.

---

## SEO Requirements

Every Product Page must output:
- title
- meta description
- canonical
- breadcrumbs
- JSON-LD
- FAQ schema
