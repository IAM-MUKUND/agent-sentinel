import os
import re
from datetime import datetime
from typing import Dict, Any

class AuditLogger:
    def __init__(self, db=None):
        self.db = db
        self.collection_name = os.getenv("COLLECTION_WAF_AUDIT_LOGS", "waf_audit_logs")

    def _sanitize_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Redact potential PII (SSN, Credit Cards) from the arguments before logging."""
        sanitized = {}
        for k, v in args.items():
            if isinstance(v, str):
                # Redact SSN
                val = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[REDACTED]', v)
                # Redact Credit Card
                val = re.sub(r'\b(?:\d{4}[-\s]?){3}\d{4}\b', '[REDACTED]', val)
                sanitized[k] = val
            elif isinstance(v, dict):
                sanitized[k] = self._sanitize_args(v)
            else:
                sanitized[k] = v
        return sanitized

    def log_decision(self, session_id: str, agent_id: str, tool_name: str, args: Dict[str, Any], decision_obj: Any):
        if self.db is None:
            print("[WAF Audit Logger] Database not provided. Skipping log insertion.")
            return

        try:
            sanitized_args = self._sanitize_args(args)
            
            audit_entry = {
                "timestamp": datetime.utcnow(),
                "session_id": session_id,
                "agent_id": agent_id,
                "tool_name": tool_name,
                "sanitized_params": sanitized_args,
                "matched_policy": decision_obj.matched_policy,
                "decision": decision_obj.decision,
                "decision_reason": decision_obj.reason,
                "trace": decision_obj.trace,
                "evaluation_latency_ms": decision_obj.evaluation_latency_ms,
                "policy_version": decision_obj.policy_version
            }
            
            self.db[self.collection_name].insert_one(audit_entry)
        except Exception as e:
            print(f"[WAF Audit Logger] Failed to insert audit log: {e}")
