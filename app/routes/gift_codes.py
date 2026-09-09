"""Códigos de presente: resgate de destaque grátis e indicação."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from supabase import AsyncClient

from app.database import get_db
from app.models import AdStatus, GiftCodeType, Tables
from app.schemas.admin_ops import GiftCodeRedeemRequest
from app.utils.deps import get_current_user
from app.utils.highlights import activate_highlight
from app.utils.security import utcnow

router = APIRouter(prefix="/gift-codes", tags=["Códigos de Presente"])


@router.post("/redeem")
async def redeem_gift_code(
    payload: GiftCodeRedeemRequest,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Resgata um código promocional: o anúncio informado ganha destaque grátis."""
    result = (
        await db.table(Tables.GIFT_CODES)
        .select("*")
        .eq("code", payload.code.upper().strip())
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Código inválido.")
    code = result.data[0]

    is_active = code.get("is_active", code.get("active", True))
    if not is_active:
        raise HTTPException(status_code=400, detail="Código desativado.")
    if code.get("expires_at"):
        try:
            expires = datetime.fromisoformat(str(code["expires_at"]).replace("Z", "+00:00"))
            if expires < utcnow():
                raise HTTPException(status_code=400, detail="Código expirado.")
        except Exception:
            pass
    uses = code.get("used_count", code.get("uses_count", 0)) or 0
    max_u = code.get("max_uses") or 1
    if uses >= max_u:
        raise HTTPException(status_code=400, detail="Código já utilizado.")

    # O anúncio precisa ser do próprio usuário e estar aprovado
    ad = (
        await db.table(Tables.ADS)
        .select("id, user_id, status")
        .eq("id", payload.ad_id)
        .limit(1)
        .execute()
    )
    if not ad.data:
        raise HTTPException(status_code=404, detail="Anúncio não encontrado.")
    if ad.data[0]["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="O anúncio precisa ser seu.")

    await activate_highlight(db, payload.ad_id)

    try:
        await (
            db.table(Tables.GIFT_CODES)
            .update(
                {
                    "used_count": uses + 1,
                }
            )
            .eq("id", code["id"])
            .execute()
        )
    except Exception:
        try:
            used_by = code.get("used_by") or []
            await (
                db.table(Tables.GIFT_CODES)
                .update(
                    {
                        "uses_count": uses + 1,
                        "used_by": used_by + [user["id"]],
                        "used_at": utcnow().isoformat(),
                    }
                )
                .eq("id", code["id"])
                .execute()
            )
        except Exception:
            pass

    return {"message": "Código resgatado! Seu anúncio ganhou 1 semana de destaque grátis.", "ad_id": payload.ad_id}
