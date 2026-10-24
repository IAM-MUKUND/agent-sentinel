
Agent Sentinel - WAF Middleware Planning

This document outlines the strategic plan for implementing the Agent Web Application Firewall (WAF) middleware across the different specialist agents in the Agent Sentinel platform.

Objective

To intercept, inspect, govern, and audit every tool invocation made by autonomous agents before execution. The Agent Sentinel operates as a transparent policy enforcement proxy between AI agents and backend tools, ensuring secure, explainable, and governed execution through configurable policy evaluation.

The middleware is designed to be application-agnostic, while supporting application-specific policy packs that extend governance for different domains.

Policy Architecture

The Agent Sentinel evaluates policies in two layers:

Layer 1 - Generic WAF Policies

These policies are reusable across any AI agent application.

Examples:

General Rate Limiting
Parameter Validation
Payload Size Validation
Retry Limits
Data Scope Validation
Sequence Validation
Output Filtering
PII Masking
Audit Logging
Emergency Lockdown
Shadow Mode
Layer 2 - Customer Support Policy Pack

These policies are specific to the Customer Support Automation platform.

Examples:

Refund Limits
Replacement Cooldown
Customer Ownership Validation
Duplicate Refund Detection
Warranty Validation
Refund Eligibility Window
Human-in-the-Loop Approval
Fraud Detection Rules
Cross-Cutting WAF Policies

The following policies execute for every intercepted tool invocation, regardless of which agent generated the request.

Audit Logging

Every tool invocation must generate an immutable audit log containing:

Timestamp
Session ID
Agent ID
Tool Name
Sanitized Parameters
Matched Policies
Decision
Decision Reason
Policy Version
Evaluation Latency

Reason:

Provides traceability, debugging, compliance, and evaluation metrics.

Shadow Mode

Supports two operating modes.

Enforce Mode

Policy violations are blocked immediately.

Shadow Mode

Policy violations are only logged while allowing execution.

Reason:

Allows administrators to safely evaluate new policies before enforcing them.

Policy Evaluation Trace

Every request records the sequence of evaluated policies.

Example:

Rate Limit           ✓
Parameter Validation ✓
Customer Ownership   ✓
Refund Eligibility   ✓
HITL                 ✓

Final Decision:
ALLOW

Reason:

Provides explainability and simplifies debugging.

Policy Versioning

Every audit record stores the active policy version.

Reason:

Ensures reproducibility of experiments and simplifies future policy updates.

WAF Performance Metrics

Measure:

Policy Evaluation Time
Total Middleware Latency
Tool Execution Latency

Reason:

Demonstrates that Agent Sentinel introduces minimal performance overhead.

1. Conversation Agent

Role: Entry point of the system responsible for conversational interaction and intent extraction.

Generic Policies
General Rate Limiting
Output Filtering
Payload Size Validation
Audit Logging
Customer Support Policies
Intent Authorization
Only valid customer support intents may be routed.
Prompt Injection Detection
Detect attempts to manipulate routing or reveal internal prompts.

Reason:

Since this is the public-facing entry point, it is the highest-risk surface for abuse and prompt injection.

2. Order Management Agent

Role: Handles order tracking, modifications, shipping information, and autonomous cancellations.

Generic Policies
Strict Parameter Validation
Data Scope Validation
Sequence Validation
Output Filtering
Audit Logging
Customer Support Policies
Customer Ownership Validation
Order State Validation
Prevent cancellation after delivery.
Shipment Visibility Rules
Hide full delivery address.
Duplicate Cancellation Detection

Reason:

Protects customer isolation while preventing invalid state transitions.

3. Refund Agent

Role: Processes financial refund requests.

Generic Policies
Parameter Validation
Sequence Validation
Retry Limits
Audit Logging
Customer Support Policies
Human-in-the-Loop Enforcement
Refund Limits
Duplicate Refund Detection
Refund Eligibility Window
Fraud Detection Rules
Customer Ownership Validation

Reason:

Financial operations require the strongest governance and auditability.

4. Replacement Agent

Role: Processes product replacement requests.

Generic Policies
Parameter Validation
Cooldown Period
Sequence Validation
Audit Logging
Customer Support Policies
Human-in-the-Loop Enforcement
Replacement Cooldown
Warranty Validation
Fraud Detection Rules
Inventory Availability Validation

Reason:

Prevents replacement abuse while ensuring inventory integrity.

5. Billing Agent

Role: Handles invoices and payment information.

Generic Policies
Output Filtering
Payload Size Validation
Retry Limits
Audit Logging
Customer Support Policies
Invoice Visibility Rules
Credit Card Masking
Payment Method Validation
Customer Ownership Validation

Reason:

Billing operations involve sensitive financial information requiring strict privacy controls.

6. Support Agent

Role: Handles technical support and issue escalation.

Generic Policies
Rate Limiting
Input Sanitization
Payload Size Validation
Audit Logging
Customer Support Policies
Ticket Flood Protection
Duplicate Ticket Detection
Priority Routing
Escalation Rules

Reason:

Prevents abuse of support channels while ensuring genuine issues receive appropriate priority.

Implementation Strategy

1. Transparent Middleware

Implement a policy-agnostic interception layer (WAFMiddleware) that intercepts every tool invocation before execution.

2. Dynamic Policy Loader

Load both:

Generic Policies
Customer Support Policy Pack

from YAML configuration files at runtime.

3. Policy Evaluation Pipeline
   LLM Tool Call
   │
   ▼
   Request Interceptor
   │
   ▼
   Generic Policy Evaluation
   │
   ▼
   Application Policy Evaluation
   │
   ▼
   Decision Engine
   │
   ┌──────┼───────────┐
   │      │           │
   ▼      ▼           ▼
   ALLOW  DENY       HITL
   │      │           │
   └──────┼───────────┘
   ▼
   Audit Logger
   ▼
   Tool Execution
4. Decision Object

Every intercepted request returns a structured decision.

Example:

{
    "decision": "DENY",
    "matched_policy": "refund_limits.yaml",
    "reason": "Refund exceeds configured threshold.",
    "policy_version": "v1.0.0",
    "evaluation_latency_ms": 8,
    "trace": [
        "Rate Limit ✓",
        "Parameter Validation ✓",
        "Refund Limit ✗"
    ]
}
Success Criteria

The Agent Sentinel should demonstrate the following capabilities:

Intercept every tool invocation transparently.
Enforce generic WAF policies independently of the application.
Apply customer support governance through application-specific policy packs.
Maintain complete audit logs for every decision.
Support Human-in-the-Loop (HITL) approval workflows.
Provide real-time dashboard updates for tool invocations and blocked requests.
Support Shadow Mode for safe policy calibration.
Maintain low middleware latency while ensuring comprehensive policy enforcement.
