import os
import json
from dotenv import load_dotenv
from groq import Groq
from pymongo import MongoClient

# Explicitly load the .env file from the backend directory
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(backend_dir, '.env')
load_dotenv(dotenv_path=env_path)

def get_system_prompt():
    prompt_path = os.path.join(backend_dir, 'prompts', 'conversation_prompt.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "You are a helpful customer support AI."

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "route_to_specialist",
            "description": "Route the customer to a specialized agent when you have collected all necessary information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "enum": [
                            "Refund", 
                            "Replacement", 
                            "Order Management", 
                            "Billing", 
                            "Complaint & Technical Support"
                        ],
                        "description": "The department to route the user to based on their request."
                    },
                    "order_id": {
                        "type": "string",
                        "description": "The order ID provided by the user, if applicable."
                    },
                    "product": {
                        "type": "string",
                        "description": "The product name mentioned by the user, if applicable."
                    },
                    "reason": {
                        "type": "string",
                        "description": "The reason for the request (e.g. damaged, wrong item, late delivery)."
                    },
                    "image_uploaded": {
                        "type": "boolean",
                        "description": "True if the user was asked to upload an image and confirmed they did."
                    },
                    "summary": {
                        "type": "string",
                        "description": "A brief summary of the user's issue to pass to the specialist."
                    }
                },
                "required": ["intent", "summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_order",
            "description": "Validate if the order ID exists and matches the product the user is asking about. USE THIS TOOL as soon as you have the order_id and product name, BEFORE asking for any images or escalating.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID provided by the user."
                    },
                    "product": {
                        "type": "string",
                        "description": "The product name mentioned by the user."
                    }
                },
                "required": ["order_id", "product"]
            }
        }
    }
]

class ConversationAgent:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is missing.")
            
        self.client = Groq(api_key=api_key)
        # Llama 3 70B is excellent at tool calling
        self.model = "llama-3.3-70b-versatile"
        
        # Connect to MongoDB for WAF
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        db_name = os.getenv("MONGO_DB_NAME", "agentsentinel")
        self.mongo_client = MongoClient(mongo_uri)
        self.db = self.mongo_client[db_name]
        
        # Initialize WAF — gates validate_order to prevent order enumeration
        from backend.middleware.waf.middleware import WAFMiddleware
        policies_dir = os.path.join(backend_dir, 'policies')
        self.waf = WAFMiddleware(policies_dir, db=self.db)
        self.agent_id = "ConversationAgent"

    def process_message(self, user_message: str = None, chat_history: list = None, session_id: str = "unknown_session", username: str = None, **kwargs):
        """
        Process the user's message, potentially using the chat history to maintain context.
        chat_history format: [{"role": "user"/"assistant", "content": "..."}]
        """
        if chat_history is None:
            chat_history = []
            
        messages = [{"role": "system", "content": get_system_prompt()}] + chat_history
        if user_message:
            messages.append({"role": "user", "content": user_message})

        try:
            response = self.client.chat.completions.create(
                messages=messages,
                model=self.model,
                temperature=0.3,
                tools=TOOLS,
                tool_choice="auto"
            )
            
            response_message = response.choices[0].message
            
            # Check if the model decided to invoke a tool
            if response_message.tool_calls:
                tool_call = response_message.tool_calls[0]
                args = json.loads(tool_call.function.arguments)
                
                if tool_call.function.name == "route_to_specialist":
                    return {
                        "status": "routed",
                        "route_data": args,
                        "reply": f"Thank you for the information. I am routing your request to the {args.get('intent')} department now."
                    }
                elif tool_call.function.name == "validate_order":
                    # WAF rate-limit check to prevent order enumeration at the entry point
                    waf_decision = self.waf.evaluate_request(
                        agent_id=self.agent_id,
                        tool_name="validate_order",
                        args=args,
                        session_id=session_id,
                        username=username
                    )
                    if waf_decision and waf_decision.decision == "DENY":
                        return {
                            "status": "error",
                            "reply": f"Your request was blocked by our security system: {waf_decision.reason}"
                        }
                    return {
                        "status": "tool_call",
                        "tool_name": "validate_order",
                        "tool_id": tool_call.id,
                        "args": args
                    }
            
            # If no tool was called, it means we are still conversing
            return {
                "status": "conversing",
                "reply": response_message.content
            }
            
        except Exception as e:
            return {
                "status": "error",
                "reply": "I'm sorry, I'm having trouble connecting to my systems right now.",
                "error": str(e)
            }

        except Exception as e:
            logger.exception("ConversationAgent failed")

            traceback.print_exc()

            return {
                "status": "error",
                "reply": "I'm sorry, I'm having trouble connecting to my systems right now.",
                "error": str(e)
            }