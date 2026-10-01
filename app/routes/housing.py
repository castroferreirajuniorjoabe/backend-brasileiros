from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from supabase import AsyncClient
import json

from app.database import get_db
from app.models import AdStatus, Tables
from app.utils.deps import get_current_verified_user, get_current_user, get_optional_user
from app.utils import image as image_utils
from app.schemas.housing import HousingAdCreate, HousingMessageCreate

router = APIRouter(prefix="/housing", tags=["Moradia"])

@router.post("", status_code=201)
async def create_housing_ad(
    name: str = Form(...),
    description: str = Form(...),
    phone: str = Form(...),
    city: str = Form(...),
    property_type: str = Form(...),
    living_preference: str = Form(...),
    
    # Checkboxes
    accepts_pets: bool = Form(False),
    accepts_children: bool = Form(False),
    is_420_friendly: bool = Form(False),
    is_quiet_environment: bool = Form(False),
    accepts_smokers: bool = Form(False),
    accepts_couples: bool = Form(False),
    accepts_visitors: bool = Form(False),
    accepts_home_office: bool = Form(False),
    
    # Extras
    announcer_identity: Optional[str] = Form(None),
    charges_included: Optional[bool] = Form(None),
    deposit: Optional[str] = Form(None),
    surface_m2: Optional[int] = Form(None),
    floor: Optional[int] = Form(None),
    furnished: Optional[bool] = Form(None),
    roommates_count: Optional[int] = Form(None),
    roommates_profile: Optional[str] = Form(None),
    house_rules: Optional[str] = Form(None),
    documents_required: Optional[str] = Form(None), # JSON string
    min_stay: Optional[str] = Form(None),
    
    availability_date: Optional[str] = Form(None),
    start_date: Optional[str] = Form(None),
    end_date: Optional[str] = Form(None),
    is_unlimited: bool = Form(False),
    
    virtual_tour_link: Optional[str] = Form(None),
    
    image: UploadFile = File(...),
    image_2: Optional[UploadFile] = File(None),
    image_3: Optional[UploadFile] = File(None),
    image_4: Optional[UploadFile] = File(None),
    image_5: Optional[UploadFile] = File(None),
    
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db),
):
    """Cria anúncio de moradia."""
    image_url = await image_utils.upload_image(image, folder="housing")
    image_url_2 = await image_utils.upload_image(image_2, folder="housing") if image_2 and image_2.filename else None
    
    # Assuming extra images are not in table natively, or if they are they can be stored in a json array. For now we only use image_url and image_url_2 if standard. But we can add them to a gallery JSON.
    # We will just map to ads fields for now.
    
    docs_req = []
    if documents_required:
        try:
            docs_req = json.loads(documents_required)
        except Exception:
            pass

    record = {
        "user_id": user["id"],
        "ad_category": "housing",
        "name": name,
        "description": description,
        "phone": phone,
        "city": city,
        "property_type": property_type,
        "living_preference": living_preference,
        
        "accepts_pets": accepts_pets,
        "accepts_children": accepts_children,
        "is_420_friendly": is_420_friendly,
        "is_quiet_environment": is_quiet_environment,
        "accepts_smokers": accepts_smokers,
        "accepts_couples": accepts_couples,
        "accepts_visitors": accepts_visitors,
        "accepts_home_office": accepts_home_office,
        
        "announcer_identity": announcer_identity,
        "charges_included": charges_included,
        "deposit": deposit,
        "surface_m2": surface_m2,
        "floor": floor,
        "furnished": furnished,
        "roommates_count": roommates_count,
        "roommates_profile": roommates_profile,
        "house_rules": house_rules,
        "documents_required": docs_req,
        "min_stay": min_stay,
        
        "availability_date": availability_date,
        "start_date": start_date,
        "end_date": end_date,
        "is_unlimited": is_unlimited,
        
        "virtual_tour_link": virtual_tour_link,
        
        "image_url": image_url,
        "image_url_2": image_url_2,
        
        # O fields default for ads
        "status": AdStatus.PENDING.value,
        "email": user["email"], 
        "address": city,
        "category": "Moradia"
    }

    result = await db.table(Tables.ADS).insert(record).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Erro ao salvar anúncio de moradia")
        
    return result.data[0]

@router.get("")
async def list_housing_ads(
    city: Optional[str] = Query(None),
    property_type: Optional[str] = Query(None),
    living_preference: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user)
):
    query = (
        db.table(Tables.ADS)
        .select("*", count="exact")
        .eq("ad_category", "housing")
        .eq("status", AdStatus.APPROVED.value)
        .eq("is_occupied", False)
    )
    
    if city:
        query = query.ilike("city", f"%{city}%")
    if property_type:
        query = query.eq("property_type", property_type)
    if living_preference:
        query = query.eq("living_preference", living_preference)
    if search:
        query = query.or_(f"name.ilike.%{search}%,description.ilike.%{search}%")
        
    offset = (page - 1) * page_size
    limit = page_size - 1
    
    res = await query.order("created_at", desc=True).range(offset, offset + limit).execute()
    
    return {
        "total": res.count if res.count is not None else 0,
        "page": page,
        "page_size": page_size,
        "items": res.data or []
    }

@router.get("/mine")
async def list_my_housing_ads(
    db: AsyncClient = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    res = (
        await db.table(Tables.ADS)
        .select("*")
        .eq("ad_category", "housing")
        .eq("user_id", user["id"])
        .neq("status", AdStatus.DELETED.value)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []

@router.get("/{id}")
async def get_housing_ad(
    id: str,
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user)
):
    res = await db.table(Tables.ADS).select("*").eq("id", id).eq("ad_category", "housing").execute()
    if not res.data or res.data[0].get("status") == AdStatus.DELETED.value:
        raise HTTPException(status_code=404, detail="Anúncio não encontrado")
    return res.data[0]

@router.post("/{id}/mark-occupied")
async def mark_occupied(
    id: str,
    db: AsyncClient = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    res = await db.table(Tables.ADS).select("user_id").eq("id", id).eq("ad_category", "housing").execute()
    if not res.data or res.data[0]["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Não autorizado")
    
    upd = await db.table(Tables.ADS).update({"is_occupied": True}).eq("id", id).execute()
    return upd.data[0]

@router.post("/{id}/reactivate")
async def reactivate(
    id: str,
    db: AsyncClient = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    res = await db.table(Tables.ADS).select("user_id").eq("id", id).eq("ad_category", "housing").execute()
    if not res.data or res.data[0]["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Não autorizado")
    
    upd = await db.table(Tables.ADS).update({"is_occupied": False}).eq("id", id).execute()
    return upd.data[0]

@router.delete("/{id}")
async def delete_housing(
    id: str,
    db: AsyncClient = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    res = await db.table(Tables.ADS).select("user_id").eq("id", id).eq("ad_category", "housing").execute()
    if not res.data or res.data[0]["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Não autorizado")
    
    await db.table(Tables.ADS).update({"status": AdStatus.DELETED.value}).eq("id", id).execute()
    return {"ok": True}

@router.post("/{id}/message")
async def send_message(
    id: str,
    payload: HousingMessageCreate,
    db: AsyncClient = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    ad = await db.table(Tables.ADS).select("*").eq("id", id).eq("ad_category", "housing").execute()
    if not ad.data:
        raise HTTPException(status_code=404, detail="Anúncio não encontrado")
        
    msg = {
        "ad_id": id,
        "sender_name": payload.sender_name,
        "sender_email": payload.sender_email,
        "sender_phone": payload.sender_phone,
        "message": payload.message
    }
    
    res = await db.table("housing_messages").insert(msg).execute()
    return res.data[0]

@router.get("/{id}/messages")
async def get_messages(
    id: str,
    db: AsyncClient = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    ad = await db.table(Tables.ADS).select("user_id").eq("id", id).eq("ad_category", "housing").execute()
    if not ad.data or ad.data[0]["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Não autorizado")
        
    res = await db.table("housing_messages").select("*").eq("ad_id", id).order("created_at", desc=True).execute()
    
    # Mark as read
    unreads = [m["id"] for m in res.data if not m.get("is_read")]
    if unreads:
        await db.table("housing_messages").update({"is_read": True}).in_("id", unreads).execute()
        
    return res.data or []
