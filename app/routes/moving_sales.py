"""Rotas da seção 'Mudança & Vendas' (Estou de Mudança - Venda de Objetos Pessoais)."""

import json
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from supabase import AsyncClient

from app.database import get_db
from app.models import ModerationStatus, Tables, MAX_MOVING_SALES_PER_USER
from app.schemas.moving_sales import (
    MovingSaleListResponse,
    MovingSaleResponse,
    MovingSaleUpdateRequest,
)
from app.utils import image as image_utils
from app.utils.deps import get_current_user, get_optional_user
from app.utils.security import utcnow

router = APIRouter(prefix="/moving-sales", tags=["Mudança & Vendas"])


def _format_moving_sale(item: dict) -> dict:
    """Normaliza o objeto retornado do banco."""
    m = dict(item)
    # Garante que images seja uma lista de URLs
    imgs = m.get("images")
    if isinstance(imgs, str):
        try:
            imgs = json.loads(imgs)
        except Exception:
            imgs = [imgs] if imgs else []
    elif not isinstance(imgs, list):
        imgs = []
    
    # Fallback para colunas legadas se existirem
    if not imgs and m.get("image_url"):
        imgs = [m.get("image_url")]
        if m.get("image_url_2") or m.get("image_2_url"):
            imgs.append(m.get("image_url_2") or m.get("image_2_url"))
            
    m["images"] = [img for img in imgs if img]
    m["price"] = float(m.get("price") or 0.0)
    m["is_available"] = bool(m.get("is_available", True))
    m["category"] = m.get("category") or "Móveis"
    m["condition"] = m.get("condition") or "usado"
    m["status"] = m.get("status") or "pending"
    return m


# ---------- CRIAÇÃO ----------

@router.post("", response_model=MovingSaleResponse, status_code=201)
async def create_moving_sale(
    title: str = Form(..., min_length=3, max_length=150),
    description: str = Form(..., min_length=10, max_length=5000),
    category: str = Form("Móveis"),
    condition: str = Form("usado"),  # novo, seminovo, usado
    price: float = Form(0.0),
    city: str = Form(...),
    address: Optional[str] = Form(None),
    phone: str = Form(...),
    image_1: Optional[UploadFile] = File(None),
    image_2: Optional[UploadFile] = File(None),
    image_3: Optional[UploadFile] = File(None),
    image_4: Optional[UploadFile] = File(None),
    image_5: Optional[UploadFile] = File(None),
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Cria um anúncio de desapego / mudança (limite de 5 anúncios ativos por usuário)."""
    # 1. Validação de limite por usuário
    try:
        user_active_ads = (
            await db.table(Tables.MOVING_SALES)
            .select("id", count="exact")
            .eq("user_id", user["id"])
            .in_("status", ["pending", "approved"])
            .eq("is_available", True)
            .execute()
        )
        count = user_active_ads.count if user_active_ads.count is not None else len(user_active_ads.data or [])
        if count >= MAX_MOVING_SALES_PER_USER and not user.get("is_admin"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Limite atingido: você já possui {count} anúncios ativos em Mudança & Vendas (máximo {MAX_MOVING_SALES_PER_USER}).",
            )
    except HTTPException:
        raise
    except Exception:
        pass

    # 2. Upload de até 5 imagens
    uploaded_images = []
    files = [image_1, image_2, image_3, image_4, image_5]
    for f in files:
        if f and f.filename:
            try:
                url = await image_utils.upload_image(f, folder="moving_sales")
                if url:
                    uploaded_images.append(url)
            except Exception:
                pass

    status_val = (
        ModerationStatus.APPROVED.value
        if user.get("is_admin")
        else ModerationStatus.PENDING.value
    )

    record = {
        "user_id": user["id"],
        "title": title.strip(),
        "description": description.strip(),
        "category": category.strip() if category else "Móveis",
        "condition": condition.strip().lower() if condition else "usado",
        "price": max(0.0, float(price)),
        "city": city.strip(),
        "address": address.strip() if address and address.strip() else None,
        "phone": phone.strip(),
        "images": uploaded_images,
        "status": status_val,
        "is_available": True,
    }

    try:
        res = await db.table(Tables.MOVING_SALES).insert(record).execute()
        if res.data:
            return _format_moving_sale(res.data[0])
    except Exception as err:
        # Fallback se images for coluna de tipo diferente
        try:
            record_fallback = dict(record)
            record_fallback["images"] = json.dumps(uploaded_images)
            res = await db.table(Tables.MOVING_SALES).insert(record_fallback).execute()
            if res.data:
                return _format_moving_sale(res.data[0])
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao salvar anúncio de mudança: {str(err)}",
            )

    raise HTTPException(status_code=500, detail="Não foi possível criar o anúncio.")


# ---------- LISTAGEM PÚBLICA ----------

@router.get("", response_model=MovingSaleListResponse)
async def list_moving_sales(
    category: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    condition: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    sort: Optional[str] = Query("recent", description="recent | price_asc | price_desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Lista anúncios de mudança aprovados e disponíveis."""
    query = (
        db.table(Tables.MOVING_SALES)
        .select("*", count="exact")
        .eq("status", ModerationStatus.APPROVED.value)
        .eq("is_available", True)
    )

    if category:
        query = query.ilike("category", f"%{category.strip()}%")
    if city:
        query = query.ilike("city", f"%{city.strip()}%")
    if condition:
        query = query.eq("condition", condition.strip().lower())

    search_term = (search or q or "").strip()
    if search_term:
        query = query.or_(
            f"title.ilike.%{search_term}%,"
            f"description.ilike.%{search_term}%,"
            f"category.ilike.%{search_term}%,"
            f"city.ilike.%{search_term}%"
        )

    # Ordenação
    if sort == "price_asc":
        query = query.order("price", desc=False).order("created_at", desc=True)
    elif sort == "price_desc":
        query = query.order("price", desc=True).order("created_at", desc=True)
    else:
        query = query.order("created_at", desc=True)

    start = (page - 1) * page_size
    query = query.range(start, start + page_size - 1)

    result = await query.execute()
    items = [_format_moving_sale(it) for it in (result.data or [])]
    total_count = result.count if result.count is not None else len(items)

    return MovingSaleListResponse(
        total=total_count,
        page=page,
        page_size=page_size,
        items=items,
    )


# ---------- MEUS ANÚNCIOS ----------

@router.get("/mine", response_model=list[MovingSaleResponse])
async def list_my_moving_sales(
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Lista todos os anúncios de mudança do usuário autenticado (incluindo pendentes e vendidos)."""
    result = (
        await db.table(Tables.MOVING_SALES)
        .select("*")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .execute()
    )
    return [_format_moving_sale(it) for it in (result.data or [])]


# ---------- DETALHES DO ANÚNCIO ----------

@router.get("/{sale_id}", response_model=MovingSaleResponse)
async def get_moving_sale_detail(
    sale_id: str,
    db: AsyncClient = Depends(get_db),
    visitor: dict | None = Depends(get_optional_user),
):
    """Retorna detalhes de um anúncio de mudança."""
    res = await db.table(Tables.MOVING_SALES).select("*").eq("id", sale_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Anúncio de mudança não encontrado.")

    item = res.data[0]
    # Se não estiver aprovado, somente o dono ou admin pode ver
    if item.get("status") != ModerationStatus.APPROVED.value:
        if not visitor or (visitor["id"] != item.get("user_id") and not visitor.get("is_admin")):
            raise HTTPException(status_code=403, detail="Este anúncio está aguardando moderação.")

    formatted = _format_moving_sale(item)

    # Busca nome/avatar do vendedor se disponível
    try:
        u_res = await db.table(Tables.USERS).select("name, avatar_url").eq("id", item.get("user_id")).limit(1).execute()
        if u_res.data:
            formatted["user_name"] = u_res.data[0].get("name")
            formatted["user_avatar"] = u_res.data[0].get("avatar_url")
    except Exception:
        pass

    return formatted


# ---------- EDIÇÃO ----------

@router.put("/{sale_id}", response_model=MovingSaleResponse)
async def update_moving_sale(
    sale_id: str,
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    condition: Optional[str] = Form(None),
    price: Optional[float] = Form(None),
    city: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    existing_images: Optional[str] = Form(None),  # JSON array de imagens já salvas
    image_1: Optional[UploadFile] = File(None),
    image_2: Optional[UploadFile] = File(None),
    image_3: Optional[UploadFile] = File(None),
    image_4: Optional[UploadFile] = File(None),
    image_5: Optional[UploadFile] = File(None),
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Edita anúncio de mudança (se for usuário comum, volta para status pendente)."""
    res = await db.table(Tables.MOVING_SALES).select("*").eq("id", sale_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Anúncio não encontrado.")

    existing = res.data[0]
    is_owner = existing.get("user_id") == user["id"]
    is_admin = bool(user.get("is_admin"))

    if not is_owner and not is_admin:
        raise HTTPException(status_code=403, detail="Permissão negada.")

    # Processar imagens mantidas
    kept_images = []
    if existing_images:
        try:
            parsed = json.loads(existing_images)
            if isinstance(parsed, list):
                kept_images = [str(x) for x in parsed if x]
        except Exception:
            kept_images = [existing_images]

    # Processar novas imagens enviadas
    new_files = [image_1, image_2, image_3, image_4, image_5]
    for f in new_files:
        if f and f.filename and len(kept_images) < 5:
            try:
                url = await image_utils.upload_image(f, folder="moving_sales")
                if url:
                    kept_images.append(url)
            except Exception:
                pass

    updates = {
        "updated_at": utcnow().isoformat(),
    }
    if title is not None:
        updates["title"] = title.strip()
    if description is not None:
        updates["description"] = description.strip()
    if category is not None:
        updates["category"] = category.strip()
    if condition is not None:
        updates["condition"] = condition.strip().lower()
    if price is not None:
        updates["price"] = max(0.0, float(price))
    if city is not None:
        updates["city"] = city.strip()
    if address is not None:
        updates["address"] = address.strip() if address.strip() else None
    if phone is not None:
        updates["phone"] = phone.strip()
    if kept_images:
        updates["images"] = kept_images

    # Se editado por usuário comum, volta para moderação
    if not is_admin:
        updates["status"] = ModerationStatus.PENDING.value

    try:
        up_res = await db.table(Tables.MOVING_SALES).update(updates).eq("id", sale_id).execute()
        if up_res.data:
            return _format_moving_sale(up_res.data[0])
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar anúncio: {str(err)}")

    raise HTTPException(status_code=500, detail="Não foi possível atualizar o anúncio.")


# ---------- MARCAR COMO VENDIDO ----------

@router.post("/{sale_id}/mark-sold", response_model=MovingSaleResponse)
async def mark_moving_sale_as_sold(
    sale_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Marca o anúncio como vendido (o item deixa de aparecer na listagem pública)."""
    res = await db.table(Tables.MOVING_SALES).select("*").eq("id", sale_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Anúncio não encontrado.")

    existing = res.data[0]
    if existing.get("user_id") != user["id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Permissão negada.")

    updates = {
        "is_available": False,
        "status": "sold",
        "updated_at": utcnow().isoformat(),
    }
    up_res = await db.table(Tables.MOVING_SALES).update(updates).eq("id", sale_id).execute()
    if not up_res.data:
        raise HTTPException(status_code=500, detail="Erro ao marcar anúncio como vendido.")

    return _format_moving_sale(up_res.data[0])


# ---------- EXCLUSÃO ----------

@router.delete("/{sale_id}", status_code=204)
async def delete_moving_sale(
    sale_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Exclui permanentemente o anúncio de mudança."""
    res = await db.table(Tables.MOVING_SALES).select("*").eq("id", sale_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Anúncio não encontrado.")

    existing = res.data[0]
    if existing.get("user_id") != user["id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Permissão negada.")

    await db.table(Tables.MOVING_SALES).delete().eq("id", sale_id).execute()
    return None
