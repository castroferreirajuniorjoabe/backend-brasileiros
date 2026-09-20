import asyncio, os, sys
sys.path.append(os.getcwd())
from app.database import get_service_db

async def main():
    db = await get_service_db()
    res = await db.table('consulate_posts').select('*').execute()
    print(res.data)

asyncio.run(main())
