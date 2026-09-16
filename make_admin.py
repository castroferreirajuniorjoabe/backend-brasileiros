import asyncio
import sys
sys.path.insert(0, '.')
from app.database import get_service_db
from app.models import Tables

async def make_admin():
    db = await get_service_db()
    # Meu usuario diagnostico
    user_id = "29cb6194-21a5-4507-976f-3b23fbd7ef07"
    
    # Update is_admin
    res = await db.table(Tables.USERS).update({"is_admin": True}).eq("id", user_id).execute()
    print("User updated:", res.data)

asyncio.run(make_admin())
