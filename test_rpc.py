import asyncio
from app.database import get_service_db

async def main():
    db = await get_service_db()
    try:
        res = await db.rpc("exec_sql", {"sql": "SELECT 1"}).execute()
        print("RPC Result:", res.data)
    except Exception as e:
        print("RPC Error:", str(e))

asyncio.run(main())
