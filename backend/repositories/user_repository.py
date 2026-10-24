from typing import Dict, Any, List, Optional
from backend.core.database import db

class UserRepository:
    def __init__(self):
        self.collection = db["users"]

    async def create_user(self, user_data: Dict[str, Any]) -> str:
        result = await self.collection.insert_one(user_data)
        return str(result.inserted_id)

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one({"user_id": user_id})

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one({"email": email})

    async def update_user(self, user_id: str, update_data: Dict[str, Any]) -> bool:
        result = await self.collection.update_one({"user_id": user_id}, {"$set": update_data})
        return result.modified_count > 0

    async def delete_user(self, user_id: str) -> bool:
        result = await self.collection.delete_one({"user_id": user_id})
        return result.deleted_count > 0

    async def get_all_users(self, limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        cursor = self.collection.find().skip(skip).limit(limit)
        return await cursor.to_list(length=limit)
