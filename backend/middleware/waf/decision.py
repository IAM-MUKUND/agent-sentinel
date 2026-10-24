from typing import List, Optional
from pydantic import BaseModel, Field

class Decision(BaseModel):
    decision: str = Field(..., description="ALLOW, DENY, or HITL")
    matched_policy: Optional[str] = Field(None, description="The ID of the policy that triggered the decision")
    reason: str = Field(..., description="Human-readable explanation of the decision")
    policy_version: str = Field("v1.0.0", description="Version of the policy engine/ruleset")
    evaluation_latency_ms: float = Field(0.0, description="Time taken to evaluate policies")
    trace: List[str] = Field(default_factory=list, description="List of evaluated policies and their status")
