"""Rotas para Influencers Brasileiros."""

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import AsyncClient

from app.database import get_db
from app.models import Tables
from app.schemas.influencers import (
    InfluencerCreate,
    InfluencerUpdate,
    InfluencerResponse,
    InfluencerEventCreate,
    InfluencerEventResponse,
    InfluencerPortfolioCreate,
    InfluencerPortfolioResponse,
    RejectRequest,
)
from app.utils.deps import get_current_verified_user, get_admin_user, get_optional_user

router = APIRouter(prefix="/influencers", tags=["Influencers"])

# --- Influencer Profile ---

@router.post("", response_model=InfluencerResponse, status_code=201)
async def create_influencer(
    influencer: InfluencerCreate,
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db)
):
    """Cria o perfil do influencer."""
    data = influencer.dict(exclude_none=True)
    data["user_id"] = user["id"]
    data["status"] = "pending"
    
    # Valida url string
    for field in ["instagram", "tiktok", "youtube", "twitter", "other_social", "website"]:
        if data.get(field):
            data[field] = str(data[field])

    result = await db.table(Tables.INFLUENCERS).insert(data).execute()
    if not result.data:
        raise HTTPException(status_code=400, detail="Erro ao criar perfil. Você já possui um?")
    return result.data[0]

@router.get("/mine", response_model=InfluencerResponse)
async def get_my_influencer(
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db)
):
    """Busca o perfil do usuário logado."""
    result = await db.table(Tables.INFLUENCERS).select("*").eq("user_id", user["id"]).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")
    return result.data[0]

@router.get("/{influencer_id}", response_model=InfluencerResponse)
async def get_influencer(influencer_id: str, db: AsyncClient = Depends(get_db)):
    """Busca detalhes de um influencer público."""
    result = await db.table(Tables.INFLUENCERS).select("*").eq("id", influencer_id).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Influencer não encontrado.")
    
    # Se não for aprovado, deveria restringir? 
    # (O RLS já deve bloquear no banco se acessado sem privilégios, mas o get_db aqui usa service_role bypass)
    # Por segurança na rota pública:
    influencer = result.data[0]
    if influencer.get("status") != "approved":
        raise HTTPException(status_code=404, detail="Influencer não encontrado ou pendente.")
        
    return influencer

@router.get("", response_model=dict)
async def list_influencers(
    area: Optional[str] = None,
    city: Optional[str] = None,
    language: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncClient = Depends(get_db)
):
    """Lista influencers aprovados com filtros."""
    query = db.table(Tables.INFLUENCERS).select("*", count="exact").eq("status", "approved")
    
    if area:
        query = query.eq("area", area)
    if city:
        query = query.ilike("city", f"%{city}%")
    if language:
        query = query.contains("languages", [language])
        
    start = (page - 1) * page_size
    query = query.order("is_featured", desc=True).order("followers_count", desc=True)
    query = query.range(start, start + page_size - 1)
    
    result = await query.execute()
    return {
        "total": result.count or 0,
        "page": page,
        "page_size": page_size,
        "items": result.data or []
    }

@router.put("/{influencer_id}", response_model=InfluencerResponse)
async def update_influencer(
    influencer_id: str,
    update_data: InfluencerUpdate,
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db)
):
    """Atualiza o perfil do influencer."""
    existing = await db.table(Tables.INFLUENCERS).select("user_id").eq("id", influencer_id).limit(1).execute()
    if not existing.data or existing.data[0]["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Não autorizado.")
        
    data = update_data.dict(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar.")
        
    for field in ["instagram", "tiktok", "youtube", "twitter", "other_social", "website"]:
        if data.get(field):
            data[field] = str(data[field])
            
    result = await db.table(Tables.INFLUENCERS).update(data).eq("id", influencer_id).execute()
    return result.data[0]


@router.delete("/{influencer_id}", status_code=204)
async def delete_influencer(
    influencer_id: str,
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db)
):
    existing = await db.table(Tables.INFLUENCERS).select("user_id").eq("id", influencer_id).limit(1).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Influencer não encontrado.")
    if existing.data[0]["user_id"] != user["id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Não autorizado.")
    await db.table(Tables.INFLUENCERS).delete().eq("id", influencer_id).execute()

# --- Influencer Events ---

@router.post("/{influencer_id}/events", response_model=InfluencerEventResponse, status_code=201)
async def create_event(
    influencer_id: str,
    event: InfluencerEventCreate,
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db)
):
    existing = await db.table(Tables.INFLUENCERS).select("user_id").eq("id", influencer_id).limit(1).execute()
    if not existing.data or existing.data[0]["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Não autorizado.")
        
    data = event.dict(exclude_none=True)
    data["influencer_id"] = influencer_id
    if data.get("registration_link"):
        data["registration_link"] = str(data["registration_link"])
        
    result = await db.table(Tables.INFLUENCER_EVENTS).insert(data).execute()
    return result.data[0]

@router.get("/{influencer_id}/events", response_model=list[InfluencerEventResponse])
async def list_events(influencer_id: str, db: AsyncClient = Depends(get_db)):
    result = await db.table(Tables.INFLUENCER_EVENTS).select("*").eq("influencer_id", influencer_id).order("event_date").execute()
    return result.data or []

# --- Influencer Portfolio ---

@router.post("/{influencer_id}/portfolio", response_model=InfluencerPortfolioResponse, status_code=201)
async def create_portfolio_item(
    influencer_id: str,
    item: InfluencerPortfolioCreate,
    image_url: str = Query(..., description="URL da imagem (enviada via upload separado)"),
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db)
):
    existing = await db.table(Tables.INFLUENCERS).select("user_id").eq("id", influencer_id).limit(1).execute()
    if not existing.data or existing.data[0]["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Não autorizado.")
        
    data = item.dict(exclude_none=True)
    data["influencer_id"] = influencer_id
    data["image_url"] = image_url
        
    result = await db.table(Tables.INFLUENCER_PORTFOLIO).insert(data).execute()
    return result.data[0]

@router.get("/{influencer_id}/portfolio", response_model=list[InfluencerPortfolioResponse])
async def list_portfolio(influencer_id: str, db: AsyncClient = Depends(get_db)):
    result = await db.table(Tables.INFLUENCER_PORTFOLIO).select("*").eq("influencer_id", influencer_id).order("order_index").execute()
    return result.data or []

@router.delete("/{influencer_id}/portfolio/{item_id}", status_code=204)
async def delete_portfolio_item(
    influencer_id: str,
    item_id: str,
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db)
):
    existing = await db.table(Tables.INFLUENCERS).select("user_id").eq("id", influencer_id).limit(1).execute()
    if not existing.data or existing.data[0]["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Não autorizado.")
    await db.table(Tables.INFLUENCER_PORTFOLIO).delete().eq("id", item_id).eq("influencer_id", influencer_id).execute()
    return None

# --- Admin Moderation ---

@router.post("/admin/moderation/{influencer_id}/approve", status_code=200)
async def approve_influencer(
    influencer_id: str,
    admin: dict = Depends(get_admin_user),
    db: AsyncClient = Depends(get_db)
):
    result = await db.table(Tables.INFLUENCERS).update({"status": "approved"}).eq("id", influencer_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Influencer não encontrado.")
    return {"message": "Aprovado com sucesso"}

@router.post("/admin/moderation/{influencer_id}/reject", status_code=200)
async def reject_influencer(
    influencer_id: str,
    req: RejectRequest,
    admin: dict = Depends(get_admin_user),
    db: AsyncClient = Depends(get_db)
):
    result = await db.table(Tables.INFLUENCERS).update({
        "status": "rejected",
        "rejection_reason": req.reason
    }).eq("id", influencer_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Influencer não encontrado.")
    return {"message": "Rejeitado com sucesso"}
