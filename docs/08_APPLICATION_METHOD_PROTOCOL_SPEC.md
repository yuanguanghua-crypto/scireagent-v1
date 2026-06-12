# Chapter 8 Application / Method / Protocol Spec

## Document Authority

This chapter defines how Application, Method, and Protocol are presented and operationalized across the LabPro Global experience.
It turns the scientific graph into concrete page behavior, content structure, and navigation rules.

If a later chapter conflicts with this chapter on page structure, content priority, navigation behavior, or relation presentation, this chapter wins on scientific content organization and the later chapter must be adjusted.

This chapter is intentionally practical:

- It defines the role of each content center.
- It defines the page structure for applications, methods, and protocols.
- It defines how products, references, and FAQ/troubleshooting content attach to these pages.
- It defines ordering, prominence, and cross-linking rules.
- It defines how these pages support the Goal -> Method -> Protocol -> Product journey.

## 1. Purpose of the Content Centers

The Application Center, Method Center, and Protocol Center are the core scientific discovery surfaces of the platform.

They exist to make the following journey usable:

`Goal -> Method -> Protocol -> Product -> Purchase`

These centers must support both human browsing and machine-readable consumption.

## 2. Content Center Definitions

### 2.1 Application Center

The Application Center organizes the platform by research use case.

It helps users answer:

- What scientific problem am I trying to solve?
- Which methods belong to this use case?
- Which protocols and products are relevant?


The Application Center sits below ResearchGoal in the scientific hierarchy: `ResearchGoal -> Application -> Method -> Protocol -> Product`. Each Application belongs to one ResearchGoal and should expose its parent goal context in the page header or overview block.

### 2.2 Method Center

The Method Center organizes the platform by workflow family.

It helps users answer:

- What method should I use?
- What are the method’s strengths and limitations?
- Which protocols and products support it?

### 2.3 Protocol Center

The Protocol Center organizes the platform by executable procedure.

It helps users answer:

- How do I execute this method?
- What materials, reagents, and equipment do I need?
- Which products are linked to the protocol?

## 3. Content Model Principles

### 3.1 Hierarchical Navigation

- Applications lead to Methods.
- Methods lead to Protocols.
- Protocols lead to Products.

### 3.2 Context Preservation

- Every page should preserve the scientific context of the current node.
- A product surfaced from a protocol should still show why it belongs there.

### 3.3 Evidence Preservation

- References and supporting documents should stay visible where they strengthen trust.
- Evidence should not be hidden in a generic footer if it supports the primary claim.

### 3.4 Commerce Bridge

- Product links should be actionable.
- Commerce must not override scientific meaning.

### 3.5 Version Stability

- Protocol content is versioned.
- Public pages should make the protocol version visible when relevant.

## 4. Application Center Specification

### 4.1 Purpose

The Application Center is the highest-level scientific browsing surface after the home page.

It should help users move from intent into a method family quickly.

### 4.2 Initial Applications

The PRD identifies the initial application set as:

- RNA Labeling
- DNA Labeling
- Click Chemistry
- mRNA Synthesis
- NGS Library Prep
- ADC Conjugation
- Cell Tracking

### 4.3 Application Page Structure

The PRD specifies the following page structure for applications:

- Overview
- Methods
- Protocols
- Products
- References
- FAQ

### 4.4 Application Page Responsibilities

The Application page must:

- Explain the use case in plain scientific language.
- Surface the methods that belong to the application.
- Surface protocols that are relevant to the application.
- Surface linked products without losing the application context.
- Surface references that justify the application’s scientific framing.
- Provide FAQ or guidance where it reduces user uncertainty.

### 4.5 Application Ordering Rules

- Methods should be the primary child content.
- Protocols should be secondary to methods but visible.
- Products should remain tied to the application, not treated as a separate catalog island.
- References should support the credibility of the application overview.

### 4.6 Application Content Priorities

Application pages should prioritize:

1. Scientific purpose
2. Method entry points
3. Protocol entry points
4. Product relevance
5. Supporting evidence
6. FAQ / guidance

### 4.7 Application Linking Rules

- Application -> Method is the primary link.
- Application -> Protocol is the secondary link.
- Application -> Product is a discovery link.
- Application -> Reference is an evidence link.

## 5. Method Center Specification

### 5.1 Purpose

The Method Center is the scientific workflow hub.

It should help users understand how to execute the scientific outcome and what products or protocols are involved.

### 5.2 Initial Methods

The PRD identifies the initial method set as:

- Sanger Sequencing
- Targeted NGS
- RNA-seq
- RIP-seq
- In Vitro Transcription
- Click Conjugation
- Terminal Transferase Labeling

### 5.3 Method Page Structure

The PRD specifies the following page structure for methods:

- Overview
- Advantages
- Limitations
- Cost
- Timeline
- Protocols
- Products

### 5.4 Method Page Responsibilities

The Method page must:

- Explain the method clearly enough for professional evaluation.
- Show why the method is useful.
- Show limitations and practical tradeoffs.
- Surface protocols in a ranked or curated order.
- Surface relevant products for the method.

### 5.5 Method Ordering Rules

- Overview should always be first.
- Advantages and limitations should be visible before deep protocol detail.
- Cost and timeline should help users gauge practical feasibility.
- Protocols should be the primary operational child content.
- Products should be presented as enabling or supporting items, not just inventory.

### 5.6 Method Content Priorities

Method pages should prioritize:

1. Scientific explanation
2. Practical decision support
3. Protocol list
4. Product list
5. Cost / timeline context

### 5.7 Method Linking Rules

- Method -> Protocol is the primary operational link.
- Method -> Product is the primary discovery link.
- Method -> Application is the parent-context link.
- Method -> Reference is the evidence link.

## 6. Protocol Center Specification

### 6.1 Purpose

The Protocol Center is the execution hub.

It should make a procedure understandable, stepwise, and linkable to products.

### 6.2 Protocol Template

The PRD specifies the protocol template as:

- Objective
- Principle
- Materials
- Reagents
- Equipment
- Steps
- Troubleshooting
- Expected Results
- References

The PRD also states that the protocol must link products.

### 6.3 Protocol Page Responsibilities

The Protocol page must:

- Present the protocol as a versioned scientific procedure.
- Show the materials and reagents required.
- Show steps in a clear ordered sequence.
- Surface troubleshooting guidance.
- Show expected results when available.
- Surface references that support the procedure.
- Link to products that are required, recommended, or otherwise relevant.

### 6.4 Protocol Ordering Rules

- Objective and principle should come before procedural detail.
- Materials, reagents, and equipment should be easy to scan.
- Steps must be ordered and visually explicit.
- Troubleshooting should be available without burying the procedure.
- References should be visible near the protocol content.

### 6.5 Protocol Content Priorities

Protocol pages should prioritize:

1. Execution clarity
2. Step ordering
3. Material and reagent completeness
4. Troubleshooting
5. Evidence
6. Product linkage

### 6.6 Protocol Linking Rules

- Protocol -> Method is the ownership link.
- Protocol -> Product is the execution link.
- Protocol -> Reference is the evidence link.
- Protocol -> ProtocolStep is the structural link.

## 7. Cross-Center Relationship Rules

### 7.1 Application to Method

- Each application should surface its related methods prominently.
- A method surfaced from an application should preserve the application context.

### 7.2 Method to Protocol

- Each method should surface its related protocols prominently.
- A protocol surfaced from a method should preserve the method context.

### 7.3 Protocol to Product

- Each protocol should surface the products required or recommended for execution.
- Product cards surfaced in protocol context should explain why the product is relevant.

### 7.4 Product Backlinks

Products should expose backlinks to:

- Applications
- Methods
- Protocols
- References

This prevents the product page from becoming a dead-end commerce object.

## 8. Page Composition Rules

### 8.1 Overview Blocks

Overview blocks should:

- Explain what the node is
- Explain why it matters
- Provide a fast path to the next level of detail

### 8.2 Child Content Blocks

Child blocks should:

- Be ordered by relevance, editorial priority, or execution importance
- Avoid overwhelming the user with every possible relation at once
- Preserve canonical graph relationships

### 8.3 Reference Blocks

Reference blocks should:

- Be visible enough to establish trust
- Avoid duplicating citation content across unrelated sections
- Link to canonical reference resources when available

### 8.4 FAQ and Guidance Blocks

FAQ or guidance blocks should:

- Reduce uncertainty
- Clarify what the page does and does not cover
- Stay subordinate to the scientific content itself

## 9. Sorting and Prominence

### 9.1 Primary Sorting Rules

Within each center, the most relevant child content should appear first.

Possible ranking inputs:

- Scientific relevance
- Editorial prominence
- Citation strength
- Product relevance
- Protocol version status

### 9.2 Deterministic Ordering

The page should not feel random.
If a relation is ordered in the backend, the frontend should respect that order unless the UX requires a clear, documented override.

### 9.3 Featured vs Complete Views

- Featured views may show a curated subset.
- Complete views should expose the full related set when needed.
- The distinction should be explicit to the user where it matters.

## 10. Product Integration Rules

### 10.1 Product Context in Application Pages

Application pages may show products that are relevant to the application.
These products should be framed as supporting items for the scientific use case.

### 10.2 Product Context in Method Pages

Method pages may show products that are relevant to the workflow.
These products should be framed as enabling items for the method.

### 10.3 Product Context in Protocol Pages

Protocol pages may show products that are required or recommended for the procedure.
These products should be framed as execution items.

### 10.4 Product Page Backlinking

Product pages should link back to:

- Applications
- Methods
- Protocols
- References

This preserves the scientific story behind the product.

## 11. References and Evidence

### 11.1 Evidence Placement

References should be visible on:

- Application pages when they support the application framing
- Method pages when they support the workflow
- Protocol pages when they support the procedure
- Product pages when they support the claim or usage context

### 11.2 Evidence Priority

Evidence should be surfaced where it is most relevant to the page’s core question.

### 11.3 Evidence Hygiene

- Avoid freeform citation duplication.
- Link to canonical reference resources where possible.
- Keep citation context tied to the node it supports.

## 12. FAQ and Troubleshooting

### 12.1 FAQ in Application and Method Context

FAQ blocks should answer:

- What is this used for?
- What is it not used for?
- How do I choose between related methods?

### 12.2 Troubleshooting in Protocol Context

Troubleshooting should answer:

- What can go wrong?
- What is the expected outcome?
- What should I check first?

### 12.3 Support Rule

FAQ and troubleshooting are support surfaces, not the main scientific content.

## 13. Structured Data and SEO Hooks

### 13.1 Structured Metadata

Application, Method, and Protocol pages should support structured metadata consistent with the frontend PRD and database chapter.

### 13.2 Canonical IDs

Pages should expose canonical IDs and canonical URLs when applicable.

### 13.3 Content Semantics

- Application pages should read like application pages.
- Method pages should read like method pages.
- Protocol pages should read like protocol pages.

This is important both for users and for search / agent systems.

## 14. Implementation Constraints

### 14.1 No Graph Flattening

Do not flatten Application, Method, and Protocol into a single undifferentiated content type.

### 14.2 No Lost Ownership

Protocol ownership by Method and Method ownership by Application must stay visible in the product structure.

### 14.3 No Product Dead Ends

Product pages must continue to connect back into the scientific graph.

### 14.4 No Unstructured Substitute

The page structure must not be replaced by a freeform CMS that loses scientific ordering or versioning.

## 15. Cross-Chapter Dependencies

This chapter depends on the product vision, system architecture, domain model, database architecture, frontend PRD, and knowledge graph chapters.
It also informs the search, agent, roadmap, and codex rule chapters.

| Chapter | Dependency on This Chapter |
|---|---|
| Chapter 1 Product Vision | Defines the scientific journey this content hierarchy must express |
| Chapter 2 System Architecture | Defines the structural boundaries this content hierarchy must respect |
| Chapter 3 Domain Model | Defines the ownership relationships surfaced here |
| Chapter 4 Database Architecture | Defines the fields and relations that populate these pages |
| Chapter 5 Frontend PRD | Defines the page and component patterns used to render this content |
| Chapter 6 Backend API Spec | Defines the resource payloads that feed this content |
| Chapter 7 Knowledge Graph | Defines the graph semantics this chapter operationalizes |
| Chapter 9 AI Agent Integration | Must consume these same relationships and page semantics |
| Chapter 10 Roadmap | Must sequence delivery of these content centers |
| Chapter 11 Codex Rules | Must preserve the hierarchy and prevent accidental flattening |

## 16. Acceptance Criteria

This chapter is complete when all of the following are true:

- Application, Method, and Protocol centers are explicitly defined.
- Each center has a page structure and content priority.
- Cross-linking rules between centers are explicit.
- Product integration rules are explicit.
- Evidence and FAQ/troubleshooting placement are explicit.
- Sorting and prominence rules are explicit.
- Structured data and SEO hooks are considered.
- The frontend and content teams can implement the centers without inventing a new information architecture.

