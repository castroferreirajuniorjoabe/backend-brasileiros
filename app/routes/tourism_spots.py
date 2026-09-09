"""Dicas de Passeios, Turismo & Férias na França postadas por brasileiros."""

from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from supabase import AsyncClient

from app.database import get_db
from app.models import ModerationStatus, Tables
from app.schemas.community import TourismSpotResponse
from app.utils import image as image_utils
from app.utils.deps import get_current_user, get_optional_user

router = APIRouter(prefix="/tourism-spots", tags=["Passeios & Férias na França"])


def _format_spot(spot: dict) -> dict:
    s = dict(spot)
    s["city"] = s.get("city") or s.get("location") or "França"
    s["badge"] = "PASSEIO"
    return s


@router.post("", response_model=TourismSpotResponse, status_code=201)
async def create_tourism_spot(
    title: str = Form(...),
    description: str = Form(...),
    city: str = Form(...),
    category: Optional[str] = Form("praia"),  # praia, parque, monumento, trilha, vila, gastronomia, etc.
    address: Optional[str] = Form(None),
    google_maps_url: Optional[str] = Form(None),
    tips: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    image_2: Optional[UploadFile] = File(None),
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Publica uma dica de passeio ou férias na França (com até 2 fotos e link do Google Maps)."""
    image_url = None
    image_url_2 = None

    if image and image.filename:
        image_url = await image_utils.upload_image(image, folder="tourism")

    if image_2 and image_2.filename:
        image_url_2 = await image_utils.upload_image(image_2, folder="tourism")

    record = {
        "user_id": user["id"],
        "title": title.strip(),
        "description": description.strip(),
        "city": city.strip(),
        "category": category.strip() if category else "praia",
        "address": address.strip() if address else None,
        "google_maps_url": google_maps_url.strip() if google_maps_url else None,
        "tips": tips.strip() if tips else None,
        "image_url": image_url,
        "image_2_url": image_url_2,
        "status": ModerationStatus.APPROVED.value,
    }

    try:
        result = await db.table(Tables.TOURISM_SPOTS).insert(record).execute()
        if result.data:
            return _format_spot(result.data[0])
    except Exception as err:
        # Fallback 1: se image_2_url der incompatibilidade de coluna, tenta com image_url_2
        try:
            fallback_record = {
                "user_id": user["id"],
                "title": title.strip(),
                "description": description.strip(),
                "city": city.strip(),
                "category": category.strip() if category else "praia",
                "address": address.strip() if address else None,
                "google_maps_url": google_maps_url.strip() if google_maps_url else None,
                "tips": tips.strip() if tips else None,
                "image_url": image_url,
                "image_url_2": image_url_2,
                "status": ModerationStatus.APPROVED.value,
            }
            result = await db.table(Tables.TOURISM_SPOTS).insert(fallback_record).execute()
            if result.data:
                return _format_spot(result.data[0])
        except Exception:
            pass

        # Fallback 2: salva como post de comunidade caso o schema Supabase seja compartilhado
        try:
            extra_info = []
            if address:
                extra_info.append(f"📍 Endereço/Como Chegar: {address.strip()}")
            if google_maps_url:
                extra_info.append(f"🗺️ Google Maps: {google_maps_url.strip()}")
            if tips:
                extra_info.append(f"✨ Dica de Ouro: {tips.strip()}")
            
            full_desc = description.strip()
            if extra_info:
                full_desc += "\n\n" + "\n\n".join(extra_info)

            basic_record = {
                "user_id": user["id"],
                "title": f"[{category.upper() if category else 'PASSEIO'}] {title.strip()}",
                "description": full_desc,
                "location": city.strip(),
                "type": "tourism",
                "contact_phone": user.get("phone") or "Comunidade",
                "image_url": image_url,
                "image_2_url": image_url_2,
                "status": ModerationStatus.APPROVED.value,
            }
            result = await db.table(Tables.CHARITY_ADS).insert(basic_record).execute()
            if result.data:
                created = result.data[0]
                return {
                    "id": created["id"],
                    "user_id": created["user_id"],
                    "title": title.strip(),
                    "description": description.strip(),
                    "city": city.strip(),
                    "category": category or "praia",
                    "address": address,
                    "google_maps_url": google_maps_url,
                    "tips": tips,
                    "image_url": image_url,
                    "image_url_2": image_url_2,
                    "badge": "PASSEIO",
                    "status": "approved",
                    "created_at": created.get("created_at"),
                }
        except Exception as e2:
            raise HTTPException(status_code=500, detail=f"Erro ao salvar passeio: {str(e2)}")

    raise HTTPException(status_code=500, detail="Não foi possível salvar o passeio.")


@router.get("", response_model=list[TourismSpotResponse])
async def list_tourism_spots(
    city: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Lista todos os passeios e dicas de férias na França cadastrados pela comunidade."""
    spots = []
    try:
        query = (
            db.table(Tables.TOURISM_SPOTS)
            .select("*")
            .eq("status", ModerationStatus.APPROVED.value)
        )
        if city:
            query = query.or_(f"city.ilike.%{city}%,address.ilike.%{city}%")
        if category:
            query = query.eq("category", category)

        result = await query.order("created_at", desc=True).execute()
        spots.extend([_format_spot(s) for s in result.data or []])
    except Exception:
        pass

    # Consulta complementar aos passeios registrados na tabela compartilhada
    try:
        query_c = (
            db.table(Tables.CHARITY_ADS)
            .select("*")
            .eq("type", "tourism")
            .eq("status", ModerationStatus.APPROVED.value)
        )
        if city:
            query_c = query_c.ilike("location", f"%{city}%")
        result_c = await query_c.order("created_at", desc=True).execute()
        for c in result_c.data or []:
            title = c.get("title", "")
            cat = "praia"
            if title.startswith("[") and "]" in title:
                cat = title[1:title.index("]")].lower()
                title = title[title.index("]") + 1:].strip()
            spots.append({
                "id": c["id"],
                "user_id": c["user_id"],
                "title": title,
                "description": c.get("description", ""),
                "city": c.get("location") or "França",
                "category": cat,
                "address": None,
                "google_maps_url": None,
                "tips": None,
                "image_url": c.get("image_url"),
                "image_url_2": c.get("image_2_url"),
                "badge": "PASSEIO",
                "status": "approved",
                "created_at": c.get("created_at"),
            })
    except Exception:
        pass

    return spots


@router.get("/{spot_id}", response_model=TourismSpotResponse)
async def get_tourism_spot(
    spot_id: str,
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Obtém detalhes de uma dica de passeio específica."""
    result = (
        await db.table(Tables.TOURISM_SPOTS)
        .select("*")
        .eq("id", spot_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Dica de passeio não encontrada.")
    return _format_spot(result.data[0])


@router.delete("/{spot_id}", status_code=204)
async def delete_tourism_spot(
    spot_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Remove uma dica de passeio (dono ou admin)."""
    result = (
        await db.table(Tables.TOURISM_SPOTS)
        .select("user_id")
        .eq("id", spot_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Dica de passeio não encontrada.")
    if result.data[0]["user_id"] != user["id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Sem permissão.")
    await db.table(Tables.TOURISM_SPOTS).delete().eq("id", spot_id).execute()
    return None
