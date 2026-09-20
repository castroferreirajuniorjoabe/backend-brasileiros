import asyncio, os, sys
sys.path.append(os.getcwd())
from app.database import get_service_db
from app.utils.security import verify_password

async def main():
    db = await get_service_db()
    res = await db.table('users').select('*').eq('email', 'consulado.paris@brasileirosfranca.app').execute()
    if res.data:
        user = res.data[0]
        print(user['email'])
        print('Password matches?', verify_password('consulado123', user.get('password_hash')))
    else:
        print('User not found')

asyncio.run(main())
