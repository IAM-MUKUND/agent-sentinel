import os
import sys

# Add the project root to sys.path to allow absolute imports starting with 'backend.'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from core.database import db
from agents.conversation_agent import ConversationAgent
from agents.intent_router import IntentRouter
from utils.logger import logger

app = FastAPI(title="Agent Sentinel API")

# CORS middleware for React
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info("FastAPI Application Starting up...")

# Models
class LoginRequest(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    username: str
    message: str
    session_id: Optional[str] = None
    image_data: Optional[str] = None
    
class ResolveTicketRequest(BaseModel):
    action: str # "Approved" or "Denied"
    admin_username: str

# Instantiate Agents
logger.debug("Instantiating agents: ConversationAgent, IntentRouter")
conv_agent = ConversationAgent()
router = IntentRouter()

# In-memory session state for conversation contexts
active_sessions = {}

@app.get("/api/status")
async def get_status():
    logger.debug("Received request on /api/status")
    return {"status": "ok", "message": "Agent Sentinel Backend is running"}

@app.post("/api/auth/login")
async def login(req: LoginRequest):
    logger.debug(f"Attempting login for user: {req.username}")
    user = await db[os.getenv("COLLECTION_USERS", "users")].find_one({"username": req.username, "password": req.password})
    
    if not user:
        logger.warning(f"Failed login attempt for user: {req.username}")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    logger.debug(f"Successful login for user: {req.username}, Role: {user.get('role')}")
    return {
        "success": True,
        "user_id": user.get("user_id"),
        "username": user.get("username"),
        "role": user.get("role")
    }

@app.post("/api/chat")
async def process_chat(req: ChatRequest):
    logger.debug(f"Received chat request from {req.username}. Message: {req.message}")
    
    session_id = req.session_id
    if not session_id:
        session_id = str(uuid.uuid4())
        logger.debug(f"Generated new session_id: {session_id}")
        
    if session_id not in active_sessions:
        active_sessions[session_id] = {"intent": None}
        
    session_data = active_sessions[session_id]
    if "history" not in session_data:
        session_data["history"] = []
    
    if req.image_data:
        session_data["uploaded_image"] = req.image_data

    # ── LOCKED-AGENT FAST PATH ──────────────────────────────────────────────
    # If a specialist agent asked a follow-up question on the previous turn,
    # we skip ConversationAgent entirely and route straight back to them so
    # they receive the user's answer in context, not a fresh routing decision.
    if session_data.get("locked_intent"):
        locked_intent = session_data["locked_intent"]
        logger.debug(f"[Locked Agent] Bypassing ConversationAgent. Routing directly to '{locked_intent}' for session {session_id}")
        try:
            # Append the new user message to history before routing
            session_data["history"].append({"role": "user", "content": req.message})
            session_data["customer_username"] = req.username
            session_data["intent"] = locked_intent

            result = router.route_request(session_data)
            final_reply = result.get("reply", result.get("message", "I'm sorry, I'm having trouble right now."))

            if "ticket_id" in result:
                # Workflow complete — save ticket, clear all locks
                ticket_doc = {
                    "ticket_id": result["ticket_id"],
                    "customer_id": session_data.get("customer_username", "Unknown"),
                    "ticket_type": result.get("ticket_type", "Unknown"),
                    "reason": result.get("ticket_reason", "Escalated by AI"),
                    "order_id": session_data.get("order_id"),
                    "image_data": session_data.get("uploaded_image"),
                    "status": "Pending",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
                await db[os.getenv("COLLECTION_SUPPORT_TICKETS", "support_tickets")].insert_one(ticket_doc)
                try:
                    await db[os.getenv("COLLECTION_USER_SESSIONS", "user_sessions")].update_one(
                        {"session_id": session_id},
                        {"$push": {"invoked_tickets": {"ticket_id": result["ticket_id"], "status": "Pending"}}}
                    )
                except Exception as e:
                    logger.error(f"Failed to log ticket to session: {e}")

                order_id = session_data.get("order_id")
                ticket_type = result.get("ticket_type")
                if order_id and ticket_type in ["Refund", "Replacement"]:
                    await db[os.getenv("COLLECTION_ORDERS", "orders")].update_one(
                        {"order_id": order_id},
                        {"$set": {"order_status": f"{ticket_type} Pending"}}
                    )

                final_reply += f"\n\n[SYSTEM] Support Ticket {result['ticket_id']} has been created. Status: Pending Admin Approval."
                active_sessions[session_id] = {"history": session_data["history"]}
            else:
                # Still mid-conversation — keep locked, save specialist reply to history
                session_data["history"].append({"role": "assistant", "content": final_reply})
                session_data["intent"] = None
                active_sessions[session_id] = session_data

            # Upsert session log
            try:
                await db[os.getenv("COLLECTION_USER_SESSIONS", "user_sessions")].update_one(
                    {"session_id": session_id},
                    {"$set": {"username": req.username, "last_updated": datetime.utcnow(), "history": session_data["history"]}},
                    upsert=True
                )
            except Exception as e:
                logger.error(f"Failed to upsert session logging: {e}")

            return {"reply": final_reply, "session_id": session_id, "extracted_data": session_data}
        except Exception as e:
            logger.error(f"Error in locked-agent path: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    # ── END LOCKED-AGENT FAST PATH ──────────────────────────────────────────

    # 1. Process via Conversation Agent
    try:
        logger.debug(f"Passing message to ConversationAgent for session {session_id}")
        
        conv_result = conv_agent.process_message(req.message, session_data["history"], session_id=session_id, username=req.username)
        
        # Handle validate_order tool calls dynamically!
        if conv_result.get("status") == "tool_call" and conv_result.get("tool_name") == "validate_order":
            args = conv_result.get("args", {})
            order_id = args.get("order_id")
            user_product = args.get("product")
            logger.debug(f"ConversationAgent executing validate_order for {order_id} and {user_product}")
            
            tool_msg = ""
            if order_id and user_product:
                order = await db[os.getenv("COLLECTION_ORDERS", "orders")].find_one({"order_id": order_id})
                if not order:
                    tool_msg = f"Order {order_id} not found in the database."
                else:
                    product = await db[os.getenv("COLLECTION_PRODUCTS", "products")].find_one({"product_id": order["product_id"]})
                    if product:
                        actual_product_name = product["product_name"]
                        user_words = set(user_product.lower().replace(',', '').split())
                        actual_words = set(actual_product_name.lower().replace(',', '').split())
                        
                        if not user_words.intersection(actual_words):
                            tool_msg = f"Mismatch! Order {order_id} is for a '{actual_product_name}'. This does not match '{user_product}'."
                        else:
                            tool_msg = f"Match! Order {order_id} contains '{actual_product_name}'."
                    else:
                        tool_msg = "Product not found."
            else:
                tool_msg = "Invalid tool arguments. order_id and product are required."
                
            session_data["history"].append({"role": "user", "content": req.message})
            session_data["history"].append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": conv_result["tool_id"],
                    "type": "function",
                    "function": {
                        "name": "validate_order",
                        "arguments": json.dumps(args)
                    }
                }]
            })
            session_data["history"].append({
                "role": "tool",
                "tool_call_id": conv_result["tool_id"],
                "name": "validate_order",
                "content": tool_msg
            })
            
            # Get conversational response based on tool result
            conv_result = conv_agent.process_message(None, session_data["history"], session_id=session_id, username=req.username)
            
            reply_text = conv_result.get("reply", "")
            session_data["history"].append({"role": "assistant", "content": reply_text})
            
        else:
            reply_text = conv_result.get("reply", "")
            session_data["history"].append({"role": "user", "content": req.message})
            session_data["history"].append({"role": "assistant", "content": reply_text})
        
        if conv_result.get("status") == "routed":
            extracted_data = conv_result.get("route_data", {})
            logger.debug(f"ConversationAgent routed with data: {extracted_data}")
            # Merge extracted data into session
            for k, v in extracted_data.items():
                if v is not None:
                    session_data[k] = v
                
        # 2. Check if Intent Routing is triggered
        final_reply = reply_text
        if conv_result.get("status") == "routed":
            intent_name = session_data['intent']
            logger.debug(f"Intent detected: {intent_name}. Handoff to IntentRouter.")
            
            # Before routing, add user info
            session_data["customer_username"] = req.username
            
            # Route to specialist agent
            result = router.route_request(session_data)
            logger.debug(f"IntentRouter executed. Result: {result}")
            
            if "reply" in result:
                final_reply = result["reply"]
            elif "message" in result:
                final_reply = result["message"]
                
            # If a ticket was created, append it to the reply and save to DB
            if "ticket_id" in result:
                logger.debug(f"Support ticket {result['ticket_id']} created from agent workflow. Saving to DB.")
                
                # Save to database so Admin Dashboard can pull it
                ticket_doc = {
                    "ticket_id": result["ticket_id"],
                    "customer_id": session_data.get("customer_username", "Unknown"),
                    "ticket_type": result.get("ticket_type", "Unknown"),
                    "reason": result.get("ticket_reason", "Escalated by AI"),
                    "order_id": session_data.get("order_id"),
                    "image_data": session_data.get("uploaded_image"),
                    "status": "Pending",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
                await db[os.getenv("COLLECTION_SUPPORT_TICKETS", "support_tickets")].insert_one(ticket_doc)
                
                # Session Logging: Track Invoked Ticket
                try:
                    await db[os.getenv("COLLECTION_USER_SESSIONS", "user_sessions")].update_one(
                        {"session_id": session_id},
                        {"$push": {"invoked_tickets": {"ticket_id": result["ticket_id"], "status": "Pending"}}}
                    )
                except Exception as e:
                    logger.error(f"Failed to log ticket to session: {e}")
                
                # Update the order status to Pending
                order_id = session_data.get("order_id")
                ticket_type = result.get("ticket_type")
                if order_id and ticket_type in ["Refund", "Replacement"]:
                    await db[os.getenv("COLLECTION_ORDERS", "orders")].update_one(
                        {"order_id": order_id},
                        {"$set": {"order_status": f"{ticket_type} Pending"}}
                    )
                
                final_reply += f"\n\n[SYSTEM] Support Ticket {result['ticket_id']} has been created. Status: Pending Admin Approval."
                
                # Clear session state since workflow is complete
                active_sessions[session_id] = {"history": session_data["history"]}
            else:
                # Specialist is mid-conversation (asked a follow-up question, no ticket yet).
                # Lock this session to the specialist so the user's next reply goes
                # directly to them without re-routing through ConversationAgent.
                session_data["locked_intent"] = intent_name
                session_data["intent"] = None
                if final_reply and final_reply != reply_text:
                    session_data["history"].append({"role": "assistant", "content": final_reply})
                active_sessions[session_id] = session_data
                
        # Session Logging: Upsert chat history
        try:
            await db[os.getenv("COLLECTION_USER_SESSIONS", "user_sessions")].update_one(
                {"session_id": session_id},
                {"$set": {
                    "username": req.username,
                    "last_updated": datetime.utcnow(),
                    "history": session_data["history"]
                }},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to upsert session logging: {e}")

        logger.debug(f"Returning final reply to {req.username}")
        return {
            "reply": final_reply,
            "session_id": session_id,
            "extracted_data": session_data
        }
        
    except Exception as e:
        logger.error(f"Error processing chat in session {session_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/user/orders")
async def get_user_orders(username: str):
    logger.debug(f"Fetching orders for user: {username}")
    user = await db[os.getenv("COLLECTION_USERS", "users")].find_one({"username": username})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    customer = await db[os.getenv("COLLECTION_CUSTOMERS", "customers")].find_one({"user_id": user["user_id"]})
    if not customer:
        return [] # Admin or user with no customer profile
        
    cursor = db[os.getenv("COLLECTION_ORDERS", "orders")].find({"customer_id": customer["customer_id"]}).sort("purchase_date", -1).limit(10)
    orders = await cursor.to_list(length=10)
    
    formatted_orders = []
    for o in orders:
        product = await db[os.getenv("COLLECTION_PRODUCTS", "products")].find_one({"product_id": o["product_id"]})
        product_name = product["product_name"] if product else "Unknown Product"
        formatted_orders.append({
            "order_id": o["order_id"],
            "product_name": product_name,
            "status": o.get("order_status", "Completed"),
            "date": str(o.get("purchase_date", ""))[:10]
        })
        
    return formatted_orders

@app.get("/api/user/tickets")
async def get_user_tickets(username: str):
    logger.debug(f"Fetching tickets for user: {username}")
    cursor = db[os.getenv("COLLECTION_SUPPORT_TICKETS", "support_tickets")].find({"customer_id": username})
    tickets = await cursor.to_list(length=20)
    
    # Return ticket_id and status
    formatted = []
    for t in tickets:
        formatted.append({
            "ticket_id": t["ticket_id"],
            "status": t["status"]
        })
    return formatted

@app.get("/api/admin/tickets")
async def get_tickets():
    logger.debug("Admin requested to fetch support tickets")
    try:
        # Fetch all tickets
        cursor = db[os.getenv("COLLECTION_SUPPORT_TICKETS", "support_tickets")].find().sort("created_at", -1).limit(50)
        tickets = await cursor.to_list(length=50)
        
        # Format for frontend
        formatted_tickets = []
        for t in tickets:
            order_details = None
            order_id = t.get("order_id")
            if order_id:
                order = await db[os.getenv("COLLECTION_ORDERS", "orders")].find_one({"order_id": order_id})
                if order:
                    product = await db[os.getenv("COLLECTION_PRODUCTS", "products")].find_one({"product_id": order.get("product_id")})
                    product_name = product.get("product_name", "Unknown Product") if product else "Unknown Product"
                    order_details = {
                        "product_name": product_name,
                        "total_amount": order.get("total_amount", 0.0),
                        "purchase_date": str(order.get("purchase_date", ""))[:10],
                        "order_status": order.get("order_status", "Unknown")
                    }
                    
            formatted_tickets.append({
                "id": t.get("ticket_id"),
                "customer": t.get("customer_id", "Unknown"),
                "type": t.get("ticket_type", "Unknown"),
                "reason": t.get("reason", "No reason provided"),
                "order_id": order_id,
                "order_details": order_details,
                "image_data": t.get("image_data"),
                "status": t.get("status", "Pending"),
                "riskScore": "High" if t.get("ticket_type") in ["Refund", "Replacement"] else "Low",
                "time": t.get("created_at", datetime.utcnow()).strftime("%Y-%m-%d %H:%M") if isinstance(t.get("created_at"), datetime) else "Just now"
            })
            
        logger.debug(f"Returning {len(formatted_tickets)} tickets to admin dashboard")
        return formatted_tickets
    except Exception as e:
        logger.error(f"Failed to fetch tickets: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch tickets")

@app.post("/api/admin/tickets/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: str, req: ResolveTicketRequest):
    logger.debug(f"Admin '{req.admin_username}' attempting to {req.action} ticket: {ticket_id}")
    try:
        ticket = await db[os.getenv("COLLECTION_SUPPORT_TICKETS", "support_tickets")].find_one({"ticket_id": ticket_id})
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        result = await db[os.getenv("COLLECTION_SUPPORT_TICKETS", "support_tickets")].update_one(
            {"ticket_id": ticket_id},
            {"$set": {
                "status": req.action,
                "approved_by": req.admin_username,
                "updated_at": datetime.utcnow()
            }}
        )
        
        # Session Logging: Track Admin Resolution
        try:
            await db[os.getenv("COLLECTION_USER_SESSIONS", "user_sessions")].update_many(
                {"invoked_tickets.ticket_id": ticket_id},
                {"$push": {
                    "admin_actions": {
                        "ticket_id": ticket_id,
                        "action": req.action,
                        "admin_username": req.admin_username,
                        "timestamp": datetime.utcnow()
                    }
                },
                "$set": {
                    "invoked_tickets.$[elem].status": req.action
                }},
                array_filters=[{"elem.ticket_id": ticket_id}]
            )
        except Exception as e:
            logger.error(f"Failed to log admin resolution to session: {e}")
        
        if result.modified_count == 0:
            logger.warning(f"Ticket {ticket_id} not found for resolution.")
            raise HTTPException(status_code=404, detail="Ticket not found")
            
        # Update order status based on resolution
        if ticket.get("order_id") and ticket.get("ticket_type") in ["Refund", "Replacement"]:
            if req.action == "Approved":
                new_status = "Refunded" if ticket.get("ticket_type") == "Refund" else "Replaced"
            else:
                new_status = "Completed" # Default back if denied
                
            update_fields = {"order_status": new_status}
            if req.action == "Approved" and ticket.get("ticket_type") == "Refund":
                update_fields["payment_status"] = "refunded"
                
            await db[os.getenv("COLLECTION_ORDERS", "orders")].update_one(
                {"order_id": ticket.get("order_id")},
                {"$set": update_fields}
            )
            
        logger.debug(f"Successfully {req.action} ticket {ticket_id}")
        return {"success": True, "status": req.action}
    except Exception as e:
        logger.error(f"Error resolving ticket {ticket_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to resolve ticket")

@app.get("/api/admin/waf-logs")
async def get_waf_logs():
    logger.debug("Admin requested to fetch WAF logs")
    try:
        cursor = db[os.getenv("COLLECTION_WAF_AUDIT_LOGS", "waf_audit_logs")].find().sort("timestamp", -1).limit(50)
        logs = await cursor.to_list(length=50)
        for log in logs:
            log["_id"] = str(log["_id"])
        return logs
    except Exception as e:
        logger.error(f"Failed to fetch WAF logs: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch WAF logs")

@app.get("/api/admin/sessions")
async def get_sessions():
    logger.debug("Admin requested to fetch user sessions")
    try:
        cursor = db[os.getenv("COLLECTION_USER_SESSIONS", "user_sessions")].find().sort("last_updated", -1).limit(50)
        sessions = await cursor.to_list(length=50)
        for session in sessions:
            session["_id"] = str(session["_id"])
        return sessions
    except Exception as e:
        logger.error(f"Failed to fetch user sessions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch user sessions")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)