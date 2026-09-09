"""Dependências FastAPI: autenticação JWT, usuário atual, admin e verificações."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import AsyncClient

from app.database import get_db
from app.models import Tables
from app.utils.security import decode_access_token

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncClient = Depends(get_db),
) -> dict:
    """Exige token JWT válido e retorna o usuário (não bloqueado)."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticação não informado.",
        )
    payload = decode_access_token(credentials.credentials)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
        )
    result = (
        await db.table(Tables.USERS)
        .select("*")
        .eq("id", payload["sub"])
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=401, detail="Usuário não encontrado.")
    user = result.data[0]
    if user.get("is_blocked"):
        raise HTTPException(status_code=403, detail="Usuário bloqueado pelo administrador.")
    return user


async def get_current_verified_user(user: dict = Depends(get_current_user)) -> dict:
    """Exige email E telefone verificados (necessário para anunciar)."""
    if not user.get("email_verified") or not user.get("phone_verified"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Para anunciar, é preciso ter o email e o telefone verificados.",
        )
    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncClient = Depends(get_db),
) -> dict | None:
    """Retorna o usuário se autenticado; None para visitantes (navegação livre)."""
    if credentials is None:
        return None
    payload = decode_access_token(credentials.credentials)
    if not payload or not payload.get("sub"):
        return None
    result = (
        await db.table(Tables.USERS)
        .select("*")
        .eq("id", payload["sub"])
        .limit(1)
        .execute()
    )
    if not result.data:
        return None
    user = result.data[0]
    return None if user.get("is_blocked") else user


async def get_admin_user(
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
) -> dict:
    """Exige que o usuário seja admin (tabela `admins` ou flag `is_admin`)."""
    if user.get("is_admin"):
        return user
    result = (
        await db.table(Tables.ADMINS)
        .select("user_id")
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores.",
        )
    return user
