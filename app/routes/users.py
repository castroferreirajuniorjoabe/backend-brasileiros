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


@router.get("/me/notifications")
async def get_user_notifications(
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Retorna notificações discretas e recentes para o usuário logado."""
    notifications = []
    
    try:
        # 1. Anúncios próprios aprovados recentemente ou com destaque ativo
        ads_res = (
            await db.table(Tables.ADS)
            .select("id, name, status, is_highlighted, created_at")
            .eq("user_id", user["id"])
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        for ad in ads_res.data or []:
            if ad.get("status") == "approved":
                notifications.append({
                    "id": f"ad_appr_{ad['id']}",
                    "type": "ad_approved",
                    "icon": "check",
                    "title": "Anúncio Aprovado",
                    "message": f"Seu anúncio \"{ad['name']}\" está visível na plataforma.",
                    "created_at": ad.get("created_at"),
                    "link": f"/anuncio/{ad['id']}",
                })
            if ad.get("is_highlighted"):
                notifications.append({
                    "id": f"ad_high_{ad['id']}",
                    "type": "highlight_active",
                    "icon": "sparkles",
                    "title": "Destaque Ativo",
                    "message": f"Seu anúncio \"{ad['name']}\" está em destaque.",
                    "created_at": ad.get("created_at"),
                    "link": f"/anuncio/{ad['id']}",
                })

        # 2. Avaliações recentes recebidas nos anúncios do usuário
        my_ad_ids = [ad["id"] for ad in (ads_res.data or [])]
        if my_ad_ids:
            rev_res = (
                await db.table(Tables.REVIEWS)
                .select("id, ad_id, rating, created_at, ads(name)")
                .in_("ad_id", my_ad_ids)
                .order("created_at", desc=True)
                .limit(5)
                .execute()
            )
            for rev in rev_res.data or []:
                ad_name = (rev.get("ads") or {}).get("name") or "seu anúncio"
                notifications.append({
                    "id": f"rev_{rev['id']}",
                    "type": "new_review",
                    "icon": "star",
                    "title": "Nova Avaliação",
                    "message": f"Nova avaliação de {rev['rating']}★ recebida em \"{ad_name}\".",
                    "created_at": rev.get("created_at"),
                    "link": f"/anuncio/{rev['ad_id']}",
                })

        # 3. Comentários recentes
        comm_res = (
            await db.table(Tables.ITEM_COMMENTS)
            .select("id, target_id, target_type, message, created_at")
            .order("created_at", desc=True)
            .limit(3)
            .execute()
        )
        for comm in comm_res.data or []:
            notifications.append({
                "id": f"comm_{comm['id']}",
                "type": "new_comment",
                "icon": "message",
                "title": "Nova Mensagem",
                "message": f"Novo comentário na comunidade: {comm['message'][:35]}...",
                "created_at": comm.get("created_at"),
                "link": f"/{comm.get('target_type', 'passeios')}",
            })
    except Exception:
        pass

    # Ordenar por mais recentes
    notifications.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    return notifications[:10]

