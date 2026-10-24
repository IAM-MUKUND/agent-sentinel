import os
import json
from dotenv import load_dotenv
from groq import Groq

# Explicitly load the .env file from the backend directory
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(backend_dir, '.env')
load_dotenv(dotenv_path=env_path)

def get_replacement_prompt():
    prompt_path = os.path.join(backend_dir, 'prompts', 'replacement_prompt.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "You are a Replacement Agent."

REPLACEMENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_warranty",
            "description": "Check if a given order is still under warranty.",
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
            "name": "check_inventory",
            "description": "Check if a product is in stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "The name of the product to check."
                    }
                },
                "required": ["product_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_admin",
            "description": "Escalate a verified request to a Human Administrator for final approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string"
                    },
                    "product_name": {
                        "type": "string"
                    },
                    "reason": {
                        "type": "string"
                    },
                    "image_uploaded": {
                        "type": "boolean"
                    }
                },
                "required": ["order_id", "product_name", "reason"]
            }
        }
    }
]

class ReplacementAgent:
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
        self.agent_id = "ReplacementAgent"
        
    def _execute_tool(self, tool_name: str, args: dict, route_data: dict = None) -> str:
        import uuid
        print(f"    [ReplacementAgent - Executing Tool] {tool_name} with args: {args}")
        
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
                
        if tool_name == "check_warranty":
            order_id = args.get("order_id")
            order = self.db[os.getenv("COLLECTION_ORDERS", "orders")].find_one({"order_id": order_id})
            if not order:
                return json.dumps({"status": "not_found", "error": f"Order {order_id} not found."})
                
            warranty_status = order.get("warranty_status", "under_warranty")
            return json.dumps({"status": warranty_status, "days_remaining": 150})
            
        elif tool_name == "check_inventory":
            product_name = args.get("product_name", "")
            product = self.db[os.getenv("COLLECTION_PRODUCTS", "products")].find_one({"product_name": {"$regex": product_name, "$options": "i"}})
            
            if not product:
                return json.dumps({"status": "not_found", "error": f"Product {product_name} not found."})
                
            stock = product.get("stock", 42)
            if stock > 0:
                return json.dumps({"status": "in_stock", "quantity_available": stock})
            else:
                return json.dumps({"status": "out_of_stock", "quantity_available": 0})
                
        elif tool_name == "escalate_to_admin":
            order_id = args.get("order_id")
            if not order_id:
                return json.dumps({"error": "order_id is required for escalation."})
            order = self.db[os.getenv("COLLECTION_ORDERS", "orders")].find_one({"order_id": order_id})
            if not order:
                return json.dumps({"error": f"Order {order_id} not found in database. Cannot escalate."})
            
            return json.dumps({"status": "success", "ticket_status": "Pending Admin Approval", "ticket_id": f"TKT-REP-{str(uuid.uuid4())[:8].upper()}"})
        return json.dumps({"error": "Unknown tool"})

    def execute(self, route_data: dict) -> dict:
        """
        Executes the replacement workflow based on the routed data.
        """
        # Create context from route data
        initial_context = f"A request has been routed to you. Here is the collected data: {json.dumps(route_data)}"
        
        messages = [
            {"role": "system", "content": get_replacement_prompt()},
            {"role": "user", "content": initial_context}
        ]
        
        print("[Replacement Agent] Started processing request...")
        
        ticket_id = None
        ticket_reason = None
        
        # Loop to allow the agent to call tools and get responses
        for _ in range(4): # Max 4 tool execution loops since there are 3 tools
            try:
                response = self.client.chat.completions.create(
                    messages=messages,
                    model=self.model,
                    temperature=0.3,
                    tools=REPLACEMENT_TOOLS,
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
                            ticket_reason = args.get("reason", "Replacement escalation")

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
                        "agent": "ReplacementAgent",
                        "reply": response_message.content
                    }
                    if ticket_id:
                        ret["ticket_id"] = ticket_id
                        ret["ticket_reason"] = ticket_reason
                        ret["ticket_type"] = "Replacement"
                    return ret
                    
            except Exception as e:
                return {
                    "status": "error",
                    "agent": "ReplacementAgent",
                    "message": str(e)
                }
                
        return {
            "status": "error",
            "message": "Replacement agent exceeded maximum tool loops."
        }
