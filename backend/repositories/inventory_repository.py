from typing import Dict, Any, List, Optional
from backend.core.database import db

class InventoryRepository:
    def __init__(self):
        self.collection = db["inventory"]

    async def create_inventory(self, inventory_data: Dict[str, Any]) -> str:
        result = await self.collection.insert_one(inventory_data)
        return str(result.inserted_id)

    async def get_inventory_by_id(self, inventory_id: str) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one({"inventory_id": inventory_id})

    async def get_inventory_by_product_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one({"product_id": product_id})

    async def update_inventory(self, inventory_id: str, update_data: Dict[str, Any]) -> bool:
        result = await self.collection.update_one({"inventory_id": inventory_id}, {"$set": update_data})
        return result.modified_count > 0

    async def update_stock(self, product_id: str, quantity_change: int) -> bool:
        """Update inventory stock relative to its current value (e.g. -1 or +1)"""
        result = await self.collection.update_one(
            {"product_id": product_id}, 
            {"$inc": {"quantity": quantity_change}}
        )
        return result.modified_count > 0

    async def delete_inventory(self, inventory_id: str) -> bool:
        result = await self.collection.delete_one({"inventory_id": inventory_id})
        return result.deleted_count > 0

    async def get_all_inventory(self, limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        cursor = self.collection.find().skip(skip).limit(limit)
        return await cursor.to_list(length=limit)
