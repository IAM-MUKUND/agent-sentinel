import os
import json
from dotenv import load_dotenv
from groq import Groq

# Explicitly load the .env file from the backend directory
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(backend_dir, '.env')
load_dotenv(dotenv_path=env_path)

def get_billing_prompt():
    prompt_path = os.path.join(backend_dir, 'prompts', 'billing_prompt.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "You are a Billing Agent."

BILLING_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "generate_invoice",
            "description": "Generate and retrieve an invoice for a specific order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The ID of the order."
                    }
                },
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "verify_payment",
            "description": "Verify the payment status of an order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The ID of the order."
                    }
                },
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "investigate_duplicate_charge",
            "description": "Investigate if a duplicate charge occurred on a given order or account.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string"
                    }
                },
                "required": ["order_id"]
            }
        }
    }
]

class BillingAgent:
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
        self.agent_id = "BillingAgent"
        
    def _execute_tool(self, tool_name: str, args: dict, route_data: dict = None) -> str:
        print(f"    [BillingAgent - Executing Tool] {tool_name} with args: {args}")
        
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
                
        order_id = args.get("order_id")
        if not order_id:
            return json.dumps({"error": "order_id is required."})

        # Fetch order from DB
        order = self.db[os.getenv("COLLECTION_ORDERS", "orders")].find_one({"order_id": order_id})
        
        if tool_name == "generate_invoice":
            if not order:
                return json.dumps({"error": f"Order {order_id} not found."})
                
            customer = self.db[os.getenv("COLLECTION_CUSTOMERS", "customers")].find_one({"customer_id": order.get("customer_id")})
            product = self.db[os.getenv("COLLECTION_PRODUCTS", "products")].find_one({"product_id": order.get("product_id")})
            
            invoice_data = {
                "type": "invoice_data",
                "company_name": "Vinayak Ecommerce",
                "invoice_number": f"INV-{order_id}",
                "date": str(order.get("purchase_date", "N/A")),
                "purchaser": {
                    "name": customer.get("full_name", "N/A") if customer else "N/A",
                    "address": customer.get("address", "N/A") if customer else "N/A",
                    "phone": customer.get("phone", "N/A") if customer else "N/A"
                },
                "order_details": {
                    "product_name": product.get("product_name", "Unknown Product") if product else "Unknown Product",
                    "quantity": order.get("quantity", 1),
                    "total_amount": order.get("total_amount", 0.0),
                    "payment_status": order.get("payment_status", "Unknown")
                }
            }
            return json.dumps({"status": "success", "invoice_data": invoice_data})
            
        elif tool_name == "verify_payment":
            if not order:
                return json.dumps({"error": f"Order {order_id} not found."})
            payment_status = order.get("payment_status", "unknown")
            return json.dumps({"status": payment_status})
            
        elif tool_name == "investigate_duplicate_charge":
            if not order:
                return json.dumps({"error": f"Order {order_id} not found."})
            
            charge_amount = order.get("total_amount", 0.0)
            return json.dumps({"charge_amount": charge_amount, "status": "investigation_completed_no_flags_found"})
            
        return json.dumps({"error": "Unknown tool"})

    def execute(self, route_data: dict) -> dict:
        initial_context = f"A request has been routed to you. Here is the collected data: {json.dumps(route_data)}"
        
        messages = [
            {"role": "system", "content": get_billing_prompt()},
            {"role": "user", "content": initial_context}
        ]
        
        print("[Billing Agent] Started processing request...")
        
        for _ in range(3): 
            try:
                response = self.client.chat.completions.create(
                    messages=messages,
                    model=self.model,
                    temperature=0.3,
                    tools=BILLING_TOOLS,
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
                    continue
                else:
                    return {
                        "status": "completed",
                        "agent": "BillingAgent",
                        "reply": response_message.content
                    }
                    
            except Exception as e:
                return {
                    "status": "error",
                    "agent": "BillingAgent",
                    "message": str(e)
                }
                
        return {
            "status": "error",
            "message": "Billing agent exceeded maximum tool loops."
        }
