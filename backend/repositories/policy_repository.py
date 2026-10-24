from typing import Optional, Dict, Any, List
from pymongo.database import AsyncDatabase
from bson.objectid import ObjectId

class PolicyRepository:
    """
    Repository for managing AgentWAF governance policies in MongoDB.
    """
    def __init__(self, db: AsyncDatabase):
        self.collection = db["policies"]

    async def create_policy(self, policy_data: Dict[str, Any]) -> str:
        """Insert a new policy document."""
        result = await self.collection.insert_one(policy_data)
        return str(result.inserted_id)

    async def get_policy_by_id(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a policy by its ID."""
        try:
            document = await self.collection.find_one({"_id": ObjectId(policy_id)})
            if document:
                document["_id"] = str(document["_id"])
            return document
        except Exception:
            return None

    async def get_policies_for_agent(self, agent_id: str) -> List[Dict[str, Any]]:
        """Retrieve all active policies targeting a specific agent."""
        cursor = self.collection.find({"agent_id": agent_id, "is_active": True})
        policies = []
        async for document in cursor:
            document["_id"] = str(document["_id"])
            policies.append(document)
        return policies
    
    async def update_policy(self, policy_id: str, update_data: Dict[str, Any]) -> bool:
        """Update an existing policy."""
        result = await self.collection.update_one(
            {"_id": ObjectId(policy_id)}, 
            {"$set": update_data}
        )
        return result.modified_count > 0
