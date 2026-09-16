import asyncio
import httpx
from jose import jwt
from datetime import datetime, timedelta

SECRET_KEY = "troque-por-uma-chave-secreta-bem-grande-e-aleatoria"

def create_admin_token(user_id):
    expire = datetime.utcnow() + timedelta(minutes=60)
    to_encode = {"sub": user_id, "is_admin": True, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")

async def run():
    token = create_admin_token("29cb6194-21a5-4507-976f-3b23fbd7ef07")
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        # Create fake post
        res_create = await client.post("http://localhost:8001/regulation/posts", json={
            "title": "Admin Audit Test",
            "content": "Testando as funcoes do admin",
            "category": "dicas"
        }, headers=headers)
        
        post = res_create.json()
        post_id = post.get("id")
        print("Criado post:", post_id)
        
        # Test 1: Admin Approve
        res_approve = await client.put(f"http://localhost:8001/admin/tables/regulation-posts/{post_id}", json={
            "status": "approved"
        }, headers=headers)
        print("Approve:", res_approve.status_code, res_approve.json().get("status"))
        
        # Test 2: Admin Delete
        res_delete = await client.delete(f"http://localhost:8001/admin/tables/regulation-posts/{post_id}", headers=headers)
        print("Delete:", res_delete.status_code)
        
asyncio.run(run())
