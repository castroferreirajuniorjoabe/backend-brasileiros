"""Espaço Pet & Comunidade Canina: Escolas, Parques Dog-Friendly e Encontros de Pets na França."""

from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from supabase import AsyncClient

from app.database import get_db
from app.models import ModerationStatus, Tables
from app.schemas.community import PetPostResponse
from app.utils import image as image_utils
from app.utils.deps import get_current_user, get_optional_user

router = APIRouter(prefix="/pet-posts", tags=["Espaço Pet & Cachorros"])


def _format_pet_post(post: dict) -> dict:
    p = dict(post)
    p["city"] = p.get("city") or p.get("location") or "França"
    p["badge"] = "PET"
    return p


@router.post("", response_model=PetPostResponse, status_code=201)
async def create_pet_post(
    title: str = Form(...),
    description: str = Form(...),
    city: str = Form(...),
    category: Optional[str] = Form("parque"),  # doacao_spa, parque, escola_canina, encontro_pet, adestramento, veterinario
    address: Optional[str] = Form(None),
    google_maps_url: Optional[str] = Form(None),
    contact_phone: Optional[str] = Form(None),
    landline_phone: Optional[str] = Form(None),
    meetup_date: Optional[str] = Form(None),
    tips: Optional[str] = Form(None),
    association_name: Optional[str] = Form(None),
    pet_name: Optional[str] = Form(None),
    pet_breed: Optional[str] = Form(None),
    pet_age: Optional[str] = Form(None),
    pet_gender: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    image_2: Optional[UploadFile] = File(None),
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Publica uma indicação canina, parque para passear com cães ou encontro de pais de pet na França."""
    image_url = None
    image_url_2 = None

    if image and image.filename:
        image_url = await image_utils.upload_image(image, folder="pets")

    if image_2 and image_2.filename:
        image_url_2 = await image_utils.upload_image(image_2, folder="pets")

    extra_info = []
    if association_name:
        extra_info.append(f"🏛️ SPA / Associação Protetora: {association_name.strip()}")
    if pet_name:
        extra_info.append(f"🐶 Nome do Cão: {pet_name.strip()}")
    if pet_breed:
        extra_info.append(f"🐾 Raça / Porte: {pet_breed.strip()}")
    if pet_age:
        extra_info.append(f"🎂 Idade Aproximada: {pet_age.strip()}")
    if pet_gender:
        extra_info.append(f"⚧️ Sexo: {pet_gender.strip()}")
    if meetup_date:
        extra_info.append(f"📅 Data/Horário: {meetup_date.strip()}")
    if address:
        extra_info.append(f"📍 Endereço / Local: {address.strip()}")
    if google_maps_url:
        extra_info.append(f"🗺️ Google Maps: {google_maps_url.strip()}")
    if tips:
        extra_info.append(f"💡 Dica / Requisitos de Adoção: {tips.strip()}")

    full_desc = description.strip()
    if extra_info:
        full_desc += "\n\n" + "\n\n".join(extra_info)

    chosen_cat = (category or "parque").strip()
    phone_to_use = contact_phone or landline_phone or user.get("phone") or "Contato Pet"

    try:
        community_record = {
            "user_id": user["id"],
            "title": f"[PET - {chosen_cat.upper()}] {title.strip()}",
            "description": full_desc,
            "location": city.strip(),
            "type": "pet",
            "contact_phone": phone_to_use,
            "image_url": image_url,
            "image_2_url": image_url_2,
            "status": ModerationStatus.APPROVED.value,
        }
        result = await db.table(Tables.CHARITY_ADS).insert(community_record).execute()
        if result.data:
            created = result.data[0]
            return {
                "id": created["id"],
                "user_id": created["user_id"],
                "title": title.strip(),
                "description": description.strip(),
                "city": city.strip(),
                "category": chosen_cat,
                "address": address,
                "google_maps_url": google_maps_url,
                "contact_phone": phone_to_use,
                "meetup_date": meetup_date,
                "tips": tips,
                "image_url": image_url,
                "image_2_url": image_url_2,
                "badge": "PET",
                "status": "approved",
                "created_at": created.get("created_at"),
            }
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar postagem pet: {str(err)}")

    raise HTTPException(status_code=500, detail="Não foi possível salvar a postagem canina.")


@router.get("", response_model=list[PetPostResponse])
async def list_pet_posts(
    city: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Lista todos os parques, escolas caninas e encontros de pets cadastrados na França."""
    posts = []
    try:
        query = (
            db.table(Tables.PET_POSTS)
            .select("*")
            .eq("status", ModerationStatus.APPROVED.value)
        )
        if city:
            query = query.or_(f"city.ilike.%{city}%,address.ilike.%{city}%")
        if category:
            query = query.eq("category", category)

        result = await query.order("created_at", desc=True).execute()
        posts.extend([_format_pet_post(s) for s in result.data or []])
    except Exception:
        pass

    # Consulta complementar em storage compartilhado
    try:
        query_c = (
            db.table(Tables.CHARITY_ADS)
            .select("*")
            .eq("type", "pet")
            .eq("status", ModerationStatus.APPROVED.value)
        )
        if city:
            query_c = query_c.ilike("location", f"%{city}%")
        result_c = await query_c.order("created_at", desc=True).execute()
        for c in result_c.data or []:
            raw_title = c.get("title", "")
            cat = "parque"
            clean_title = raw_title
            if raw_title.startswith("[PET - ") and "]" in raw_title:
                cat = raw_title[7:raw_title.index("]")].lower()
                clean_title = raw_title[raw_title.index("]") + 1:].strip()
            
            if category and cat != category:
                continue

            posts.append({
                "id": c["id"],
                "user_id": c["user_id"],
                "title": clean_title,
                "description": c.get("description", ""),
                "city": c.get("location") or "França",
                "category": cat,
                "address": None,
                "google_maps_url": None,
                "contact_phone": c.get("contact_phone"),
                "meetup_date": None,
                "tips": None,
                "image_url": c.get("image_url"),
                "image_url_2": c.get("image_2_url"),
                "badge": "PET",
                "status": "approved",
                "created_at": c.get("created_at"),
            })
    except Exception:
        pass

    return posts


@router.get("/{post_id}", response_model=PetPostResponse)
async def get_pet_post(
    post_id: str,
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Obtém detalhes de uma postagem pet específica."""
    result = (
        await db.table(Tables.PET_POSTS)
        .select("*")
        .eq("id", post_id)
        .limit(1)
        .execute()
    )
    if result.data:
        return _format_pet_post(result.data[0])

    # Fallback na tabela comunitária
    result_c = (
        await db.table(Tables.CHARITY_ADS)
        .select("*")
        .eq("id", post_id)
        .limit(1)
        .execute()
    )
    if result_c.data:
        c = result_c.data[0]
        raw_title = c.get("title", "")
        clean_title = raw_title
        cat = "parque"
        if raw_title.startswith("[PET - ") and "]" in raw_title:
            cat = raw_title[7:raw_title.index("]")].lower()
            clean_title = raw_title[raw_title.index("]") + 1:].strip()
        return {
            "id": c["id"],
            "user_id": c["user_id"],
            "title": clean_title,
            "description": c.get("description", ""),
            "city": c.get("location") or "França",
            "category": cat,
            "address": None,
            "google_maps_url": None,
            "contact_phone": c.get("contact_phone"),
            "meetup_date": None,
            "tips": None,
            "image_url": c.get("image_url"),
            "image_url_2": c.get("image_2_url"),
            "badge": "PET",
            "status": "approved",
            "created_at": c.get("created_at"),
        }

    raise HTTPException(status_code=404, detail="Postagem pet não encontrada.")


@router.delete("/{post_id}", status_code=204)
async def delete_pet_post(
    post_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Remove uma postagem pet (dono ou admin)."""
    # Tenta apagar da tabela PET_POSTS
    try:
        res = await db.table(Tables.PET_POSTS).select("user_id").eq("id", post_id).limit(1).execute()
        if res.data:
            if res.data[0]["user_id"] != user["id"] and not user.get("is_admin"):
                raise HTTPException(status_code=403, detail="Sem permissão.")
            await db.table(Tables.PET_POSTS).delete().eq("id", post_id).execute()
            return None
    except HTTPException:
        raise
    except Exception:
        pass

    # Tenta apagar da tabela CHARITY_ADS
    res_c = await db.table(Tables.CHARITY_ADS).select("user_id").eq("id", post_id).limit(1).execute()
    if res_c.data:
        if res_c.data[0]["user_id"] != user["id"] and not user.get("is_admin"):
            raise HTTPException(status_code=403, detail="Sem permissão.")
        await db.table(Tables.CHARITY_ADS).delete().eq("id", post_id).execute()
        return None

    raise HTTPException(status_code=404, detail="Postagem pet não encontrada.")
