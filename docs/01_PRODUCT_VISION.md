# Chapter 1 Product Vision

## Document Authority

This chapter defines the product intent for LabPro Global.
It is the top-level business and experience baseline for the full documentation set and must remain consistent with the V1 PRD and the downstream architecture chapters.

If a later technical chapter conflicts with this chapter on product direction, user intent, scope, or priority, this chapter wins on product meaning and the later chapter must be adjusted to match it.

This chapter is intentionally practical:

- It defines what the platform is.
- It defines who it is for.
- It defines why the platform exists.
- It defines how the platform evolves across versions.
- It defines how success is measured.
- It defines what is out of scope.

It does not duplicate implementation details that belong in later chapters unless they are required to make the vision operational.

## 1. Executive Vision

LabPro Global is an AI-readable scientific reagent platform for nucleotides and click chemistry.
The platform is designed to connect research intent to research methods, protocols, products, and purchase actions in a single navigable system.

The platform must satisfy two goals at the same time:

1. Help researchers and lab operators find the right scientific capability faster.
2. Help the business convert that scientific intent into product sales, custom synthesis, enterprise quotations, and future API usage.

The platform is not just an ecommerce catalog.
It is a knowledge-backed commercial platform where the scientific graph is part of the product experience.

## 2. Mission and Positioning

### 2.1 Mission

Build the world's leading AI-native scientific capability platform for nucleotides and click chemistry.

### 2.2 Positioning Statement

LabPro Global turns research goals into actionable scientific pathways:

`Research Goal -> Application -> Method -> Protocol -> Product -> SKU -> Order`

This chain is the core product logic.
It must be visible to human users in the UI and machine-readable to downstream systems and AI agents.

### 2.3 What the Platform Is

- A reagent commerce platform with scientific context.
- A research application platform that helps users browse by use case.
- A method platform that organizes scientific workflows.
- A protocol platform that provides structured experimental procedures.
- A capability platform that links products, protocols, references, and compatibility data.
- An AI-readable knowledge surface that can support retrieval, recommendation, and citation.

### 2.4 What the Platform Is Not

- Not a generic ecommerce storefront.
- Not a full LIMS.
- Not an ELN.
- Not a discussion forum.
- Not a freeform content management system.
- Not a second source of truth for scientific or transactional data outside the canonical database and service layer.

## 3. Product Evolution

The platform evolves through four explicit stages.
Each stage adds a new layer of value without discarding the previous layer.

| Stage | Name | Primary Value | Required Capabilities | Exit Criteria |
|---|---|---|---|---|
| V1 | Ecommerce | Sell reagents efficiently | Product catalog, SKU visibility, quote/cart/order flow, basic product search | A customer can discover a product and complete a purchase path |
| V2 | Research Application Platform | Help users browse by research intent | Application pages, application-method navigation, contextual product discovery | A user can start from a research use case and reach relevant products |
| V3 | Research Method Platform | Organize workflows and procedures | Method pages, protocol pages, protocol-product links, references, compatibility | A user can move from a method to a protocol and then to matching products |
| V4 | AI-Callable Scientific Capability Platform | Make the knowledge base machine-readable and agent-ready | Structured metadata, JSON-LD, read APIs, capability retrieval, MCP reservation, citation stability | An AI agent can retrieve, explain, and cite the scientific graph reliably |

### 3.1 V1 Meaning

V1 is the current commercial base.
It must support product discovery, quotation, carting, ordering, and the ability to present products in a scientifically meaningful way.

### 3.2 V2 Meaning

V2 adds application-centric navigation.
Users should be able to start from a research goal or application, not only from a product name.

### 3.3 V3 Meaning

V3 adds method-centric and protocol-centric navigation.
The platform becomes useful for research planning, not only procurement.

### 3.4 V4 Meaning

V4 makes the platform consumable by AI systems.
The scientific graph must be explicit, stable, citable, and exposed through structured data and future capability interfaces.

## 4. Target Users

The platform serves four primary user groups.

| User Group | Primary Needs | Typical Questions | Success Signal |
|---|---|---|---|
| Researchers | Find the right application, method, protocol, and product | What method should I use? Which protocol is appropriate? Which reagents are compatible? | They can move from intent to a credible protocol and product set |
| Lab Managers | Standardize procedures and reduce operational risk | Is the protocol reproducible? What are the handling constraints? What has been validated? | They can validate a workflow quickly and consistently |
| Procurement Teams | Convert scientific need into a purchasable order | Which products are required? Which SKU fits the pack size and lead time? What is the quote path? | They can complete quoting and purchasing with fewer clarification loops |
| AI Agents | Retrieve structured, citable knowledge | What is the method? Which protocol is linked? What products are compatible? | They can answer with stable identifiers and canonical sources |


**V-Stage 与 Roadmap Phase 映射说明**：

- V1 = 现有基线（当前代码库）
- V2 = Phase 2（Application Center）
- V3 = Phase 3 + Phase 4（Method Center + Protocol Center）
- V4 = Phase 5（Agent Layer）
- Phase 1（Database & Knowledge Layer）为所有后续阶段的公共基础设施，无独立 V-stage 编号。

### 4.1 Primary User Jobs

- Translate intent into a navigable research pathway.
- Validate whether a reagent is appropriate for a method or protocol.
- Move from scientific context to procurement without losing traceability.
- Retrieve structured evidence instead of freeform marketing copy.

### 4.2 User Experience Principle

The experience must serve users in the order they think:

1. Goal
2. Application
3. Method
4. Protocol
5. Product
6. SKU
7. Order

That journey must be visible in navigation, linking, structured data, and content hierarchy.

## 5. Business Model

The platform supports multiple revenue paths.
These revenue paths should appear naturally in the user journey and not feel bolted on.

| Revenue Path | What It Means | Product Surface |
|---|---|---|
| Product sales | Standard reagent and catalog sales | Product detail pages, SKU selection, cart, order |
| Custom synthesis | Tailored scientific manufacturing requests | Quote flow, contact/enterprise path, solution-oriented product pages |
| Enterprise quotation | Larger, negotiated commercial deals | Quote workflow, account handling, lead capture |
| Future API access | External or partner system access to structured data | Read APIs, structured data, future capability interfaces |

### 5.1 Commercial Logic

- Product pages must support both scientific evaluation and buying decisions.
- Quote flows must be connected to products and scientific context.
- Custom synthesis should feel like an extension of the platform, not a separate silo.
- Future API access must be grounded in the same canonical data model as the public site.

### 5.2 Revenue Measurement

The business should be able to measure:

- Total product revenue
- Quote conversion
- Protocol-driven product discovery
- API usage
- AI citation usage

## 6. Core Value Proposition

The platform wins if it delivers all of the following at once:

### 6.1 Scientific Relevance

Users can navigate from a research problem to a valid application, method, protocol, and product set.

### 6.2 Commercial Conversion

Scientific discovery should naturally lead to quote requests, cart additions, and orders.

### 6.3 Evidence and Trust

Every important scientific claim should be grounded in references, compatibility data, or structured knowledge links.

### 6.4 Machine Readability

The platform should be understandable by AI systems without requiring manual interpretation of every page.

### 6.5 Navigation by Intent

Users should be able to start from a goal, not only from a product keyword.

## 7. Product Principles

These principles govern all downstream chapters and implementation work.

### 7.1 Evidence First

Claims, compatibility, and protocol guidance must be grounded in explicit data, not vague copy.

### 7.2 Navigation by Research Intent

The user journey begins with a goal or application, not with a raw SKU list.

### 7.3 Machine Readable by Default

Structured metadata is not optional.
The platform must support JSON-LD and future agent consumption as a baseline requirement.

### 7.4 Reuse Before Duplication

Existing models, components, and content structures should be reused unless a new structure is explicitly required.

### 7.5 Versioned Scientific Content

Protocols and method-related knowledge must remain version-aware and citation-stable.

### 7.6 Commerce and Knowledge Must Stay Linked

Products should not be isolated from the scientific use cases they support.

### 7.7 Explicit Relationship Graph

The platform should prefer explicit relations over implied relationships or unstructured text.

### 7.8 Safe Agent Readability

AI-facing surfaces must be read-only, structured, and traceable to canonical data.

## 8. Information Architecture

The top-level information architecture must support both browsing and task completion.

### 8.1 Primary Navigation

- Home
- Applications
- Methods
- Protocols
- Products
- Resources
- Search
- Quote
- Cart

### 8.2 User Journey

The canonical journey is:

`Goal -> Method -> Protocol -> Product -> Purchase`

This does not eliminate other entry points.
It is the primary design path that all other paths should reinforce.

### 8.3 Content Families

- Home surfaces the product promise and entry points.
- Applications organize use-case-driven discovery.
- Methods organize workflow families.
- Protocols provide structured procedures.
- Products convert scientific context into commercial action.
- Resources provide supporting evidence and documents.
- Search is a universal access point across product and knowledge surfaces.
- Quote and Cart connect evaluation to purchase.

## 9. Initial Domain Scope

The product should launch with a clear seed domain rather than a vague taxonomy.

### 9.1 Initial Application Areas

The initial application set from the PRD is:

- RNA Labeling
- DNA Labeling
- Click Chemistry
- mRNA Synthesis
- NGS Library Prep
- ADC Conjugation
- Cell Tracking

### 9.2 Initial Method Areas

The initial method set from the PRD is:

- Sanger Sequencing
- Targeted NGS
- RNA-seq
- RIP-seq
- In Vitro Transcription
- Click Conjugation
- Terminal Transferase Labeling

### 9.3 Initial Knowledge Shape

These seed areas should be enough to prove the model:

- Research intent can be organized by application.
- Methods can be linked to protocols.
- Protocols can link to products.
- Products can be supported by references and compatibility rules.

### 9.4 Initial Product Surface Expectations

Each product must be able to expose:

- Scientific context
- Related applications
- Related methods
- Related protocols
- Compatibility evidence
- Reference links
- Inventory and commerce readiness

## 10. Existing System Baseline

This chapter assumes the following baseline snapshot from the PRD:

| Area | Baseline |
|---|---|
| Frontend | Vue 3 |
| Backend | Django 5.1 REST |
| Existing catalog size | 109 products, 292 SKUs |
| Existing retained model families | ProductClass, Product, ProductCatalog, Application, Order, Quote, Wishlist, Basket, PdfFile |

### 10.1 Baseline Meaning

- The platform is not greenfield.
- Existing retained models must be respected unless a later chapter explicitly proposes controlled evolution.
- New structures must extend the current baseline, not casually replace it.

## 11. Success Metrics

Success metrics must be measurable from product behavior and system data, not from subjective sentiment.

| Metric | What It Measures | Source of Truth | Why It Matters |
|---|---|---|---|
| Revenue | Sales performance across products and enterprise motions | Orders, quotes, finance records | Confirms the platform drives business value |
| Quote Conversion | How often quote requests become accepted deals | Quote workflow data | Measures commercial effectiveness |
| Protocol Usage | How often users consult protocol content | Protocol views, saves, downstream product actions | Measures scientific utility |
| API Calls | Structured data usage by internal and external clients | API logs and analytics | Measures platform reusability |
| AI Citations | How often AI systems reference canonical platform data | Agent logs, structured outputs, citation telemetry | Measures machine-readability and authority |

### 11.1 Metric Rules

- Metrics must be instrumented consistently.
- Metrics must be attributable to a stable resource or event.
- Metrics should support trend analysis over time.
- Metrics should be aligned to product stages, not only overall traffic.

## 12. Release Philosophy

The roadmap should respect the product evolution sequence.

### 12.1 Phase 1

Database and knowledge layer.
This establishes the canonical product graph and stable relationships.

### 12.2 Phase 2

Application center.
This makes research intent a first-class navigation model.

### 12.3 Phase 3

Method center.
This makes workflow families and protocols discoverable and usable.

### 12.4 Phase 4

Protocol center.
This makes procedures structured, versioned, and linkable to products.

### 12.5 Phase 5

Agent layer.
This makes the platform machine-readable and capability-ready.

## 13. Scope Boundaries and Non-Goals

The product must stay focused on the scientific reagent platform mission.

### 13.1 In Scope

- Reagent discovery
- Research application navigation
- Method and protocol discovery
- Product-method-protocol linkage
- Evidence and reference linking
- Compatibility exposure
- Quote/cart/order flows
- Structured metadata and agent-friendly retrieval

### 13.2 Out of Scope

- Full LIMS replacement
- Full ELN replacement
- Social collaboration features
- Arbitrary user-generated scientific publishing
- Unstructured CMS behavior as the primary content model
- Agent write access to transactional data

### 13.3 Boundary Rule

If a requested feature does not strengthen the research-to-product chain or the machine-readable scientific graph, it should be treated as out of scope unless explicitly approved.

## 14. Cross-Chapter Dependencies

This chapter defines the why.
The other chapters define the how.

| Chapter | Dependency on This Chapter |
|---|---|
| Chapter 2 System Architecture | Must implement the layering implied here |
| Chapter 3 Domain Model | Must formalize the entities and relationships described here |
| Chapter 4 Database Architecture | Must persist the product graph implied here |
| Chapter 5 Frontend PRD | Must express the navigation and user journey defined here |
| Chapter 6 Backend API Spec | Must expose the resources required by this vision |
| Chapter 7 Knowledge Graph | Must represent the scientific graph described here |
| Chapter 8 Application / Method / Protocol Spec | Must operationalize the journey defined here |
| Chapter 9 AI Agent Integration | Must support the machine-readable goals defined here |
| Chapter 10 Roadmap | Must sequence delivery according to this evolution |
| Chapter 11 Codex Rules | Must protect the intent and scope defined here |
| Chapter 12 Design System | Must support the experience quality implied here |

## 15. Acceptance Criteria

This chapter is complete when all of the following are true:

- The product can be described in one sentence without ambiguity.
- The product evolution from ecommerce to agent infrastructure is explicit.
- The primary user groups and their needs are clearly defined.
- The business model is tied to platform surfaces.
- The information architecture reflects the research-to-purchase journey.
- The initial domain scope is concrete and seedable.
- The success metrics are measurable and aligned to the business.
- The platform boundaries and non-goals are explicit.
- Downstream chapters can implement against this chapter without needing to rewrite the product intent.

## 16. Glossary

### 16.1 Research Goal

The scientific intent that starts the journey.

### 16.2 Application

A use-case category that groups methods by scientific purpose.

### 16.3 Method

A research workflow family that explains how an application is executed.

### 16.4 Protocol

A versioned, structured procedure that can be followed and cited.

### 16.5 Product

A commercial reagent or scientific item that participates in the knowledge graph.

### 16.6 SKU

The purchase-specific selling unit for a product.

### 16.7 Order

The transactional result of a completed purchase path.

### 16.8 AI-Readable

Structured in a way that supports retrieval, citation, and downstream machine consumption without manual interpretation.

