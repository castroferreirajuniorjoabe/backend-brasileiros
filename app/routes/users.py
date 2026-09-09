from fastapi import APIRouter, Depends, File, UploadFile
from supabase import AsyncClient

from app.database import get_db
from app.models import Tables
from app.schemas.auth import UserResponse, UserUpdateRequest
from app.routes.auth import _user_response
from app.utils.deps import get_current_user
from app.utils.security import hash_password
from app.utils import image as image_utils

router = APIRouter(prefix="/users", tags=["Usuários"])


@router.get("/me", response_model=UserResponse)
async def get_profile(user: dict = Depends(get_current_user)):
    """Retorna o perfil do usuário autenticado."""
    return _user_response(user)


@router.post("/me/avatar", response_model=UserResponse)
async def upload_user_avatar(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Faz upload da foto de perfil do usuário (opcional)."""
    photo_url = await image_utils.upload_image(file, folder="avatars")
    result = (
        await db.table(Tables.USERS)
        .update({"avatar_url": photo_url})
        .eq("id", user["id"])
        .execute()
    )
    user_data = result.data[0] if result.data else {**user, "avatar_url": photo_url}
    return _user_response(user_data)


@router.put("/me", response_model=UserResponse)
async def update_profile(
    payload: UserUpdateRequest,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Edita o perfil. Trocar telefone exige nova verificação por SMS."""
    updates: dict = {}
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.city is not None:
        updates["city"] = payload.city
    if payload.avatar_url is not None:
        updates["avatar_url"] = payload.avatar_url
    if payload.password is not None:
        updates["password_hash"] = hash_password(payload.password)
    if payload.phone is not None and payload.phone != user["phone"]:
        from app.utils import sms as sms_utils
        from app.utils.security import generate_sms_code, utcnow
        from datetime import timedelta

        code = generate_sms_code()
        updates.update(
            {
                "phone": payload.phone,
                "phone_verified": False,
                "phone_verification_code": code,
                "phone_code_expires_at": (utcnow() + timedelta(minutes=10)).isoformat(),
            }
        )
        await sms_utils.send_phone_verification_code(payload.phone, code)

    if not updates:
        return _user_response(user)

    result = (
        await db.table(Tables.USERS)
        .update(updates)
        .eq("id", user["id"])
        .execute()
    )
    return _user_response(result.data[0])
