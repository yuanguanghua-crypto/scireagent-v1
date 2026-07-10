# Order Flow — Complete Test Plan

## Test Environment

- Django 5.1 + DRF + SQLite (test DB)
- pytest + pytest-django + factory_boy
- All tests independent, no execution order dependency

---

## Category 1: Order Status Transitions (15 tests)

### 1.1 Valid Transitions

| ID | Test | Setup | Action | Assert |
|----|------|-------|--------|--------|
| TC-ORD-01 | Single org: draft → confirmed | user in individual org, order with PO | `order.transition_to('confirmed')` | status == 'confirmed', no error |
| TC-ORD-02 | Multi org + PO: draft → confirmed | user in multi org, order has po_number='PO-001' | `order.transition_to('confirmed')` | status == 'confirmed', po_number preserved |
| TC-ORD-03 | Credit card: draft → confirmed | order with payment_method='credit_card' | `order.transition_to('confirmed')` | status == 'confirmed' |
| TC-ORD-04 | Quote request: draft → quote_pending | order with payment_method='quote' | `order.transition_to('quote_pending')` | status == 'quote_pending' |
| TC-ORD-05 | Admin provides quote | order status=quote_pending | `admin_quote(order, price=1500)` | status == 'quoted', grand_total == 1500 |
| TC-ORD-06 | User accepts quote | order status=quoted | `user_accept_quote(order)` | status == 'quote_accepted' → auto → 'confirmed' |
| TC-ORD-07 | User rejects quote | order status=quoted | `user_reject_quote(order)` | status == 'quote_rejected' |
| TC-ORD-08 | Generate invoice | order status=confirmed | `generate_invoice(order)` | status == 'invoiced', invoice.invoice_no exists |
| TC-ORD-09 | Online payment → paid | order status=invoiced, method=credit_card | `process_online_payment(order)` | status == 'paid', invoice.paid_at not None |
| TC-ORD-10 | Wire transfer → paid (admin verify) | order status=invoiced, method=wire_transfer | admin verifies payment proof | status == 'paid' |
| TC-ORD-11 | Processing → shipped | order status=paid | `mark_shipped(order, carrier='FedEx', tracking='123')` | status == 'shipped', shipping.tracking_number == '123' |
| TC-ORD-12 | Shipped → completed | order status=shipped | `complete_order(order)` | status == 'completed' |
| TC-ORD-13 | Cancel draft order | order status=draft | `cancel_order(order)` | status == 'cancelled' |

### 1.2 Invalid Transitions (should raise error)

| ID | Test | Setup | Action | Assert |
|----|------|-------|--------|--------|
| TC-ORD-14 | Cannot cancel after confirmed | order status=confirmed | `cancel_order(order)` | raises InvalidTransitionError |
| TC-ORD-15 | Invalid: paid → draft | order status=paid | `order.transition_to('draft')` | raises InvalidTransitionError |

---

## Category 2: Checkout Validation (12 tests)

| ID | Test | Input | Assert |
|----|------|-------|--------|
| TC-CHK-01 | Empty basket | basket has 0 items | 400, error: 'Basket is empty' |
| TC-CHK-02 | Missing shipping address | no address provided | 400, error: 'Shipping address required' |
| TC-CHK-03 | PO method requires po_number | method=PO, po_number='' | 400, error: 'PO number required' |
| TC-CHK-04 | Valid PO checkout | method=PO, po_number='PO-001', address provided | 201, order created, status=confirmed |
| TC-CHK-05 | Valid credit card checkout | method=credit_card, address provided | 201, order created |
| TC-CHK-06 | Quote checkout | method=quote | 201, order status=quote_pending |
| TC-CHK-07 | Basket items → order items | 3 items in basket | order.items.count() == 3, prices match |
| TC-CHK-08 | Total calculation | items: 2×$100 + 3×$50 | grand_total == 350.00 |
| TC-CHK-09 | Basket cleared after checkout | basket had 3 items | basket.count() == 0 after checkout |
| TC-CHK-10 | Order number auto-generated | checkout | order_no matches format 'ORD-YYYYMMDD-NNN' |
| TC-CHK-11 | Guest user cannot checkout | user not authenticated | 401 |
| TC-CHK-12 | SKU inventory check | SKU status=out_of_stock | 400, error: 'SKU {code} is out of stock' |

---

## Category 3: Invoice Tests (10 tests)

| ID | Test | Setup | Assert |
|----|------|-------|--------|
| TC-INV-01 | Auto invoice_no | create invoice | invoice_no matches 'INV-YYYYMMDD-NNN' |
| TC-INV-02 | Due date NET30 | terms=NET30, issued=today | due_date == today + 30 days |
| TC-INV-03 | Due date NET60 | terms=NET60 | due_date == today + 60 days |
| TC-INV-04 | Due date NET90 | terms=NET90 | due_date == today + 90 days |
| TC-INV-05 | Overdue detection | invoice due_date = yesterday | `invoice.is_overdue` == True |
| TC-INV-06 | Not overdue | invoice due_date = tomorrow | `invoice.is_overdue` == False |
| TC-INV-07 | Void invoice | invoice status=issued | `void_invoice(invoice)` → status=void |
| TC-INV-08 | Cannot void paid invoice | invoice status=paid | raises error |
| TC-INV-09 | Invoice items = order items | order has 3 items | invoice.items.count() == 3, amounts match |
| TC-INV-10 | Invoice grand_total = order grand_total | order.total = 1500 | invoice.grand_total == 1500 |

---

## Category 4: Payment Tests (10 tests)

| ID | Test | Setup | Assert |
|----|------|-------|--------|
| TC-PAY-01 | Upload wire transfer proof | file + reference | PaymentRecord created, status=pending |
| TC-PAY-02 | Admin verifies payment | admin calls verify endpoint | payment.status=verified, invoice.paid_at set |
| TC-PAY-03 | Admin rejects payment | admin calls reject endpoint | payment.status=rejected |
| TC-PAY-04 | Invoice auto-updates on verify | invoice status=issued, payment verified | invoice.status=paid |
| TC-PAY-05 | Order auto-updates on invoice paid | order status=invoiced | order.status=paid |
| TC-PAY-06 | Cannot verify already verified payment | payment.status=verified | raises error |
| TC-PAY-07 | Payment amount must match invoice | amount=100, invoice.total=200 | 400, error: 'Amount mismatch' |
| TC-PAY-08 | Multiple payments allowed | 2 payments for same invoice | both records exist, sum matches |
| TC-PAY-09 | Payment proof file saved | upload PDF | file path exists |
| TC-PAY-10 | Non-admin cannot verify | researcher tries verify | 403 |

---

## Category 5: Shipping Tests (8 tests)

| ID | Test | Setup | Assert |
|----|------|-------|--------|
| TC-SHP-01 | Create shipping record | order status=paid | ShippingRecord created, status=preparing |
| TC-SHP-02 | Update tracking | set carrier + tracking_number | shipping.carrier = 'FedEx' |
| TC-SHP-03 | Mark shipped | call mark_shipped | order.status=shipped, shipping.shipped_at set |
| TC-SHP-04 | Mark delivered | call mark_delivered | shipping.status=delivered, shipping.delivered_at set |
| TC-SHP-05 | Auto-complete on delivery | shipping delivered | order.status=completed (or manual trigger) |
| TC-SHP-06 | Cannot ship unpaid order | order status=confirmed | raises error |
| TC-SHP-07 | Tracking URL generation | carrier='FedEx', tracking='123' | shipping.tracking_url contains 'fedex' |
| TC-SHP-08 | Non-admin cannot ship | researcher tries ship | 403 |

---

## Category 6: Quote Flow Tests (8 tests)

| ID | Test | Setup | Assert |
|----|------|-------|--------|
| TC-QUO-01 | Request quote from basket | 3 items in basket | Quote created, status=quote_pending, items match |
| TC-QUO-02 | Admin enters quote price | quote status=quote_pending | status=quoted, grand_total set |
| TC-QUO-03 | Quote valid_until set | admin sets 30-day validity | quote.valid_until == today + 30 |
| TC-QUO-04 | User accepts quote | quote status=quoted | quote → quote_accepted → order confirmed |
| TC-QUO-05 | User rejects quote | quote status=quoted | quote → quote_rejected, order cancelled |
| TC-QUO-06 | Cannot accept expired quote | quote.valid_until = yesterday | raises error |
| TC-QUO-07 | Quote items match basket | 3 items in basket | quote.items.count() == 3 |
| TC-QUO-08 | Non-owner cannot accept quote | different user tries accept | 403 |

---

## Category 7: Permission Tests (10 tests)

| ID | Test | User | Action | Assert |
|----|------|------|--------|--------|
| TC-PERM-01 | Researcher creates order | researcher | checkout | 201 |
| TC-PERM-02 | Researcher views own orders | researcher | GET /orders | returns only own orders |
| TC-PERM-03 | Researcher cannot view others' orders | researcher A | GET /orders/{id of B} | 404 |
| TC-PERM-04 | Procurement views org orders | procurement | GET /orders | returns org orders |
| TC-PERM-05 | Procurement cannot view other org | procurement org A | GET /orders/{id of org B} | 404 |
| TC-PERM-06 | Admin views all orders | admin | GET /admin/orders | returns all |
| TC-PERM-07 | Admin confirms order | admin | POST /admin/orders/{id}/confirm | 200 |
| TC-PERM-08 | Researcher cannot confirm | researcher | POST /admin/orders/{id}/confirm | 403 |
| TC-PERM-09 | Admin generates invoice | admin | POST /admin/orders/{id}/invoice | 200 |
| TC-PERM-10 | Admin ships order | admin | POST /admin/orders/{id}/ship | 200 |

---

## Category 8: API Response Format Tests (5 tests)

| ID | Test | Assert |
|----|------|--------|
| TC-API-01 | Success response format | `{success: true, data: {...}, meta: {}}` |
| TC-API-02 | Error response format | `{success: false, meta: {error: {code, message, details}}}` |
| TC-API-03 | Pagination format | `meta: {pagination: {page, pageSize, count, totalPages}}` |
| TC-API-04 | 401 for unauthenticated | `{success: false, meta: {error: {code: 'UNAUTHORIZED'}}}` |
| TC-API-05 | 403 for forbidden | `{success: false, meta: {error: {code: 'FORBIDDEN'}}}` |

---

## Test Summary

| Category | Count |
|----------|-------|
| Order Status Transitions | 15 |
| Checkout Validation | 12 |
| Invoice | 10 |
| Payment | 10 |
| Shipping | 8 |
| Quote Flow | 8 |
| Permission | 10 |
| API Response Format | 5 |
| **Total** | **78** |

---

## E2E Test Scenarios (Playwright, 8 scenarios)

| ID | Scenario | Steps |
|----|----------|-------|
| E2E-01 | PO checkout flow | Login → Add to cart → Checkout with PO → View order → View invoice |
| E2E-02 | Credit card checkout | Login → Add to cart → Checkout with CC → Order confirmed |
| E2E-03 | Quote request → accept | Login → Add to cart → Request Quote → Admin enters price → User accepts |
| E2E-04 | Quote request → reject | Login → Add to cart → Request Quote → Admin enters price → User rejects |
| E2E-05 | Wire transfer payment | Login → View invoiced order → Upload proof → Admin verifies → Paid |
| E2E-06 | Full lifecycle | Create → Confirm → Invoice → Pay → Process → Ship → Complete |
| E2E-07 | Cancel draft order | Create order → Cancel → Status = cancelled |
| E2E-08 | Permission: researcher blocked | Researcher tries to access admin endpoint → 403 |
