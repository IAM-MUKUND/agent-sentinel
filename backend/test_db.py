import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

async def check():
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["agentsentinel"]
    tickets = await db.support_tickets.find().to_list(10)
    for t in tickets:
        print(f"Ticket: {t.get('ticket_id')}, OrderID: {t.get('order_id')}, Reason: {t.get('reason')}")

asyncio.run(check())
