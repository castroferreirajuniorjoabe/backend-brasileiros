import asyncio
import httpx
import json

async def run():
    token = json.load(open('../token.json'))['access_token']
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        # Create fake regulation post
        res_create = await client.post("https://brasileiros-api.onrender.com/regulation/posts", json={
            "title": "Admin Audit Test - Regulation",
            "content": "Testando as funcoes do admin",
            "category": "dicas"
        }, headers=headers)
        
        post = res_create.json()
        post_id = post.get("id")
        print("Criado regulation post:", post_id)
        if not post_id:
            print("Failed to create post:", res_create.text)
            return
            
        # Test 1: Admin Approve
        res_approve = await client.put(f"https://brasileiros-api.onrender.com/admin/tables/regulation-posts/{post_id}", json={
            "status": "approved"
        }, headers=headers)
        print("Approve Regulation Post:", res_approve.status_code, res_approve.json().get("status") if res_approve.status_code == 200 else res_approve.text)
        
        # Test 2: Admin Delete
        res_delete = await client.delete(f"https://brasileiros-api.onrender.com/admin/tables/regulation-posts/{post_id}", headers=headers)
        print("Delete Regulation Post (Admin):", res_delete.status_code)

asyncio.run(run())
