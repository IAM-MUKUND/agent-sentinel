import os
import time
import re
import json
from typing import Dict, Any
from .policy_loader import PolicyLoader
from .decision import Decision
from .audit_logger import AuditLogger

class WAFMiddleware:
    def __init__(self, policies_dir: str, db=None):
        self.policy_loader = PolicyLoader(policies_dir)
        self.audit_logger = AuditLogger(db)
        self.db = db
        self._rate_limits: Dict[str, list] = {}

    def _apply_rate_limit(self, key: str, max_calls: int, window_seconds: int) -> bool:
        now = time.time()
        if key not in self._rate_limits:
            self._rate_limits[key] = []
        
        # Clean up old timestamps
        self._rate_limits[key] = [t for t in self._rate_limits[key] if now - t <= window_seconds]
        
        if len(self._rate_limits[key]) >= max_calls:
            return False # Rate limited
            
        self._rate_limits[key].append(now)
        return True

    def evaluate_request(self, agent_id: str, tool_name: str, args: Dict[str, Any], session_id: str = "default_session", username: str = None) -> Decision:
        start_time = time.time()
        trace = []
        
        policies = self.policy_loader.get_policies_for_agent_and_tool(agent_id, tool_name)
        
        for policy in policies:
            policy_id = policy.get('id', 'unknown_policy')
            rules = policy.get('rules', {})
            shadow_mode = policy.get('shadow_mode', False)
            
            def handle_violation(reason: str):
                if shadow_mode:
                    trace.append(f"{policy_id} (Shadow Violation: {reason})")
                    return None
                latency = (time.time() - start_time) * 1000
                return Decision(
                    decision="DENY",
                    matched_policy=policy_id,
                    reason=reason,
                    evaluation_latency_ms=latency,
                    trace=trace + [f"{policy_id} ✗"]
                )

            # 1. Emergency Lockdown
            if 'emergency_lockdown' in rules and rules.get('emergency_lockdown', {}).get('enabled', False):
                violation = handle_violation("Global emergency lockdown is active.")
                if violation: 
                    self.audit_logger.log_decision(session_id, agent_id, tool_name, args, violation)
                    return violation
                
            # 2. Parameter Validation
            if 'parameter_validation' in rules:
                for param_name, param_rules in rules['parameter_validation'].items():
                    if param_name in args:
                        pattern = param_rules.get('allow_pattern')
                        if pattern and not re.match(pattern, str(args[param_name])):
                            violation = handle_violation(f"Parameter '{param_name}' failed validation against pattern '{pattern}'.")
                            if violation: 
                                self.audit_logger.log_decision(session_id, agent_id, tool_name, args, violation)
                                return violation

            # 4. Payload Size Limit
            if 'payload_size_limit' in rules:
                max_kb = rules['payload_size_limit'].get('max_kilobytes', 1024)
                payload_bytes = len(json.dumps(args).encode('utf-8'))
                if payload_bytes > max_kb * 1024:
                    violation = handle_violation(f"Payload size ({payload_bytes} bytes) exceeds limit ({max_kb} KB).")
                    if violation: 
                        self.audit_logger.log_decision(session_id, agent_id, tool_name, args, violation)
                        return violation

            # 5. Rate Limit
            if 'rate_limit' in rules:
                max_calls = rules['rate_limit'].get('max_calls', 10)
                window_seconds = rules['rate_limit'].get('window_seconds', 60)
                rate_key = f"{session_id}:{tool_name}"
                if not self._apply_rate_limit(rate_key, max_calls, window_seconds):
                    violation = handle_violation(f"Rate limit exceeded for tool {tool_name} (max {max_calls} per {window_seconds}s).")
                    if violation: 
                        self.audit_logger.log_decision(session_id, agent_id, tool_name, args, violation)
                        return violation

            # 6. Data Scope Validation (IDOR Protection)
            if 'data_scope' in rules and rules.get('data_scope', {}).get('validate_customer_ownership', False):
                order_id = args.get('order_id')
                if order_id and self.db is not None:
                    # SECURITY: A missing username is a hard violation — do not silently bypass
                    if not username:
                        violation = handle_violation(f"Data Scope Violation: Unauthenticated request — username is required to access order {order_id}.")
                        if violation:
                            self.audit_logger.log_decision(session_id, agent_id, tool_name, args, violation)
                            return violation
                    else:
                        user = self.db[os.getenv("COLLECTION_USERS", "users")].find_one({"username": username})
                        if user:
                            customer = self.db[os.getenv("COLLECTION_CUSTOMERS", "customers")].find_one({"user_id": user.get("user_id")})
                            if customer:
                                order = self.db[os.getenv("COLLECTION_ORDERS", "orders")].find_one({"order_id": order_id, "customer_id": customer.get("customer_id")})
                                if not order:
                                    violation = handle_violation(f"Data Scope Violation: Order {order_id} does not belong to user {username}.")
                                    if violation: 
                                        self.audit_logger.log_decision(session_id, agent_id, tool_name, args, violation)
                                        return violation
                            else:
                                violation = handle_violation(f"Data Scope Violation: No customer profile found for user {username}.")
                                if violation: 
                                    self.audit_logger.log_decision(session_id, agent_id, tool_name, args, violation)
                                    return violation
                        else:
                            violation = handle_violation(f"Data Scope Violation: User '{username}' not found in the system.")
                            if violation:
                                self.audit_logger.log_decision(session_id, agent_id, tool_name, args, violation)
                                return violation

            # 7. State Transition Validation
            if 'state_transition' in rules:
                order_id = args.get('order_id')
                if order_id and self.db is not None:
                    order = self.db[os.getenv("COLLECTION_ORDERS", "orders")].find_one({"order_id": order_id})
                    if order:
                        order_status = order.get("order_status", "Pending").lower()
                        block_after = [s.lower() for s in rules['state_transition'].get('block_cancellation_after', [])]
                        if order_status in block_after and tool_name in ["cancel_order", "modify_delivery_address"]:
                            violation = handle_violation(f"State Transition Violation: Cannot modify order {order_id} because its status is '{order_status}'.")
                            if violation:
                                self.audit_logger.log_decision(session_id, agent_id, tool_name, args, violation)
                                return violation

            # 8. Duplicate Request Detection
            if 'duplicate_detection' in rules:
                order_id = args.get('order_id')
                if order_id and self.db is not None:
                    time_window = rules['duplicate_detection'].get('time_window_minutes', 60)
                    from datetime import datetime, timedelta
                    cutoff_time = datetime.utcnow() - timedelta(minutes=time_window)
                    existing_ticket = self.db[os.getenv("COLLECTION_SUPPORT_TICKETS", "support_tickets")].find_one({
                        "order_id": order_id,
                        "created_at": {"$gte": cutoff_time},
                        "status": {"$ne": "Completed"}
                    })
                    if existing_ticket:
                        violation = handle_violation(f"Duplicate Detection Violation: An active support ticket already exists for order {order_id}.")
                        if violation:
                            self.audit_logger.log_decision(session_id, agent_id, tool_name, args, violation)
                            return violation
            
            # 9. HITL Approval (Evaluated last so security checks run first)
            if 'human_in_loop' in rules and rules.get('human_in_loop', {}).get('require_approval', False):
                if 'escalate' in tool_name or tool_name == 'escalate_to_admin':
                    latency = (time.time() - start_time) * 1000
                    dec = Decision(
                        decision="HITL",
                        matched_policy=policy_id,
                        reason="Tool requires human approval.",
                        evaluation_latency_ms=latency,
                        trace=trace + [f"{policy_id} (HITL triggered)"]
                    )
                    self.audit_logger.log_decision(session_id, agent_id, tool_name, args, dec)
                    return dec
            
            trace.append(f"{policy_id} ✓")

        latency = (time.time() - start_time) * 1000
        dec = Decision(
            decision="ALLOW",
            matched_policy=None,
            reason="All policies passed.",
            evaluation_latency_ms=latency,
            trace=trace
        )
        self.audit_logger.log_decision(session_id, agent_id, tool_name, args, dec)
        return dec

    def evaluate_response(self, agent_id: str, tool_name: str, response: str) -> str:
        policies = self.policy_loader.get_policies_for_agent_and_tool(agent_id, tool_name)
        redacted_response = response
        
        for policy in policies:
            rules = policy.get('rules', {})
            if 'output_filtering' in rules:
                filters = rules['output_filtering'].get('redact_pii', [])
                replacement = rules['output_filtering'].get('replacement_string', '[REDACTED]')
                
                # Mock PII redaction patterns based on keywords
                for pii_type in filters:
                    if pii_type == 'ssn':
                        redacted_response = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', replacement, redacted_response)
                    elif pii_type == 'credit_card':
                        redacted_response = re.sub(r'\b(?:\d{4}[-\s]?){3}\d{4}\b', replacement, redacted_response)
                        
        return redacted_response
