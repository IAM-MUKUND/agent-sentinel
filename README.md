# Agent Sentinel

**Agent Sentinel** is a production-oriented AI Customer Support platform secured by a custom-built **Agent WAF** (Web Application Firewall) middleware. It demonstrates how autonomous LLM agents can be governed at the tool-execution layer — intercepting every tool invocation before it touches enterprise data, enforcing YAML-driven security policies, and providing full observability through an administrative dashboard.

---

## What It Does

A customer interacts with an AI assistant to resolve support requests (refunds, replacements, order tracking, billing, technical support). Instead of serving users directly, a **ConversationAgent** gathers information and routes them to one of five specialist agents. Each specialist agent has access to database-backed tools. Before any tool executes, the **WAF Middleware** evaluates the call against a policy engine and either ALLOWs, DENYs, or flags it for Human-in-the-Loop (HITL) review.

Administrators monitor everything — live ticket queues, WAF intervention logs, and session transcripts — from a dedicated React dashboard.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        React Frontend                        │
│   Customer Chat  ◄──────────────────────►  Admin Dashboard  │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTP (FastAPI)
┌───────────────────────────▼─────────────────────────────────┐
│                       FastAPI Backend                         │
│                                                               │
│   ConversationAgent  ──►  IntentRouter  ──►  Specialist      │
│         │                                     Agents         │
│         │                            ┌─────────────────────┐ │
│         │                            │  WAF Middleware      │ │
│         │                            │  ┌───────────────┐  │ │
│         └───────────────────────────►│  │ Policy Engine │  │ │
│                                       │  │  22 Policies  │  │ │
│                                       │  └───────────────┘  │ │
│                                       │  ┌───────────────┐  │ │
│                                       │  │ Audit Logger  │  │ │
│                                       │  └───────────────┘  │ │
│                                       └─────────────────────┘ │
└───────────────────────────┬─────────────────────────────────┘
                            │
                ┌───────────▼───────────┐
                │   MongoDB Atlas        │
                │  users · customers     │
                │  orders · products     │
                │  support_tickets       │
                │  waf_audit_logs        │
                │  user_sessions         │
                └───────────────────────┘
```

---

## Repository Structure

```
agent-sentinel/
├── backend/
│   ├── main.py                     # FastAPI app — all API routes
│   ├── requirements.txt
│   ├── .env                        # (not committed) secrets
│   ├── agents/
│   │   ├── conversation_agent.py   # Entry-point — collects info, routes
│   │   ├── intent_router.py        # Dispatches to specialist agents
│   │   ├── order_management_agent.py
│   │   ├── replacement_agent.py
│   │   ├── refund_agent.py
│   │   ├── billing_agent.py
│   │   └── support_agent.py
│   ├── middleware/
│   │   └── waf/
│   │       ├── middleware.py       # WAF evaluation engine
│   │       ├── policy_loader.py    # YAML policy loader
│   │       ├── audit_logger.py     # MongoDB audit log writer
│   │       └── decision.py         # Decision dataclass
│   ├── policies/                   # 22 YAML security policy files
│   ├── prompts/                    # System prompts for each agent
│   ├── models/                     # Pydantic request/response models
│   └── repositories/               # MongoDB data-access layer
│
├── agentsentinel/                  # React + Vite frontend
│   └── src/
│       └── components/
│           ├── SupportChat.jsx     # Customer chat interface
│           └── AdminDashboard.jsx  # Admin observability panel
│
├── docs/
│   ├── ec2_deployment_guide.md        # Full AWS EC2 deploy instructions
│   ├── application_testing_protocol.md # 42-case test suite
│   ├── waf_planning.md
│   └── ...
│
├── docker/                         # Dockerfile and compose configs
└── tests/                          # Integration tests
```

---

## Specialist Agents & Tools

| Agent | Tools | WAF Coverage |
|---|---|---|
| **ConversationAgent** | `validate_order`, `route_to_specialist` | Rate limiting on order validation |
| **OrderManagementAgent** | `track_shipment`, `cancel_order`, `modify_delivery_address` | IDOR, state transition, parameter validation, rate limit |
| **ReplacementAgent** | `check_warranty`, `check_inventory`, `escalate_to_admin` | IDOR, duplicate detection |
| **RefundAgent** | `verify_order_eligibility`, `escalate_to_admin` | IDOR, duplicate detection |
| **BillingAgent** | `generate_invoice`, `verify_payment`, `investigate_duplicate_charge` | IDOR, rate limit |
| **SupportAgent** | `search_knowledge_base`, `create_support_ticket` | Rate limit |

---

## WAF Policy Engine

Policies are defined as YAML files in `backend/policies/`. The WAF evaluates them in order on every tool invocation. **22 policies** are currently active.

### Policy Types

| Policy | File | Effect |
|---|---|---|
| **IDOR / Data Scope** | `customer_data_scope.yaml` | Blocks any tool call where the `order_id` does not belong to the authenticated user |
| **Rate Limiting** | `general_rate_limit.yaml` | Max 5 tool calls per 60s per session |
| **Duplicate Detection** | `duplicate_request_detection.yaml` | Blocks re-escalation if an active ticket already exists for the same order |
| **Parameter Validation** | `strict_param_validation.yaml` | Regex-validates `order_id` format on `cancel_order` |
| **State Transition** | `ticket_state_transition.yaml` | Blocks cancellation of orders already shipped/delivered/completed |
| **Human-in-the-Loop** | `human_in_loop.yaml` | Requires admin approval for `escalate_to_admin` (configurable) |
| **Emergency Lockdown** | `emergency_lockdown.yaml` | Toggle to instantly block all tool executions |
| **Audit & Masking** | `audit_and_masking.yaml` | Logs every decision; redacts PII (SSN, card numbers) from audit entries |
| **PII Output Filtering** | `output_filtering.yaml` | Redacts PII from agent responses |
| **Fraud Detection** | `fraud_detection_rules.yaml` | Limits refund frequency per account |
| **Payload Size Limit** | `payload_size.yaml` | Blocks oversized tool payloads |
| **Role-Based Access** | `role_based_access.yaml` | Denies tool access to guest/unverified roles |

### Decision Outcomes

| Decision | Meaning |
|---|---|
| `ALLOW` | Policy passed — tool executes |
| `DENY` | Policy violated — tool blocked, agent informs user |
| `HITL` | Human approval required — ticket held in admin queue |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite, Lucide Icons |
| Backend | Python 3.11, FastAPI, Uvicorn |
| LLM | Groq API (`llama-3.3-70b-versatile`) |
| Database | MongoDB Atlas |
| WAF Engine | Custom Python middleware + YAML policies |
| Auth | Username/password (session-based, in-memory) |

---

## Local Development Setup

### Prerequisites
- Python 3.11+
- Node.js 20+
- MongoDB Atlas account (free M0 tier)
- Groq API key (free tier available at [console.groq.com](https://console.groq.com))

### 1. Clone and set up the backend

```bash
cd agent-sentinel

# Create and activate a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
cd backend
pip install -r requirements.txt
```

### 2. Configure environment variables

Create `backend/.env`:

```env
MONGO_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/
MONGO_DB_NAME=agentsentinel
GROQ_API_KEY=gsk_...

# Collection names (customise if needed)
COLLECTION_USERS=users
COLLECTION_CUSTOMERS=customers
COLLECTION_ORDERS=orders
COLLECTION_PRODUCTS=products
COLLECTION_SUPPORT_TICKETS=support_tickets
COLLECTION_WAF_AUDIT_LOGS=waf_audit_logs
COLLECTION_USER_SESSIONS=user_sessions
```

### 3. Start the backend

```bash
# From the backend/ directory, with venv active
python3 main.py
# FastAPI runs at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### 4. Start the frontend

```bash
cd agentsentinel
npm install
npm run dev
# React app runs at http://localhost:5173
```

---

## Key API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/login` | Authenticate a user |
| `POST` | `/api/chat` | Main chat endpoint (ConversationAgent entry point) |
| `GET` | `/api/user/orders?username=` | Fetch orders for a customer |
| `GET` | `/api/user/tickets?username=` | Fetch support tickets for a customer |
| `GET` | `/api/admin/tickets` | Fetch all pending tickets (admin) |
| `POST` | `/api/admin/tickets/{id}/resolve` | Approve or Deny a ticket (admin) |
| `GET` | `/api/admin/waf-logs` | Fetch recent WAF audit log entries |
| `GET` | `/api/admin/sessions` | Fetch user session transcripts |
| `GET` | `/api/status` | Health check |

---

## Security Design Highlights

- **Zero-trust tool execution**: Every tool call — even from trusted specialist agents — is evaluated by the WAF before it reaches the database.
- **IDOR prevention**: The `customer_data_scope` policy queries the `users → customers → orders` chain to verify ownership before any order-related tool fires.
- **Anti-hallucination guard**: The `cancel_order` tool performs a verbatim substring check against the user's actual last message to block LLM-fabricated cancellation reasons.
- **Session locking**: When a specialist agent asks a follow-up question, the session is locked to that agent. The next message bypasses `ConversationAgent` entirely and is delivered directly to the specialist — preventing routing loops.
- **PII sanitization**: The `AuditLogger` strips credit card numbers and SSNs from arguments before writing to `waf_audit_logs`.
- **Duplicate suppression**: A time-windowed check prevents multiple support tickets from being created for the same order within 60 minutes.

---

## Deployment

See [`docs/ec2_deployment_guide.md`](docs/ec2_deployment_guide.md) for step-by-step instructions to deploy the full stack on an AWS EC2 t3.micro instance using Nginx as a reverse proxy and systemd for process management.

---

## Testing

See [`docs/application_testing_protocol.md`](docs/application_testing_protocol.md) for a 42-case test suite covering:
- Base agent workflows
- All five specialist agents
- WAF security enforcement (IDOR, rate limiting, PII, state transitions, duplicate detection)
- Admin dashboard operations
- Edge cases

---

## Testing Credentials

For evaluators and local testing, you can use the following mock accounts seeded in the database:

| Role | Username | Password |
|---|---|---|
| **Admin** | `mukundvinayak` | `mukund` |
| **Customer** | `scottpowell` | `password123` |
| **Customer** | `terrywilliams` | `password123` |
| **Customer** | `danielholt` | `password123` |

---

*Built for the AI Governance and Security space.*