from typing import Dict, Any, List, Optional
from backend.core.database import db

class SupportTicketRepository:
    def __init__(self):
        self.collection = db["support_tickets"]

    async def create_ticket(self, ticket_data: Dict[str, Any]) -> str:
        result = await self.collection.insert_one(ticket_data)
        return str(result.inserted_id)

    async def get_ticket_by_id(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one({"ticket_id": ticket_id})

    async def get_tickets_by_customer_id(self, customer_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        cursor = self.collection.find({"customer_id": customer_id}).limit(limit)
        return await cursor.to_list(length=limit)
        
    async def get_tickets_by_status(self, status: str, limit: int = 100) -> List[Dict[str, Any]]:
        cursor = self.collection.find({"status": status}).limit(limit)
        return await cursor.to_list(length=limit)

    async def append_tool_call(self, ticket_id: str, tool_call: Dict[str, Any]) -> bool:
        """Appends a tool execution result to the ticket"""
        result = await self.collection.update_one(
            {"ticket_id": ticket_id},
            {"$push": {"tool_calls": tool_call}}
        )
        return result.modified_count > 0

    async def update_ticket(self, ticket_id: str, update_data: Dict[str, Any]) -> bool:
        result = await self.collection.update_one({"ticket_id": ticket_id}, {"$set": update_data})
        return result.modified_count > 0

    async def delete_ticket(self, ticket_id: str) -> bool:
        result = await self.collection.delete_one({"ticket_id": ticket_id})
        return result.deleted_count > 0
