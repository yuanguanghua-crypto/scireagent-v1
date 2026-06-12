# Chapter 5 Frontend PRD

## Document Authority

This chapter defines the frontend product requirements for LabPro Global.
It translates the product vision, system architecture, domain model, and database baseline into a concrete user-facing UI and navigation specification.

If a later UI implementation chapter conflicts with this chapter on page structure, component usage, navigation, or content hierarchy, this chapter wins on frontend intent and the later chapter must be adjusted.

This chapter is intentionally implementation-oriented:

- It defines the page inventory.
- It defines page composition and content blocks.
- It defines reusable components.
- It defines interaction patterns and states.
- It defines responsive behavior and SEO/AEO expectations.
- It defines what the frontend must expose to support the scientific graph and commerce flow.

## 1. Frontend Mission

The frontend must turn the LabPro Global scientific graph into a usable browsing and purchasing experience.

The UI must help users:

- Start from a research goal or application.
- Navigate into methods and protocols.
- Evaluate products with scientific context.
- Move into quote, cart, and order flows without losing traceability.
- Discover structured evidence and compatibility information.

The frontend must also make the platform readable to search engines and AI consumers by exposing structured metadata and clean page semantics.

## 2. Frontend Principles

### 2.1 Navigation by Intent

Users should be able to start from:

- A research goal
- An application
- A method
- A protocol
- A product
- Search

### 2.2 Scientific Context First

Product pages must never feel disconnected from the scientific workflow they support.

### 2.3 Commerce Without Friction

Quote, cart, and order paths should remain easy to complete, but they must preserve the research context.

### 2.4 Reusable UI Language

Reusable cards, tabs, tables, and detail layouts must be shared across the platform rather than recreated per page.

### 2.5 Structured by Default

Every public-facing resource page should be able to support structured metadata, SEO hooks, and future AI consumption.

### 2.6 Responsive and Clear

The interface must work on desktop and mobile without collapsing the scientific hierarchy.

## 3. Frontend Stack Assumptions

The frontend is built on the existing PRD baseline:

- Vue 3
- Composition API
- Existing backend: Django 5.1 REST
- Existing structured resource model from Chapter 4

### 3.1 Frontend Architectural Rules

- Use reusable components for repeated content patterns.
- Keep page-level data fetching separate from page rendering when practical.
- Prefer a component hierarchy that reflects the domain hierarchy.
- Avoid duplicating the same scientific resource presentation logic in multiple pages.
- Keep business logic out of presentation components.

### 3.2 Required Component Pattern

The PRD explicitly requires reusable components such as:

- `ApplicationCard`
- `MethodCard`
- `ProtocolCard`
- `ProductCard`

These components must be treated as canonical UI building blocks, not one-off page widgets.

## 4. Information Architecture

### 4.1 Primary Navigation

The frontend navigation must support the PRD structure:

- Home
- Applications
- Methods
- Protocols
- Products
- Resources
- Search
- Quote
- Cart

### 4.2 Canonical User Journey

The primary user journey is:

`Goal -> Method -> Protocol -> Product -> Purchase`

### 4.3 Content Families

- Home: entry points and value proposition
- Applications: research intent browsing
- Methods: workflow families
- Protocols: stepwise procedures
- Products: commercial and scientific evaluation
- Resources: references and supporting documents
- Search: universal discovery
- Quote: commercial negotiation
- Cart: selection and checkout preparation

### 4.4 Cross-Linking Rule

Every major page type should be able to link to the adjacent levels in the scientific chain.

Examples:

- Application pages should link to methods, protocols, and products.
- Method pages should link to protocols and products.
- Protocol pages should link to methods, products, and references.
- Product pages should link to applications, methods, protocols, compatibility, and references.

## 5. Page Inventory

### 5.1 Home

Purpose:

- Explain the platform value quickly.
- Provide entry points into the scientific graph and search.

Required blocks:

- Hero / value proposition
- Primary search
- Featured applications
- Featured methods
- Featured products
- Resource highlights
- Quote / contact entry

### 5.1b Research Goals Index

Purpose:

- Let users browse by top-level scientific intent.

Required blocks:

- ResearchGoal grid or list
- Short descriptive copy per goal
- Links to child Applications

### 5.1c Research Goal Detail

Purpose:

- Anchor one research goal and route users into its child applications, methods, and products.

Required blocks:

- Overview
- Applications
- Key Methods
- Key Products


### 5.2 Applications Index

Purpose:

- Let users browse by research use case.

Required blocks:

- Application grid or list
- Search/filter
- Short explanatory copy
- Links to methods and relevant products

### 5.3 Application Detail

Purpose:

- Explain one research application and route users into relevant methods, protocols, products, and references.

Required blocks:

- Overview
- Methods
- Protocols
- Products
- References
- FAQ

### 5.4 Methods Index

Purpose:

- Let users browse workflow families by scientific method.

Required blocks:

- Method list or grid
- Search/filter
- Category cues if needed
- Links to protocols and products

### 5.5 Method Detail

Purpose:

- Explain one method and surface its protocols and product context.

Required blocks:

- Overview
- Advantages
- Limitations
- Cost
- Timeline
- Protocols
- Products

### 5.6 Protocols Index

Purpose:

- Allow users to discover protocols as reusable scientific procedures.

Required blocks:

- Protocol list or grid
- Search/filter
- Method grouping
- Evidence cues

### 5.7 Protocol Detail

Purpose:

- Present a structured, versioned scientific procedure.

Required blocks:

- Objective
- Principle
- Materials
- Reagents
- Equipment
- Steps
- Troubleshooting
- Expected Results
- References
- Product links

### 5.8 Products Index

Purpose:

- Present the commercial catalog while preserving scientific context.

Required blocks:

- Product list or grid
- Product search
- CAS / SMILES search affordances when supported
- Filters
- Inventory cues
- Quick links to scientific context

### 5.9 Product Detail

Purpose:

- Be the canonical product evaluation page.

Required blocks:

- Overview
- Applications
- Methods
- Protocols
- Compatibility
- References
- Documents
- Inventory

### 5.10 Resources

Purpose:

- Provide supporting documents, references, and evidence content.

Required blocks:

- Documents
- References
- Other supporting assets

### 5.11 Search

Purpose:

- Let users search across the scientific and commerce graph from one entry point.

Required blocks:

- Search input
- Resource-type switching or filtering
- Ranked results
- Facets when appropriate

### 5.12 Quote

Purpose:

- Convert scientific and product evaluation into a quote request or negotiated deal path.

Required blocks:

- Selected items
- Quantity / pack adjustments
- Company / contact details
- Request context
- Submission status

### 5.13 Cart

Purpose:

- Hold user selections before checkout or quote conversion.

Required blocks:

- Line items
- Quantity controls
- Product summaries
- SKU summaries
- Next-step actions

## 6. Page Templates and Content Structure

### 6.1 Application Page Template

The Application page must follow the PRD structure:

- Overview
- Methods
- Protocols
- Products
- References
- FAQ

Implementation notes:

- Overview should answer what problem the application solves.
- Methods should be the primary content transition.
- Protocols should not be buried.
- Products should remain tied to scientific context.

### 6.2 Method Page Template

The Method page must follow the PRD structure:

- Overview
- Advantages
- Limitations
- Cost
- Timeline
- Protocols
- Products

Implementation notes:

- The Method page should balance scientific explanation with practical evaluation.
- Protocols should be ranked by relevance or editorial prominence.
- Products should reflect method relevance, not just inventory presence.

### 6.3 Protocol Page Template

The Protocol page template from the PRD is:

- Objective
- Principle
- Materials
- Reagents
- Equipment
- Steps
- Troubleshooting
- Expected Results
- References

Implementation notes:

- Protocol steps must be visually ordered.
- Product links should be available near the relevant step or section.
- References should be visible enough to establish trust.

### 6.4 Product Page Template

The Product page template from the PRD is:

- Overview
- Applications
- Methods
- Protocols
- Compatibility
- References
- Documents
- Inventory

Implementation notes:

- Product page must expose chemical identity fields such as CAS, SMILES, InChI, purity, storage, shipping, and lead time when available.
- Product page must support both scientific review and purchase readiness.
- Product page must not bury stock or delivery information.

### 6.5 Product Page Tabs and Exposed Fields

The PRD explicitly requires the following product tabs or surfaces:

- Overview
- Applications
- Methods
- Protocols
- Compatibility
- References
- Documents
- Inventory

The product page should expose:

- CAS
- SMILES
- InChI
- Purity
- Storage
- Shipping
- Lead time

## 7. Reusable Components

### 7.1 Core Card Components

The PRD requires reusable card components:

- `ApplicationCard`
- `MethodCard`
- `ProtocolCard`
- `ProductCard`

Each card must support:

- Title
- Summary
- Primary metadata
- Canonical link
- Optional secondary signals

### 7.2 Supporting Components

The frontend should also standardize the following component families:

- Search bar
- Filter panel
- Tag / badge
- Tabbed resource layout
- Citation list
- Step list
- Inventory summary
- Quote item row
- Product summary row
- Empty state
- Loading state
- Error state

### 7.3 Component Reuse Rules

- Do not create separate card systems for each page if the same data shape can be reused.
- Do not duplicate list item presentation logic across Applications, Methods, Protocols, and Products.
- Keep relation cards lightweight and consistent.

## 8. Interaction and State Requirements

### 8.1 Search State

Search must support:

- Empty input state
- Loading state
- Query result state
- No result state
- Error state
- Faceted refinement state

### 8.2 Detail Page State

Detail pages must support:

- Loading state
- Data-loaded state
- Related-content state
- Error state
- Empty relation state

### 8.3 Commerce State

Commerce pages must support:

- SKU selection
- Quantity adjustment
- Cart update
- Quote request
- Submission success/failure

### 8.4 Scientific Content State

Scientific content pages must support:

- Published content
- Draft or hidden content when authorized
- Versioned content display
- Reference / citation visibility

## 9. Responsive Behavior

### 9.1 Desktop

- Use a multi-column layout when it improves scanability.
- Keep scientific navigation visible.
- Preserve tab and section hierarchy.

### 9.2 Tablet

- Maintain strong hierarchy without overcrowding.
- Collapse secondary columns when needed.
- Preserve access to search and key actions.

### 9.3 Mobile

- Stack content vertically.
- Keep primary actions accessible.
- Avoid hiding scientific relationships behind excessive navigation friction.
- Preserve readability of protocol steps and product metadata.

### 9.4 Responsive Priority

On smaller screens, prioritize:

1. Primary content
2. Primary action
3. Related content
4. Secondary metadata

## 10. SEO and AEO Requirements

### 10.1 Structured Metadata

Every product should include structured metadata, including:

- Schema.org ChemicalSubstance
- Application links
- Protocol links
- Reference links

### 10.2 Metadata Rules

- Use canonical URLs.
- Expose stable titles and descriptions.
- Make structured data consistent with visible content.
- Do not inject invisible content solely for search engines.

### 10.3 Search Engine Objectives

The frontend should help the platform be discoverable for:

- Product queries
- Application queries
- Method queries
- Protocol queries
- Scientific reagent queries

### 10.4 AI Readiness

The same structured content that helps SEO should also support AI retrieval.

## 11. Accessibility and Usability

### 11.1 Accessibility Baseline

- Semantic headings
- Keyboard navigability
- Visible focus states
- Sufficient contrast
- Clear labels for controls and filters
- Descriptive link text

### 11.2 Scientific Usability

- Keep technical terms readable and searchable.
- Avoid over-collapsing scientific content into generic marketing language.
- Show enough context for professional evaluation without forcing page hops for basic understanding.

## 12. Data Dependencies

The frontend depends on the canonical resource model defined in Chapter 4 and the domain model in Chapter 3.

### 12.1 Data Expectations by Page Type

- Home depends on featured applications, methods, products, and resources.
- Application pages depend on application records and linked methods, protocols, and products.
- Method pages depend on method records and linked protocols and products.
- Protocol pages depend on protocol records, steps, references, and linked products.
- Product pages depend on product records, SKU records, compatibility, references, applications, methods, and protocols.
- Search depends on cross-resource indexing and canonical IDs.

### 12.2 Frontend Data Rule

The frontend must not invent domain relations that do not exist in the canonical data model.

## 13. Implementation Rules

### 13.1 Component Authoring

- Use Composition API for reusable page behavior.
- Keep page-level data loading isolated where practical.
- Prefer small, composable pieces over deeply nested page-specific code.

### 13.2 Rendering Rule

- Do not hide essential scientific metadata behind interactions that make the page unusable without hover or desktop-only behavior.
- Keep tabs and sections discoverable.

### 13.3 Performance Rule

- Avoid unnecessary re-renders.
- Load only the data needed for the current page state.
- Support progressive disclosure for heavy scientific content.

### 13.4 Content Rule

- Use concise summaries for cards and lists.
- Reserve detail for resource pages.
- Preserve canonical names, identifiers, and citations.

## 14. Cross-Chapter Dependencies

This chapter depends on the product vision, architecture, domain model, and database architecture chapters.
It also defines the frontend obligations for the API, knowledge graph, and design system chapters.

| Chapter | Dependency on This Chapter |
|---|---|
| Chapter 1 Product Vision | Defines the user journey and value proposition this frontend must express |
| Chapter 2 System Architecture | Defines the layer boundaries this frontend must respect |
| Chapter 3 Domain Model | Defines the entities and relation order this frontend must expose |
| Chapter 4 Database Architecture | Defines the fields and canonical resource identities this frontend must render |
| Chapter 6 Backend API Spec | Must provide the payloads and endpoints this frontend consumes |
| Chapter 7 Knowledge Graph | Must provide the scientific graph surfaces this frontend navigates |
| Chapter 8 Application / Method / Protocol Spec | Must operationalize the content architecture described here |
| Chapter 9 AI Agent Integration | Must consume the structured metadata exposed by the frontend |
| Chapter 10 Roadmap | Must sequence the page families described here |
| Chapter 12 Design System | Must provide the visual language and reusable UI primitives for this frontend |

## 15. Acceptance Criteria

This chapter is complete when all of the following are true:

- The full navigation and page inventory are defined.
- Application, Method, Protocol, and Product page templates are explicit.
- Reusable component requirements are explicit.
- Search, quote, cart, and detail page states are defined.
- Responsive behavior is defined for desktop, tablet, and mobile.
- SEO/AEO requirements are explicit.
- Product page scientific metadata requirements are explicit.
- The frontend can be implemented without inventing page structure or component intent.

