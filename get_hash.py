from app.utils.security import hash_password

password = "71RoseIsaellaJunioor#"
hashed = hash_password(password)
print(f"PASSWORD_HASH: {hashed}")
