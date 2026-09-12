"""Rotas de notificações do usuário."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import AsyncClient

from app.database import get_db
from app.models import Tables
from app.utils.deps import get_current_user

router = APIRouter(prefix="/notifications", tags=["Notificações"])


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    title: Optional[str] = ""
    message: str
    type: Optional[str] = "general"
    link: Optional[str] = ""
    is_read: bool = False
    created_at: Optional[str] = None


@router.get("", response_model=List[NotificationResponse])
async def list_user_notifications(
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Retorna as notificações não lidas e recentes do usuário logado."""
    try:
        res = (
            await db.table(Tables.NOTIFICATIONS)
            .select("*")
            .eq("user_id", user["id"])
            .eq("is_read", False)
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        )
        return res.data or []
    except Exception:
        return []


@router.post("/{notification_id}/read")
async def mark_notification_as_read(
    notification_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Marca uma notificação como lida."""
    try:
        await (
            db.table(Tables.NOTIFICATIONS)
            .update({"is_read": True})
            .eq("id", notification_id)
            .eq("user_id", user["id"])
            .execute()
        )
        return {"status": "ok", "id": notification_id}
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Erro ao marcar como lida.") from exc


@router.post("/read-all")
async def mark_all_notifications_as_read(
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Marca todas as notificações do usuário como lidas."""
    try:
        await (
            db.table(Tables.NOTIFICATIONS)
            .update({"is_read": True})
            .eq("user_id", user["id"])
            .eq("is_read", False)
            .execute()
        )
        return {"status": "ok"}
    except Exception:
        return {"status": "ok"}
