# CLAUDE.md — SciReagent Backend

> This is the backend-specific context. For full project context, see `/CLAUDE.md` at the repo root.

## Quick Commands

```bash
# Run all tests (use this exact format to avoid sandbox permission issues)
DB_ENGINE=sqlite PYTHONDONTWRITEBYTECODE=1 venv/Scripts/python.exe -B -m pytest -p no:cacheprovider

# Quick test with short tracebacks
DB_ENGINE=sqlite PYTHONDONTWRITEBYTECODE=1 venv/Scripts/python.exe -B -m pytest -q --tb=short -p no:cacheprovider

# Run specific test file
DB_ENGINE=sqlite PYTHONDONTWRITEBYTECODE=1 venv/Scripts/python.exe -B -m pytest apps/commerce/tests/test_product_detail_api.py -p no:cacheprovider

# Dev server
DB_ENGINE=sqlite python manage.py runserver

# Migrations
python manage.py makemigrations && python manage.py migrate

# Django shell
DB_ENGINE=sqlite python manage.py shell
```

## Architecture

```
Request → View (thin) → Service (business logic) → Model
                        ↘ Serializer (validation/shaping)
```

**Rules:**
- Views only route requests, return responses
- Business logic → `services/` directory
- Serializers only validate and shape data
- Cross-model writes → services with transactions

## Key Files

| File | Purpose |
|------|---------|
| `config/settings/base.py` | Main settings, DRF config, throttle |
| `config/settings/development.py` | Dev overrides — throttle DISABLED here |
| `config/urls.py` | Root URL routing |
| `core/renderers.py` | EnvelopeRenderer — global response wrapping |
| `core/permissions.py` | IsAdminOrReadOnly, LoginRateThrottle |
| `core/svg_sanitizer.py` | SVG XSS cleaning |
| `core/mixins.py` | EnvelopeMixin (success_response/error_response) |

## App Structure

| App | Models | Key Features |
|-----|--------|-------------|
| `accounts` | User, Organization | Token auth, registration |
| `knowledge` | ResearchGoal, Application, Method, Protocol, Reference, Compatibility | Knowledge graph, homepage API, search, graph API |
| `commerce` | Product, SKU, ProductClass, ProductDocument | Product detail, FAQ, related products, categories |
| `bridges` | ProductMethod, MethodProtocol, ProductReference, ProductCompatibility, ProductProduct | Many-to-many with meaning |
| `transactions` | Order, Invoice, Quote, Basket, Wishlist, PaymentRecord, ShippingRecord | Full order lifecycle, admin order management |
| `quotes` | QuoteRequest, QuoteRequestItem | Anonymous RFQ submission |
| `assets` | Static asset management | File serving |

## API Prefix

All APIs: `/api/v1/`

## Response Format

ALL responses use envelope: `{success: bool, data: any, meta: object}`

Never return bare arrays or objects from views.

## Security

- Throttle: AnonRateThrottle (100/hour) + LoginRateThrottle (5/min) — DISABLED in development.py
- Permissions: IsAdminOrReadOnly for knowledge entities, IsAuthenticated for user-scoped resources
- SVG: structure_svg must go through sanitize_svg() in serializers
- File upload: extension whitelist + 10MB limit
- QuoteViewSet: user-scoped (staff=all, user=own, anon=none)

## Test Count Convention

Include test count in commit messages: "757/757 tests passing"

*Last updated: 2026-06-17 | 757 passed, 10 skipped*
