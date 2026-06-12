# Chapter 11 Codex Rules

## Document Authority

This chapter defines the mandatory development rules for Codex and any downstream code-generating or code-editing agents working on LabPro Global.
It turns the product vision, architecture, domain model, database design, and roadmap into a set of change-control rules.

If a later implementation note conflicts with this chapter on model changes, API changes, schema changes, or layering, this chapter wins on change-control policy and the later note must be adjusted.

This chapter is intentionally strict:

- It defines what agents may change.
- It defines what agents must not change.
- It defines when the agent must stop and ask.
- It defines compatibility and migration rules.
- It defines review and audit expectations.

## 1. Codex Mission

Codex exists to help implement the platform safely and consistently.

Its job is to:

- Extend the platform without violating canonical design
- Reuse existing structures instead of duplicating them
- Preserve compatibility during migration windows
- Respect the scientific-to-commercial hierarchy
- Avoid introducing unreviewed architecture drift

Codex is not allowed to act as an autonomous product architect that silently changes the system’s meaning.

## 2. Core Rules

### 2.1 Do Not Redesign Existing Database Without Approval

- The existing database must not be redesigned casually.
- Major schema redesigns require explicit approval and documentation updates.
- If a change alters entity meaning, ownership, or canonical relations, it is a redesign and must be treated as such.

### 2.2 Reuse Models

- Reuse existing models when they already express the business meaning.
- Prefer extending canonical models over inventing parallel ones.
- Do not introduce a new model that duplicates the purpose of an existing model.

### 2.3 Reuse Components

- Reuse frontend components whenever the same data shape or interaction pattern already exists.
- Do not create multiple components for the same semantic UI unit unless there is a clearly documented reason.

### 2.4 Follow Domain Hierarchy

- Respect the canonical chain:

`Research Goal -> Application -> Method -> Protocol -> Product -> SKU -> Order`

- Do not flatten this hierarchy into a generic content system.

### 2.5 No Duplicated APIs

- Do not create duplicate APIs for the same canonical resource.
- Do not create parallel routes that expose the same concept through conflicting contracts.

### 2.6 No Direct DB Access from Views

- Views must not perform direct database orchestration for core domain operations.
- Views must call services or equivalent domain orchestration layers.

## 3. What Codex May Change

Codex may safely change the following classes of artifacts when the change is within the documented scope:

- Documentation files
- Service-layer logic
- Serializers
- Thin views
- Reusable frontend components
- Styles and layout code consistent with the design system
- Query helpers and read models
- Migration scripts that follow the documented migration strategy
- Tests that validate the documented contracts

## 4. What Codex Must Not Change Without Explicit Approval

### 4.1 Schema Redesign

- Renaming canonical tables or changing their meaning
- Reversing ownership relations
- Replacing explicit through tables with anonymous many-to-many relations when the relation has meaning
- Removing or renaming stable identity fields

### 4.2 Public Contract Breakage

- Breaking public API fields without a version or migration plan
- Changing canonical JSON-LD vocabulary without coordination
- Changing public page structure in a way that breaks the documented frontend PRD

### 4.3 Knowledge Graph Breakage

- Breaking the Goal -> Application -> Method -> Protocol -> Product -> SKU chain
- Removing evidence links or compatibility semantics without replacement
- Rewriting published protocol history destructively

### 4.4 Agent Boundary Breakage

- Letting agent layers write directly to canonical data
- Creating a shadow knowledge base
- Exposing private or unpublished content through public AI surfaces

## 5. Approval Conditions

Codex must stop and ask for approval before performing changes that:

- Redesign the database schema
- Change canonical entity meaning
- Change public resource contracts in a breaking way
- Remove or rename public-facing stable identifiers
- Collapse versioned scientific content into unversioned content
- Introduce a new data source of truth
- Alter the canonical knowledge graph direction
- Change the product vision or roadmap sequencing

## 6. Compatibility Rules

### 6.1 Backward Compatibility

- Preserve existing public behavior during migration windows.
- Add new fields before removing old ones when possible.
- Maintain read compatibility until replacement behavior is verified.

### 6.2 Dual-Path Strategy

- When replacing a field or relation, support both old and new paths during transition.
- Use derived compatibility layers when necessary.
- Remove the old path only after the new one has been validated and documented.

### 6.3 Safe Deprecation

- Mark resources deprecated before removal when the public or scientific graph may depend on them.
- Do not hard-delete published scientific content unless the business rules explicitly permit it and the consequences are documented.

### 6.4 Version Discipline

- Version public APIs.
- Version scientific content when the content is cited or published.
- Preserve protocol history and citation stability.

## 7. Model Change Rules

### 7.1 Adding a Model

A new model may be added only if:

- Its purpose cannot be expressed by an existing model
- Its ownership is documented
- Its API exposure is documented
- Its migration path is documented
- Its relation to the knowledge graph is documented

### 7.2 Modifying a Model

When modifying an existing model, Codex must consider:

- Field meaning
- Index impact
- API impact
- JSON-LD impact
- Search impact
- Migration impact
- Compatibility impact

### 7.3 Deleting a Model

Deletion of a canonical model is highly restricted.

- Prefer archival semantics.
- Prefer deprecation over deletion.
- If deletion is unavoidable, document the replacement path and data retention implications.

## 8. API Change Rules

### 8.1 Stable Contracts

- API fields exposed to the frontend or agents should be treated as contracts.
- Internal refactors must not break published resource shape without a versioning plan.

### 8.2 Route Discipline

- Avoid duplicate endpoints for the same resource.
- Keep route names aligned with canonical entities.

### 8.3 Response Discipline

- Keep the `success / data / meta` envelope consistent.
- Preserve canonical IDs and relationship semantics.

### 8.4 Expansion Discipline

- `include` and `expand` are opt-in only.
- Expanded payloads must not become a second canonical source.

## 9. Frontend Change Rules

### 9.1 Component Reuse

- Reuse `ApplicationCard`, `MethodCard`, `ProtocolCard`, and `ProductCard` patterns where appropriate.
- Avoid recreating equivalent components with different names.

### 9.2 Page Structure

- Preserve the page structures defined in the frontend PRD.
- Do not collapse scientific sections into generic content blocks.

### 9.3 Scientific Context

- Product pages must keep applications, methods, protocols, references, and inventory visible in the documented way.
- Do not hide essential scientific metadata behind interaction patterns that make the page unusable.

## 10. Migration Rules

### 10.1 Migration Order

- Add nullable or additive structures first.
- Backfill data.
- Validate read paths.
- Tighten constraints only after compatibility is confirmed.

### 10.2 Zero-Downtime Preference

- Prefer non-disruptive migrations.
- Use concurrent index creation when appropriate.
- Avoid table rewrites on large or public tables unless necessary and approved.

### 10.3 Backfill Discipline

- Backfills must be idempotent.
- Backfills must be rerunnable.
- Backfills must not duplicate canonical records.

### 10.4 Validation After Migration

- After migration, validate row counts, relation integrity, and key public flows.

## 11. Service Boundary Rules

### 11.1 Thin Views

- Keep views thin.
- Views should only route requests and return responses.
- Domain logic belongs in services.

### 11.2 Serializer Role

- Serializers validate structure and shape.
- Serializers do not orchestrate multi-model business workflows.

### 11.3 Service Role

- Services own transactions and cross-model writes.
- Services are responsible for enforcing the domain model and compatibility logic.

### 11.4 Query Layer

- Query helpers may be used for complex reads.
- Query helpers must not replace service-layer ownership of business behavior.

## 12. Agent Safety Rules

### 12.1 Read-Only Default

- Agent surfaces are read-only unless explicitly redefined.
- Agent layers must not mutate canonical state directly.

### 12.2 No Shadow Truth

- Agents must not create or depend on a hidden alternate source of truth.

### 12.3 Traceability

- Agent outputs must be traceable to canonical data, graph paths, or evidence.

### 12.4 Private Data Protection

- Agents must not expose unpublished or restricted data through public surfaces.

## 13. Review and Audit Rules

### 13.1 Self-Check Requirement

Before landing any substantial change, Codex should verify:

- The change matches the relevant chapter
- The change does not break known contracts
- The change preserves or documents compatibility

### 13.2 Review Focus

Code review should pay special attention to:

- Schema changes
- API contract changes
- Relation changes
- Search behavior
- Agent output shape
- Versioning and deprecation

### 13.3 Audit Trail

Material changes should leave a clear trail in:

- Documentation
- Migration history
- Tests
- Changelog or release notes when appropriate

## 14. Escalation Rules

Codex must escalate to human review when:

- A change alters canonical meaning
- A change risks breaking public contracts
- A change affects published scientific history
- A change introduces new write paths for agents
- A change requires approval per the roadmap sequencing

## 15. Forbidden Patterns

The following patterns are forbidden unless explicitly approved:

- Direct ORM writes from views
- Duplicated APIs for one resource concept
- Shadow databases or undocumented read stores acting as truth
- Silent schema redesigns
- Unversioned breaking API changes
- Product pages that no longer connect to the scientific graph
- Agent write access to canonical tables

## 16. Cross-Chapter Dependencies

This chapter depends on the product vision, system architecture, domain model, database architecture, frontend PRD, backend API spec, knowledge graph, roadmap, and AI integration chapters.
It also governs how future work should be implemented and reviewed.

| Chapter | Dependency on This Chapter |
|---|---|
| Chapter 1 Product Vision | Defines the product direction that this chapter protects |
| Chapter 2 System Architecture | Defines the layer boundaries that this chapter enforces |
| Chapter 3 Domain Model | Defines the entity hierarchy that this chapter protects |
| Chapter 4 Database Architecture | Defines the schema rules that this chapter protects |
| Chapter 5 Frontend PRD | Defines the page structures and reusable components this chapter protects |
| Chapter 6 Backend API Spec | Defines the public contract this chapter protects |
| Chapter 7 Research Knowledge Graph | Defines the scientific graph semantics this chapter protects |
| Chapter 8 Application / Method / Protocol Spec | Defines the content structure this chapter protects |
| Chapter 9 AI Agent Integration | Defines the read-only AI boundary this chapter protects |
| Chapter 10 Roadmap | Defines the delivery sequence this chapter must respect |
| Chapter 12 Design System | Defines the visual and component consistency rules this chapter must protect |

## 17. Acceptance Criteria

This chapter is complete when all of the following are true:

- The no-redesign rule is explicit.
- The reuse rules are explicit.
- The no-duplicate-API rule is explicit.
- The no-direct-DB-from-views rule is explicit.
- Approval conditions are explicit.
- Compatibility and migration rules are explicit.
- Service, frontend, and agent boundaries are explicit.
- Review and escalation expectations are explicit.
- The chapter can be used as a change-control policy for future Codex work.
