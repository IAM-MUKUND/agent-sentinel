import os
import json
from dotenv import load_dotenv
from groq import Groq

# Explicitly load the .env file from the backend directory
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(backend_dir, '.env')
load_dotenv(dotenv_path=env_path)

def get_order_management_prompt():
    prompt_path = os.path.join(backend_dir, 'prompts', 'order_management_prompt.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "You are an Order Management Agent."

ORDER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "track_shipment",
            "description": "Track the current shipping status and ETA of an order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The ID of the order to track."
                    }
                },
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_order",
            "description": "Attempt to cancel an order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The ID of the order to cancel."
                    },
                    "customer_reason_quote": {
                        "type": "string",
                        "description": "The exact quote from the customer explaining the specific cause for cancellation (e.g., 'ordered by mistake'). IMPORTANT: Phrases like 'I want to cancel my order' express INTENT, not a REASON. If the user only states intent, DO NOT CALL THIS TOOL. You must ask them why first."
                    }
                },
                "required": ["order_id", "customer_reason_quote"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "modify_delivery_address",
            "description": "Modify the delivery address of an existing order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string"
                    },
                    "new_address": {
                        "type": "string",
                        "description": "The new delivery address provided by the customer."
                    }
                },
                "required": ["order_id", "new_address"]
            }
        }
    }
]

class OrderManagementAgent:
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
        
        # Initialize WAF Middleware
        from backend.middleware.waf.middleware import WAFMiddleware
        policies_dir = os.path.join(backend_dir, 'policies')
        self.waf = WAFMiddleware(policies_dir, db=self.db)
        self.agent_id = "order_management_agent"
        
    def _execute_tool(self, tool_name: str, args: dict, history: dict = None) -> str:
        print(f"    [OrderManagementAgent - Executing Tool] {tool_name} with args: {args}")
        
        # Extract username and session_id from route_data context
        username = history.get("customer_username") if isinstance(history, dict) else None
        session_id = history.get("session_id", "unknown_session") if isinstance(history, dict) else "unknown_session"
        
        # WAF Interception
        decision = self.waf.evaluate_request(
            agent_id=self.agent_id,
            tool_name=tool_name,
            args=args,
            session_id=session_id,
            username=username
        )
        print(f"    [WAF] Decision: {decision.decision} | Reason: {decision.reason}")
        if decision.decision == "DENY":
            return json.dumps({"error": f"WAF Blocked Execution: {decision.reason}"})
        elif decision.decision == "HITL":
            return json.dumps({"status": "hitl_required", "reason": decision.reason})
            
        order_id = args.get("order_id")
        if not order_id:
            return json.dumps({"error": "order_id is required."})
            
        orders_col = self.db[os.getenv("COLLECTION_ORDERS", "orders")]
        order = orders_col.find_one({"order_id": order_id})
        
        if not order:
            return json.dumps({"error": f"Order {order_id} not found."})
            
        order_status = order.get("order_status", "Pending")
        
        if tool_name == "track_shipment":
            eta = order.get("delivery_date", "TBD")
            carrier = order.get("carrier", "Standard Shipping")
            return json.dumps({"status": order_status, "eta": eta, "carrier": carrier})
            
        elif tool_name == "cancel_order":
            
            reason = args.get("customer_reason_quote", "No reason provided")
            reason_lower = reason.lower()
            
            # 1. Catch explicit LLM admissions of missing data
            if "not provided" in reason_lower or "no reason" in reason_lower:
                return json.dumps({"status": "failed", "error": "Reason not provided. You MUST reply to the user and ask them 'Why do you want to cancel?' before trying again."})

            # 2. Check for generic intent
            generic_phrases = ["would like to cancel", "want to cancel", "cancel my order", "please cancel", "request to cancel"]
            if any(phrase in reason_lower for phrase in generic_phrases) and len(reason) < 50:
                return json.dumps({"status": "failed", "error": "The provided reason is an expression of intent (e.g., 'I want to cancel') rather than a valid cause. You MUST reply to the user and ask them 'Why do you want to cancel?' before trying again."})
                
            # 3. Anti-Hallucination check: ensure the reason maps to the user's actual words
            if history and "history" in history:
                last_user_msg = ""
                for msg in reversed(history["history"]):
                    if msg.get("role") == "user":
                        last_user_msg = msg.get("content", "").lower()
                        break
                
                if last_user_msg:
                    import string
                    # Strip punctuation for strict substring comparison
                    clean_reason = reason_lower.translate(str.maketrans('', '', string.punctuation))
                    clean_msg = last_user_msg.translate(str.maketrans('', '', string.punctuation))
                    
                    if clean_reason not in clean_msg:
                        return json.dumps({"status": "failed", "error": "The quote provided does not exactly match the user's message. You hallucinated it! You MUST ask the user 'Why do you want to cancel?' and wait for their response."})
                
            orders_col.update_one({"order_id": order_id}, {"$set": {"order_status": "cancelled", "cancellation_reason": reason, "payment_status": "refunded"}})
            
            # Notify Admin by creating an autonomously 'Approved' ticket
            import uuid
            from datetime import datetime
            self.db[os.getenv("COLLECTION_SUPPORT_TICKETS", "support_tickets")].insert_one({
                "ticket_id": f"TKT-NOTIF-{str(uuid.uuid4())[:8]}".upper(),
                "customer_id": "System",
                "ticket_type": "Auto-Cancellation",
                "reason": f"System Alert: Order {order_id} was automatically cancelled. Customer Reason: {reason}",
                "order_id": order_id,
                "status": "Approved",
                "created_at": datetime.utcnow()
            })
            
            return json.dumps({"status": "success", "message": "Order successfully cancelled."})
            
        elif tool_name == "modify_delivery_address":
                
            new_address = args.get("new_address")
            orders_col.update_one({"order_id": order_id}, {"$set": {"delivery_address": new_address}})
            return json.dumps({"status": "success", "message": "Address updated successfully."})
            
        return json.dumps({"error": "Unknown tool"})

    def execute(self, route_data: dict) -> dict:
        """
        Executes the order management workflow based on the routed data.
        """
        initial_context = f"A request has been routed to you. Here is the collected data: {json.dumps(route_data)}"
        
        messages = [
            {"role": "system", "content": get_order_management_prompt()},
            {"role": "user", "content": initial_context}
        ]
        
        print("[Order Management Agent] Started processing request...")
        
        # Loop to allow the agent to call tools and get responses
        for _ in range(3): 
            try:
                response = self.client.chat.completions.create(
                    messages=messages,
                    model=self.model,
                    temperature=0.3,
                    tools=ORDER_TOOLS,
                    tool_choice="auto"
                )
                
                response_message = response.choices[0].message
                messages.append(response_message)
                
                if response_message.tool_calls:
                    for tool_call in response_message.tool_calls:
                        args = json.loads(tool_call.function.arguments)
                        tool_result = self._execute_tool(tool_call.function.name, args, route_data)
                        
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_call.function.name,
                            "content": tool_result
                        })
                    # Continue loop to let the LLM evaluate the tool results
                    continue
                else:
                    return {
                        "status": "completed",
                        "agent": "OrderManagementAgent",
                        "reply": response_message.content
                    }
                    
            except Exception as e:
                return {
                    "status": "error",
                    "agent": "OrderManagementAgent",
                    "message": str(e)
                }
                
        return {
            "status": "error",
            "message": "Order Management agent exceeded maximum tool loops."
        }
