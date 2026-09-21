import asyncio
from app.database import get_service_db
from app.models import Tables

async def main():
    db = await get_service_db()
    res = await db.table("ads").select("id").eq("category", "gastronomia").limit(1).execute()
    print("Test insert result:", res.data)

asyncio.run(main())
