from typing import Dict, Any, List, Optional
from backend.core.database import db

class WafLogRepository:
    def __init__(self):
        self.collection = db["waf_logs"]

    async def create_log(self, log_data: Dict[str, Any]) -> str:
        result = await self.collection.insert_one(log_data)
        return str(result.inserted_id)

    async def get_log_by_id(self, log_id: str) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one({"log_id": log_id})

    async def get_logs_by_ticket(self, ticket_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        cursor = self.collection.find({"ticket_id": ticket_id}).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)
        
    async def get_logs_by_decision(self, decision: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch logs based on decision: ALLOW, DENY, HITL"""
        cursor = self.collection.find({"decision": decision}).sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_recent_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        cursor = self.collection.find().sort("timestamp", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def delete_log(self, log_id: str) -> bool:
        result = await self.collection.delete_one({"log_id": log_id})
        return result.deleted_count > 0
