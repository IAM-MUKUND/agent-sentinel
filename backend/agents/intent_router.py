from typing import Dict, Any
from agents.refund_agent import RefundAgent
from agents.replacement_agent import ReplacementAgent
from agents.order_management_agent import OrderManagementAgent
from agents.billing_agent import BillingAgent
from agents.support_agent import SupportAgent

class IntentRouter:
    def __init__(self):
        # We will populate this map as we build out the specialist agents.
        self.specialist_agents = {
            "Refund": RefundAgent(),
            "Replacement": ReplacementAgent(),
            "Order Management": OrderManagementAgent(),
            "Billing": BillingAgent(),
            "Complaint & Technical Support": SupportAgent()
        }

    def route_request(self, route_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Takes the structured JSON output from the Conversation Agent and
        dispatches the request to the correct specialist agent.
        """
        intent = route_data.get("intent")
        
        if not intent:
            return {
                "status": "error",
                "message": "No intent provided for routing."
            }

        agent = self.specialist_agents.get(intent)
        
        if not agent:
            # Placeholder until the specialist agent is implemented
            return {
                "status": "pending_implementation",
                "intent": intent,
                "message": f"The specialist agent for '{intent}' has not been implemented yet.",
                "data_passed": route_data
            }
            
        # Strip out huge payloads like base64 images before passing to the LLM
        clean_route_data = {k: v for k, v in route_data.items() if k not in ["uploaded_image", "image_data"]}
        
        # Keep a flag so the agent knows an image exists
        clean_route_data["image_uploaded"] = bool(route_data.get("uploaded_image"))
        
        print(f"[Intent Router] Routing request for intent: {intent}")
        print(f"[Intent Router] Entities collected: {clean_route_data}")
            
        # If the agent exists, we would call it here.
        response = agent.execute(clean_route_data)
        return response

