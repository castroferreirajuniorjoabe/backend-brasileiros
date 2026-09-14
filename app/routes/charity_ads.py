"""Anúncios de caridade: gratuitos, até 2 imagens, 1 por semana por usuário."""

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from supabase import AsyncClient

from app.database import get_db
from app.models import ModerationStatus, Tables
from app.schemas.community import CharityAdResponse
from app.utils import image as image_utils
from app.utils.deps import get_current_user, get_optional_user
from app.utils.security import utcnow

router = APIRouter(prefix="/charity-ads", tags=["Anúncios de Caridade"])


def _format_charity_ad(ad: dict) -> dict:
    a = dict(ad)
    a["city"] = a.get("location") or a.get("city") or "França"
    a["badge"] = "CARIDADE"
    a["contact_phone"] = a.get("contact_phone") or ""
    return a


@router.post("", response_model=CharityAdResponse, status_code=201)
async def create_charity_ad(
    title: str = Form(...),
    description: str = Form(...),
    city: str = Form(...),
    contact_phone: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    image_2: Optional[UploadFile] = File(None),
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Cria anúncio de caridade (gratuito, até 2 imagens).
    Limite: 1 anúncio por semana por usuário."""
    # Administradores não possuem restrição de quantidade para testes e moderação
    if not user.get("is_admin"):
        week_ago = (utcnow() - timedelta(days=7)).isoformat()
        try:
            recent = (
                await db.table(Tables.CHARITY_ADS)
                .select("id", count="exact")
                .eq("user_id", user["id"])
                .gte("created_at", week_ago)
                .execute()
            )
            if (recent.count or 0) >= 1:
                raise HTTPException(
                    status_code=429,
                    detail="Você já publicou 1 anúncio de caridade nos últimos 7 dias. Aguarde para publicar outro ou exclua o anterior.",
                )
        except HTTPException:
            raise
        except Exception:
            pass

    final_phone = contact_phone or phone or ""
    if not final_phone:
        raise HTTPException(
            status_code=422,
            detail="Telefone de contato é obrigatório.",
        )

    image_url = (
        await image_utils.upload_image(image, folder="charity")
        if image and image.filename
        else None
    )
    image_url_2 = (
        await image_utils.upload_image(image_2, folder="charity")
        if image_2 and image_2.filename
        else None
    )

    record = {
        "user_id": user["id"],
        "type": "donation",
        "title": title,
        "description": description,
        "location": city,
        "contact_phone": final_phone,
        "image_url": image_url,
        "image_2_url": image_url_2,
        "status": ModerationStatus.APPROVED.value,  # Aprovado diretamente para visualização imediata
    }
    result = await db.table(Tables.CHARITY_ADS).insert(record).execute()

    return _format_charity_ad(result.data[0])


@router.get("", response_model=list[CharityAdResponse])
async def list_charity_ads(
    city: Optional[str] = Query(None),
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Lista anúncios de caridade aprovados, com selo CARIDADE (público). Apenas caridade/doações."""
    try:
        query = (
            db.table(Tables.CHARITY_ADS)
            .select("*")
            .eq("status", ModerationStatus.APPROVED.value)
            .neq("type", "tourism")
            .neq("type", "pet")
            .neq("type", "job")
            .neq("type", "moving_sale")
            .not_.like("title", "[%]")
        )
        if city:
            query = query.or_(f"location.ilike.%{city}%,city.ilike.%{city}%")
        result = await query.order("created_at", desc=True).execute()
        
        # Filtro de segurança rigoroso em memória
        clean_items = []
        for a in result.data or []:
            ad_type = str(a.get("type") or "").lower()
            if ad_type in ["tourism", "pet", "job", "job_ad", "employment", "moving_sale", "moving"]:
                continue
            title = str(a.get("title") or "")
            desc = str(a.get("description") or "")
            # Se tiver prefixo de colchetes ou for remanescente de teste de emprego ou mudança
            if (title.startswith("[") and "]" in title) or "[meta_job]" in desc.lower() or "[emprego]" in title.lower() or "moving_meta:" in desc.lower() or "[mudança]" in title.lower() or "[mudanca]" in title.lower():
                continue
            clean_items.append(_format_charity_ad(a))
            
        return clean_items
    except Exception:
        # Fallback de segurança filtrando em memória
        try:
            res_all = await db.table(Tables.CHARITY_ADS).select("*").eq("status", ModerationStatus.APPROVED.value).order("created_at", desc=True).execute()
            filtered = []
            for a in res_all.data or []:
                ad_type = str(a.get("type") or "").lower()
                if ad_type in ["tourism", "pet", "job", "job_ad", "employment", "moving_sale", "moving"]:
                    continue
                t = str(a.get("title") or "")
                desc = str(a.get("description") or "")
                if (t.startswith("[") and "]" in t) or "[meta_job]" in desc.lower() or "[emprego]" in t.lower() or "moving_meta:" in desc.lower() or "[mudança]" in t.lower() or "[mudanca]" in t.lower():
                    continue
                if city and (city.lower() not in (a.get("location") or "").lower() and city.lower() not in (a.get("city") or "").lower()):
                    continue
                filtered.append(_format_charity_ad(a))
            return filtered
        except Exception:
            return []


@router.get("/{charity_ad_id}", response_model=CharityAdResponse)
async def get_charity_ad(
    charity_ad_id: str,
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    result = (
        await db.table(Tables.CHARITY_ADS)
        .select("*")
        .eq("id", charity_ad_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Anúncio de caridade não encontrado.")
    return result.data[0]


@router.delete("/{charity_ad_id}", status_code=204)
async def delete_charity_ad(
    charity_ad_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Remove anúncio de caridade (dono ou admin)."""
    result = (
        await db.table(Tables.CHARITY_ADS)
        .select("user_id")
        .eq("id", charity_ad_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Anúncio de caridade não encontrado.")
    if result.data[0]["user_id"] != user["id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Sem permissão.")
    await db.table(Tables.CHARITY_ADS).delete().eq("id", charity_ad_id).execute()
    return None
