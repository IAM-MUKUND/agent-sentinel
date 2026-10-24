from typing import Dict, Any, List
from pymongo.database import AsyncDatabase
from bson.objectid import ObjectId
import datetime

class AlertRepository:
    """
    Repository for managing high-priority alerts triggered by WAF policy violations.
    """
    def __init__(self, db: AsyncDatabase):
        self.collection = db["alerts"]

    async def create_alert(self, agent_id: str, severity: str, message: str, context: Dict[str, Any]) -> str:
        """Create a new alert."""
        alert_data = {
            "agent_id": agent_id,
            "severity": severity,  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
            "message": message,
            "context": context,
            "status": "UNRESOLVED",
            "timestamp": datetime.datetime.now(datetime.timezone.utc)
        }
        result = await self.collection.insert_one(alert_data)
        return str(result.inserted_id)

    async def get_unresolved_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch active, unresolved alerts."""
        cursor = self.collection.find({"status": "UNRESOLVED"}).sort("timestamp", -1).limit(limit)
        alerts = []
        async for document in cursor:
            document["_id"] = str(document["_id"])
            alerts.append(document)
        return alerts

    async def resolve_alert(self, alert_id: str, resolution_notes: str) -> bool:
        """Mark an alert as resolved."""
        result = await self.collection.update_one(
            {"_id": ObjectId(alert_id)},
            {"$set": {"status": "RESOLVED", "resolution_notes": resolution_notes}}
        )
        return result.modified_count > 0
