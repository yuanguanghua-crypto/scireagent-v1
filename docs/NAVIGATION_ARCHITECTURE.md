# Navigation Architecture — V1.2 Frozen

## Entity Definitions (Scientific Entity Constitution)

| Entity | Question | Example |
|--------|----------|---------|
| Research Goal | WHY — Why am I doing this research? | RNA Labeling |
| Application | WHAT — What experiment am I performing? | RNA Fluorescent Labeling |
| Method | HOW — How can this experiment be performed? | CuAAC |
| Protocol | HOW EXACTLY — How do I execute it? | RNA CuAAC Labeling Protocol |
| Product | WITH WHAT — Which reagent enables this? | 2'-Fluoro-dATP |
| SKU | WHICH PACKAGE — Which pack size? | SC8036-1 |

## Core Principles

1. **Research Intent > Catalog** — Navigation follows research paths, not product categories
2. **Bidirectional** — Every entity navigates both upstream and downstream
3. **Graceful Degradation** — When knowledge links are missing, show fallback content, not empty sections
4. **Data Completeness First** — Top 20 Products must reach Knowledge Coverage Level 3

## 4 Core Questions (every page must answer)

| Question | Component |
|----------|-----------|
| Where am I? | Research Path Card |
| Where did I come from? | Upstream Context Card |
| Where can I go next? | Downstream Context Card |
| What if links are missing? | Graceful Degradation Fallback |

## Knowledge Coverage KPI

| Level | Definition |
|-------|-----------|
| 0 | Product — no connections |
| 1 | Product → Application |
| 2 | Application → Method → Product |
| 3 | Research Goal → Application → Method → Protocol → Product → SKU |

**V1.2 Target:** Top 20 Products at Level 3.

## Navigation Fallback Matrix

| Entity | Has Full Path | Missing Path Fallback |
|--------|--------------|----------------------|
| Research Goal | Applications | Featured Applications |
| Application | Methods | Related Applications |
| Method | Protocols | Featured Products |
| Protocol | Products | Related Products |
| Product | Full upstream graph | Category + Related Products + "Request protocol support" |

## P0 Components (Implementation Priority)

1. **Context Cards** — Top of each detail page, upstream + downstream entity links
2. **Research Path Card** — Right sidebar on product pages, full research path
3. **Unified CTA** — Bottom of all detail pages: Explore / Request Quote
4. **Graceful Degradation** — Fallback content when links are incomplete

## P1 Components (after data enrichment)

5. Research Breadcrumb (replaces Catalog Breadcrumb)
6. Research Path Chips (lightweight path indicator)
7. Relationship Widgets (direct entity connections)

## Phase 2+ Components

8. Persistent Research Cart
9. Smart Recommendations

---
*Frozen: 2026-06-14 | Agreed by: 凯峰 + WorkBuddy + GPT review*
