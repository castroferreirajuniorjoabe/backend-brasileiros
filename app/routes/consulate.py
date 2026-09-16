from fastapi import APIRouter, Depends, HTTPException
from supabase import AsyncClient
from typing import List

from app.database import get_db
from app.models import Tables, UserType
from app.schemas.consulate import ConsulatePostCreate, ConsulatePostUpdate, ConsulatePostResponse
from app.utils.deps import get_current_user

router = APIRouter(prefix="/consulate/posts", tags=["Consulado Brasileiro"])

@router.get("", response_model=List[ConsulatePostResponse])
async def list_public_posts(consulate: str = None, db: AsyncClient = Depends(get_db)):
    """Lista postagens públicas ativas do consulado."""
    query = db.table(Tables.CONSULATE_POSTS).select("*").eq("status", "active")
    if consulate:
        query = query.eq("consulate", consulate.lower())
    
    res = await query.order("created_at", desc=True).execute()
    return res.data

@router.get("/mine", response_model=List[ConsulatePostResponse])
async def list_my_posts(
    current_user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db)
):
    """Lista postagens criadas pela conta do consulado atual."""
    if current_user.get("user_type") != UserType.CONSULATE and not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Acesso restrito a contas do consulado.")
    
    res = await db.table(Tables.CONSULATE_POSTS).select("*").eq("user_id", current_user["id"]).order("created_at", desc=True).execute()
    return res.data

@router.get("/{post_id}", response_model=ConsulatePostResponse)
async def get_post(post_id: str, db: AsyncClient = Depends(get_db)):
    res = await db.table(Tables.CONSULATE_POSTS).select("*").eq("id", post_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Postagem não encontrada.")
    return res.data[0]

@router.post("", response_model=ConsulatePostResponse, status_code=201)
async def create_post(
    payload: ConsulatePostCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db)
):
    """Cria uma nova postagem do consulado (Apenas consulado ou admin)."""
    if current_user.get("user_type") != UserType.CONSULATE and not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Apenas contas oficiais podem publicar aqui.")
        
    data = payload.model_dump(exclude_unset=True)
    
    # Enforce jurisdiction
    if current_user.get("user_type") == UserType.CONSULATE and current_user.get("city"):
        user_consulate = current_user["city"].lower()
        if data.get("consulate") and data["consulate"].lower() != user_consulate:
            raise HTTPException(status_code=403, detail="Você só pode publicar para sua própria jurisdição.")
        data["consulate"] = user_consulate
    
    # Ensure times are serialized properly if needed, pydantic usually handles it to dict, but let's be safe.
    if data.get("event_date"):
        data["event_date"] = data["event_date"].isoformat()
    if data.get("event_time"):
        data["event_time"] = data["event_time"].isoformat()
        
    record = {
        **data,
        "user_id": current_user["id"],
        "is_official": True,
        "status": "active"
    }
    
    res = await db.table(Tables.CONSULATE_POSTS).insert(record).execute()
    return res.data[0]

@router.put("/{post_id}", response_model=ConsulatePostResponse)
async def update_post(
    post_id: str,
    payload: ConsulatePostUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db)
):
    # Verify ownership
    res = await db.table(Tables.CONSULATE_POSTS).select("user_id").eq("id", post_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Postagem não encontrada.")
        
    if res.data[0]["user_id"] != current_user["id"] and not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Você não tem permissão para editar esta postagem.")
        
    data = payload.model_dump(exclude_unset=True)
    if data.get("event_date"):
        data["event_date"] = data["event_date"].isoformat()
    if data.get("event_time"):
        data["event_time"] = data["event_time"].isoformat()
        
    if not data:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar.")
        
    update_res = await db.table(Tables.CONSULATE_POSTS).update(data).eq("id", post_id).execute()
    return update_res.data[0]

@router.delete("/{post_id}", status_code=204)
async def delete_post(
    post_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db)
):
    res = await db.table(Tables.CONSULATE_POSTS).select("user_id").eq("id", post_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Postagem não encontrada.")
        
    if res.data[0]["user_id"] != current_user["id"] and not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Você não tem permissão para apagar esta postagem.")
        
    await db.table(Tables.CONSULATE_POSTS).delete().eq("id", post_id).execute()
