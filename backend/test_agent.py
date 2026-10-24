import os
import sys

# Add the backend dir to the python path to import agents
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.conversation_agent import ConversationAgent
from agents.intent_router import IntentRouter

def main():
    agent = ConversationAgent()
    router = IntentRouter()
    print("Testing Full Workflow (Conversation -> Router -> Refund). Type 'exit' to quit.")
    
    chat_history = []
    while True:
        user_msg = input("User: ")
        if user_msg.lower() in ["exit", "quit"]:
            break
            
        print("Processing...")
        response = agent.process_message(user_msg, chat_history)
        
        if response["status"] == "routed":
            print(f"Agent (Routing): {response['reply']}")
            
            print("\n--- Handoff to Intent Router ---")
            specialist_response = router.route_request(response["route_data"])
            
            print("\n--- Specialist Agent Response ---")
            print(specialist_response)
            break
        elif response["status"] == "conversing":
            print(f"Agent: {response['reply']}")
            
            # Update chat history
            chat_history.append({"role": "user", "content": user_msg})
            chat_history.append({"role": "assistant", "content": response["reply"]})
        else:
            print("Error:", response)
            break

if __name__ == "__main__":
    main()
