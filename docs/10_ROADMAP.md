# Chapter 10 Roadmap

## Document Authority

This chapter defines the delivery roadmap for LabPro Global.
It sequences the platform from the current ecommerce baseline toward the AI-native scientific capability platform described in Chapter 1 and supported by the other chapters.

If a later planning or delivery document conflicts with this chapter on sequencing, dependency order, or phase exit criteria, this chapter wins on roadmap intent and the later document must be adjusted.

This chapter is intentionally execution-oriented:

- It defines the delivery phases.
- It defines what each phase must deliver.
- It defines the dependencies between phases.
- It defines the exit criteria for each phase.
- It defines the main risks and transition constraints.

## 1. Roadmap Purpose

The roadmap exists to turn the platform vision into a controlled sequence of deliverables.

It must ensure that:

- Database and knowledge foundations are built first.
- Application, method, and protocol experiences follow in a stable order.
- Agent capabilities are added only after the structured data foundation is in place.
- Existing ecommerce behavior remains intact while the platform evolves.

## 2. Roadmap Principles

### 2.1 Foundation First

- Build the canonical data and knowledge layer before layering advanced experiences.
- Do not expose agent capabilities before the graph is stable.

### 2.2 Incremental Value

- Each phase should create visible user value.
- Each phase should leave the platform in a usable state.

### 2.3 Dependency Discipline

- Later phases must not assume work from earlier phases that has not yet been completed.
- Each phase must have explicit entry and exit conditions.

### 2.4 Compatibility Preservation

- Existing ecommerce functions must continue to work while the platform gains scientific depth.
- New work should extend the product, not destroy the current baseline.

### 2.5 Readiness for AI

- AI capability comes last in the initial roadmap sequence because it depends on stable graph and structured-data foundations.

## 3. Roadmap Phases

The PRD defines the roadmap sequence as:

1. Database and Knowledge Layer
2. Application Center
3. Method Center
4. Protocol Center
5. Agent Layer

## 4. Phase 1 - Database and Knowledge Layer

### 4.1 Objective

Establish the canonical scientific and commerce foundation.

### 4.2 Deliverables

- Canonical database baseline
- Knowledge graph nodes and relations
- Product extension fields
- Mapping tables for scientific and evidence relationships
- Core API and read model foundations
- Initial structured metadata support

### 4.3 Primary Chapters Involved

- Chapter 3 Domain Model
- Chapter 4 Database Architecture
- Chapter 6 Backend API Spec
- Chapter 7 Research Knowledge Graph

### 4.4 Exit Criteria

- The canonical graph exists in the data model.
- Products can be linked to applications, methods, protocols, references, and compatibility.
- Structured data can be derived from the canonical source.
- The platform can support goal -> method -> protocol -> product navigation at a data level.

### 4.5 Risks

- Model drift between old and new product structures
- Incomplete migration or backfill
- Unclear compatibility semantics

## 5. Phase 2 - Application Center

### 5.1 Objective

Make research intent a first-class browsing surface.

### 5.2 Deliverables

- Application index and detail experiences
- Application-to-method navigation
- Application-to-protocol/product/reference surfacing
- Application page SEO and structured metadata

### 5.3 Primary Chapters Involved

- Chapter 1 Product Vision
- Chapter 5 Frontend PRD
- Chapter 7 Research Knowledge Graph
- Chapter 8 Application / Method / Protocol Spec

### 5.4 Exit Criteria

- Users can start from an application and reach methods, protocols, and products.
- Initial application set is visible and navigable.
- Application pages preserve scientific context and evidence.

### 5.5 Risks

- Application pages becoming shallow taxonomy pages instead of scientific entry points
- Weak linking between applications and the rest of the graph

## 6. Phase 3 - Method Center

### 6.1 Objective

Turn workflow families into a navigable, evaluable product surface.

### 6.2 Deliverables

- Method index and detail experiences
- Method advantages / limitations / cost / timeline views
- Method-to-protocol navigation
- Method-to-product navigation
- Method-page structured data support

### 6.3 Primary Chapters Involved

- Chapter 5 Frontend PRD
- Chapter 6 Backend API Spec
- Chapter 7 Research Knowledge Graph
- Chapter 8 Application / Method / Protocol Spec

### 6.4 Exit Criteria

- Users can evaluate methods by practical tradeoffs.
- Users can navigate from method to protocol and product context.
- Method pages support the scientific and commercial journey without ambiguity.

### 6.5 Risks

- Method pages overfocusing on marketing and underexposing scientific evidence
- Inconsistent presentation of method ranking or relevance

## 7. Phase 4 - Protocol Center

### 7.1 Objective

Make procedures stepwise, versioned, and product-linked.

### 7.2 Deliverables

- Protocol index and detail experiences
- Stepwise protocol presentation
- Troubleshooting and expected results
- Reference and product linkage
- Protocol version visibility

### 7.3 Primary Chapters Involved

- Chapter 4 Database Architecture
- Chapter 5 Frontend PRD
- Chapter 6 Backend API Spec
- Chapter 7 Research Knowledge Graph
- Chapter 8 Application / Method / Protocol Spec

### 7.4 Exit Criteria

- Users can read a protocol as a structured procedure.
- Protocol pages can connect users to the products required to execute them.
- Protocol content preserves version and citation context.

### 7.5 Risks

- Protocol pages becoming unstructured long-form text without executable structure
- Product links becoming disconnected from the step context

## 8. Phase 5 - Agent Layer

### 8.1 Objective

Expose the platform as a machine-readable scientific capability surface for agents.

### 8.2 Deliverables

- JSON-LD rollout on public resources
- Read-only agent retrieval patterns
- MCP reservation and read-model readiness
- Agent capability alignment for product recommendation, protocol retrieval, compatibility validation, and inventory validation
- Citation-safe structured outputs

### 8.3 Primary Chapters Involved

- Chapter 6 Backend API Spec
- Chapter 7 Research Knowledge Graph
- Chapter 9 AI Agent Integration

### 8.4 Exit Criteria

- AI systems can retrieve structured scientific knowledge.
- Agent outputs can be traced to canonical resources.
- Read-only AI surfaces do not mutate the source of truth.

### 8.5 Risks

- Adding AI capability before the graph is stable
- Creating a shadow knowledge base
- Exposing private or unpublished data through read surfaces

## 9. Dependency Map

### 9.1 Phase Dependency Order

- Phase 1 must complete before Phases 2-5.
- Phase 2 depends on the graph and data foundation from Phase 1.
- Phase 3 depends on Phase 2 and the same foundation.
- Phase 4 depends on Phase 3 and the underlying versioned protocol model.
- Phase 5 depends on the previous phases and on stable structured data.

### 9.2 Delivery Dependency Rules

- Do not start agent capability work before public structured data is stable.
- Do not publish protocol center content before the protocol data model supports versioning and step structure.
- Do not deepen frontend scientific navigation before the underlying API and graph can support it.

## 10. Release Milestones

The roadmap should be treated as milestone-based rather than purely chronological.

### 10.1 Milestone A

- Canonical graph and database foundation complete
- Core scientific resources available through APIs

### 10.2 Milestone B

- Application Center live
- Goal-driven browsing is usable

### 10.3 Milestone C

- Method Center live
- Workflow evaluation is usable

### 10.4 Milestone D

- Protocol Center live
- Execution-oriented knowledge is usable

### 10.5 Milestone E

- Agent layer live
- Structured AI retrieval is usable

## 11. Platform Evolution Narrative



### 11.1 V-Stage 与 Roadmap Phase 映射



| 第01章 V-Stage | 第10章 Phase | 内容 |

|---|---|---|

| V1 Ecommerce | （现有基线） | 产品目录 + SKU + 购物车/报价/订单 |

| — | Phase 1 | Database & Knowledge Layer（所有阶段公共基础设施） |

| V2 Research Application Platform | Phase 2 | Application Center |

| V3 Research Method Platform | Phase 3 + Phase 4 | Method Center + Protocol Center |

| V4 AI-Callable Platform | Phase 5 | Agent Layer |



These are not separate products.

They are successive capability layers over the same platform.



## 12. Scope Control

### 12.1 In Scope

- Scientific graph foundation
- Application / method / protocol surfaces
- Structured product context
- Search and read models
- Agent-read structured outputs

### 12.2 Out of Scope

- Replacing the entire commerce system
- Replacing the whole frontend with a new design language mid-stream
- Introducing agent writes into canonical tables
- Building non-canonical alternate knowledge stores

## 13. Risk Register

### 13.1 Data Risk

- Incomplete backfill
- Schema drift
- Unclear canonical identifiers

### 13.2 Product Risk

- Scientific pages losing commercial usefulness
- Commerce pages losing scientific context

### 13.3 Delivery Risk

- Too much parallel work before the foundation is stable
- Overcommitting to agent capabilities too early

### 13.4 Mitigation Rules

- Freeze canonical identifiers early.
- Keep APIs versioned.
- Preserve compatibility windows.
- Sequence agent work after structured data is stable.

## 14. Success Metrics by Phase

### 14.1 Phase 1 Metrics

- Canonical graph coverage
- Migration completeness
- Read model stability

### 14.2 Phase 2 Metrics

- Application page usage
- Navigation depth from application to method
- Engagement with reference and product links

### 14.3 Phase 3 Metrics

- Method page engagement
- Protocol click-through
- Product discovery from method pages

### 14.4 Phase 4 Metrics

- Protocol page usage
- Product usage from protocols
- Reference engagement

### 14.5 Phase 5 Metrics

- API calls
- AI citations
- Agent retrieval success
- Protocol retrieval success
- Compatibility validation usage

## 15. Cross-Chapter Dependencies

This chapter depends on the product vision, architecture, domain model, database architecture, frontend PRD, backend API spec, knowledge graph, and AI integration chapters.
It also informs the Codex rules chapter by defining what changes are allowed to land in which phase.

| Chapter | Dependency on This Chapter |
|---|---|
| Chapter 1 Product Vision | Defines the platform evolution this roadmap sequences |
| Chapter 2 System Architecture | Defines the structural delivery boundaries this roadmap respects |
| Chapter 3 Domain Model | Defines the domain objects that must exist before later phases |
| Chapter 4 Database Architecture | Defines the persistence foundation required by Phase 1 |
| Chapter 5 Frontend PRD | Defines the page families that map to Phase 2-4 delivery |
| Chapter 6 Backend API Spec | Defines the resource contracts required by the roadmap |
| Chapter 7 Research Knowledge Graph | Defines the graph foundation required by Phase 1 and beyond |
| Chapter 8 Application / Method / Protocol Spec | Defines the content centers delivered in Phases 2-4 |
| Chapter 9 AI Agent Integration | Defines the final phase and read-only AI constraints |
| Chapter 11 Codex Rules | Must enforce the sequence and compatibility rules defined here |
| Chapter 12 Design System | Defines the visual language required for frontend delivery |

## 16. Acceptance Criteria

This chapter is complete when all of the following are true:

- The phase order is explicit.
- Each phase has a clear objective and deliverables.
- Each phase has entry and exit criteria.
- Dependencies between phases are explicit.
- Risks and mitigations are explicit.
- The roadmap is aligned with the product evolution stated in Chapter 1.
- The roadmap is usable by human planners and coding agents without interpretation gaps.
