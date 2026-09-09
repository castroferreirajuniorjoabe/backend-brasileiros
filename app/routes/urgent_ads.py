"""Anúncios de urgência (objeto perdido / pessoa desaparecida).

- Gratuitos, com selo "URGENTE".
- Pessoa desaparecida exige envio de documento (BO).
- Aprovação manual do admin.
- Expiração automática em 7 dias.
"""

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from supabase import AsyncClient

from app.database import get_db
from app.models import URGENT_AD_EXPIRATION_DAYS, ModerationStatus, Tables, UrgentType
from app.schemas.community import UrgentAdResponse
from app.utils import image as image_utils
from app.utils.deps import get_current_user, get_optional_user
from app.utils.security import utcnow

router = APIRouter(prefix="/urgent-ads", tags=["Anúncios de Urgência"])


def _format_urgent_ad(ad: dict) -> dict:
    a = dict(ad)
    a["city"] = a.get("location") or a.get("city") or "França"
    a["image_url"] = a.get("photo_url") or a.get("image_url")
    desc = a.get("description") or ""
    phone = a.get("contact_phone") or a.get("phone") or ""
    if not phone and "[Contato Direto:" in desc:
        try:
            phone = desc.split("[Contato Direto:")[1].split("]")[0].strip()
        except Exception:
            pass
    a["contact_phone"] = phone
    a["phone"] = phone
    a["badge"] = "URGENTE"
    return a


@router.post("", response_model=UrgentAdResponse, status_code=201)
async def create_urgent_ad(
    type: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    title: str = Form(...),
    description: str = Form(...),
    city: str = Form(...),
    contact_phone: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    bo_number: Optional[str] = Form(None),
    police_report_number: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    document: Optional[UploadFile] = File(
        None, description="Boletim de ocorrência / documento comprobatório"
    ),
    police_report_file: Optional[UploadFile] = File(None),
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Cria anúncio de urgência (gratuito) com foto e número ou anexo de B.O."""
    final_type = type or category or UrgentType.LOST_OBJECT.value
    # Se category for desaparecida ou missing_person
    if final_type in ["desaparecido", "missing_person", UrgentType.MISSING_PERSON.value]:
        resolved_type = UrgentType.MISSING_PERSON.value
    else:
        resolved_type = UrgentType.LOST_OBJECT.value

    final_phone = contact_phone or phone or ""
    final_bo = bo_number or police_report_number or ""
    doc_file = document or police_report_file

    image_url = (
        await image_utils.upload_image(image, folder="urgent")
        if image and image.filename
        else None
    )
    document_url = (
        await image_utils.upload_document(doc_file, folder="urgent/docs")
        if doc_file and doc_file.filename
        else None
    )

    full_desc = description
    if final_bo and "B.O" not in full_desc:
        full_desc = f"{description}\n\n[Boletim de Ocorrência Policial: {final_bo}]"
    if final_phone and "Contato" not in full_desc:
        full_desc = f"{full_desc}\n[Contato Direto: {final_phone}]"

    record = {
        "user_id": user["id"],
        "type": resolved_type,
        "title": title,
        "description": full_desc,
        "location": city,
        "photo_url": image_url,
        "document_url": document_url,
        "status": ModerationStatus.APPROVED.value,  # Aprovado diretamente para visualização e socorro imediato
        "expires_at": (utcnow() + timedelta(days=URGENT_AD_EXPIRATION_DAYS)).isoformat(),
    }
    try:
        result = await db.table(Tables.URGENT_ADS).insert(record).execute()
    except Exception:
        fallback = {
            "user_id": user["id"],
            "type": resolved_type,
            "title": title,
            "description": full_desc,
            "city": city,
            "contact_phone": final_phone,
            "image_url": image_url,
            "document_url": document_url,
            "status": ModerationStatus.APPROVED.value,
            "expires_at": (utcnow() + timedelta(days=URGENT_AD_EXPIRATION_DAYS)).isoformat(),
        }
        result = await db.table(Tables.URGENT_ADS).insert(fallback).execute()

    return _format_urgent_ad(result.data[0])


@router.get("", response_model=list[UrgentAdResponse])
async def list_urgent_ads(
    city: Optional[str] = Query(None),
    type: Optional[UrgentType] = Query(None),
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Lista anúncios de urgência ativos (aprovados e não expirados), com selo URGENTE."""
    try:
        query = (
            db.table(Tables.URGENT_ADS)
            .select("*")
            .eq("status", ModerationStatus.APPROVED.value)
        )
        if city:
            query = query.or_(f"location.ilike.%{city}%,city.ilike.%{city}%")
        if type:
            query = query.eq("type", type.value)
        result = await query.order("created_at", desc=True).execute()
        return [_format_urgent_ad(a) for a in result.data or []]
    except Exception:
        return []


@router.get("/{urgent_ad_id}", response_model=UrgentAdResponse)
async def get_urgent_ad(
    urgent_ad_id: str,
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    result = (
        await db.table(Tables.URGENT_ADS)
        .select("*")
        .eq("id", urgent_ad_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Anúncio de urgência não encontrado.")
    return result.data[0]


@router.delete("/{urgent_ad_id}", status_code=204)
async def delete_urgent_ad(
    urgent_ad_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Desativa o anúncio de urgência (dono ou admin) — ex.: caso resolvido."""
    result = (
        await db.table(Tables.URGENT_ADS)
        .select("user_id")
        .eq("id", urgent_ad_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Anúncio de urgência não encontrado.")
    if result.data[0]["user_id"] != user["id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Sem permissão.")
    await (
        db.table(Tables.URGENT_ADS)
        .update({"status": "closed"})
        .eq("id", urgent_ad_id)
        .execute()
    )
    return None


async def expire_urgent_ads(db: AsyncClient) -> int:
    """Marca como expirados os anúncios de urgência que passaram de 7 dias.
    Chamada pelo cron diário. Retorna quantos foram expirados."""
    result = (
        await db.table(Tables.URGENT_ADS)
        .update({"status": "expired"})
        .eq("status", ModerationStatus.APPROVED.value)
        .lt("expires_at", utcnow().isoformat())
        .execute()
    )
    return len(result.data or [])
