from typing import Dict, Any, List, Optional
from backend.core.database import db

class CustomerRepository:
    def __init__(self):
        self.collection = db["customers"]

    async def create_customer(self, customer_data: Dict[str, Any]) -> str:
        result = await self.collection.insert_one(customer_data)
        return str(result.inserted_id)

    async def get_customer_by_id(self, customer_id: str) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one({"customer_id": customer_id})
        
    async def get_customer_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one({"user_id": user_id})

    async def update_customer(self, customer_id: str, update_data: Dict[str, Any]) -> bool:
        result = await self.collection.update_one({"customer_id": customer_id}, {"$set": update_data})
        return result.modified_count > 0

    async def delete_customer(self, customer_id: str) -> bool:
        result = await self.collection.delete_one({"customer_id": customer_id})
        return result.deleted_count > 0

    async def get_all_customers(self, limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        cursor = self.collection.find().skip(skip).limit(limit)
        return await cursor.to_list(length=limit)
