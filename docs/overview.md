# AgentWAF: Overview

## System Context
AgentWAF acts as a policy-enforcing proxy between an AI agent and its external tools. It intercepts, evaluates, and logs all tool calls in real-time.

## Key Components
1. **Tool Router**: Intercepts and routes calls.
2. **Policy Engine**: Evaluates calls against predefined governance rules (Rate Limiting, Parameter Validation, Data Scope, Workflow Sequence).
3. **Logging & Auditing**: Records all tool invocation attempts and decisions.
4. **Dashboard**: Real-time visualization of tool usage and blocked calls.
