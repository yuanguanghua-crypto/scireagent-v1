# B2B Life Science Order Flow — Implementation Plan

## Overview

Align SciReagent's order flow with B2B life science industry conventions (Thermo Fisher, Sigma-Aldrich, NEB, IDT style). Support PO-based ordering, invoice/payment terms, quote management, and simple shipping — serving both large institutions (with their own procurement systems) and small labs (without).

---

## Phase 0: Data Model Refactor

### 0.1 Order Model — Extend

**File**: `apps/transactions/models.py`

```python
class Order(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        CONFIRMED = 'confirmed', 'Confirmed'
        INVOICED = 'invoiced', 'Invoiced'
        PAID = 'paid', 'Paid'
        PROCESSING = 'processing', 'Processing'
        SHIPPED = 'shipped', 'Shipped'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
        QUOTE_PENDING = 'quote_pending', 'Quote Pending'
        QUOTED = 'quoted', 'Quoted'
        QUOTE_ACCEPTED = 'quote_accepted', 'Quote Accepted'
        QUOTE_REJECTED = 'quote_rejected', 'Quote Rejected'

    class PaymentMethod(models.TextChoices):
        PO = 'purchase_order', 'Purchase Order'
        CREDIT_CARD = 'credit_card', 'Credit Card'
        WIRE_TRANSFER = 'wire_transfer', 'Wire Transfer'
        QUOTE = 'quote', 'Quote'

    # Existing fields (keep)
    user, order_no, status, subtotal, tax_total, grand_total, currency, comment

    # New fields
    payment_method = CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.PO)
    po_number = CharField(max_length=100, blank=True, default='')        # PO number from customer
    po_contact = CharField(max_length=200, blank=True, default='')       # PO contact person
    organization = ForeignKey(Organization, null=True, blank=True)       # Linked org
    shipping_name = CharField(max_length=200)
    shipping_address = TextField()
    shipping_phone = CharField(max_length=30, blank=True)
    shipping_email = EmailField(blank=True)
    billing_name = CharField(max_length=200, blank=True)
    billing_address = TextField(blank=True)
    notes = TextField(blank=True)                                        # Customer notes
    internal_notes = TextField(blank=True)                               # Admin-only notes
    payment_terms = CharField(max_length=20, default='NET30')            # NET30/NET60/NET90
    payment_due_date = DateField(null=True, blank=True)                  # Calculated from terms
```

### 0.2 Invoice Model — New

```python
class Invoice(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        ISSUED = 'issued', 'Issued'
        PAID = 'paid', 'Paid'
        OVERDUE = 'overdue', 'Overdue'
        VOID = 'void', 'Void'

    order = OneToOneField(Order, related_name='invoice')
    invoice_no = CharField(max_length=50, unique=True)      # e.g. INV-20260613-001
    status = CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    issued_at = DateTimeField(null=True)
    due_date = DateField()
    paid_at = DateTimeField(null=True)
    subtotal, tax_total, grand_total, currency               # Snapshot from order
    payment_ref = CharField(max_length=200, blank=True)      # Bank transfer reference
    notes = TextField(blank=True)
```

### 0.3 PaymentRecord Model — New

```python
class PaymentRecord(TimeStampedModel):
    class Method(models.TextChoices):
        ONLINE = 'online', 'Online Payment'
        WIRE = 'wire', 'Wire Transfer'
        CHECK = 'check', 'Check'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Verification'
        VERIFIED = 'verified', 'Verified'
        REJECTED = 'rejected', 'Rejected'

    invoice = ForeignKey(Invoice, related_name='payments')
    method = CharField(max_length=20, choices=Method.choices)
    amount = DecimalField(max_digits=12, decimal_places=2)
    currency = CharField(max_length=10, default='USD')
    reference = CharField(max_length=200, blank=True)        # Transaction ID / check number
    proof_file = FileField(upload_to='payment_proofs/%Y/%m/', blank=True)
    status = CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    verified_by = ForeignKey(User, null=True, blank=True)
    verified_at = DateTimeField(null=True)
    notes = TextField(blank=True)
```

### 0.4 ShippingRecord Model — New

```python
class ShippingRecord(TimeStampedModel):
    class Status(models.TextChoices):
        PREPARING = 'preparing', 'Preparing'
        SHIPPED = 'shipped', 'Shipped'
        IN_TRANSIT = 'in_transit', 'In Transit'
        DELIVERED = 'delivered', 'Delivered'

    order = OneToOneField(Order, related_name='shipping')
    status = CharField(max_length=20, choices=Status.choices, default=Status.PREPARING)
    carrier = CharField(max_length=100)                       # FedEx, UPS, DHL, etc.
    tracking_number = CharField(max_length=200)
    tracking_url = URLField(blank=True)
    shipped_at = DateTimeField(null=True)
    estimated_delivery = DateField(null=True)
    delivered_at = DateTimeField(null=True)
    notes = TextField(blank=True)
```

### 0.5 Migration Strategy

1. `makemigrations` with default values for new fields
2. Migrate existing Order statuses: `pending` → `draft`, `paid` → `paid`, etc.
3. Run migration

---

## Phase 1: Test Cases (TDD)

> **完整测试计划见**: `docs/TEST_PLAN_ORDER_FLOW.md`

8 个测试类别，共 78 个单元测试 + 8 个 E2E 场景：

| 类别 | 数量 | 覆盖范围 |
|------|------|---------|
| 订单状态流转 | 15 | 13 个合法流转 + 2 个非法拒绝 |
| 结算验证 | 12 | 空购物车、缺地址、缺 PO、库存检查等 |
| 发票 | 10 | 编号生成、到期日计算、逾期检测、作废等 |
| 付款 | 10 | 凭证上传、审核、拒绝、金额校验等 |
| 发货 | 8 | 创建记录、更新物流、标记送达等 |
| 报价流程 | 8 | 请求报价、录入价格、接受/拒绝、过期等 |
| 权限 | 10 | 研究员/采购经理/管理员各角色权限 |
| API 格式 | 5 | 响应格式、分页、401/403 错误 |

### 1.1 Order Status Transition Tests (15 cases)

| ID | Test | Expected |
|----|------|----------|
| TC-ORD-01 | Single org: draft → confirmed (no approval needed) | ✅ |
| TC-ORD-02 | Multi org with PO: draft → confirmed (PO provided) | ✅ |
| TC-ORD-03 | Multi org without PO: draft → confirmed (credit card) | ✅ |
| TC-ORD-04 | Quote flow: draft → quote_pending | ✅ |
| TC-ORD-05 | Quote provided: quote_pending → quoted | ✅ |
| TC-ORD-06 | Quote accepted: quoted → quote_accepted → confirmed | ✅ |
| TC-ORD-07 | Quote rejected: quoted → quote_rejected | ✅ |
| TC-ORD-08 | Invoice generated: confirmed → invoiced | ✅ |
| TC-ORD-09 | Online payment: invoiced → paid (auto) | ✅ |
| TC-ORD-10 | Wire transfer: invoiced → paid (admin verify) | ✅ |
| TC-ORD-11 | Mark shipped: paid → processing → shipped | ✅ |
| TC-ORD-12 | Complete: shipped → completed | ✅ |
| TC-ORD-13 | Cancel: draft → cancelled | ✅ |
| TC-ORD-14 | Cancel after confirmed: blocked | ❌ |
| TC-ORD-15 | Invalid transition: paid → draft | ❌ |

### 1.2 Invoice Tests (10 cases)

| ID | Test |
|----|------|
| TC-INV-01 | Auto-generate invoice_no on creation |
| TC-INV-02 | Calculate due_date from payment_terms |
| TC-INV-03 | Mark overdue when past due_date |
| TC-INV-04 | Void invoice |
| TC-INV-05 | Invoice items match order items |

### 1.3 Payment Tests (10 cases)

| ID | Test |
|----|------|
| TC-PAY-01 | Upload payment proof |
| TC-PAY-02 | Admin verifies payment |
| TC-PAY-03 | Admin rejects payment |
| TC-PAY-04 | Auto-update invoice status on payment verify |

### 1.4 Shipping Tests (5 cases)

| ID | Test |
|----|------|
| TC-SHP-01 | Create shipping record |
| TC-SHP-02 | Update tracking info |
| TC-SHP-03 | Mark delivered |
| TC-SHP-04 | Auto-complete order after delivery |

### 1.5 Permission Tests (8 cases)

| ID | Test |
|----|------|
| TC-PERM-01 | Researcher can create order from basket |
| TC-PERM-02 | Researcher can view own orders only |
| TC-PERM-03 | Procurement can view org orders |
| TC-PERM-04 | Admin can view all orders |
| TC-PERM-05 | Only admin can mark as shipped |
| TC-PERM-06 | Only admin can verify payment |
| TC-PERM-07 | Only admin can generate invoice |

**Total: 48 test cases**

---

## Phase 2: Backend API Implementation

### 2.1 New API Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/v1/checkout` | Create order from basket | Auth |
| GET | `/api/v1/orders` | List orders (filtered by role) | Auth |
| GET | `/api/v1/orders/{id}` | Order detail | Auth |
| POST | `/api/v1/orders/{id}/cancel` | Cancel order | Auth |
| POST | `/api/v1/orders/{id}/confirm-quote` | Accept/reject quote | Auth |
| GET | `/api/v1/orders/{id}/invoice` | Get invoice | Auth |
| POST | `/api/v1/orders/{id}/pay` | Submit payment proof | Auth |
| GET | `/api/v1/invoices` | List invoices | Auth |
| GET | `/api/v1/invoices/{id}` | Invoice detail | Auth |
| **Admin endpoints** | | | |
| POST | `/api/v1/admin/orders/{id}/confirm` | Confirm order | Admin |
| POST | `/api/v1/admin/orders/{id}/invoice` | Generate invoice | Admin |
| POST | `/api/v1/admin/orders/{id}/ship` | Mark shipped | Admin |
| POST | `/api/v1/admin/orders/{id}/complete` | Mark completed | Admin |
| POST | `/api/v1/admin/orders/{id}/quote` | Enter quote price | Admin |
| POST | `/api/v1/admin/invoices/{id}/verify-payment` | Verify payment | Admin |
| GET | `/api/v1/admin/orders` | All orders with filters | Admin |

### 2.2 Checkout Payload

```json
{
  "payment_method": "purchase_order",
  "po_number": "PO-2026-00123",
  "po_contact": "Dr. Smith",
  "shipping_address": {
    "name": "Dr. John Smith",
    "address": "123 Lab Street, Cambridge, MA 02139",
    "phone": "+1-617-555-0123",
    "email": "jsmith@university.edu"
  },
  "notes": "Please ship on Monday"
}
```

### 2.3 Order Status Machine

```python
VALID_TRANSITIONS = {
    'draft':           ['confirmed', 'quote_pending', 'cancelled'],
    'confirmed':       ['invoiced', 'paid', 'cancelled'],
    'invoiced':        ['paid'],
    'paid':            ['processing'],
    'processing':      ['shipped'],
    'shipped':         ['completed'],
    'completed':       [],
    'cancelled':       [],
    'quote_pending':   ['quoted', 'cancelled'],
    'quoted':          ['quote_accepted', 'quote_rejected'],
    'quote_accepted':  ['confirmed'],
    'quote_rejected':  [],
}
```

---

## Phase 3: Frontend Pages

### 3.1 Checkout Page (`/checkout`)

**Step 1: Shipping Address**
- Select from saved addresses or enter new
- Fields: name, address line 1/2, city, state, postal code, country, phone, email

**Step 2: Payment Method**
- Radio selection:
  - Purchase Order → show PO number + PO contact inputs
  - Credit Card → show card form (placeholder for now)
  - Wire Transfer → show bank details
  - Request Quote → show quote form

**Step 3: Order Review**
- Order summary (items, quantities, prices, total)
- Notes textarea
- Place Order button

### 3.2 Order List Page (`/orders`)

- Table: Order #, Date, Status (badge), Items count, Total, Actions
- Status filter tabs: All, Pending, Confirmed, Shipped, Completed
- Click to view order detail

### 3.3 Order Detail Page (`/orders/:id`)

- Order header: order #, status badge, date
- Items table: product, SKU, qty, unit price, subtotal
- Shipping info
- Payment info (PO #, payment method)
- Invoice section (if invoiced)
- Action buttons based on status:
  - `quoted` → Accept / Reject Quote
  - `invoiced` + wire → Upload Payment Proof
  - `invoiced` + PO → View Invoice (payment by terms)

### 3.4 Admin Order Management (`/admin/orders`)

- Table with all orders, sortable/filterable
- Status filter, date range filter, search by order # / PO #
- Quick actions: Confirm, Invoice, Ship, Complete

### 3.5 Admin Order Detail (`/admin/orders/:id`)

- Full order info
- Customer info (user, org, contact)
- Quote entry form (when status = quote_pending)
- Invoice generation form
- Shipping form (carrier, tracking #)
- Payment verification (approve/reject proof)
- Internal notes

---

## Phase 4: Integration

### 4.1 Checkout → Order Creation Flow

```
User clicks "Place Order"
  → Validate basket not empty
  → Validate shipping address
  → Validate PO number (if PO method)
  → Create Order (status: draft)
  → Create OrderItems from BasketItems
  → Calculate totals
  → Auto-transition based on org type:
     - Single org + PO → confirmed
     - Single org + credit card → confirmed (pending payment)
     - Multi org + PO → confirmed
     - Quote → quote_pending
  → Clear basket
  → Return order detail
```

### 4.2 Invoice Auto-Generation

When order status → `invoiced`:
- Generate invoice_no: `INV-{YYYYMMDD}-{sequence}`
- Calculate due_date: today + payment_terms days
- Copy order items to invoice

### 4.3 Payment Verification Flow

```
Wire transfer path:
  User uploads proof → PaymentRecord created (status: pending)
  Admin reviews → verifies/rejects
  If verified → Invoice.paid_at set → Order status → paid
  If rejected → notify user to resubmit
```

---

## Phase 5: E2E Tests

### Test Scenarios

| ID | Scenario | Steps |
|----|----------|-------|
| E2E-01 | PO order (single org) | Login → Add to cart → Checkout with PO → View order → View invoice |
| E2E-02 | Credit card order | Login → Add to cart → Checkout with CC → Order confirmed |
| E2E-03 | Quote request | Login → Add to cart → Request Quote → Admin enters price → User accepts → Order confirmed |
| E2E-04 | Wire transfer payment | Login → View invoiced order → Upload payment proof → Admin verifies → Order paid |
| E2E-05 | Order lifecycle | Create → Confirm → Invoice → Pay → Ship → Complete |
| E2E-06 | Cancel order | Create order → Cancel before confirmation |
| E2E-07 | Admin shipping | Admin views paid order → Enter tracking → Mark shipped |
| E2E-08 | Permission check | Researcher cannot see other users' orders |

---

## Implementation Order

| Phase | Content | Depends On |
|-------|---------|------------|
| **0** | Data model refactor (Order extend + Invoice + Payment + Shipping) | — |
| **1** | Write 48 test cases | Phase 0 |
| **2** | Backend API (17 endpoints) | Phase 1 |
| **3** | Frontend pages (5 pages) | Phase 2 |
| **4** | Integration (checkout flow, invoice gen, payment verify) | Phase 3 |
| **5** | E2E tests (8 scenarios) | Phase 4 |

---

## File Changes Summary

### Backend
| File | Action |
|------|--------|
| `apps/transactions/models.py` | Extend Order, add Invoice/PaymentRecord/ShippingRecord |
| `apps/transactions/migrations/0004_*.py` | New migration |
| `apps/transactions/api/v1/serializers.py` | Update + add new serializers |
| `apps/transactions/api/v1/views.py` | Add checkout, order, invoice, admin views |
| `apps/transactions/api/v1/urls.py` | Add new endpoints |
| `apps/transactions/api/v1/checkout_views.py` | New: checkout logic |
| `apps/transactions/api/v1/admin_order_views.py` | New: admin order management |
| `apps/transactions/tests/test_order_flow.py` | New: 48 test cases |
| `apps/transactions/admin.py` | Register new models |

### Frontend
| File | Action |
|------|--------|
| `src/views/CheckoutPage.vue` | New: 3-step checkout |
| `src/views/OrderListPage.vue` | New: order list |
| `src/views/OrderDetailPage.vue` | New: order detail + actions |
| `src/views/admin/AdminOrdersPage.vue` | New: admin order list |
| `src/views/admin/AdminOrderDetail.vue` | New: admin order management |
| `src/api/orders.js` | New: order API module |
| `src/api/invoices.js` | New: invoice API module |
| `src/stores/orders.js` | New: order store |
| `src/router/index.js` | Add 5 new routes |
| `src/components/layout/AppHeader.vue` | Add orders link in user menu |
