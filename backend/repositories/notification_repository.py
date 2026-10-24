from typing import Dict, Any, List, Optional
from backend.core.database import db

class NotificationRepository:
    def __init__(self):
        self.collection = db["notifications"]

    async def create_notification(self, notification_data: Dict[str, Any]) -> str:
        result = await self.collection.insert_one(notification_data)
        return str(result.inserted_id)

    async def get_notification_by_id(self, notification_id: str) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one({"notification_id": notification_id})

    async def get_notifications_by_recipient(self, recipient_id: str, unread_only: bool = False, limit: int = 100) -> List[Dict[str, Any]]:
        query = {"recipient_id": recipient_id}
        if unread_only:
            query["read"] = False
        cursor = self.collection.find(query).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def mark_as_read(self, notification_id: str) -> bool:
        result = await self.collection.update_one(
            {"notification_id": notification_id}, 
            {"$set": {"read": True}}
        )
        return result.modified_count > 0
        
    async def mark_all_as_read(self, recipient_id: str) -> int:
        result = await self.collection.update_many(
            {"recipient_id": recipient_id, "read": False}, 
            {"$set": {"read": True}}
        )
        return result.modified_count

    async def delete_notification(self, notification_id: str) -> bool:
        result = await self.collection.delete_one({"notification_id": notification_id})
        return result.deleted_count > 0
