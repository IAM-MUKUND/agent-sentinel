import os
from pymongo import AsyncMongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("MONGO_DB_NAME", "agent_sentinel")

# Initialize the async client natively using PyMongo 4.5+
client = AsyncMongoClient(MONGO_URI)
db = client[DATABASE_NAME]

async def get_db():
    """Dependency injection to get the database instance."""
    return db
