import asyncio
import sys
from app.database import get_service_db
from app.models import Tables
from app.utils.security import hash_password

async def fix_admin():
    try:
        db = await get_service_db()
        email = "joabes773@gmail.com"
        password = "71RoseIsaellaJunioor#"
        name = "Joabes Admin"
        phone = "+33614326493"

        # 1. Delete existing user if any
        existing = await db.table(Tables.USERS).select("id").eq("email", email).execute()
        if existing.data:
            uid = existing.data[0]["id"]
            # remove from admins first if exists
            await db.table(Tables.ADMINS).delete().eq("user_id", uid).execute()
            await db.table(Tables.USERS).delete().eq("id", uid).execute()
            print(f"🗑️ Usuário antigo removido: {uid}")

        # 2. Create new user
        hashed = hash_password(password)
        new_user = {
            "name": name,
            "email": email,
            "phone": phone,
            "city": "Paris",
            "password_hash": hashed,
            "email_verified": True,
            "phone_verified": True,
            "is_admin": True,
            "is_blocked": False,
        }
        res = await db.table(Tables.USERS).insert(new_user).execute()
        user_id = res.data[0]["id"]
        print(f"✅ Usuário criado: {user_id}")

        # 3. Insert into admins
        await db.table(Tables.ADMINS).upsert({"user_id": user_id, "role": "admin"}).execute()
        print("✅ Admin inserido na tabela admins")
        
        # 4. Verify
        verify = await db.table(Tables.USERS).select("id, email, is_admin, email_verified, phone_verified").eq("id", user_id).execute()
        print(f"🔍 Verificação final na tabela users: {verify.data}")
        
        admin_verify = await db.table(Tables.ADMINS).select("*").eq("user_id", user_id).execute()
        print(f"🔍 Verificação final na tabela admins: {admin_verify.data}")

    except Exception as e:
        print(f"❌ Erro ao executar fix_admin: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(fix_admin())
