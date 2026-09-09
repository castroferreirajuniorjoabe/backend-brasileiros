"""Segurança: hash de senha (bcrypt), JWT e geração de códigos/tokens."""

import secrets
import string
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings


# ---------- Senha ----------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


# ---------- JWT ----------

def create_access_token(user_id: str, is_admin: bool = False) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": user_id,
        "is_admin": is_admin,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        return None


# ---------- Tokens e códigos ----------

def generate_verification_token() -> str:
    """Token URL-safe para verificação de email."""
    return secrets.token_urlsafe(32)


def generate_sms_code() -> str:
    """Código numérico de 6 dígitos para verificação de telefone."""
    return "".join(secrets.choice(string.digits) for _ in range(6))


def generate_gift_code(prefix: str = "BNF") -> str:
    """Código promocional legível, ex.: BNF-8F3K-2Q9Z."""
    alphabet = string.ascii_uppercase + string.digits
    part = lambda: "".join(secrets.choice(alphabet) for _ in range(4))
    return f"{prefix}-{part()}-{part()}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
