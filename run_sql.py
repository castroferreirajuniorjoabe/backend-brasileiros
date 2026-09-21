import asyncio
import os
import asyncpg
from app.config import settings

async def main():
    # If DATABASE_URL is in settings, we can use asyncpg
    if not hasattr(settings, 'DATABASE_URL') or not settings.DATABASE_URL:
        print("DATABASE_URL not found. Need to find another way.")
        return
        
    conn = await asyncpg.connect(settings.DATABASE_URL)
    
    with open("sql/create_influencers_tables.sql", "r") as f:
        sql = f.read()
        await conn.execute(sql)
        print("Influencers tables created.")
        
    with open("sql/create_churches_tables.sql", "r") as f:
        sql = f.read()
        await conn.execute(sql)
        print("Churches tables created.")
        
    await conn.close()

asyncio.run(main())
