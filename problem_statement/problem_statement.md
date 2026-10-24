PS-5.1 The Agent WAF


Context

    A Web Application Firewall sits between the internet and a web server, inspecting and filtering
requests before they reach the application. There is no equivalent for agent tool calls. An
agent can invoke any tool it has a connection to, with any parameters, with no inspection layer
between the agent's decision and the tool's execution.


The Challenge

Build an Agent WAF — a policy-enforcing proxy between an agent and its tools that inspects,
filters, and logs every tool invocation in real time.



What to Build

• A transparent proxy layer that intercepts all tool calls from a sample agent.

• A rule engine with at least these rule types: rate limit (agent may call Tool X no more
than N times per minute); parameter validation (reject calls where parameter values
match a blocklist or exceed size limits); data scope (reject calls that reference data
outside the agent's declared scope); sequence rules (reject calls to Tool B unless Tool A
was called first in this session).

• Each intercepted call is logged with timestamp, agent ID, tool, parameters sanitised,
rule evaluation outcome, and final disposition.

• A real-time dashboard showing tool call traffic and block events.


Success Criteria

• Rate limit fires correctly after N calls within the window.

• Parameter blocklist catches a simulated injection attempt in a tool parameter.

• Out-of-scope data access is blocked.

• Sequence rule enforcement correctly blocks a tool called out of expected order.

• Dashboard updates in real time as calls flow through.



Bonus

• Add shadow mode: the WAF logs what it would have blocked without actually blocking,
for safe calibration of new rules before enforcement.
