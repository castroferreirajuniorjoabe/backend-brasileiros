"""Ativação de destaque (carrossel) de anúncios — pago ou gratuito."""

from datetime import timedelta

from supabase import AsyncClient

from app.models import HIGHLIGHT_DURATION_DAYS, Tables
from app.utils.security import utcnow


async def activate_highlight(
    db: AsyncClient, ad_id: str, days: int = HIGHLIGHT_DURATION_DAYS
) -> dict:
    """Ativa (ou estende) o destaque de um anúncio por N dias.

    Se o anúncio já está destacado, estende a partir do fim atual;
    caso contrário, a partir de agora.
    """
    try:
        result = (
            await db.table(Tables.ADS)
            .select("*")
            .eq("id", ad_id)
            .limit(1)
            .execute()
        )
    except Exception:
        result = (
            await db.table(Tables.ADS)
            .select("id")
            .eq("id", ad_id)
            .limit(1)
            .execute()
        )
    if not result.data:
        raise ValueError("Anúncio não encontrado.")

    ad = result.data[0]
    now = utcnow()
    base = now
    current_until = ad.get("highlight_expires") or ad.get("highlight_until")
    if current_until:
        try:
            from datetime import datetime

            until = datetime.fromisoformat(str(current_until).replace("Z", "+00:00"))
            if until > now:
                base = until
        except Exception:
            pass

    new_until = (base + timedelta(days=days)).isoformat()
    try:
        update = (
            await db.table(Tables.ADS)
            .update({
                "is_highlighted": True,
                "highlight_expires": new_until,
                "highlight_until": new_until,
                "highlighted_until": new_until,
            })
            .eq("id", ad_id)
            .execute()
        )
    except Exception:
        try:
            update = (
                await db.table(Tables.ADS)
                .update({"is_highlighted": True, "highlight_until": new_until})
                .eq("id", ad_id)
                .execute()
            )
        except Exception:
            update = (
                await db.table(Tables.ADS)
                .update({"is_highlighted": True})
                .eq("id", ad_id)
                .execute()
            )
    
    updated_ad = update.data[0] if update.data else ad
    # Notifica o usuário que o anúncio está em destaque
    user_id = updated_ad.get("user_id")
    if user_id:
        from app.utils.notifications import create_notification
        ad_title = updated_ad.get("name") or "seu anúncio"
        await create_notification(
            db=db,
            user_id=user_id,
            title="Destaque Ativado!",
            message=f"Seu anúncio \"{ad_title}\" agora está em destaque no topo.",
            type="highlight_active",
            link=f"/anuncio/{ad_id}",
        )

    return updated_ad

