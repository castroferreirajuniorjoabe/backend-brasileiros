"""Bate-papo & Comentários específicos por anúncio para Passeios/Turismo e Espaço Pet."""

import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from supabase import AsyncClient

from app.database import get_db
from app.models import Tables
from app.schemas.community import (
    ItemCommentCreateRequest,
    ItemCommentListResponse,
    ItemCommentResponse,
)
from app.utils.deps import get_current_user, get_optional_user
from app.utils.security import utcnow

router = APIRouter(prefix="/item-comments", tags=["Bate-papo de Anúncios"])

CHAT_CATEGORY_PREFIX = "chat:"


@router.get("/{target_type}/{target_id}", response_model=ItemCommentListResponse)
async def list_comments(
    target_type: str,
    target_id: str,
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Lista as mensagens do bate-papo de um anúncio específico de turismo ou pet."""
    if target_type not in ["tourism", "pet", "ad"]:
        target_type = "tourism"

    # Tentativa 1: Tabela dedicada ITEM_COMMENTS
    try:
        res = (
            await db.table(Tables.ITEM_COMMENTS)
            .select("*, users(name)")
            .eq("target_type", target_type)
            .eq("target_id", target_id)
            .order("created_at", desc=False)
            .execute()
        )
        if res.data is not None:
            items = []
            for c in res.data:
                u_name = (c.pop("users", None) or {}).get("name") or c.get("user_name") or "Brasileiro(a)"
                items.append(
                    ItemCommentResponse(
                        id=str(c["id"]),
                        target_id=str(c["target_id"]),
                        target_type=str(c.get("target_type") or target_type),
                        user_id=str(c.get("user_id", "")),
                        user_name=u_name,
                        message=c["message"],
                        created_at=str(c.get("created_at", "")),
                    )
                )
            return ItemCommentListResponse(
                target_id=target_id,
                target_type=target_type,
                total=len(items),
                items=items,
            )
    except Exception:
        pass

    # Tentativa 2: Persistência robusta no banco usando tabela GROUPS com tag CHAT_CATEGORY_PREFIX
    try:
        chat_cat = f"{CHAT_CATEGORY_PREFIX}{target_type}:{target_id}"
        res = (
            await db.table(Tables.GROUPS)
            .select("*, users:created_by(name)")
            .eq("category", chat_cat)
            .order("created_at", desc=False)
            .execute()
        )
        items = []
        for g in res.data or []:
            u_name = (g.pop("users", None) or {}).get("name") or g.get("name") or "Brasileiro(a)"
            items.append(
                ItemCommentResponse(
                    id=str(g["id"]),
                    target_id=target_id,
                    target_type=target_type,
                    user_id=str(g.get("created_by", "")),
                    user_name=u_name,
                    message=g.get("description", ""),
                    created_at=str(g.get("created_at", "")),
                )
            )
        return ItemCommentListResponse(
            target_id=target_id,
            target_type=target_type,
            total=len(items),
            items=items,
        )
    except Exception:
        pass

    return ItemCommentListResponse(
        target_id=target_id,
        target_type=target_type,
        total=0,
        items=[],
    )


@router.post("/{target_type}/{target_id}", response_model=ItemCommentResponse, status_code=201)
async def create_comment(
    target_type: str,
    target_id: str,
    payload: ItemCommentCreateRequest,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Envia uma nova mensagem no bate-papo exclusivo daquele anúncio de passeio ou pet."""
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="A mensagem não pode estar vazia.")

    msg = payload.message.strip()
    u_name = user.get("name") or "Brasileiro(a)"

    # Tentativa 1: Inserir na tabela ITEM_COMMENTS se existir
    try:
        record = {
            "target_type": target_type,
            "target_id": target_id,
            "user_id": user["id"],
            "user_name": u_name,
            "message": msg,
        }
        res = await db.table(Tables.ITEM_COMMENTS).insert(record).execute()
        if res.data:
            created = res.data[0]
            return ItemCommentResponse(
                id=str(created["id"]),
                target_id=str(created.get("target_id") or target_id),
                target_type=str(created.get("target_type") or target_type),
                user_id=str(created["user_id"]),
                user_name=u_name,
                message=msg,
                created_at=str(created.get("created_at") or utcnow().isoformat()),
            )
    except Exception:
        pass

    # Tentativa 2: Persistência garantida na tabela GROUPS
    try:
        chat_cat = f"{CHAT_CATEGORY_PREFIX}{target_type}:{target_id}"
        group_msg_record = {
            "name": u_name,
            "description": msg,
            "category": chat_cat,
            "city": "França",
            "platform": "whatsapp",
            "invite_link": f"chat://{target_type}/{target_id}",
            "is_approved": True,
            "is_active": True,
            "created_by": user["id"],
        }
        res = await db.table(Tables.GROUPS).insert(group_msg_record).execute()
        if res.data:
            created = res.data[0]
            return ItemCommentResponse(
                id=str(created["id"]),
                target_id=target_id,
                target_type=target_type,
                user_id=str(created["created_by"]),
                user_name=u_name,
                message=msg,
                created_at=str(created.get("created_at") or utcnow().isoformat()),
            )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro ao enviar mensagem no bate-papo: {str(e)}"
        )

    raise HTTPException(status_code=500, detail="Não foi possível salvar sua mensagem.")


@router.delete("/{comment_id}", status_code=204)
async def delete_comment(
    comment_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Apaga mensagem do bate-papo (autor da mensagem ou administrador)."""
    # Tenta na tabela ITEM_COMMENTS
    try:
        res = await db.table(Tables.ITEM_COMMENTS).select("user_id").eq("id", comment_id).limit(1).execute()
        if res.data:
            if res.data[0]["user_id"] != user["id"] and not user.get("is_admin"):
                raise HTTPException(status_code=403, detail="Sem permissão para remover esta mensagem.")
            await db.table(Tables.ITEM_COMMENTS).delete().eq("id", comment_id).execute()
            return None
    except HTTPException:
        raise
    except Exception:
        pass

    # Tenta na tabela GROUPS
    try:
        res_g = await db.table(Tables.GROUPS).select("created_by").eq("id", comment_id).limit(1).execute()
        if res_g.data:
            if res_g.data[0]["created_by"] != user["id"] and not user.get("is_admin"):
                raise HTTPException(status_code=403, detail="Sem permissão para remover esta mensagem.")
            await db.table(Tables.GROUPS).delete().eq("id", comment_id).execute()
            return None
    except HTTPException:
        raise
    except Exception:
        pass

    raise HTTPException(status_code=404, detail="Mensagem não encontrada.")
