# Chapter 9 AI Agent Integration Spec

## Document Authority

This chapter defines how AI systems and agents integrate with LabPro Global.
It specifies what can be read, what must remain read-only, how the platform exposes structured scientific knowledge, and how future capability layers should be built.

If a later chapter conflicts with this chapter on AI capability scope, read/write boundaries, structured output rules, or agent access semantics, this chapter wins on AI integration intent and the later chapter must be adjusted.

This chapter is intentionally strict:

- It defines the AI integration phases.
- It defines the canonical capabilities.
- It defines what agents may read.
- It defines what agents may not do.
- It defines how REST, JSON-LD, MCP, and future capability APIs relate.

## 1. AI Integration Mission

The AI layer exists to make the scientific graph machine-readable, retrievable, explainable, and citable.

The platform should let AI systems:

- Recommend products
- Retrieve protocols
- Validate compatibility
- Validate inventory-related conditions
- Explain the scientific reasoning path behind a recommendation

The AI layer must never become a second source of truth or a write path into canonical transactional data.

## 2. AI Integration Principles

### 2.1 Read First

- AI integrations are read-oriented by default.
- AI systems should consume canonical, structured data.
- AI systems must not write directly to the core data model.

### 2.2 Canonical Data Only

- Agent outputs must be traceable back to canonical resources.
- AI systems must not invent relationships that are not present in the graph or supporting evidence.

### 2.3 Structured by Default

- AI-facing data should be structured, not freeform.
- Structured output should align with REST, JSON-LD, and future MCP layers.

### 2.4 Evidence and Citation Safety

- AI responses should preserve source references when possible.
- Protocols and products should be cited through canonical identifiers, not opaque text blobs.

### 2.5 Stable Vocabulary

- The AI layer must share the same canonical entity vocabulary as the domain model and database layer.
- The same product or protocol should not appear under multiple conflicting identities.

## 3. AI Layer Phases

The PRD defines the AI evolution in four phases:

1. REST API
2. JSON-LD
3. MCP
4. Agent Capability API

### 3.1 Phase 1: REST API

REST is the baseline machine consumption layer.

It provides:

- Canonical resource retrieval
- Search
- Relationship traversal
- Structured lists and detail pages

### 3.2 Phase 2: JSON-LD

JSON-LD is the structured public data layer for SEO and machine readability.

It provides:

- Schema-compatible structured representations
- Public resource semantics
- Canonical IDs and URLs

### 3.3 Phase 3: MCP

MCP is reserved as a future agent-facing read layer.

It provides:

- Read-only retrieval for agent workflows
- Shape-stable resource payloads
- Canonical vocabulary for capability consumption

### 3.4 Phase 4: Agent Capability API

The Agent Capability API is a future higher-level capability surface built on the canonical data and read layers.

It may provide:

- Product recommendation
- Protocol retrieval
- Compatibility validation
- Inventory validation

This phase must remain grounded in canonical resources rather than acting as a separate data store.

## 4. Canonical Capability Set

The PRD explicitly names these AI capabilities:

- Product recommendation
- Protocol retrieval
- Compatibility validation
- Inventory validation

### 4.1 Product Recommendation

Purpose:

- Recommend products based on scientific context, method, protocol, and compatibility data.

Required inputs:

- Product resource data
- Application context
- Method context
- Protocol context
- Compatibility facts
- Reference evidence

Required output traits:

- Explainable
- Citable
- Traceable to canonical resources

### 4.2 Protocol Retrieval

Purpose:

- Retrieve protocols that match a method, application, or product context.

Required inputs:

- Method
- Application
- Protocol
- ProtocolStep
- Reference

Required output traits:

- Version-aware
- Structured
- Step-preserving

### 4.3 Compatibility Validation

Purpose:

- Determine whether products, methods, or protocols are compatible according to canonical rules.

Required inputs:

- ProductCompatibility
- Compatibility
- Product
- Method
- Protocol

Required output traits:

- Explicit
- Rule-based
- Traceable to canonical compatibility definitions

### 4.4 Inventory Validation

Purpose:

- Help determine whether a requested product or SKU is available or operationally suitable.

Required inputs:

- Product
- SKU
- Inventory status
- Commerce state

Required output traits:

- Current
- Read-only
- Non-authoritative for inventory mutation

## 5. Agent Read Boundaries

### 5.1 Allowed Reads

Agents may read:

- Public product data
- Public application data
- Public method data
- Public protocol data
- Public references where allowed
- Public compatibility summaries
- Search results
- JSON-LD payloads
- Canonical resource metadata

### 5.2 Restricted Reads

Agents may have restricted or controlled access to:

- Draft content
- Hidden products
- Internal editorial notes
- Unpublished protocol versions
- Private compatibility reasoning

### 5.3 Disallowed Actions

Agents must not:

- Write directly to canonical tables
- Mutate transaction state
- Create or delete products, protocols, or references without an explicit privileged service path
- Rewrite compatibility or protocol history
- Act as an authority over source-of-truth data

### 5.4 Boundary Rule

If an AI workflow needs a write action, that action must go through the same backend service and permission model as any other privileged system action.

## 6. Data Sources for AI

The AI layer must be derived from canonical data sources:

- Chapter 3 domain model
- Chapter 4 database architecture
- Chapter 6 backend API contract
- Chapter 7 research knowledge graph

### 6.1 Source of Truth

The canonical database remains the source of truth.

### 6.2 Derived Read Layers

The platform may expose:

- REST read models
- JSON-LD payloads
- Search projections
- MCP read projections

These must remain rebuildable from canonical data.

### 6.3 No Shadow Truth

- Search indexes are not authoritative truth.
- Agent memory is not authoritative truth.
- Cached response bodies are not authoritative truth.

## 7. Structured Output Rules

### 7.1 Canonical Identity

Structured outputs must preserve:

- Canonical IDs
- Canonical URLs where applicable
- Canonical resource names
- Canonical relation direction

### 7.2 Output Shape Stability

- AI-readable payloads should remain stable over time.
- If a field is removed or renamed, a migration or versioning strategy is required.

### 7.3 Citation Safety

- If a response includes a claim, it should ideally be traceable to a reference, protocol, or compatibility rule.
- Avoid uncited claims when the underlying data can be cited.

### 7.4 Schema Compatibility

- JSON-LD should align with visible content.
- MCP should align with REST and JSON-LD vocabulary.
- Agent capability outputs should align with canonical resource types.

## 8. Reasoning Model

The agent reasoning model should be graph-based.

### 8.1 Primary Reasoning Paths

Canonical reasoning paths include:

- ResearchGoal -> Application -> Method -> Protocol -> Product -> SKU
- Product -> Method -> Application -> ResearchGoal
- Protocol -> Product -> SKU
- Product -> ProductReference -> Reference
- Product -> ProductCompatibility -> Compatibility

### 8.2 Reasoning Rule

Agents should prefer explicit graph paths over freeform inference.

### 8.3 Explanation Rule

When an agent answers a question, it should ideally be able to explain:

- Why this product
- Why this protocol
- Why this compatibility result
- Why this inventory state

## 9. Retrieval and Recommendation Flow

### 9.1 Retrieval Flow

1. Agent receives a question or task.
2. The agent queries canonical read resources.
3. The agent resolves the graph path.
4. The agent returns a structured answer with traceable source data.

### 9.2 Recommendation Flow

1. Agent identifies user intent.
2. Agent evaluates the scientific context.
3. Agent checks protocol and compatibility constraints.
4. Agent recommends products or protocols with explanations.

### 9.3 Validation Flow

1. Agent or system asks whether a combination is valid.
2. The system evaluates canonical compatibility data.
3. The system returns a structured verdict and supporting rule context.

## 10. Public vs Private AI Surfaces

### 10.1 Public AI Surfaces

Public AI surfaces include:

- Public product pages
- Public applications
- Public methods
- Public protocols
- Public references
- Public search
- Public JSON-LD

### 10.2 Private AI Surfaces

Private AI surfaces may include:

- Draft scientific content
- Hidden products
- Internal editorial notes
- Unpublished protocol versions
- Internal compatibility logic

### 10.3 Visibility Rule

Public AI surfaces must not reveal private content unless explicitly published or authorized.

## 11. Error Handling and Safety

### 11.1 AI Error Behavior

When an AI system cannot answer confidently, it should:

- Say what is missing
- Return the best available canonical path
- Avoid inventing facts

### 11.2 Safety Rules

- Do not hallucinate unsupported compatibility claims.
- Do not invent protocol steps or product relations.
- Do not silently upgrade draft data to published data.
- Do not convert operational uncertainty into factual certainty.

### 11.3 Fallback Rules

If a capability cannot be fully satisfied, the agent should degrade gracefully to:

- Resource retrieval
- Search
- Canonical product or protocol summaries
- Evidence links

## 12. Versioning and Stability

### 12.1 Versioned Contracts

- REST endpoints should be versioned.
- JSON-LD vocabulary should remain stable.
- MCP payloads should be versioned or shape-stable.

### 12.2 Backward Compatibility

- Existing agent workflows should remain functional during migration windows.
- Breaking changes require explicit coordination.

### 12.3 Identity Stability

- Canonical IDs must remain stable.
- Canonical URLs should remain stable when possible.
- Protocol versioning must not destroy prior citation paths.

## 13. Integration with Search and Knowledge Graph

The AI layer must align with the search and knowledge graph layers.

### 13.1 Search Alignment

- Search results may seed agent reasoning.
- Search results must still point back to canonical resources.

### 13.2 Knowledge Graph Alignment

- Agent reasoning should traverse the same graph described in Chapter 7.
- The AI layer should not invent an alternate graph.

### 13.3 Recommendation Alignment

- Recommendation should use scientific context, not only popularity or inventory.

## 14. Implementation Constraints

### 14.1 No Direct Database Writes

Agents must not write directly to the database.

### 14.2 No Shadow Knowledge Base

Agents must not maintain a separate authoritative knowledge base outside the canonical platform.

### 14.3 No Untracked Derivations

Derived outputs must be traceable to source data and reproducible.

### 14.4 No Silent Expansion of Capability Scope

If a new AI capability is added, it must be documented and aligned to the canonical data model.

## 15. Cross-Chapter Dependencies

This chapter depends on the product vision, system architecture, domain model, database architecture, backend API spec, knowledge graph, and application/method/protocol chapters.
It also informs the roadmap and Codex rules chapters.

| Chapter | Dependency on This Chapter |
|---|---|
| Chapter 1 Product Vision | Defines the AI-native platform purpose this chapter supports |
| Chapter 2 System Architecture | Defines the read/write boundaries this chapter must respect |
| Chapter 3 Domain Model | Defines the entity graph this chapter consumes |
| Chapter 4 Database Architecture | Defines the canonical resources this chapter reads from |
| Chapter 5 Frontend PRD | Defines the frontend surfaces that may emit structured data |
| Chapter 6 Backend API Spec | Defines the REST contracts used by AI workflows |
| Chapter 7 Knowledge Graph | Defines the reasoning graph used by agents |
| Chapter 8 Application / Method / Protocol Spec | Defines the scientific content pages agents may reference |
| Chapter 10 Roadmap | Must sequence the AI capabilities described here |
| Chapter 11 Codex Rules | Must protect the read-only and canonical-data constraints described here |

## 16. Acceptance Criteria

This chapter is complete when all of the following are true:

- The AI integration phases are explicit.
- The canonical capability set is explicit.
- Agent read boundaries are explicit.
- Disallowed actions are explicit.
- Structured output rules are explicit.
- Retrieval and recommendation flows are explicit.
- Public and private AI surfaces are explicit.
- Versioning and stability rules are explicit.
- The AI layer can be implemented without inventing a separate source of truth.

