import os
import json
from dotenv import load_dotenv
from groq import Groq

# Explicitly load the .env file from the backend directory
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(backend_dir, '.env')
load_dotenv(dotenv_path=env_path)

def get_refund_prompt():
    prompt_path = os.path.join(backend_dir, 'prompts', 'refund_prompt.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "You are a Refund Agent."

REFUND_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "verify_order_eligibility",
            "description": "Check if an order exists and is eligible for a refund.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The ID of the order to check."
                    }
                },
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_admin",
            "description": "Escalate a verified refund request to a Human Administrator for final approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string"
                    },
                    "reason": {
                        "type": "string"
                    },
                    "image_uploaded": {
                        "type": "boolean"
                    }
                },
                "required": ["order_id", "reason"]
            }
        }
    }
]

class RefundAgent:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is missing.")
            
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile" 
        
        # Connect to MongoDB
        from pymongo import MongoClient
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DB_NAME", "agentsentinel")
        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client[db_name]
        
        # Initialize WAF
        from backend.middleware.waf.middleware import WAFMiddleware
        policies_dir = os.path.join(backend_dir, 'policies')
        self.waf = WAFMiddleware(policies_dir, db=self.db)
        self.agent_id = "RefundAgent"
        
    def _execute_tool(self, tool_name: str, args: dict, route_data: dict = None) -> str:
        import uuid
        print(f"    [RefundAgent - Executing Tool] {tool_name} with args: {args}")
        
        # WAF Evaluation
        username = route_data.get("customer_username") if isinstance(route_data, dict) else None
        session_id = route_data.get("session_id", "unknown_session") if isinstance(route_data, dict) else "unknown_session"
        waf_decision = self.waf.evaluate_request(
            agent_id=self.agent_id, 
            tool_name=tool_name, 
            args=args, 
            session_id=session_id, 
            username=username
        )
        
        if waf_decision:
            if waf_decision.decision == "DENY":
                return json.dumps({"error": f"WAF Blocked Execution: {waf_decision.reason}"})
            elif waf_decision.decision == "HITL":
                return json.dumps({"status": "hitl_required", "reason": waf_decision.reason})
                
        if tool_name == "verify_order_eligibility":
            order_id = args.get("order_id")
            if not order_id:
                return json.dumps({"error": "order_id is required."})
                
            order = self.db[os.getenv("COLLECTION_ORDERS", "orders")].find_one({"order_id": order_id})
            if not order:
                return json.dumps({"status": "not_found", "error": f"Order {order_id} not found."})
                
            # Basic eligibility check: order exists and is not already refunded
            order_status = order.get("order_status", "Completed")
            if order_status in ["Refunded", "Refund Pending"]:
                return json.dumps({"status": "ineligible", "reason": f"Order is already {order_status}."})
                
            return json.dumps({"status": "eligible", "order_amount": order.get("total_amount", 120.50)})
            
        elif tool_name == "escalate_to_admin":
            order_id = args.get("order_id")
            if not order_id:
                return json.dumps({"error": "order_id is required for escalation."})
            order = self.db[os.getenv("COLLECTION_ORDERS", "orders")].find_one({"order_id": order_id})
            if not order:
                return json.dumps({"error": f"Order {order_id} not found in database. Cannot escalate."})
            
            return json.dumps({"status": "success", "ticket_status": "Pending Admin Approval", "ticket_id": f"TKT-REF-{str(uuid.uuid4())[:8].upper()}"})
        return json.dumps({"error": "Unknown tool"})

    def execute(self, route_data: dict) -> dict:
        """
        Executes the refund workflow based on the routed data.
        """
        # Create context from route data
        initial_context = f"A request has been routed to you. Here is the collected data: {json.dumps(route_data)}"
        
        messages = [
            {"role": "system", "content": get_refund_prompt()},
            {"role": "user", "content": initial_context}
        ]
        
        print("[Refund Agent] Started processing request...")
        
        ticket_id = None
        ticket_reason = None
        
        # Loop to allow the agent to call tools and get responses
        for _ in range(3): 
            try:
                response = self.client.chat.completions.create(
                    messages=messages,
                    model=self.model,
                    temperature=0.3,
                    tools=REFUND_TOOLS,
                    tool_choice="auto"
                )
                
                response_message = response.choices[0].message
                messages.append(response_message)
                
                if response_message.tool_calls:
                    for tool_call in response_message.tool_calls:
                        args = json.loads(tool_call.function.arguments)
                        tool_result = self._execute_tool(tool_call.function.name, args, route_data)
                        
                        if tool_call.function.name == "escalate_to_admin":
                            ticket_id = json.loads(tool_result).get("ticket_id")
                            ticket_reason = args.get("reason", "Refund escalation")

                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_call.function.name,
                            "content": tool_result
                        })
                    # Continue loop to let the LLM evaluate the tool results
                    continue
                else:
                    # The agent has produced a final conversational response
                    ret = {
                        "status": "completed",
                        "agent": "RefundAgent",
                        "reply": response_message.content
                    }
                    if ticket_id:
                        ret["ticket_id"] = ticket_id
                        ret["ticket_reason"] = ticket_reason
                        ret["ticket_type"] = "Refund"
                    return ret
                    
            except Exception as e:
                return {
                    "status": "error",
                    "agent": "RefundAgent",
                    "message": str(e)
                }
                
        return {
            "status": "error",
            "message": "Refund agent exceeded maximum tool loops."
        }
