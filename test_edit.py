import asyncio
from app.database import get_service_db
from app.models import Tables

async def main():
    db = await get_service_db()
    res = await db.table(Tables.CONSULATE_POSTS).select("*").limit(1).execute()
    if not res.data:
        print("No posts found.")
        return
    post = res.data[0]
    print(f"Found post: {post['id']}")
    
    update_res = await db.table(Tables.CONSULATE_POSTS).update({"title": post["title"] + " Editado"}).eq("id", post["id"]).execute()
    print("Update result:", update_res.data)

asyncio.run(main())
