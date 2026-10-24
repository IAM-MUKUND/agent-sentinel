# Agent Sentinel - WAF Implementation Sprints

This document breaks down the implementation of the Agent WAF Middleware (as defined in `waf_planning.md`) into logical, manageable Agile sprints. The focus is on building a robust foundation first, followed by generic policies, domain-specific logic, and finally UI integration.

---

## Sprint 1: Foundation & Core Middleware Engine
**Goal**: Establish the core architectural skeleton, enabling the interception of agent tool calls and the dynamic loading of policies.

**Key Deliverables**:
- **Directory Structure**: Create the `backend/waf/` directory and module structure.
- **Dynamic Policy Loader**: Implement a Python parser to read, validate, and load YAML policy configurations from the `policies/` directory.
- **WAF Middleware Class**: Build the core `WAFMiddleware` interception layer that sits between the LLM and the backend tools.
- **Decision Engine**: Define the structured `Decision` JSON object (`ALLOW`, `DENY`, `HITL`) and the evaluation pipeline.
- **Proof of Concept**: Integrate the middleware into a single agent (e.g., `OrderManagementAgent`) for initial testing.

---

## Sprint 2: Layer 1 - Generic WAF Policies
**Goal**: Implement the application-agnostic, cross-cutting security rules that protect the system at a fundamental level.

**Key Deliverables**:
- **Parameter Validation Policy**: Engine to validate tool arguments against regex patterns (e.g., ensuring `order_id` matches `^ORD\d+$`).
- **Payload Size Policy**: Logic to drop payloads exceeding a configured byte limit.
- **Output Filtering Policy**: Regex-based redaction engine to strip PII (like SSNs or credit cards) from tool outputs before returning them to the LLM.
- **General Rate Limiting**: In-memory (or database-backed) counter to limit the frequency of tool calls per session.
- **Shadow Mode Toggle**: Implement the logic to allow execution while still logging the violation if `shadow_mode: true` is configured.

---

## Sprint 3: Observability & Audit Logging
**Goal**: Implement the immutable audit trail and performance tracking to ensure the WAF provides explainability and compliance.

**Key Deliverables**:
- **MongoDB Audit Integration**: Create a new `waf_audit_logs` collection in MongoDB Atlas.
- **Audit Logger Service**: Write the logic to construct and insert the comprehensive audit log (Timestamp, Session ID, Sanitized Params, Matched Policies, Decision).
- **Policy Evaluation Trace**: Ensure the engine tracks the exact sequence of evaluated policies and records them in the trace array.
- **Metrics Collection**: Implement timers to calculate and log `evaluation_latency_ms`.

---

## Sprint 4: Layer 2 - Customer Support Policy Pack (Financial & Data Isolation)
**Goal**: Implement the high-stakes, domain-specific rules required for the Order, Refund, and Billing agents.

**Key Deliverables**:
- **Customer Ownership Validation (IDOR Protection)**: Cross-reference the requested `order_id` with the active user's session to ensure they own the data.
- **Refund Limits Policy**: Query the database to calculate recent refund totals and block escalations that exceed monetary thresholds.
- **Duplicate Request Detection**: Prevent the creation of duplicate support tickets for the same issue/order.
- **Human-in-the-Loop (HITL) Enforcement**: Ensure specific tools (like `escalate_to_admin`) unconditionally return a `HITL` decision routing to the admin dashboard.

---

## Sprint 5: Layer 2 - Customer Support Policy Pack (Abuse & Security)
**Goal**: Implement the remaining domain-specific rules to protect the Replacement, Support, and Conversation agents.

**Key Deliverables**:
- **Replacement Cooldown Policy**: Prevent rapid, repeated replacement requests for the same item within a specified time window.
- **Input Sanitization**: Strip potential XSS payloads from technical support descriptions before they are passed to the database.
- **Intent Authorization**: Restrict the Conversation Agent from routing to restricted or hidden internal intents.
- **Order State Validation**: Block modifications or cancellations for orders that are already marked as "Delivered" or "Shipped".

---

## Sprint 6: Full Integration, Dashboard UI & Testing
**Goal**: Roll out the WAF across the entire multi-agent system and visualize its effectiveness in the Admin UI.

**Key Deliverables**:
- **System-Wide Rollout**: Apply the `WAFMiddleware` interceptor to the `_execute_tool` methods of *all* remaining agents.
- **Admin Dashboard Integration**: Update `AdminDashboard.jsx` to fetch data from the `waf_audit_logs` collection.
- **WAF Analytics UI**: Create a visual component in the dashboard to display "Blocked Threats", "Active Policies", and a feed of recent WAF decisions.
- **Security Penetration Testing**: Conduct simulated attacks (prompt injection attempts, out-of-bounds refund requests, cross-tenant data access) to verify the WAF's resilience in Enforce Mode.
