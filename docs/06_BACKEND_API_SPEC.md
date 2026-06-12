# Chapter 6 Backend API Spec

## Document Authority

This chapter defines the backend API contract for LabPro Global.
It translates the domain model and system architecture into stable, implementation-grade HTTP resources that the frontend, agents, and future integrations can rely on.

If a later chapter conflicts with this chapter on API shape, response rules, versioning, or read/write boundaries, this chapter wins on backend interface contract and the later chapter must be adjusted.

This chapter is intentionally strict:

- It defines the public route inventory.
- It defines list/detail/search behavior.
- It defines the standard response envelope.
- It defines query parameter conventions.
- It defines write semantics and service boundaries.
- It defines structured output and agent-facing read contracts.

## 1. API Mission

The backend API must expose the LabPro Global scientific graph and commerce objects in a stable, versioned, and machine-readable way.

The API must support:

- Human browsing and commerce flows
- Scientific navigation across applications, methods, protocols, and products
- Search across product and knowledge resources
- Structured output for SEO, AEO, and future AI consumption
- Safe write operations for commerce and content management

## 2. API Principles

### 2.1 Version First

**版本路径格式**：当前 API 版本为 `v1`。所有公共 API 端点使用 `/api/v1/` 前缀（与现有代码库一致）。示例：`/api` 在本规范其他位置为简写形式，实际实现时需替换为 `/api/v1`。

- Public APIs must be versioned.
- Versioned routes must remain stable during a release window.
- Breaking contract changes require explicit versioning or a migration plan.

### 2.2 Service Layer Ownership

- Views must stay thin.
- Business logic must live in services.
- Serializers validate and shape payloads.
- The API layer must not become the domain engine.

### 2.3 Canonical Identity

- Every resource must resolve to a canonical ID.
- The same object must not appear as multiple public identities across resources.

### 2.4 Read Models over Duplication

- REST responses may include derived summaries.
- Public APIs must not expose duplicate authoritative records for the same concept.
- Search, JSON-LD, and future MCP payloads must derive from canonical data.

### 2.5 Scientific Context Preservation

- Product endpoints must preserve scientific context.
- Protocol endpoints must preserve version and citation context.
- Compatibility endpoints must preserve rule semantics.

### 2.6 Stable Response Shape

- Responses must use the same envelope across the public API.
- Payload structure should be predictable by resource type.

## 3. API Surface Overview

The PRD explicitly calls for these primary routes:

- `/api/products`
- `/api/applications`
- `/api/methods`
- `/api/protocols`
- `/api/references`
- `/api/compatibility`

The platform also requires connected commerce and supporting routes for completeness.

### 3.1 API Families

- Core knowledge and commerce resources
- Search and discovery
- Commerce workflow resources
- Structured data and agent-oriented read resources

### 3.2 HTTP Method Policy

- `GET` for retrieval
- `POST` for creation
- `PUT` or `PATCH` for controlled updates
- `DELETE` only where deletion is intentionally supported by business rules

### 3.3 Write Policy

- Write endpoints must be transactional and service-driven.
- Write endpoints must validate relationships explicitly.
- Write endpoints must not bypass canonical domain rules.


### 3.4 Site Endpoints

Site-level endpoints provide aggregated data for the Home page and global navigation.

#### Endpoints

- `GET /api/v1/site/home`
- `GET /api/v1/site/navigation`

#### Home Response

The `/api/v1/site/home` endpoint returns a composite payload including:

- `hero`: Value proposition and primary call-to-action
- `search`: Search affordance data
- `featured_applications`: Curated application highlights
- `featured_methods`: Curated method highlights
- `featured_products`: Curated product highlights
- `resources`: Supporting content links
- `quote_contact`: Quote/contact entry point

#### Navigation Response

The `/api/v1/site/navigation` endpoint returns the primary navigation tree for the frontend, including category/classification hierarchy and user session state.

#### Write Rules

- Site endpoints are read-only.
- Content selection is editorial/curated and managed through the admin interface.


## 4. Standard Response Envelope

All public REST responses must use the canonical envelope:

```json
{
  "success": true,
  "data": {},
  "meta": {}
}
```

### 4.1 Envelope Rules

- The canonical public envelope is `success / data / meta`.
- `success` is a boolean.
- `data` contains the primary payload.
- `meta` contains pagination, filters, counts, errors, or request context as needed.
- Error responses must keep the same envelope shape when practical.

### 4.2 Error Envelope Shape

For errors, the API should still be predictable:

```json
{
  "success": false,
  "data": null,
  "meta": {
    "error": {
      "code": "validation_error",
      "message": "Human readable message",
      "details": {}
    }
  }
}
```

## 5. Common Query Conventions

### 5.1 Pagination

List endpoints should support pagination.

Recommended parameters:

- `page`
- `page_size`

### 5.2 Sorting

List endpoints should support sorting where meaningful.

Recommended parameter:

- `ordering`

### 5.3 Filtering

List endpoints may support resource-specific filters.

### 5.4 Search

Search endpoints or search query support should use a dedicated search parameter.

Recommended parameters:

- `q`
- `type`
- `scope`
- `include`
- `expand`

### 5.5 Relationship Expansion

- `include` and/or `expand` should be opt-in.
- Default responses should remain compact.
- Expanded payloads must not become a second authoritative source of truth.

## 6. Resource Contract Patterns

### 6.1 List Response Pattern

List responses should return:

- Resource IDs
- Canonical titles / names
- Summary fields
- Minimal relationship summaries
- Pagination metadata

### 6.2 Detail Response Pattern

Detail responses should return:

- Canonical resource fields
- Direct relationships as IDs or compact summaries
- Derived navigation aids
- Contextual scientific or commerce fields

### 6.3 Mutating Response Pattern

Write responses should return:

- Canonical IDs
- The created or updated resource summary
- Validation or workflow metadata
- Any next-step state needed by the client

## 7. Core Resource Specifications

### 7.1 Products

#### Endpoints

- `GET /api/products`
- `GET /api/products/{id}`
- `POST /api/products`
- `PATCH /api/products/{id}`

#### List Behavior

The product list must support:

- Product name search
- CAS search
- SMILES search
- InChI search
- Application-based discovery
- Method-based discovery
- Protocol-based discovery
- Inventory awareness where available

#### Detail Behavior

The product detail response should expose:

- Canonical product identity
- Scientific context
- Applications
- Methods
- Protocols
- Compatibility
- References
- Documents
- Inventory

#### Required Public Fields

- `id`
- `slug`
- `name`
- `cas`
- `smiles`
- `synonyms`
- `inchi`
- `purity`
- `storage`
- `shipping`
- `lead_time`
- `handling_notes`
- `shelf_life`
- `research_use_only`
- `application_ids`
- `method_ids`
- `protocol_ids`
- `reference_ids`
- `compatibility_summary`
- `sku_summary`

#### Write Rules

- Product creation and updates must go through the service layer.
- Product identity fields must be validated before persistence.
- Related objects must not be mutated implicitly by a product write unless explicitly requested and authorized.

### 7.1b ResearchGoals

#### Endpoints

- `GET /api/research-goals`
- `GET /api/research-goals/{id}`

#### Required Public Fields

- `id`
- `slug`
- `name`
- `summary`
- `priority`
- `status`
- `application_ids`

#### Write Rules

- ResearchGoals are read-only through the public API.
- ResearchGoal creation and updates are managed through the admin interface.
- ResearchGoal changes must preserve navigation stability.

### 7.2 Applications

#### Endpoints

- `GET /api/applications`
- `GET /api/applications/{id}`
- `POST /api/applications`
- `PATCH /api/applications/{id}`

#### Required Public Fields

- `id`
- `slug`
- `name`
- `summary`
- `sort_order`
- `status`
- `research_goal_id`
- `method_ids`
- `product_ids`
- `reference_ids`

#### Write Rules

- Applications are curated content and should be managed through controlled writes.
- Application changes must preserve navigation stability where possible.

### 7.3 Methods

#### Endpoints

- `GET /api/methods`
- `GET /api/methods/{id}`
- `POST /api/methods`
- `PATCH /api/methods/{id}`

#### Required Public Fields

- `id`
- `slug`
- `application_id`
- `name`
- `summary`
- `purpose`
- `advantages`
- `limitations`
- `cost_band`
- `timeline`
- `status`
- `protocol_ids`
- `product_ids`
- `reference_ids`

#### Write Rules

- A method must always belong to a single application.
- Method creation must not orphan the method from its application.

### 7.4 Protocols

#### Endpoints

- `GET /api/protocols`
- `GET /api/protocols/{id}`
- `POST /api/protocols`
- `PATCH /api/protocols/{id}`

#### Required Public Fields

- `id`
- `slug`
- `method_id`
- `version`
- `objective`
- `principle`
- `materials`
- `reagents`
- `equipment`
- `troubleshooting`
- `expected_results`
- `status`
- `steps`
- `reference_ids`
- `product_ids`

Notes:

- `reference_ids` is a read projection derived from canonical citation data and protocol content; the API must not imply a separate writable protocol-reference table unless a later schema chapter introduces one.
**派生规则**：Protocol detail 响应中的 `reference_ids` 通过解析 Protocol 的 `references` 文本字段提取引用标识符（如 DOI、PMID），在 `Reference` 表中匹配已规范化的引用记录，按文本中出现顺序返回匹配到的 `id` 列表。未能匹配的引用仅保留在原始文本中，不产生孤儿 ID。


#### Write Rules

- Protocols must be version-aware.
- Protocol updates must preserve published history.
- Protocol steps must be written through the service layer in the proper order.

### 7.5 References

#### Endpoints

- `GET /api/references`
- `GET /api/references/{id}`
- `POST /api/references`
- `PATCH /api/references/{id}`

#### Required Public Fields

- `id`
- `title`
- `authors`
- `journal`
- `year`
- `doi`
- `pmid`
- `url`
- `citation_text`
- `source_type`

#### Write Rules

- DOI and PMID normalization must occur before persistence or on canonicalization.
- References should remain reusable and canonical.

### 7.6 Compatibility

#### Endpoints

- `GET /api/compatibility`
- `GET /api/compatibility/{id}`
- `POST /api/compatibility`
- `PATCH /api/compatibility/{id}`

#### Required Public Fields

- `id`
- `source_product_id`
- `target_product_id`
- `compatibility_code`
- `verdict`
- `severity`
- `notes`
- `compatibility_id`

#### Write Rules

- Compatibility records are controlled data and must be validated against the governing rule definition.
- Compatibility facts must remain traceable to a canonical rule object.

### 7.7 SKUs

#### Endpoints

- `GET /api/skus`
- `GET /api/skus/{id}`
- `POST /api/skus`
- `PATCH /api/skus/{id}`

#### Required Public Fields

- `id`
- `product_id`
- `sku_code`
- `pack_size`
- `price`
- `currency`
- `inventory_status`

### 7.8 Quotes

#### Endpoints

- `GET /api/quotes`
- `GET /api/quotes/{id}`
- `POST /api/quotes`
- `PATCH /api/quotes/{id}`

#### Required Public Fields

- `id`
- `quote_no`
- `customer_id`
- `status`
- `valid_until`
- `subtotal`
- `grand_total`
- `currency`
- `items`

### 7.9 Quote Items

#### Endpoints

- `POST /api/quotes/{id}/items`
- `PATCH /api/quotes/{id}/items/{item_id}`
- `DELETE /api/quotes/{id}/items/{item_id}`

#### Required Public Fields

- `id`
- `quote_id`
- `product_id`
- `sku_id`
- `quantity`
- `unit_price`

### 7.10 Orders

#### Endpoints

- `GET /api/orders`
- `GET /api/orders/{id}`
- `POST /api/orders`
- `PATCH /api/orders/{id}`

#### Required Public Fields

- `id`
- `order_no`
- `customer_id`
- `status`
- `subtotal`
- `tax_total`
- `grand_total`
- `currency`
- `items`

### 7.11 Order Items

#### Endpoints

- `POST /api/orders/{id}/items`
- `PATCH /api/orders/{id}/items/{item_id}`
- `DELETE /api/orders/{id}/items/{item_id}`

#### Required Public Fields

- `id`
- `order_id`
- `product_id`
- `sku_id`
- `quantity`
- `unit_price`

### 7.12 Basket
**迁移注意**：当前现有前端使用 `/api/v1/cart` 路径，Phase 1 迁移时需将前端 API 调用迁移至 `/api/basket` 并同步更新文档。


#### Endpoints

- `GET /api/basket`
- `POST /api/basket/items`
- `PATCH /api/basket/items/{item_id}`
- `DELETE /api/basket/items/{item_id}`

#### Required Public Fields

- `id`
- `user_id`
- `session_key`
- `state`
- `expires_at`
- `items`

### 7.13 Wishlist

#### Endpoints

- `GET /api/wishlist`
- `POST /api/wishlist`
- `PATCH /api/wishlist/{id}`
- `POST /api/wishlist/{id}/items`
- `DELETE /api/wishlist/{id}/items/{item_id}`

#### Required Public Fields

- `id`
- `user_id`
- `name`
- `state`
- `visibility`
- `items`

### 7.14 Product Classes and Catalogs

#### Endpoints

- `GET /api/product-classes`
- `GET /api/product-catalogs`

#### Purpose

- Support internal or curated navigation for existing catalog structures.

## 8. Search API

Search is part of the backend API contract and must support the PRD search architecture.

### 8.1 Search Endpoint

Recommended route:

- `GET /api/search`

### 8.2 Search Parameters

Recommended parameters:

- `q`
- `type`
- `scope`
- `page`
- `page_size`
- `ordering`

### 8.3 Search Types

Search should support:

- Product search
- CAS search
- SMILES search
- Application search
- Method search
- Protocol search
- Reference search
- Natural language search

### 8.4 Search Output

Search results must include:

- Resource type
- Canonical ID
- Canonical title / name
- Relevance signal
- Minimal context summary

### 8.5 Search Rules

- Search is a read interface.
- Search results may be derived but must remain traceable to canonical data.
- Search should not return incomplete or misleading resource identities.

## 9. Structured Data and Agent Read APIs

### 9.1 JSON-LD Support

Public resource pages and API responses that feed structured data must be consistent with JSON-LD requirements from the frontend and database chapters.

### 9.2 Read-Only Agent Resources

The API must support read-only structured access for future AI agents.

### 9.3 Agent Read Rules

- Agent-facing resources must be read-only.
- Agent-facing payloads must be canonical and citable.
- Agent-facing payloads must not expose write paths to transactional data.

### 9.4 Future MCP Alignment

The API must remain compatible with future MCP read models by preserving stable resource identifiers and predictable field vocabulary.

### 9.5 Future Agent Capability Alignment

The API should be capable of serving the PRD’s future AI capability set through read-oriented resource contracts:

- Product recommendation
- Protocol retrieval
- Compatibility validation
- Inventory validation

These capabilities should be built on canonical read resources and services, not on ad hoc response shapes.

## 10. Validation and Error Model

### 10.1 Validation Rules

- Input validation must occur before persistence.
- Cross-resource validation must occur in services.
- Validation errors should be field-specific where possible.

### 10.2 Error Categories

Recommended error categories:

- `validation_error`
- `not_found`
- `unauthorized`
- `forbidden`
- `conflict`
- `rate_limited`
- `server_error`

### 10.3 HTTP Status Code Mapping

| Error Category | HTTP Status | Description |
|---|---|---|
| `validation_error` | `400 Bad Request` | 输入数据格式或业务规则校验失败 |
| `not_found` | `404 Not Found` | 请求的资源不存在 |
| `unauthorized` | `401 Unauthorized` | 未提供有效认证凭据 |
| `forbidden` | `403 Forbidden` | 认证通过但无权限访问该资源 |
| `conflict` | `409 Conflict` | 资源状态冲突（如重复创建） |
| `rate_limited` | `429 Too Many Requests` | 请求频率超出限制 |
| `server_error` | `500 Internal Server Error` | 服务端内部错误 |

All error responses MUST use the standard envelope (`success: false`) with the appropriate HTTP status code.


### 10.3 Error Response Behavior

- Error responses should remain readable and structured.
- The API should avoid leaking internal stack traces in public responses.

## 11. Permissions and Access Control

### 11.1 Public Read

- Product discovery resources may be publicly readable.
- Scientific graph pages that support public browsing may be publicly readable.

### 11.2 Authenticated Write

- Quotes, cart actions, wishlists, orders, and any controlled content edits should require authenticated access as appropriate.

### 11.3 Admin / Curated Write

- Curated or editorial resources such as applications, methods, protocols, references, and compatibility may require privileged access for writes.

### 11.4 Agent Access

- Agent access must be read-only unless explicitly redefined later.

## 12. Pagination, Filtering, and Sorting Rules

### 12.1 Pagination

- All list endpoints should support pagination.
- Pagination metadata should be exposed in `meta`.

### 12.2 Filtering

- Resource-specific filters are allowed.
- Filters should map to canonical fields, not ad hoc display fields.

### 12.3 Sorting

- List endpoints should provide stable default ordering.
- Any alternate ordering should be explicit.

### 12.4 Inclusion / Expansion

- Use `include` or `expand` only when the API needs to traverse known relationships.
- Expansion depth should remain bounded.

## 13. Cross-Chapter Dependencies

This chapter depends on the domain model, database architecture, frontend PRD, and AI agent integration chapters.
It also defines the resource contract that the future search and knowledge graph chapters must honor.

| Chapter | Dependency on This Chapter |
|---|---|
| Chapter 1 Product Vision | Defines the product intent that the API must enable |
| Chapter 2 System Architecture | Defines the service and read/write boundaries the API must respect |
| Chapter 3 Domain Model | Defines the entities and relation semantics the API must expose |
| Chapter 4 Database Architecture | Defines the canonical fields and identifiers the API must serialize |
| Chapter 5 Frontend PRD | Defines the frontend consumption patterns the API must satisfy |
| Chapter 7 Knowledge Graph | Must align with the resource graph exposed here |
| Chapter 8 Application / Method / Protocol Spec | Must align with the scientific resource behavior exposed here |
| Chapter 9 AI Agent Integration | Must use these read contracts and stable identifiers |
| Chapter 10 Roadmap | Must sequence API work according to these resource families |
| Chapter 11 Codex Rules | Must preserve these contracts and reject incompatible changes |

## 14. Acceptance Criteria

This chapter is complete when all of the following are true:

- The required route inventory is explicit.
- The response envelope is explicit.
- List/detail/write behavior is explicit.
- Product, application, method, protocol, reference, compatibility, and commerce resource contracts are explicit.
- Search behavior is explicit.
- Agent read constraints are explicit.
- Permissions and validation behavior are explicit.
- The frontend can implement against this chapter without inventing missing API shapes.
- The backend service layer can implement against this chapter without needing further route-level clarification.
