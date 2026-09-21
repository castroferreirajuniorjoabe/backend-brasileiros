import asyncio
from app.database import get_service_db
from app.models import Tables

async def main():
    db = await get_service_db()
    for table in [Tables.CONSULATE_POSTS, Tables.REGULATION_POSTS, Tables.CHARITY_ADS, Tables.MOVING_SALES]:
        try:
            res = await db.table(table).select("*").eq("id", "474c38aa-f509-45f5-8bac-0914e20d272e").execute()
            if res.data:
                print(f"Found in {table}:", res.data)
                return
        except Exception as e:
            pass
    print("Not found anywhere")

asyncio.run(main())
