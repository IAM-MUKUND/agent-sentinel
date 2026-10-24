# AgentWAF: Workflow

## The Tool Call Lifecycle

1. **Request Interception**: The AI agent attempts to call a tool, sending the request to the WAF instead of the tool directly.
2. **Policy Parsing**: The WAF loads relevant policies for the specific agent and tool from the database/YAML.
3. **Rule Evaluation**:
   - **Rate Limiting**: Has the agent exceeded its quota for this window?
   - **Parameter Validation**: Do the arguments match expected schemas and avoid blocklisted patterns?
   - **Sequence Validation**: Is this call logically allowed at this step?
4. **Decision Execution**:
   - If *Allowed*: The WAF forwards the request to the target tool, receives the response, and passes it back to the agent.
   - If *Blocked*: The WAF returns an immediate denial error to the agent.
5. **Auditing**: Regardless of outcome, the request, context, and decision are recorded in the database.
