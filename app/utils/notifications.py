"""Utilitário para gerenciar notificações no sistema."""

import logging
from typing import Optional
from supabase import AsyncClient

from app.models import Tables

logger = logging.getLogger(__name__)


async def create_notification(
    db: AsyncClient,
    user_id: str,
    title: str,
    message: str,
    type: str = "general",
    link: Optional[str] = None,
) -> Optional[dict]:
    """Cria uma notificação discreta no banco de dados para um usuário específico."""
    if not user_id:
        return None
    try:
        data = {
            "user_id": user_id,
            "title": title,
            "message": message,
            "type": type,
            "link": link or "",
            "is_read": False,
        }
        res = await db.table(Tables.NOTIFICATIONS).insert(data).execute()
        if res.data:
            return res.data[0]
    except Exception as exc:
        logger.warning("Erro ao criar notificação para o usuário %s: %s", user_id, exc)
    return None
