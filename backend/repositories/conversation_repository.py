from typing import Dict, Any, List, Optional
from backend.core.database import db

class ConversationRepository:
    def __init__(self):
        self.collection = db["conversations"]

    async def create_conversation(self, conversation_data: Dict[str, Any]) -> str:
        result = await self.collection.insert_one(conversation_data)
        return str(result.inserted_id)

    async def get_conversation_by_id(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one({"conversation_id": conversation_id})

    async def get_conversations_by_customer_id(self, customer_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        cursor = self.collection.find({"customer_id": customer_id}).limit(limit)
        return await cursor.to_list(length=limit)

    async def append_message(self, conversation_id: str, message: Dict[str, Any]) -> bool:
        """Appends a single message to the messages array in a conversation"""
        result = await self.collection.update_one(
            {"conversation_id": conversation_id},
            {"$push": {"messages": message}}
        )
        return result.modified_count > 0

    async def update_conversation(self, conversation_id: str, update_data: Dict[str, Any]) -> bool:
        result = await self.collection.update_one({"conversation_id": conversation_id}, {"$set": update_data})
        return result.modified_count > 0

    async def delete_conversation(self, conversation_id: str) -> bool:
        result = await self.collection.delete_one({"conversation_id": conversation_id})
        return result.deleted_count > 0
