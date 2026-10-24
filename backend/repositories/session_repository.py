from typing import Optional, Dict, Any
from pymongo.database import AsyncDatabase
import datetime

class SessionRepository:
    """
    Repository for tracking stateful agent sessions (e.g. for Sequence Validation rules).
    """
    def __init__(self, db: AsyncDatabase):
        self.collection = db["sessions"]

    async def create_session(self, session_id: str, agent_id: str) -> str:
        """Initialize a new workflow session for an agent."""
        session_data = {
            "session_id": session_id,
            "agent_id": agent_id,
            "state": {},
            "history": [],
            "created_at": datetime.datetime.now(datetime.timezone.utc),
            "updated_at": datetime.datetime.now(datetime.timezone.utc)
        }
        result = await self.collection.insert_one(session_data)
        return str(result.inserted_id)

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a session by its custom session_id."""
        document = await self.collection.find_one({"session_id": session_id})
        if document:
             document["_id"] = str(document["_id"])
        return document

    async def update_session_state(self, session_id: str, new_state: Dict[str, Any], action: str) -> bool:
        """Update session state and append an action to the history."""
        result = await self.collection.update_one(
            {"session_id": session_id},
            {
                "$set": {"state": new_state, "updated_at": datetime.datetime.now(datetime.timezone.utc)},
                "$push": {"history": action}
            }
        )
        return result.modified_count > 0
