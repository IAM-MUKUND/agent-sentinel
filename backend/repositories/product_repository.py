from typing import Dict, Any, List, Optional
from backend.core.database import db

class ProductRepository:
    def __init__(self):
        self.collection = db["products"]

    async def create_product(self, product_data: Dict[str, Any]) -> str:
        result = await self.collection.insert_one(product_data)
        return str(result.inserted_id)

    async def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one({"product_id": product_id})

    async def update_product(self, product_id: str, update_data: Dict[str, Any]) -> bool:
        result = await self.collection.update_one({"product_id": product_id}, {"$set": update_data})
        return result.modified_count > 0

    async def delete_product(self, product_id: str) -> bool:
        result = await self.collection.delete_one({"product_id": product_id})
        return result.deleted_count > 0

    async def get_all_products(self, limit: int = 100, skip: int = 0) -> List[Dict[str, Any]]:
        cursor = self.collection.find().skip(skip).limit(limit)
        return await cursor.to_list(length=limit)
