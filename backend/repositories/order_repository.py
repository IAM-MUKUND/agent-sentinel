from typing import Dict, Any, List, Optional
from backend.core.database import db

class OrderRepository:
    def __init__(self):
        self.collection = db["orders"]

    async def create_order(self, order_data: Dict[str, Any]) -> str:
        result = await self.collection.insert_one(order_data)
        return str(result.inserted_id)

    async def get_order_by_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one({"order_id": order_id})

    async def get_orders_by_customer_id(self, customer_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        cursor = self.collection.find({"customer_id": customer_id}).limit(limit)
        return await cursor.to_list(length=limit)

    async def update_order(self, order_id: str, update_data: Dict[str, Any]) -> bool:
        result = await self.collection.update_one({"order_id": order_id}, {"$set": update_data})
        return result.modified_count > 0

    async def delete_order(self, order_id: str) -> bool:
        result = await self.collection.delete_one({"order_id": order_id})
        return result.deleted_count > 0

    async def get_all_orders(self, limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        cursor = self.collection.find().skip(skip).limit(limit)
        return await cursor.to_list(length=limit)
