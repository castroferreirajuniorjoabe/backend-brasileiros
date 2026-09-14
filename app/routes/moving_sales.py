"""Rotas da seção 'Mudança & Vendas' (Estou de Mudança - Venda de Objetos Pessoais).
Implementa armazenamento resiliente com fallback automático caso a tabela dedicada ainda não tenha sido criada no Supabase."""

import json
import logging
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/moving-sales", tags=["Mudança & Vendas"])


def _format_moving_sale(item: dict) -> dict:
    """Normaliza o objeto retornado do banco, suportando tanto moving_sales quanto o fallback em charity_ads."""
    m = dict(item)
    raw_desc = m.get("description") or ""

    category = m.get("category") or "Móveis"
    condition = m.get("condition") or "usado"
    price = float(m.get("price") or 0.0)
    address = m.get("address")
    phone = m.get("phone") or m.get("contact_phone") or ""

    clean_title = (m.get("title") or m.get("name") or "Item de Mudança")
    clean_title = clean_title.replace("[MUDANÇA] ", "").replace("[MUDANCA] ", "").strip()
    clean_desc = raw_desc

    # Decodificação de metadados se gravado via fallback
    if "MOVING_META:" in raw_desc:
        try:
            parts = raw_desc.split("MOVING_META:", 1)
            meta_str = parts[1].split("\n---DESC---\n", 1)
            meta = json.loads(meta_str[0])
            category = meta.get("category", category)
            condition = meta.get("condition", condition)
            price = float(meta.get("price", price))
            address = meta.get("address", address)
            phone = meta.get("phone", phone)
            if len(meta_str) > 1:
                clean_desc = meta_str[1].strip()
            if meta.get("images") and not m.get("images"):
                m["images"] = meta.get("images")
        except Exception:
            pass

    imgs = m.get("images")
    if isinstance(imgs, str):
        try:
            imgs = json.loads(imgs)
        except Exception:
            imgs = [imgs] if imgs else []
    elif not isinstance(imgs, list):
        imgs = []

    # Fallback para colunas de imagens unitárias
    if not imgs and m.get("image_url"):
        imgs = [m.get("image_url")]
        if m.get("image_url_2") or m.get("image_2_url"):
            imgs.append(m.get("image_url_2") or m.get("image_2_url"))

    m["id"] = str(m.get("id"))
    m["user_id"] = str(m.get("user_id") or "")
    m["title"] = clean_title
    m["description"] = clean_desc
    m["images"] = [img for img in imgs if img]
    m["price"] = price
    m["city"] = m.get("city") or "França"
    m["address"] = address
    m["phone"] = phone
    m["category"] = category
    m["condition"] = condition
    m["status"] = m.get("status") or "pending"
    m["is_available"] = bool(m.get("is_available", True)) and m["status"] != "sold"
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
    """Cria um anúncio de desapego / mudança (com fallback resiliente)."""
    # 1. Validação de limite por usuário
    try:
        count = 0
        try:
            res_count = (
                await db.table(Tables.MOVING_SALES)
                .select("id", count="exact")
                .eq("user_id", user["id"])
                .in_("status", ["pending", "approved"])
                .eq("is_available", True)
                .execute()
            )
            count = res_count.count if res_count.count is not None else len(res_count.data or [])
        except Exception:
            res_count = (
                await db.table(Tables.CHARITY_ADS)
                .select("id", count="exact")
                .eq("user_id", user["id"])
                .ilike("title", "[MUDANÇA]%")
                .in_("status", ["pending", "approved"])
                .execute()
            )
            count = res_count.count if res_count.count is not None else len(res_count.data or [])

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
        if f and f.filename and len(str(f.filename).strip()) > 0:
            try:
                url = await image_utils.upload_image(f, folder="moving_sales")
                if url:
                    uploaded_images.append(url)
            except Exception as e:
                logger.warning(f"Erro ao fazer upload da imagem: {e}")

    status_val = (
        ModerationStatus.APPROVED.value
        if user.get("is_admin")
        else ModerationStatus.PENDING.value
    )

    clean_category = category.strip() if category else "Móveis"
    clean_condition = condition.strip().lower() if condition else "usado"
    clean_price = max(0.0, float(price))
    clean_address = address.strip() if address and address.strip() else None

    # Tentativa 1: Inserção na tabela dedicada `moving_sales`
    record = {
        "user_id": user["id"],
        "title": title.strip(),
        "description": description.strip(),
        "category": clean_category,
        "condition": clean_condition,
        "price": clean_price,
        "city": city.strip(),
        "address": clean_address,
        "phone": phone.strip(),
        "images": uploaded_images,
        "status": status_val,
        "is_available": True,
    }

    try:
        res = await db.table(Tables.MOVING_SALES).insert(record).execute()
        if res.data:
            return _format_moving_sale(res.data[0])
    except Exception as e1:
        logger.debug(f"Tentativa 1 insert em moving_sales falhou: {e1}")
        try:
            record_str = dict(record)
            record_str["images"] = json.dumps(uploaded_images)
            res = await db.table(Tables.MOVING_SALES).insert(record_str).execute()
            if res.data:
                return _format_moving_sale(res.data[0])
        except Exception:
            pass

    # Tentativa 2 (Fallback resiliente): Inserção na tabela `charity_ads`
    meta_dict = {
        "category": clean_category,
        "condition": clean_condition,
        "price": clean_price,
        "address": clean_address,
        "phone": phone.strip(),
        "images": uploaded_images,
    }
    encoded_desc = f"MOVING_META:{json.dumps(meta_dict)}\n---DESC---\n{description.strip()}"

    charity_record = {
        "user_id": user["id"],
        "title": f"[MUDANÇA] {title.strip()}",
        "description": encoded_desc,
        "city": city.strip(),
        "contact_phone": phone.strip(),
        "image_url": uploaded_images[0] if len(uploaded_images) > 0 else None,
        "image_url_2": uploaded_images[1] if len(uploaded_images) > 1 else None,
        "status": status_val,
        "type": "moving_sale",
    }

    try:
        res_charity = await db.table(Tables.CHARITY_ADS).insert(charity_record).execute()
        if res_charity.data:
            return _format_moving_sale(res_charity.data[0])
    except Exception as e2:
        try:
            charity_simple = {
                "user_id": user["id"],
                "title": f"[MUDANÇA] {title.strip()}",
                "description": encoded_desc,
                "city": city.strip(),
                "contact_phone": phone.strip(),
                "image_url": uploaded_images[0] if len(uploaded_images) > 0 else None,
                "image_url_2": uploaded_images[1] if len(uploaded_images) > 1 else None,
                "status": status_val,
            }
            res_simple = await db.table(Tables.CHARITY_ADS).insert(charity_simple).execute()
            if res_simple.data:
                return _format_moving_sale(res_simple.data[0])
        except Exception as e3:
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao salvar anúncio de mudança: {str(e3)}",
            )

    raise HTTPException(status_code=500, detail="Não foi possível criar o anúncio de mudança.")


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
    all_raw = []

    # 1. Busca na tabela moving_sales
    try:
        res_main = (
            await db.table(Tables.MOVING_SALES)
            .select("*")
            .eq("status", ModerationStatus.APPROVED.value)
            .eq("is_available", True)
            .order("created_at", desc=True)
            .execute()
        )
        if res_main.data:
            all_raw.extend(res_main.data)
    except Exception:
        pass

    # 2. Busca na tabela charity_ads (fallback)
    try:
        res_fallback = (
            await db.table(Tables.CHARITY_ADS)
            .select("*")
            .eq("status", ModerationStatus.APPROVED.value)
            .or_("type.eq.moving_sale,title.ilike.[MUDANÇA]%")
            .order("created_at", desc=True)
            .execute()
        )
        if res_fallback.data:
            # Evita duplicatas se algum ID já veio da tabela principal
            existing_ids = {str(x.get("id")) for x in all_raw}
            for item in res_fallback.data:
                if str(item.get("id")) not in existing_ids:
                    all_raw.append(item)
    except Exception:
        pass

    # Formatação padronizada
    formatted = [_format_moving_sale(x) for x in all_raw]

    # Filtros em memória
    search_term = (search or q or "").strip().lower()
    cat_filter = category.strip().lower() if category else None
    city_filter = city.strip().lower() if city else None
    cond_filter = condition.strip().lower() if condition else None

    filtered = []
    for it in formatted:
        if not it.get("is_available"):
            continue
        if cat_filter and cat_filter not in (it.get("category") or "").lower():
            continue
        if city_filter and city_filter not in (it.get("city") or "").lower():
            continue
        if cond_filter and cond_filter != (it.get("condition") or "").lower():
            continue
        if search_term:
            in_title = search_term in (it.get("title") or "").lower()
            in_desc = search_term in (it.get("description") or "").lower()
            in_city = search_term in (it.get("city") or "").lower()
            in_cat = search_term in (it.get("category") or "").lower()
            if not (in_title or in_desc or in_city or in_cat):
                continue
        filtered.append(it)

    # Ordenação
    if sort == "price_asc":
        filtered.sort(key=lambda x: (x.get("price", 0.0), x.get("created_at") or ""))
    elif sort == "price_desc":
        filtered.sort(key=lambda x: (x.get("price", 0.0)), reverse=True)
    else:
        filtered.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    total_count = len(filtered)
    start = (page - 1) * page_size
    paged = filtered[start : start + page_size]

    return MovingSaleListResponse(
        total=total_count,
        page=page,
        page_size=page_size,
        items=paged,
    )


# ---------- MEUS ANÚNCIOS ----------

@router.get("/mine", response_model=list[MovingSaleResponse])
async def list_my_moving_sales(
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Lista todos os anúncios de mudança do usuário autenticado."""
    all_raw = []
    try:
        res1 = await db.table(Tables.MOVING_SALES).select("*").eq("user_id", user["id"]).order("created_at", desc=True).execute()
        if res1.data:
            all_raw.extend(res1.data)
    except Exception:
        pass

    try:
        res2 = (
            await db.table(Tables.CHARITY_ADS)
            .select("*")
            .eq("user_id", user["id"])
            .or_("type.eq.moving_sale,title.ilike.[MUDANÇA]%")
            .order("created_at", desc=True)
            .execute()
        )
        if res2.data:
            existing_ids = {str(x.get("id")) for x in all_raw}
            for it in res2.data:
                if str(it.get("id")) not in existing_ids:
                    all_raw.append(it)
    except Exception:
        pass

    return [_format_moving_sale(it) for it in all_raw]


# ---------- DETALHES DO ANÚNCIO ----------

@router.get("/{sale_id}", response_model=MovingSaleResponse)
async def get_moving_sale_detail(
    sale_id: str,
    db: AsyncClient = Depends(get_db),
    visitor: dict | None = Depends(get_optional_user),
):
    """Retorna detalhes de um anúncio de mudança."""
    item = None
    try:
        res = await db.table(Tables.MOVING_SALES).select("*").eq("id", sale_id).limit(1).execute()
        if res.data:
            item = res.data[0]
    except Exception:
        pass

    if not item:
        try:
            res_fallback = await db.table(Tables.CHARITY_ADS).select("*").eq("id", sale_id).limit(1).execute()
            if res_fallback.data:
                item = res_fallback.data[0]
        except Exception:
            pass

    if not item:
        raise HTTPException(status_code=404, detail="Anúncio de mudança não encontrado.")

    formatted = _format_moving_sale(item)

    # Se não estiver aprovado, somente o dono ou admin pode ver
    if formatted.get("status") != ModerationStatus.APPROVED.value:
        if not visitor or (visitor["id"] != formatted.get("user_id") and not visitor.get("is_admin")):
            raise HTTPException(status_code=403, detail="Este anúncio está aguardando moderação.")

    # Busca nome/avatar do vendedor
    if formatted.get("user_id"):
        try:
            u_res = await db.table(Tables.USERS).select("name, avatar_url").eq("id", formatted["user_id"]).limit(1).execute()
            if u_res.data:
                formatted["user_name"] = u_res.data[0].get("name")
                formatted["user_avatar"] = u_res.data[0].get("avatar_url")
        except Exception:
            pass

    return formatted


# ---------- MARCAR COMO VENDIDO ----------

@router.post("/{sale_id}/mark-sold", response_model=MovingSaleResponse)
async def mark_moving_sale_as_sold(
    sale_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Marca o anúncio como vendido."""
    # 1. Tenta atualizar em moving_sales
    try:
        res = await db.table(Tables.MOVING_SALES).select("*").eq("id", sale_id).limit(1).execute()
        if res.data:
            existing = res.data[0]
            if existing.get("user_id") != user["id"] and not user.get("is_admin"):
                raise HTTPException(status_code=403, detail="Permissão negada.")
            up_res = await db.table(Tables.MOVING_SALES).update({
                "is_available": False,
                "status": "sold",
                "updated_at": utcnow().isoformat(),
            }).eq("id", sale_id).execute()
            if up_res.data:
                return _format_moving_sale(up_res.data[0])
    except HTTPException:
        raise
    except Exception:
        pass

    # 2. Tenta atualizar em charity_ads
    try:
        res_charity = await db.table(Tables.CHARITY_ADS).select("*").eq("id", sale_id).limit(1).execute()
        if res_charity.data:
            existing = res_charity.data[0]
            if existing.get("user_id") != user["id"] and not user.get("is_admin"):
                raise HTTPException(status_code=403, detail="Permissão negada.")
            up_charity = await db.table(Tables.CHARITY_ADS).update({"status": "sold"}).eq("id", sale_id).execute()
            if up_charity.data:
                return _format_moving_sale(up_charity.data[0])
    except HTTPException:
        raise
    except Exception:
        pass

    raise HTTPException(status_code=404, detail="Anúncio não encontrado.")


# ---------- EXCLUSÃO ----------

@router.delete("/{sale_id}", status_code=204)
async def delete_moving_sale(
    sale_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Exclui permanentemente o anúncio de mudança."""
    deleted = False
    try:
        res = await db.table(Tables.MOVING_SALES).select("user_id").eq("id", sale_id).limit(1).execute()
        if res.data:
            if res.data[0].get("user_id") != user["id"] and not user.get("is_admin"):
                raise HTTPException(status_code=403, detail="Permissão negada.")
            await db.table(Tables.MOVING_SALES).delete().eq("id", sale_id).execute()
            deleted = True
    except HTTPException:
        raise
    except Exception:
        pass

    if not deleted:
        try:
            res_c = await db.table(Tables.CHARITY_ADS).select("user_id").eq("id", sale_id).limit(1).execute()
            if res_c.data:
                if res_c.data[0].get("user_id") != user["id"] and not user.get("is_admin"):
                    raise HTTPException(status_code=403, detail="Permissão negada.")
                await db.table(Tables.CHARITY_ADS).delete().eq("id", sale_id).execute()
                deleted = True
        except HTTPException:
            raise
        except Exception:
            pass

    if not deleted:
        raise HTTPException(status_code=404, detail="Anúncio não encontrado.")

    return None
