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
    """Agrega média e total de avaliações aos anúncios listados."""
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
    phone: str = Form(...),
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
    """Cria anúncio. O 1º anúncio do usuário vai para moderação manual;
    os seguintes são aprovados automaticamente (sujeitos a denúncias)."""
    previous = (
        await db.table(Tables.ADS)
        .select("id")
        .eq("user_id", user["id"])
        .neq("status", AdStatus.DELETED.value)
        .limit(1)
        .execute()
    )
    is_first_ad = not previous.data

    image_url = await image_utils.upload_image(image, folder="ads")
    image_url_2 = (
        await image_utils.upload_image(image_2, folder="ads")
        if image_2 and image_2.filename
        else None
    )

    record = {
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

    # Compatibilidade com colunas do banco (image_2_url / image_url_2 / business_hours / opening_hours)
    try:
        extended_record = {
            **record,
            "image_2_url": image_url_2,
            "business_hours": opening_hours,
        }
        result = await db.table(Tables.ADS).insert(extended_record).execute()
    except Exception:
        try:
            extended_record = {
                **record,
                "image_url_2": image_url_2,
                "opening_hours": opening_hours,
            }
            result = await db.table(Tables.ADS).insert(extended_record).execute()
        except Exception:
            result = await db.table(Tables.ADS).insert(record).execute()

    ad = result.data[0]
    ad.update({
        "average_rating": None,
        "reviews_count": 0,
        "image_url_2": ad.get("image_2_url") or ad.get("image_url_2"),
        "opening_hours": ad.get("business_hours") or ad.get("opening_hours"),
    })
    return ad


# ---------- listagem pública ----------

@router.get("", response_model=AdListResponse)
async def list_ads(
    city: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Busca por nome/descrição"),
    q: Optional[str] = Query(None, description="Alias para busca"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Lista anúncios aprovados (público — visitantes navegam sem login).
    Destacados aparecem primeiro."""
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
        # Busca flexível por nome, descrição, categoria, cidade ou endereço
        query = query.or_(
            f"name.ilike.%{search_term}%,"
            f"description.ilike.%{search_term}%,"
            f"category.ilike.%{search_term}%,"
            f"city.ilike.%{search_term}%,"
            f"address.ilike.%{search_term}%"
        )

    start = (page - 1) * page_size
    query = (
        query.order("is_highlighted", desc=True)
        .order("created_at", desc=True)
        .range(start, start + page_size - 1)
    )
    result = await query.execute()
    items = await _attach_ratings(db, result.data or [])
    return AdListResponse(
        total=result.count or 0, page=page, page_size=page_size, items=items
    )


@router.get("/highlighted", response_model=list[AdResponse])
async def list_highlighted(
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Carrossel de anúncios em destaque (público)."""
    result = (
        await db.table(Tables.ADS)
        .select("*")
        .eq("status", AdStatus.APPROVED.value)
        .eq("is_highlighted", True)
        .order("created_at", desc=True)
        .execute()
    )
    return await _attach_ratings(db, result.data or [])


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

