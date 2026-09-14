"""Anúncios comerciais: CRUD, moderação, edições limitadas e destaque."""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from supabase import AsyncClient

from app.database import get_db
from app.models import MAX_AD_EDITS_PER_WEEK, AdStatus, Tables
from app.schemas.ads import AdListResponse, AdResponse, AdUpdateRequest
from app.utils import image as image_utils
from app.utils.deps import get_current_verified_user, get_current_user, get_optional_user
from app.utils.security import utcnow

router = APIRouter(prefix="/ads", tags=["Anúncios"])


# ---------- helpers ----------

async def _attach_ratings(db: AsyncClient, ads: list[dict]) -> list[dict]:
    """Agrega média e total de avaliações aos anúncios listados e normaliza type/event_date."""
    if not ads:
        return ads
    ad_ids = [ad["id"] for ad in ads]
    reviews = (
        await db.table(Tables.REVIEWS)
        .select("ad_id, rating")
        .in_("ad_id", ad_ids)
        .execute()
    )
    stats: dict[str, list[int]] = {}
    for r in reviews.data or []:
        stats.setdefault(r["ad_id"], []).append(r["rating"])
    for ad in ads:
        ratings = stats.get(ad["id"], [])
        ad["reviews_count"] = len(ratings)
        ad["average_rating"] = round(sum(ratings) / len(ratings), 2) if ratings else None
        if "image_2_url" in ad and "image_url_2" not in ad:
            ad["image_url_2"] = ad.get("image_2_url")
        if "business_hours" in ad and "opening_hours" not in ad:
            ad["opening_hours"] = ad.get("business_hours")
        # Normalização rigorosa do tipo: 'service' ou 'event'
        if not ad.get("type"):
            if ad.get("category") == "eventos" or ad.get("event_date"):
                ad["type"] = "event"
            else:
                ad["type"] = "service"
    return ads


async def _get_ad_or_404(db: AsyncClient, ad_id: str) -> dict:
    result = (
        await db.table(Tables.ADS).select("*").eq("id", ad_id).limit(1).execute()
    )
    if not result.data or result.data[0].get("status") == AdStatus.DELETED.value:
        raise HTTPException(status_code=404, detail="Anúncio não encontrado.")
    return result.data[0]


# ---------- criação ----------

@router.post("", response_model=AdResponse, status_code=201)
async def create_ad(
    name: str = Form(...),
    address: str = Form(...),
    city: str = Form(...),
    category: str = Form(...),
    type: Optional[str] = Form("service", description="service ou event"),
    event_date: Optional[str] = Form(None, description="Data e hora do evento (se for evento)"),
    phone: str = Form(...),
    landline_phone: Optional[str] = Form(None),
    email: str = Form(...),
    description: str = Form(...),
    website: Optional[str] = Form(None),
    instagram: Optional[str] = Form(None),
    facebook: Optional[str] = Form(None),
    opening_hours: Optional[str] = Form(None),
    image: UploadFile = File(..., description="Imagem principal (obrigatória)"),
    image_2: Optional[UploadFile] = File(None, description="Segunda imagem (opcional)"),
    user: dict = Depends(get_current_verified_user),
    db: AsyncClient = Depends(get_db),
):
    """Cria anúncio comercial (serviço) ou evento temporário."""
    clean_type = "event" if (category == "eventos" or (type and type.strip().lower() == "event")) else "service"
    clean_event_date = event_date.strip() if event_date and clean_type == "event" else None

    image_url = await image_utils.upload_image(image, folder="ads")
    image_url_2 = (
        await image_utils.upload_image(image_2, folder="ads")
        if image_2 and image_2.filename
        else None
    )

    clean_landline = landline_phone.strip() if landline_phone and landline_phone.strip() else None

    record = {
        "user_id": user["id"],
        "name": name,
        "address": address,
        "city": city,
        "category": category,
        "type": clean_type,
        "event_date": clean_event_date,
        "phone": phone,
        "email": email,
        "description": description,
        "website": website,
        "instagram": instagram,
        "facebook": facebook,
        "image_url": image_url,
        "status": AdStatus.APPROVED.value if user.get("is_admin") else AdStatus.PENDING.value,
        "is_highlighted": False,
    }

    # Compatibilidade com colunas do banco
    insert_attempts = [
        {**record, "image_2_url": image_url_2, "business_hours": opening_hours, "landline_phone": clean_landline},
        {**record, "image_url_2": image_url_2, "opening_hours": opening_hours, "landline_phone": clean_landline},
        {**record, "image_2_url": image_url_2, "business_hours": opening_hours},
        {**record, "image_url_2": image_url_2, "opening_hours": opening_hours},
        record,
        # Fallback sem colunas extras se não existirem
        {
            "user_id": user["id"],
            "name": name,
            "address": address,
            "city": city,
            "category": category,
            "phone": phone,
            "email": email,
            "description": description,
            "website": website,
            "instagram": instagram,
            "facebook": facebook,
            "image_url": image_url,
            "status": AdStatus.APPROVED.value if user.get("is_admin") else AdStatus.PENDING.value,
            "is_highlighted": False,
        }
    ]

    result = None
    for attempt in insert_attempts:
        try:
            result = await db.table(Tables.ADS).insert(attempt).execute()
            if result.data:
                break
        except Exception:
            continue

    if not result or not result.data:
        raise HTTPException(status_code=500, detail="Não foi possível salvar o anúncio.")

    ad = result.data[0]
    ad.update({
        "type": clean_type,
        "event_date": clean_event_date,
        "average_rating": None,
        "reviews_count": 0,
        "image_url_2": ad.get("image_2_url") or ad.get("image_url_2"),
        "opening_hours": ad.get("business_hours") or ad.get("opening_hours"),
        "landline_phone": ad.get("landline_phone") or clean_landline,
    })
    return ad


# ---------- listagem pública ----------

@router.get("", response_model=AdListResponse)
async def list_ads(
    type: Optional[str] = Query(None, description="Filtro por tipo: service ou event"),
    city: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Busca por nome/descrição"),
    q: Optional[str] = Query(None, description="Alias para busca"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Lista anúncios aprovados (público). Destacados aparecem primeiro.
    Suporta separação estrita entre serviços contínuos e eventos com data."""
    query = (
        db.table(Tables.ADS)
        .select("*", count="exact")
        .eq("status", AdStatus.APPROVED.value)
    )
    if city:
        query = query.ilike("city", f"%{city}%")
    if category:
        query = query.eq("category", category)
    search_term = (search or q or "").strip()
    if search_term:
        query = query.or_(
            f"name.ilike.%{search_term}%,"
            f"description.ilike.%{search_term}%,"
            f"category.ilike.%{search_term}%,"
            f"city.ilike.%{search_term}%,"
            f"address.ilike.%{search_term}%"
        )

    # Executa consulta ordenada
    start = (page - 1) * page_size
    query = (
        query.order("is_highlighted", desc=True)
        .order("created_at", desc=True)
    )
    result = await query.execute()
    raw_items = await _attach_ratings(db, result.data or [])

    # Filtro em memória robusto para garantir separação de tipos e expiração
    now_cutoff = (utcnow() - timedelta(hours=24)).isoformat()
    filtered_items = []
    for item in raw_items:
        item_type = item.get("type", "service")
        item_category = item.get("category", "")
        item_event_date = item.get("event_date")

        # Se for evento, verificar se não expirou
        if item_type == "event" or item_category == "eventos":
            if item_event_date:
                try:
                    ev_clean = item_event_date.replace("Z", "+00:00")
                    if ev_clean < now_cutoff:
                        continue  # Evento expirado
                except Exception:
                    pass

        # Aplica filtro de tipo solicitado
        if type == "service":
            if item_type == "service" and item_category != "eventos":
                filtered_items.append(item)
        elif type == "event":
            if item_type == "event" or item_category == "eventos":
                filtered_items.append(item)
        else:
            filtered_items.append(item)

    total_count = len(filtered_items)
    paged_items = filtered_items[start : start + page_size]

    return AdListResponse(
        total=total_count, page=page, page_size=page_size, items=paged_items
    )


@router.get("/highlighted", response_model=list[AdResponse])
async def list_highlighted(
    type: Optional[str] = Query(None, description="Filtro por tipo: service ou event"),
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Carrossel de anúncios em destaque (público), respeitando separação de tipo."""
    result = (
        await db.table(Tables.ADS)
        .select("*")
        .eq("status", AdStatus.APPROVED.value)
        .eq("is_highlighted", True)
        .order("created_at", desc=True)
        .execute()
    )
    items = await _attach_ratings(db, result.data or [])
    if type == "service":
        items = [i for i in items if i.get("type") == "service" and i.get("category") != "eventos"]
    elif type == "event":
        items = [i for i in items if i.get("type") == "event" or i.get("category") == "eventos"]
    return items


@router.post("/{ad_id}/highlight", response_model=AdResponse)
async def activate_ad_highlight_free(
    ad_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Ativa o destaque do anúncio gratuitamente para o anunciante (sem checkout/cobrança)."""
    from app.utils.highlights import activate_highlight

    ad = await _get_ad_or_404(db, ad_id)
    if ad["user_id"] != user["id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Você não é o dono deste anúncio.")
    
    updated_ad = await activate_highlight(db, ad_id)
    items = await _attach_ratings(db, [updated_ad])
    return items[0]


@router.get("/mine", response_model=list[AdResponse])
async def list_my_ads(
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Anúncios do usuário autenticado (qualquer status, exceto apagados)."""
    result = (
        await db.table(Tables.ADS)
        .select("*")
        .eq("user_id", user["id"])
        .neq("status", AdStatus.DELETED.value)
        .order("created_at", desc=True)
        .execute()
    )
    return await _attach_ratings(db, result.data or [])


@router.get("/{ad_id}", response_model=AdResponse)
async def get_ad(
    ad_id: str,
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Busca anúncio por ID (público)."""
    ad = await _get_ad_or_404(db, ad_id)
    items = await _attach_ratings(db, [ad])
    return items[0]


# ---------- edição (2/semana, com moderação) ----------

@router.put("/{ad_id}", response_model=AdResponse)
async def update_ad(
    ad_id: str,
    payload: AdUpdateRequest,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Edita anúncio. Limite de 2 edições por semana (últimos 7 dias); toda edição volta para moderação."""
    ad = await _get_ad_or_404(db, ad_id)
    if ad["user_id"] != user["id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Você não é o dono deste anúncio.")

    if not user.get("is_admin"):
        now = utcnow()
        week_start = now - timedelta(days=7)
        try:
            edits = (
                await db.table(Tables.EDIT_HISTORY)
                .select("id", count="exact")
                .eq("ad_id", ad_id)
                .eq("user_id", user["id"])
                .gte("created_at", week_start.isoformat())
                .execute()
            )
            if (edits.count or 0) >= MAX_AD_EDITS_PER_WEEK:
                raise HTTPException(
                    status_code=429,
                    detail=f"Limite de {MAX_AD_EDITS_PER_WEEK} edições na semana atingido. Você pode editar novamente após 7 dias.",
                )
        except HTTPException:
            raise
        except Exception:
            pass  # Se a tabela de histórico não existir ou falhar, permite edição

    changes = {k: (str(v) if v is not None else None)
               for k, v in payload.model_dump(exclude_unset=True).items()}
    if not changes:
        raise HTTPException(status_code=400, detail="Nenhum campo para editar.")

    old_values = {k: ad.get(k) for k in changes}
    try:
        await db.table(Tables.EDIT_HISTORY).insert(
            {
                "ad_id": ad_id,
                "user_id": user["id"],
                "old_data": old_values,
                "new_data": changes,
            }
        ).execute()
    except Exception:
        try:
            await db.table(Tables.EDIT_HISTORY).insert(
                {
                    "ad_id": ad_id,
                    "user_id": user["id"],
                    "old_values": old_values,
                    "new_values": changes,
                }
            ).execute()
        except Exception:
            pass

    # Toda edição passa por moderação manual
    changes["status"] = AdStatus.PENDING.value
    result = (
        await db.table(Tables.ADS).update(changes).eq("id", ad_id).execute()
    )
    updated = result.data[0]
    items = await _attach_ratings(db, [updated])
    return items[0]


@router.delete("/{ad_id}", status_code=204)
async def delete_ad(
    ad_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Apaga o anúncio (dono ou admin)."""
    ad = await _get_ad_or_404(db, ad_id)
    if ad["user_id"] != user["id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Você não é o dono deste anúncio.")
    
    # Exclui diretamente ou marca como deleted se suportado
    try:
        await db.table(Tables.ADS).delete().eq("id", ad_id).execute()
    except Exception:
        await (
            db.table(Tables.ADS)
            .update({"status": "deleted"})
            .eq("id", ad_id)
            .execute()
        )
    return None


# ---------- rotina de expiração de eventos ----------

async def expire_passed_events(db: AsyncClient) -> int:
    """Expira eventos cuja data do evento já passou há mais de 24 horas.
    Anúncios de serviços contínuos/comerciais NUNCA são afetados."""
    try:
        cutoff = (utcnow() - timedelta(hours=24)).isoformat()
        res = (
            await db.table(Tables.ADS)
            .select("id, name, event_date, type, category")
            .in_("status", [AdStatus.APPROVED.value, AdStatus.PENDING.value])
            .execute()
        )
        expired_count = 0
        for item in res.data or []:
            is_event = item.get("type") == "event" or item.get("category") == "eventos"
            ev_date = item.get("event_date")
            if is_event and ev_date:
                try:
                    ev_dt = ev_date.replace("Z", "+00:00")
                    if ev_dt < cutoff:
                        await db.table(Tables.ADS).update({"status": AdStatus.EXPIRED.value}).eq("id", item["id"]).execute()
                        expired_count += 1
                except Exception:
                    pass
        return expired_count
    except Exception:
        return 0


async def run_scheduled_event_expiration() -> None:
    """Ponto de entrada do cron diário para expirar eventos passados."""
    from app.database import get_service_db
    db = await get_service_db()
    await expire_passed_events(db)


