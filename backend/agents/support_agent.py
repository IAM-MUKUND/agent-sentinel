import os
import json
from dotenv import load_dotenv
from groq import Groq
from pymongo import MongoClient

# Explicitly load the .env file from the backend directory
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(backend_dir, '.env')
load_dotenv(dotenv_path=env_path)

def get_support_prompt():
    prompt_path = os.path.join(backend_dir, 'prompts', 'support_prompt.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "You are a Tech Support Agent."

SUPPORT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "Search the technical support and complaint knowledge base.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "The exact or partial name of the product (e.g., 'Steering Wheel Cover')."
                    }
                },
                "required": ["product_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_support_ticket",
            "description": "Create a support ticket to escalate an unresolved issue to a human agent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_description": {
                        "type": "string",
                        "description": "A detailed summary of the customer's issue."
                    }
                },
                "required": ["issue_description"]
            }
        }
    }
]

class SupportAgent:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is missing.")
            
        self.client = Groq(api_key=api_key)
        self.model = "llama-3.3-70b-versatile" 
        
        # Connect to MongoDB
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DB_NAME", "agentsentinel")
        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client[db_name]
        
        # Initialize WAF
        from backend.middleware.waf.middleware import WAFMiddleware
        policies_dir = os.path.join(backend_dir, 'policies')
        self.waf = WAFMiddleware(policies_dir, db=self.db)
        self.agent_id = "SupportAgent"
        
    def _execute_tool(self, tool_name: str, args: dict, route_data: dict = None) -> str:
        print(f"    [SupportAgent - Executing Tool] {tool_name} with args: {args}")
        
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
                
        if tool_name == "search_knowledge_base":
            query = args.get("product_name", "")
            if not query:
                return json.dumps({"solution_found": False, "article": "No product name provided."})
                
            # Search in MongoDB products collection
            product = self.db[os.getenv("COLLECTION_PRODUCTS", "products")].find_one({"product_name": {"$regex": query, "$options": "i"}})
            
            if product and "usage_instructions" in product:
                article = f"Description: {product.get('description', '')}\nUsage Instructions:\n{product['usage_instructions']}"
                return json.dumps({"solution_found": True, "article": article})
                
            return json.dumps({"solution_found": False, "article": "No internal articles found. Please use your broad general knowledge to assist the customer directly. Only escalate if you are completely unable to help."})
            
        elif tool_name == "create_support_ticket":
            import uuid
            ticket_id = f"TKT-TECH-{str(uuid.uuid4())[:6].upper()}"
            return json.dumps({"status": "success", "ticket_id": ticket_id})
            
        return json.dumps({"error": "Unknown tool"})

    def execute(self, route_data: dict) -> dict:
        initial_context = f"A request has been routed to you. Here is the collected data: {json.dumps(route_data)}"
        
        messages = [
            {"role": "system", "content": get_support_prompt()},
            {"role": "user", "content": initial_context}
        ]
        
        print("[Support Agent] Started processing request...")
        
        ticket_id = None
        ticket_reason = None
        
        for _ in range(3): 
            try:
                response = self.client.chat.completions.create(
                    messages=messages,
                    model=self.model,
                    temperature=0.3,
                    tools=SUPPORT_TOOLS,
                    tool_choice="auto"
                )
                
                response_message = response.choices[0].message
                messages.append(response_message)
                
                if response_message.tool_calls:
                    for tool_call in response_message.tool_calls:
                        args = json.loads(tool_call.function.arguments)
                        tool_result = self._execute_tool(tool_call.function.name, args, route_data)
                        
                        if tool_call.function.name == "create_support_ticket":
                            ticket_id = json.loads(tool_result).get("ticket_id")
                            ticket_reason = args.get("issue_description", "Technical Support escalation")

                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_call.function.name,
                            "content": tool_result
                        })
                    continue
                else:
                    ret = {
                        "status": "completed",
                        "agent": "SupportAgent",
                        "reply": response_message.content
                    }
                    if ticket_id:
                        ret["ticket_id"] = ticket_id
                        ret["ticket_reason"] = ticket_reason
                        ret["ticket_type"] = "Technical Support"
                    return ret
                    
            except Exception as e:
                return {
                    "status": "error",
                    "agent": "SupportAgent",
                    "message": str(e)
                }
                
        return {
            "status": "error",
            "message": "Support agent exceeded maximum tool loops."
        }
