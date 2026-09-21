"""Rotas para Igrejas Brasileiras na França."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import AsyncClient

from app.database import get_db
from app.models import Tables
from app.schemas.churches import (
    ChurchCreate,
    ChurchUpdate,
    ChurchResponse,
    ChurchScheduleCreate,
    ChurchScheduleResponse,
    ChurchEventCreate,
    ChurchEventResponse,
    ChurchGroupCreate,
    ChurchGroupResponse,
    ChurchLeaderCreate,
    ChurchLeaderResponse,
    ChurchSocialServiceCreate,
    ChurchSocialServiceResponse,
)
from app.schemas.influencers import RejectRequest  # Reaproveitando do schema
from app.utils.deps import get_current_verified_user, get_admin_user, get_optional_user

router = APIRouter(prefix="/churches", tags=["Igrejas"])

# --- Church Profile ---

@router.post("", response_model=ChurchResponse, status_code=201)
async def create_church(
    church: ChurchCreate,
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db)
):
    data = church.dict(exclude_none=True)
    data["user_id"] = user["id"]
    data["status"] = "pending"

    for field in ["website", "instagram", "facebook", "youtube"]:
        if data.get(field):
            data[field] = str(data[field])

    result = await db.table(Tables.CHURCHES).insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Erro ao criar perfil. Você já possui uma igreja cadastrada?")
    return result.data[0]

@router.get("/mine", response_model=ChurchResponse)
async def get_my_church(
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db)
):
    result = await db.table(Tables.CHURCHES).select("*").eq("user_id", user["id"]).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")
    return result.data[0]

@router.get("/{church_id}", response_model=ChurchResponse)
async def get_church(church_id: str, db: AsyncClient = Depends(get_db)):
    result = await db.table(Tables.CHURCHES).select("*").eq("id", church_id).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Igreja não encontrada.")
    church = result.data[0]
    if church.get("status") != "approved":
        raise HTTPException(status_code=404, detail="Igreja não encontrada ou pendente.")
    return church

@router.get("", response_model=dict)
async def list_churches(
    denomination: Optional[str] = None,
    city: Optional[str] = None,
    service: Optional[str] = None,
    language: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncClient = Depends(get_db)
):
    query = db.table(Tables.CHURCHES).select("*", count="exact").eq("status", "approved")
    
    if denomination:
        query = query.eq("denomination", denomination)
    if city:
        query = query.ilike("city", f"%{city}%")
    if service:
        query = query.contains("services_offered", [service])
    if language:
        query = query.contains("languages", [language])
        
    start = (page - 1) * page_size
    query = query.order("is_featured", desc=True).order("name", desc=False)
    query = query.range(start, start + page_size - 1)
    
    result = await query.execute()
    return {
        "total": result.count or 0,
        "page": page,
        "page_size": page_size,
        "items": result.data or []
    }

@router.put("/{church_id}", response_model=ChurchResponse)
async def update_church(
    church_id: str,
    update_data: ChurchUpdate,
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db)
):
    existing = await db.table(Tables.CHURCHES).select("user_id").eq("id", church_id).limit(1).execute()
    if not existing.data or existing.data[0]["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Não autorizado.")
        
    data = update_data.dict(exclude_unset=True)
        
    if not data:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar.")
        
    for field in ["website", "instagram", "facebook", "youtube"]:
        if data.get(field):
            data[field] = str(data[field])
            
    result = await db.table(Tables.CHURCHES).update(data).eq("id", church_id).execute()
    return result.data[0]

# --- Church Schedule ---

@router.delete("/{church_id}", status_code=204)
async def delete_church(
    church_id: str,
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db)
):
    existing = await db.table(Tables.CHURCHES).select("user_id").eq("id", church_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Igreja não encontrada.")
    if existing.data[0]["user_id"] != user["id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Não autorizado.")
    await db.table(Tables.CHURCHES).delete().eq("id", church_id).execute()

@router.post("/{church_id}/schedule", response_model=ChurchScheduleResponse, status_code=201)
async def create_schedule(
    church_id: str,
    schedule: ChurchScheduleCreate,
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db)
):
    existing = await db.table(Tables.CHURCHES).select("user_id").eq("id", church_id).limit(1).execute()
    if not existing.data or existing.data[0]["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Não autorizado.")
        
    data = schedule.dict(exclude_none=True)
    data["church_id"] = church_id
    result = await db.table(Tables.CHURCH_SCHEDULE).insert(data).execute()
    return result.data[0]

@router.get("/{church_id}/schedule", response_model=list[ChurchScheduleResponse])
async def list_schedule(church_id: str, db: AsyncClient = Depends(get_db)):
    result = await db.table(Tables.CHURCH_SCHEDULE).select("*").eq("church_id", church_id).order("order_index").execute()
    return result.data or []

@router.delete("/{church_id}/schedule/{item_id}", status_code=204)
async def delete_schedule(
    church_id: str,
    item_id: str,
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db)
):
    existing = await db.table(Tables.CHURCHES).select("user_id").eq("id", church_id).limit(1).execute()
    if not existing.data or existing.data[0]["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Não autorizado.")
    await db.table(Tables.CHURCH_SCHEDULE).delete().eq("id", item_id).eq("church_id", church_id).execute()
    return None

# --- Church Events ---

@router.post("/{church_id}/events", response_model=ChurchEventResponse, status_code=201)
async def create_event(
    church_id: str,
    event: ChurchEventCreate,
    image_url: Optional[str] = Query(None),
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db)
):
    existing = await db.table(Tables.CHURCHES).select("user_id").eq("id", church_id).limit(1).execute()
    if not existing.data or existing.data[0]["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Não autorizado.")
        
    data = event.dict(exclude_none=True)
    data["church_id"] = church_id
    if image_url:
        data["image_url"] = image_url
    if data.get("registration_link"):
        data["registration_link"] = str(data["registration_link"])
        
    result = await db.table(Tables.CHURCH_EVENTS).insert(data).execute()
    return result.data[0]

@router.get("/{church_id}/events", response_model=list[ChurchEventResponse])
async def list_events(church_id: str, db: AsyncClient = Depends(get_db)):
    result = await db.table(Tables.CHURCH_EVENTS).select("*").eq("church_id", church_id).order("event_date").execute()
    return result.data or []

@router.delete("/{church_id}/events/{item_id}", status_code=204)
async def delete_event(
    church_id: str,
    item_id: str,
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db)
):
    existing = await db.table(Tables.CHURCHES).select("user_id").eq("id", church_id).limit(1).execute()
    if not existing.data or existing.data[0]["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Não autorizado.")
    await db.table(Tables.CHURCH_EVENTS).delete().eq("id", item_id).eq("church_id", church_id).execute()
    return None

# --- Church Groups ---

@router.post("/{church_id}/groups", response_model=ChurchGroupResponse, status_code=201)
async def create_group(
    church_id: str,
    group: ChurchGroupCreate,
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db)
):
    existing = await db.table(Tables.CHURCHES).select("user_id").eq("id", church_id).limit(1).execute()
    if not existing.data or existing.data[0]["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Não autorizado.")
        
    data = group.dict(exclude_none=True)
    data["church_id"] = church_id
    result = await db.table(Tables.CHURCH_GROUPS).insert(data).execute()
    return result.data[0]

@router.get("/{church_id}/groups", response_model=list[ChurchGroupResponse])
async def list_groups(church_id: str, db: AsyncClient = Depends(get_db)):
    result = await db.table(Tables.CHURCH_GROUPS).select("*").eq("church_id", church_id).order("name").execute()
    return result.data or []

@router.delete("/{church_id}/groups/{item_id}", status_code=204)
async def delete_group(
    church_id: str,
    item_id: str,
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db)
):
    existing = await db.table(Tables.CHURCHES).select("user_id").eq("id", church_id).limit(1).execute()
    if not existing.data or existing.data[0]["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Não autorizado.")
    await db.table(Tables.CHURCH_GROUPS).delete().eq("id", item_id).eq("church_id", church_id).execute()
    return None

# --- Church Leaders ---

@router.post("/{church_id}/leaders", response_model=ChurchLeaderResponse, status_code=201)
async def create_leader(
    church_id: str,
    leader: ChurchLeaderCreate,
    photo_url: Optional[str] = Query(None),
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db)
):
    existing = await db.table(Tables.CHURCHES).select("user_id").eq("id", church_id).limit(1).execute()
    if not existing.data or existing.data[0]["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Não autorizado.")
        
    data = leader.dict(exclude_none=True)
    data["church_id"] = church_id
    if photo_url:
        data["photo_url"] = photo_url
        
    result = await db.table(Tables.CHURCH_LEADERS).insert(data).execute()
    return result.data[0]

@router.get("/{church_id}/leaders", response_model=list[ChurchLeaderResponse])
async def list_leaders(church_id: str, db: AsyncClient = Depends(get_db)):
    result = await db.table(Tables.CHURCH_LEADERS).select("*").eq("church_id", church_id).order("order_index").execute()
    return result.data or []

@router.delete("/{church_id}/leaders/{item_id}", status_code=204)
async def delete_leader(
    church_id: str,
    item_id: str,
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db)
):
    existing = await db.table(Tables.CHURCHES).select("user_id").eq("id", church_id).limit(1).execute()
    if not existing.data or existing.data[0]["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Não autorizado.")
    await db.table(Tables.CHURCH_LEADERS).delete().eq("id", item_id).eq("church_id", church_id).execute()
    return None

# --- Church Social Services ---

@router.post("/{church_id}/services", response_model=ChurchSocialServiceResponse, status_code=201)
async def create_social_service(
    church_id: str,
    service: ChurchSocialServiceCreate,
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db)
):
    existing = await db.table(Tables.CHURCHES).select("user_id").eq("id", church_id).limit(1).execute()
    if not existing.data or existing.data[0]["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Não autorizado.")
        
    data = service.dict(exclude_none=True)
    data["church_id"] = church_id
    result = await db.table(Tables.CHURCH_SOCIAL_SERVICES).insert(data).execute()
    return result.data[0]

@router.get("/{church_id}/services", response_model=list[ChurchSocialServiceResponse])
async def list_social_services(church_id: str, db: AsyncClient = Depends(get_db)):
    result = await db.table(Tables.CHURCH_SOCIAL_SERVICES).select("*").eq("church_id", church_id).order("order_index").execute()
    return result.data or []

@router.delete("/{church_id}/services/{item_id}", status_code=204)
async def delete_social_service(
    church_id: str,
    item_id: str,
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db)
):
    existing = await db.table(Tables.CHURCHES).select("user_id").eq("id", church_id).limit(1).execute()
    if not existing.data or existing.data[0]["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Não autorizado.")
    await db.table(Tables.CHURCH_SOCIAL_SERVICES).delete().eq("id", item_id).eq("church_id", church_id).execute()
    return None

# --- Admin Moderation ---

@router.post("/admin/moderation/{church_id}/approve", status_code=200)
async def approve_church(
    church_id: str,
    admin: dict = Depends(get_admin_user),
    db: AsyncClient = Depends(get_db)
):
    result = await db.table(Tables.CHURCHES).update({"status": "approved"}).eq("id", church_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Igreja não encontrada.")
    return {"message": "Aprovado com sucesso"}

@router.post("/admin/moderation/{church_id}/reject", status_code=200)
async def reject_church(
    church_id: str,
    req: RejectRequest,
    admin: dict = Depends(get_admin_user),
    db: AsyncClient = Depends(get_db)
):
    result = await db.table(Tables.CHURCHES).update({
        "status": "rejected",
        "rejection_reason": req.reason
    }).eq("id", church_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Igreja não encontrada.")
    return {"message": "Rejeitado com sucesso"}
