# AgentWAF: API Design

## Mock Enterprise Tools API (Phase 3)

These endpoints simulate external tools that the agent might want to interact with.

- `POST /send_email`: Simulates sending an email.
- `POST /delete_customer`: Simulates a destructive action.
- `POST /customer`: Adds a new customerlalsl
- `GET /customer`: Retrieves customer data.
- `POST /upload_document`: Simulates a file upload.
- `GET /download_logs`: Can download the logs/trace of the LLM.
- `POST /process_refund`: Simulates a financial transaction (for testing rate limits & parameter validation).
- `POST /update_server_config`: Simulates a high-risk action (for testing sequence validation).
- `POST /request_approval`: Simulates asking a human for a token before a high-risk action.
- `GET /export_database`: Simulates mass data egress (for testing data scope enforcement).

## AgentWAF Proxy API (Phase 4)

- `POST /v1/agent/invoke_tool`: The primary entry point for the AI agent to make tool requests.

## Dashboard APIs (Phase 9)

- `GET /api/metrics`: Retrieve summary metrics.
- `GET /api/logs`: Retrieve recent audit logs.
