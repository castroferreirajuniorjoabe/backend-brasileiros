import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from app.database import get_service_db
from app.models import Tables
from app.utils.security import hash_password

async def main():
    db = await get_service_db()
    
    users = [
        {
            "name": "Consulado-Geral do Brasil em Paris",
            "email": "consulado.paris@brasileirosfranca.app",
            "phone": "+33145616300",
            "city": "Paris",
            "password_hash": hash_password("consulado123"),
            "email_verified": True,
            "phone_verified": True,
            "is_admin": False,
            "user_type": "consulate"
        },
        {
            "name": "Consulado-Geral do Brasil em Marseille",
            "email": "consulado.marseille@brasileirosfranca.app",
            "phone": "+33486838850",
            "city": "Marseille",
            "password_hash": hash_password("consulado123"),
            "email_verified": True,
            "phone_verified": True,
            "is_admin": False,
            "user_type": "consulate"
        }
    ]
    
    for user in users:
        # Check if exists
        existing = await db.table(Tables.USERS).select("id").eq("email", user["email"]).execute()
        if existing.data:
            print(f"User {user['email']} already exists. Updating user_type...")
            await db.table(Tables.USERS).update({"user_type": "consulate"}).eq("email", user["email"]).execute()
        else:
            print(f"Creating {user['email']}...")
            await db.table(Tables.USERS).insert(user).execute()

    print("Contas de consulado criadas/atualizadas com sucesso!")

if __name__ == "__main__":
    asyncio.run(main())
