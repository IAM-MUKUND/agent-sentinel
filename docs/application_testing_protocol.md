# Agent Sentinel — Comprehensive Testing Protocol

This document is the definitive guide for testing the Agent Sentinel platform end-to-end. It covers base agentic workflows, all five specialist agents, WAF security enforcement, admin observability, and edge-case bypass resistance.

> [!IMPORTANT]
> Run all tests with the backend (`python3 main.py` in `backend/`) and the frontend (`npm run dev` in `agentsentinel/`) running simultaneously. MongoDB must be live and seeded.

---

## 1. Environment Setup

| Component             | Command                             | Expected Port             |
| --------------------- | ----------------------------------- | ------------------------- |
| Backend (FastAPI)     | `cd backend && python3 main.py`   | `http://localhost:8000` |
| Frontend (React/Vite) | `cd agentsentinel && npm run dev` | `http://localhost:5173` |
| MongoDB               | Atlas cluster or`mongod`          | `27017`                 |

### Pre-Test Checklist

- [X] Confirm `http://localhost:8000/docs` shows the FastAPI Swagger UI
- [X] Confirm `http://localhost:5173` loads the Agent Sentinel login page
- [X] Confirm MongoDB has seeded collections: `users`, `customers`, `orders`, `products`, `support_tickets`, `waf_audit_logs`, `user_sessions`
- [ ] Note down **one valid order** owned by the test user (e.g., `terrywilliams`) and **one order belonging to a different user** for IDOR tests

---

## 2. Authentication Tests

### TC-AUTH-01: Valid Customer Login

- **Login as**: Any seeded customer (e.g., `terrywilliams` / their password)
- **Expected**: Dashboard loads with support chat interface
- **Check**: Session cookie / token is stored; chat shows welcome message

### TC-AUTH-02: Valid Admin Login

- **Login as**: Admin account
- **Expected**: Admin Dashboard loads showing **Pending Tickets**, **WAF Security Logs**, **User Sessions** tabs
- **Check**: Customer chat interface is NOT shown to admin

### TC-AUTH-03: Invalid Credentials

- **Login as**: `fakeuser` / `wrongpassword`
- **Expected**: Login fails with an appropriate error message; no session is created

---

## 3. Base Agentic Workflow Tests

### TC-BASE-01: Greeting (No Tool Call)

- **Say**: `"Hi, how are you?"`
- **Expected**: ConversationAgent replies naturally without calling any tool
- **WAF Check**: No WAF log entry should be created (no tool was called)

### TC-BASE-02: Order Validation — Match

- **Say**: `"I need help with my order [VALID_ORDER_ID]. It's a [PRODUCT_NAME]."`
- **Expected**: `validate_order` tool fires internally; agent confirms the order matches the product and continues the conversation
- **WAF Check**: WAF logs one `ALLOW` entry for `validate_order` from `ConversationAgent`

### TC-BASE-03: Order Validation — Mismatch

- **Say**: `"I need help with my order [VALID_ORDER_ID]. It's a gaming laptop."` *(use an order that is NOT a gaming laptop)*
- **Expected**: Agent replies that the product description doesn't match the order ID and asks for correction
- **WAF Check**: One `ALLOW` log for `validate_order`; no specialist agent is invoked

### TC-BASE-04: Order Validation — Non-Existent Order

- **Say**: `"I need help with my order ORD-INVALID. It's a gaming laptop."`
- **Expected**: Agent replies that the order ID was not found in the system
- **WAF Check**: WAF logs a `DENY` for `validate_order` from `ConversationAgent` (rate limit or IDOR depending on configuration)

---

## 4. Order Management Agent Tests

### TC-OM-01: Track Shipment — Happy Path

- **Say**: `"Can you track my order [VALID_ORDER_ID]?"`
- **Expected**: Agent calls `track_shipment`; returns shipping status, ETA, and carrier
- **WAF Check**: `ALLOW` in WAF logs for `track_shipment`

### TC-OM-02: Cancel Order — Missing Reason (Anti-Hallucination)

- **Say**: `"I want to cancel my order [VALID_ORDER_ID]."`
- **Expected**: Agent does NOT call `cancel_order` immediately. It must ask: *"Why do you want to cancel?"*
- **What to verify**: The backend logs should NOT show `[OrderManagementAgent - Executing Tool] cancel_order`. The agent correctly holds off.

### TC-OM-03: Cancel Order — Valid Reason (Happy Path)

- **Continue from TC-OM-02**: Reply `"I ordered it by mistake."`
- **Expected**: Agent calls `cancel_order` with `customer_reason_quote: "I ordered it by mistake"`; order status in MongoDB changes to `cancelled`; an `Auto-Cancellation` notification ticket appears in the Admin Dashboard
- **WAF Check**: `ALLOW` for `cancel_order`

### TC-OM-04: Cancel Order — Hallucinated Reason (Anti-Hallucination Guard)

- **Say in one message**: `"Cancel my order [VALID_ORDER_ID]. The reason is that the product was defective and I am not satisfied."` *(without ever saying "defective" in a prior message)*
- **Expected**: The backend's anti-hallucination guard detects the quoted reason doesn't appear verbatim in the conversation history; returns a failure asking the agent to re-ask the user
- **WAF Check**: `ALLOW` (WAF doesn't block this; it's a business logic guard)

### TC-OM-05: Cancel Order — Shipped/Delivered Block (State Transition)

- **Pre-condition**: Use an order with `order_status: "shipped"` or `"delivered"`
- **Say**: `"Cancel my order [SHIPPED_ORDER_ID]. I changed my mind."`
- **Expected**: WAF intercepts `cancel_order`; returns `DENY` — *"State Transition Violation: Cannot modify order because its status is 'shipped'."*
- **WAF Check**: `DENY` entry in WAF logs with `matched_policy: pol_ticket_state_transition`

### TC-OM-06: Modify Delivery Address

- **Say**: `"Change the delivery address for [VALID_ORDER_ID] to 123 New Street, Chennai."`
- **Expected**: Agent calls `modify_delivery_address`; MongoDB order document is updated; agent confirms the change
- **WAF Check**: `ALLOW` in WAF logs

---

## 5. Replacement Agent Tests

### TC-REP-01: Valid Replacement Request — Full Happy Path

- **Pre-condition**: Use a valid order owned by the logged-in user
- **Say**: `"My [PRODUCT_NAME] from order [VALID_ORDER_ID] is broken. I need a replacement."`
- **Flow**:
  1. ConversationAgent routes to `ReplacementAgent`
  2. ReplacementAgent calls `check_warranty` → should return `under_warranty`
  3. ReplacementAgent calls `check_inventory` → should return `in_stock`
  4. Agent asks for image; user says image is uploaded
  5. ReplacementAgent calls `escalate_to_admin`
- **Expected**: Ticket `TKT-REP-XXXXXXXX` created in DB with `status: Pending`; Admin Dashboard shows the ticket
- **WAF Check**: `ALLOW` for all three tool calls

### TC-REP-02: Replacement for Non-Existent Order (IDOR / Data Scope)

- **Say**: `"I need a replacement for order ORD-FAKE123. It's a gaming laptop."`
- **Expected**: WAF blocks `check_warranty` (or whichever tool fires first) with `DENY — Data Scope Violation: Order ORD-FAKE123 does not belong to user [username].`
- **WAF Check**: `DENY` in logs; NO ticket is created in the database

### TC-REP-03: Replacement for Another User's Order

- **Pre-condition**: Note an order ID belonging to a *different* customer in MongoDB
- **Say**: `"I need a replacement for order [OTHER_USERS_ORDER_ID]."`
- **Expected**: WAF fires on `check_warranty` with `DENY — Data Scope Violation`
- **WAF Check**: `DENY` with `matched_policy: pol_customer_data_scope`; user is informed the action was blocked

### TC-REP-04: Duplicate Replacement Ticket

- **Pre-condition**: A `Pending` ticket already exists for the order from TC-REP-01
- **Say**: `"I still need a replacement for [VALID_ORDER_ID]. Please escalate again."`
- **Expected**: WAF fires on `escalate_to_admin` with `DENY — Duplicate Detection Violation: An active support ticket already exists for order [ORDER_ID].`
- **WAF Check**: `DENY` with `matched_policy: pol_duplicate_request_detection`

---

## 6. Refund Agent Tests

### TC-REF-01: Valid Refund Request — Happy Path

- **Say**: `"I want a refund for my order [VALID_ORDER_ID]. The product never arrived."`
- **Flow**:
  1. Routes to `RefundAgent`
  2. Agent calls `verify_order_eligibility` → eligible
  3. Agent escalates to admin
- **Expected**: Ticket `TKT-REF-XXXXXXXX` created; Admin Dashboard shows it
- **WAF Check**: `ALLOW` for both tool calls

### TC-REF-02: Refund for Non-Existent Order

- **Say**: `"Refund order ORD-DOES-NOT-EXIST please."`
- **Expected**: WAF blocks `verify_order_eligibility` with `DENY — Data Scope Violation`
- **WAF Check**: `DENY` in logs; NO ticket created

### TC-REF-03: Refund for Already-Refunded Order

- **Pre-condition**: Manually set an order's `order_status` to `"Refunded"` in MongoDB
- **Say**: `"I want a refund for [ALREADY_REFUNDED_ORDER]."`
- **Expected**: `verify_order_eligibility` returns `ineligible`; agent apologizes and does NOT escalate
- **WAF Check**: `ALLOW` for `verify_order_eligibility` (business logic handles the block, not WAF)

---

## 7. Billing Agent Tests

### TC-BILL-01: Generate Invoice — Happy Path

- **Say**: `"Can you give me an invoice for order [VALID_ORDER_ID]?"`
- **Expected**: Agent calls `generate_invoice`; returns structured invoice with customer name, address, product, amount, and payment status. Invoice data is rendered in the chat.
- **WAF Check**: `ALLOW` for `generate_invoice`

### TC-BILL-02: Invoice for Non-Existent Order

- **Say**: `"Give me invoice for order ORD-99999."`
- **Expected**: WAF blocks with `DENY — Data Scope Violation` OR `generate_invoice` returns `Order not found`
- **WAF Check**: `DENY` if the data scope policy fires; otherwise business logic returns an error

### TC-BILL-03: Verify Payment Status

- **Say**: `"What is the payment status of order [VALID_ORDER_ID]?"`
- **Expected**: Agent calls `verify_payment`; returns payment status from MongoDB
- **WAF Check**: `ALLOW` in logs

### TC-BILL-04: Investigate Duplicate Charge

- **Say**: `"I think I was charged twice for [VALID_ORDER_ID]."`
- **Expected**: Agent calls `investigate_duplicate_charge`; returns investigation result
- **WAF Check**: `ALLOW` in logs

---

## 8. Technical Support Agent Tests

### TC-SUPP-01: Product Issue with KB Match

- **Pre-condition**: A product in DB has `usage_instructions` populated
- **Say**: `"I'm having trouble with my [PRODUCT_NAME]. How do I use it?"`
- **Expected**: Agent calls `search_knowledge_base`; returns usage instructions from the product document; answers the user without escalating
- **WAF Check**: `ALLOW` for `search_knowledge_base`

### TC-SUPP-02: Product Issue — No KB Match (Escalation)

- **Say**: `"My Quantum Blaster X7000 is making a weird noise."`
- **Expected**: Agent searches KB (no match); uses general knowledge to attempt a resolution first; if unable, calls `create_support_ticket`
- **WAF Check**: `ALLOW` for both tool calls

---

## 9. WAF Security Enforcement Tests (Core Security Suite)

> [!CAUTION]
> These tests are specifically designed to attempt attacks and verify the WAF **blocks them correctly**. Run these from the customer chat UI while monitoring Admin > WAF Security Logs.

### TC-WAF-01: Rate Limiting

- **Action**: Send 6 or more tool-invoking messages within 60 seconds (e.g., rapidly ask to track the same order 6 times)
- **Expected**: The 6th request is blocked with `DENY — Rate limit exceeded for tool track_shipment (max 5 per 60s)`
- **WAF Check**: `DENY` with `matched_policy: pol_general_rate_limit`

### TC-WAF-02: IDOR Protection — Unauthenticated Path

- **Action**: Manually `POST` to `/api/chat` via `curl` or Postman *without* a valid `username` in the request body, but with an `order_id` in the message
- **Expected**: WAF blocks with `DENY — Data Scope Violation: Unauthenticated request — username is required`
- **WAF Check**: `DENY` with `matched_policy: pol_customer_data_scope`

### TC-WAF-03: Order Enumeration via ConversationAgent

- **Action**: Rapidly validate different order IDs: `"Help with ORD00001"`, `"Help with ORD00002"`, `"Help with ORD00003"`, etc. — 6 times in 60 seconds
- **Expected**: After 5 `validate_order` calls, the 6th is rate-limited by the WAF with `DENY`
- **WAF Check**: `DENY` in logs attributed to `ConversationAgent`

### TC-WAF-04: PII Injection in Tool Arguments

- **Action**: Include a credit card or SSN in a message: *"Cancel my order [VALID_ORDER_ID]. Refund to card 4111-1111-1111-1111, SSN 123-45-6789."*
- **Expected**: The action may be allowed or denied on other grounds. But in MongoDB `waf_audit_logs`, the `sanitized_params` field MUST show `[REDACTED]` instead of the raw numbers.
- **Check MongoDB**: `db.waf_audit_logs.find().sort({timestamp:-1}).limit(1)` — verify the `sanitized_params` field

### TC-WAF-05: Ticket Escalation for Non-Owned Order (End-to-End)

- **Action**: As `terrywilliams`, send a full replacement flow request for an order that belongs to `johndoe`
- **Expected**:
  - [ ] WAF blocks at the first tool call (`check_warranty`) with `DENY — Data Scope Violation`
  - [ ] Agent informs the user the action was blocked
  - [ ] **NO ticket appears in the Admin Dashboard**
  - [ ] **NO document is inserted** into `support_tickets` collection in MongoDB
- **This is the primary security regression test. If a ticket is created, the WAF enforcement is broken.**

### TC-WAF-06: Duplicate Ticket Prevention (End-to-End)

- **Pre-condition**: A `Pending` ticket exists for a valid order
- **Action**: Ask the agent to escalate for the same order again
- **Expected**: WAF fires `DENY — Duplicate Detection Violation` before `escalate_to_admin` inserts a new ticket
- **Check MongoDB**: Only ONE ticket exists for the order

---

## 10. Admin Dashboard Tests

### TC-ADMIN-01: Pending Tickets View

- **Pre-condition**: At least one `Pending` ticket exists from the test scenarios above
- **Action**: Log in as Admin; navigate to **Pending Tickets**
- **Expected**: Ticket card shows:
  - [ ] Customer name
  - [ ] Order ID
  - [ ] Reason
  - [ ] Risk Score (High for Refund/Replacement)
  - [ ] Order Details (Product, Amount, Purchase Date, Status) — fetched live from DB
  - [ ] Image attachment (if uploaded during the flow)

### TC-ADMIN-02: Approve a Ticket

- **Action**: Click **Approve** on a Pending replacement ticket
- **Expected**:
  - [ ] Ticket status changes to `Approved` in the UI
  - [ ] MongoDB `support_tickets` collection shows `status: "Approved"`
  - [ ] Customer chat receives a `[SYSTEM NOTIFICATION]` message: `"Your ticket TKT-XXX has been APPROVED"`

### TC-ADMIN-03: Deny a Ticket

- **Action**: Click **Deny** on a Pending replacement ticket
- **Expected**:
  - [ ] Ticket status changes to `Denied` in the UI
  - [ ] MongoDB shows `status: "Denied"`
  - [ ] Customer chat receives a `[SYSTEM NOTIFICATION]` message: `"Your ticket TKT-XXX has been DENIED"`

### TC-ADMIN-04: WAF Security Logs Table

- **Action**: Navigate to **WAF Security Logs**
- **Expected**: A table displays with columns: `Timestamp`, `Agent / Tool`, `Decision`, `Policy Matched`, `Reason`
  - [ ] ALLOW decisions appear in green
  - [ ] DENY decisions appear in red
  - [ ] Evaluation latency (ms) is shown under the Decision column
  - [ ] All previous TC-WAF-* test entries are visible

### TC-ADMIN-05: User Session Transcript

- **Action**: Navigate to **User Sessions**; click **View Transcript** on the test user's session
- **Expected**:
  - [ ] Full conversation chat is rendered in a styled bubble format
  - [ ] Tool invocations are shown as `[Invoking Tool: track_shipment]`
  - [ ] Admin interventions appear at the bottom: `"admin approved ticket TKT-XXX on [timestamp]"`

---

## 11. Edge Case & Regression Tests

### TC-EDGE-01: Empty Message

- **Action**: Send a blank message or a message with only spaces
- **Expected**: Backend handles gracefully; no crash; agent asks for input

### TC-EDGE-02: Very Long Message

- **Action**: Send a message with 10,000+ characters
- **Expected**: System handles gracefully; no crash or 500 error

### TC-EDGE-03: Image Upload Without Order Context

- **Action**: Upload an image immediately on first message without providing any order ID
- **Expected**: Agent does not crash; it asks for the order ID before proceeding

### TC-EDGE-04: Backend Server Restart Resilience

- **Action**: Restart the backend while the frontend is open
- **Expected**: Frontend shows a connectivity error gracefully; resumes on reconnect

### TC-EDGE-05: Agent `tool_choice: auto` with No Tool Needed

- **Action**: Ask a generic question: *"What is Agent Sentinel?"*
- **Expected**: Agent answers conversationally without invoking any tool (no WAF logs for this turn)

---

## 12. Test Result Tracking

Use this table to record your results:

| Test ID     | Description                                                  | Status | Notes |
| ----------- | ------------------------------------------------------------ | ------ | ----- |
| TC-AUTH-01  | Valid customer login                                         | ⬜     |       |
| TC-AUTH-02  | Valid admin login                                            | ⬜     |       |
| TC-AUTH-03  | Invalid credentials                                          | ⬜     |       |
| TC-BASE-01  | Greeting, no tool                                            | ⬜     |       |
| TC-BASE-02  | Order validation match                                       | ⬜     |       |
| TC-BASE-03  | Order validation mismatch                                    | ⬜     |       |
| TC-BASE-04  | Order validation non-existent                                | ⬜     |       |
| TC-OM-01    | Track shipment                                               | ⬜     |       |
| TC-OM-02    | Cancel without reason                                        | ⬜     |       |
| TC-OM-03    | Cancel with valid reason                                     | ⬜     |       |
| TC-OM-04    | Cancel hallucinated reason                                   | ⬜     |       |
| TC-OM-05    | Cancel shipped order (WAF block)                             | ⬜     |       |
| TC-OM-06    | Modify delivery address                                      | ⬜     |       |
| TC-REP-01   | Replacement happy path                                       | ⬜     |       |
| TC-REP-02   | Replacement fake order                                       | ⬜     |       |
| TC-REP-03   | Replacement other user's order                               | ⬜     |       |
| TC-REP-04   | Duplicate replacement ticket                                 | ⬜     |       |
| TC-REF-01   | Refund happy path                                            | ⬜     |       |
| TC-REF-02   | Refund non-existent order                                    | ⬜     |       |
| TC-REF-03   | Refund already refunded order                                | ⬜     |       |
| TC-BILL-01  | Generate invoice                                             | ⬜     |       |
| TC-BILL-02  | Invoice non-existent order                                   | ⬜     |       |
| TC-BILL-03  | Verify payment status                                        | ⬜     |       |
| TC-BILL-04  | Duplicate charge investigation                               | ⬜     |       |
| TC-SUPP-01  | Support with KB match                                        | ⬜     |       |
| TC-SUPP-02  | Support KB miss → ticket                                    | ⬜     |       |
| TC-WAF-01   | Rate limiting                                                | ⬜     |       |
| TC-WAF-02   | IDOR unauthenticated path                                    | ⬜     |       |
| TC-WAF-03   | Order enumeration via conv agent                             | ⬜     |       |
| TC-WAF-04   | PII sanitization in audit logs                               | ⬜     |       |
| TC-WAF-05   | Escalation for non-owned order (primary security regression) | ⬜     |       |
| TC-WAF-06   | Duplicate ticket prevention                                  | ⬜     |       |
| TC-ADMIN-01 | Pending tickets view                                         | ⬜     |       |
| TC-ADMIN-02 | Approve ticket                                               | ⬜     |       |
| TC-ADMIN-03 | Deny ticket                                                  | ⬜     |       |
| TC-ADMIN-04 | WAF security logs table                                      | ⬜     |       |
| TC-ADMIN-05 | Session transcript                                           | ⬜     |       |
| TC-EDGE-01  | Empty message                                                | ⬜     |       |
| TC-EDGE-02  | Very long message                                            | ⬜     |       |
| TC-EDGE-03  | Image without order context                                  | ⬜     |       |
| TC-EDGE-04  | Backend restart resilience                                   | ⬜     |       |
| TC-EDGE-05  | Generic question, no tool                                    | ⬜     |       |

**Legend**: ✅ Pass &nbsp; ❌ Fail &nbsp; ⚠️ Partial &nbsp; ⬜ Not Run

---

## Appendix: MongoDB Verification Queries

After security tests, run these in MongoDB Shell or Compass to verify enforcement:

```js
// 1. Check WAF audit logs for recent DENY decisions
db.waf_audit_logs.find({ decision: "DENY" }).sort({ timestamp: -1 }).limit(10)

// 2. Verify no ghost tickets were created for invalid orders
db.support_tickets.find({ order_id: "ORD-FAKE123" })

// 3. Check PII was redacted in audit logs
db.waf_audit_logs.find().sort({ timestamp: -1 }).limit(1).pretty()
// Look at sanitized_params — should show [REDACTED] for card/SSN

// 4. Confirm cancelled order status
db.orders.findOne({ order_id: "YOUR_ORDER_ID" }, { order_status: 1, payment_status: 1 })

// 5. Count active (Pending) tickets per order — should be max 1
db.support_tickets.aggregate([
  { $match: { status: "Pending" } },
  { $group: { _id: "$order_id", count: { $sum: 1 } } },
  { $match: { count: { $gt: 1 } } }
])
// Should return empty — any result here means duplicate detection is broken
```
