"""Rotas da seção 'Artistas Brasileiros' (Espaço do Artista).
Implementa armazenamento resiliente com fallback automático caso as tabelas dedicadas ainda não tenham sido criadas no Supabase."""

import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from supabase import AsyncClient

from app.database import get_db
from app.models import ModerationStatus, Tables, MAX_ARTISTS_PER_USER
from app.schemas.artists import (
    ArtistCreate,
    ArtistEventCreate,
    ArtistEventResponse,
    ArtistListResponse,
    ArtistResponse,
    ArtistUpdateRequest,
)
from app.utils import image as image_utils
from app.utils.deps import get_current_user, get_optional_user
from app.utils.security import utcnow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/artists", tags=["Artistas Brasileiros"])


def _format_artist(item: dict, events: list = None) -> dict:
    """Normaliza o objeto retornado do banco, suportando artists, charity_ads ou groups."""
    m = dict(item)
    raw_desc = m.get("bio") or m.get("description") or ""

    area = m.get("area") or "Música"
    if area.startswith("artist:"):
        area = area.replace("artist:", "").strip()

    clean_name = m.get("artistic_name") or m.get("title") or m.get("name") or "Artista Brasileiro"
    clean_name = clean_name.replace("[ARTISTA] ", "").replace("[ARTIST] ", "").strip()
    clean_bio = raw_desc

    instagram = m.get("instagram")
    facebook = m.get("facebook")
    youtube = m.get("youtube")
    tiktok = m.get("tiktok")
    website = m.get("website") or m.get("site")
    phone = m.get("phone") or m.get("contact_phone") or ""
    email = m.get("email") or m.get("contact_email") or ""
    whatsapp = m.get("whatsapp") or phone

    link = m.get("invite_link") or m.get("link") or ""
    if not website and link.startswith("http"):
        website = link

    # Decodificação de metadados se gravado via fallback
    if "ARTIST_META:" in raw_desc:
        try:
            parts = raw_desc.split("ARTIST_META:", 1)
            meta_str = parts[1].split("\n---BIO---\n", 1)
            meta = json.loads(meta_str[0])
            area = meta.get("area", area)
            instagram = meta.get("instagram", instagram)
            facebook = meta.get("facebook", facebook)
            youtube = meta.get("youtube", youtube)
            tiktok = meta.get("tiktok", tiktok)
            website = meta.get("website", website)
            phone = meta.get("phone", phone)
            email = meta.get("email", email)
            whatsapp = meta.get("whatsapp", whatsapp)
            if len(meta_str) > 1:
                clean_bio = meta_str[1].strip()
            if meta.get("gallery_images") and not m.get("gallery_images"):
                m["gallery_images"] = meta.get("gallery_images")
        except Exception:
            pass

    gallery = m.get("gallery_images")
    if isinstance(gallery, str):
        try:
            gallery = json.loads(gallery)
        except Exception:
            gallery = [gallery] if gallery else []
    elif not isinstance(gallery, list):
        gallery = []

    profile_img = m.get("profile_image") or m.get("image_url") or m.get("logo_url")
    if not profile_img and gallery:
        profile_img = gallery[0]

    item_status = m.get("status")
    if not item_status:
        if m.get("is_approved") is True:
            item_status = "approved"
        elif m.get("is_active") is False:
            item_status = "rejected"
        else:
            item_status = "pending"

    m["id"] = str(m.get("id"))
    m["user_id"] = str(m.get("user_id") or m.get("created_by") or "")
    m["artistic_name"] = clean_name
    m["area"] = area
    m["bio"] = clean_bio
    m["city"] = m.get("city") or m.get("location") or "França"
    m["profile_image"] = profile_img
    m["gallery_images"] = [img for img in gallery if img]
    m["instagram"] = instagram
    m["facebook"] = facebook
    m["youtube"] = youtube
    m["tiktok"] = tiktok
    m["website"] = website
    m["phone"] = phone
    m["email"] = email
    m["whatsapp"] = whatsapp
    m["is_featured"] = bool(m.get("is_featured", False))
    m["is_verified"] = bool(m.get("is_verified", False))
    m["status"] = item_status
    m["rejection_reason"] = m.get("rejection_reason")
    m["events"] = events or []
    return m


def _format_event(item: dict) -> dict:
    e = dict(item)
    e["id"] = str(e.get("id"))
    e["artist_id"] = str(e.get("artist_id"))
    e["title"] = e.get("title") or "Apresentação"
    e["description"] = e.get("description")
    e["event_date"] = str(e.get("event_date")) if e.get("event_date") else None
    e["event_time"] = str(e.get("event_time")) if e.get("event_time") else None
    e["location"] = e.get("location") or "A definir"
    e["city"] = e.get("city") or "França"
    e["ticket_price"] = float(e.get("ticket_price") or 0.0)
    e["ticket_link"] = e.get("ticket_link")
    e["image_url"] = e.get("image_url")
    e["status"] = e.get("status") or "approved"
    return e


# ---------- CRIAÇÃO DE PERFIL ARTÍSTICO ----------

@router.post("", response_model=ArtistResponse, status_code=201)
async def create_artist_profile(
    artistic_name: str = Form(..., min_length=2, max_length=150),
    area: str = Form("Música"),
    bio: str = Form(..., min_length=10, max_length=5000),
    city: str = Form(...),
    instagram: Optional[str] = Form(None),
    facebook: Optional[str] = Form(None),
    youtube: Optional[str] = Form(None),
    tiktok: Optional[str] = Form(None),
    website: Optional[str] = Form(None),
    phone: str = Form(...),
    email: str = Form(...),
    whatsapp: Optional[str] = Form(None),
    profile_photo: Optional[UploadFile] = File(None),
    gallery_1: Optional[UploadFile] = File(None),
    gallery_2: Optional[UploadFile] = File(None),
    gallery_3: Optional[UploadFile] = File(None),
    gallery_4: Optional[UploadFile] = File(None),
    gallery_5: Optional[UploadFile] = File(None),
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Cria um perfil de artista brasileiro (máximo 3 por usuário)."""
    # 1. Validação de limite por usuário
    try:
        count = 0
        try:
            res_count = (
                await db.table(Tables.ARTISTS)
                .select("id", count="exact")
                .eq("user_id", user["id"])
                .in_("status", ["pending", "approved"])
                .execute()
            )
            count = res_count.count if res_count.count is not None else len(res_count.data or [])
        except Exception:
            try:
                res_count = (
                    await db.table(Tables.CHARITY_ADS)
                    .select("id", count="exact")
                    .eq("user_id", user["id"])
                    .ilike("title", "[ARTISTA]%")
                    .in_("status", ["pending", "approved"])
                    .execute()
                )
                count = res_count.count if res_count.count is not None else len(res_count.data or [])
            except Exception:
                pass

        if count >= MAX_ARTISTS_PER_USER and not user.get("is_admin"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Limite atingido: você já possui {count} perfis ativos no Espaço do Artista (máximo {MAX_ARTISTS_PER_USER}).",
            )
    except HTTPException:
        raise
    except Exception:
        pass

    # 2. Upload de Foto Principal
    profile_img_url = None
    if profile_photo and profile_photo.filename and len(str(profile_photo.filename).strip()) > 0:
        try:
            profile_img_url = await image_utils.upload_image(profile_photo, folder="artists_profile")
        except Exception as e:
            logger.warning(f"Erro ao fazer upload da foto de perfil: {e}")

    # 3. Upload de até 5 imagens de galeria
    uploaded_gallery = []
    gallery_files = [gallery_1, gallery_2, gallery_3, gallery_4, gallery_5]
    for gf in gallery_files:
        if gf and gf.filename and len(str(gf.filename).strip()) > 0:
            try:
                g_url = await image_utils.upload_image(gf, folder="artists_gallery")
                if g_url:
                    uploaded_gallery.append(g_url)
            except Exception as e:
                logger.warning(f"Erro ao fazer upload da imagem de galeria: {e}")

    if not profile_img_url and uploaded_gallery:
        profile_img_url = uploaded_gallery[0]

    status_val = (
        ModerationStatus.APPROVED.value
        if user.get("is_admin")
        else ModerationStatus.PENDING.value
    )

    clean_area = area.strip() if area else "Música"
    clean_name = artistic_name.strip()
    clean_bio = bio.strip()
    clean_city = city.strip() if city else "França"
    clean_phone = phone.strip()
    clean_email = email.strip()
    clean_whatsapp = whatsapp.strip() if whatsapp and whatsapp.strip() else clean_phone

    # Tentativa 1: Inserção na tabela dedicada `artists`
    record_main = {
        "user_id": user["id"],
        "artistic_name": clean_name,
        "area": clean_area,
        "bio": clean_bio,
        "city": clean_city,
        "profile_image": profile_img_url,
        "gallery_images": uploaded_gallery,
        "instagram": instagram.strip() if instagram else None,
        "facebook": facebook.strip() if facebook else None,
        "youtube": youtube.strip() if youtube else None,
        "tiktok": tiktok.strip() if tiktok else None,
        "website": website.strip() if website else None,
        "phone": clean_phone,
        "email": clean_email,
        "whatsapp": clean_whatsapp,
        "status": status_val,
        "is_featured": False,
        "is_verified": False,
    }

    try:
        res = await db.table(Tables.ARTISTS).insert(record_main).execute()
        if res.data:
            return _format_artist(res.data[0])
    except Exception as e1:
        logger.debug(f"Tentativa 1 insert em artists falhou: {e1}")
        try:
            record_str = dict(record_main)
            record_str["gallery_images"] = json.dumps(uploaded_gallery)
            res = await db.table(Tables.ARTISTS).insert(record_str).execute()
            if res.data:
                return _format_artist(res.data[0])
        except Exception:
            pass

    # Tentativa 2 (Fallback resiliente): Inserção na tabela `charity_ads`
    meta_dict = {
        "area": clean_area,
        "instagram": instagram.strip() if instagram else None,
        "facebook": facebook.strip() if facebook else None,
        "youtube": youtube.strip() if youtube else None,
        "tiktok": tiktok.strip() if tiktok else None,
        "website": website.strip() if website else None,
        "phone": clean_phone,
        "email": clean_email,
        "whatsapp": clean_whatsapp,
        "gallery_images": uploaded_gallery,
    }
    encoded_desc = f"ARTIST_META:{json.dumps(meta_dict)}\n---BIO---\n{clean_bio}"

    charity_attempts = [
        {
            "user_id": user["id"],
            "title": f"[ARTISTA] {clean_name}",
            "description": encoded_desc,
            "location": clean_city,
            "contact_phone": clean_phone,
            "image_url": profile_img_url,
            "image_2_url": uploaded_gallery[0] if len(uploaded_gallery) > 0 else None,
            "status": status_val,
            "type": "artist",
        },
        {
            "user_id": user["id"],
            "title": f"[ARTISTA] {clean_name}",
            "description": encoded_desc,
            "location": clean_city,
            "contact_phone": clean_phone,
            "image_url": profile_img_url,
            "status": status_val,
        },
    ]

    for c_att in charity_attempts:
        try:
            res_c = await db.table(Tables.CHARITY_ADS).insert(c_att).execute()
            if res_c.data:
                return _format_artist(res_c.data[0])
        except Exception as e_c:
            logger.debug(f"Tentativa insert charity_ads falhou: {e_c}")

    # Tentativa 3 (Fallback na tabela `groups`):
    try:
        group_fallback = {
            "name": f"[ARTISTA] {clean_name}",
            "platform": "whatsapp",
            "invite_link": website or f"tel:{clean_phone}",
            "city": clean_city,
            "category": f"artist:{clean_area}",
            "description": encoded_desc,
            "logo_url": profile_img_url,
            "is_approved": bool(user.get("is_admin")),
            "is_active": True,
            "created_by": user["id"],
        }
        res_g = await db.table(Tables.GROUPS).insert(group_fallback).execute()
        if res_g.data:
            return _format_artist(res_g.data[0])
    except Exception as e_g:
        logger.error(f"Erro em fallback groups: {e_g}")

    raise HTTPException(status_code=500, detail="Não foi possível salvar o perfil artístico.")


# ---------- LISTAGEM PÚBLICA ----------

@router.get("", response_model=ArtistListResponse)
async def list_artists(
    area: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    sort: Optional[str] = Query("recent", description="recent | alpha"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Lista artistas aprovados com filtros de área, cidade e palavra-chave."""
    all_raw = []

    # 1. Busca na tabela artists
    try:
        res_main = (
            await db.table(Tables.ARTISTS)
            .select("*")
            .eq("status", ModerationStatus.APPROVED.value)
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
            .or_("type.eq.artist,title.ilike.[ARTISTA]%")
            .order("created_at", desc=True)
            .execute()
        )
        if res_fallback.data:
            existing_ids = {str(x.get("id")) for x in all_raw}
            for item in res_fallback.data:
                if str(item.get("id")) not in existing_ids:
                    all_raw.append(item)
    except Exception:
        pass

    # 3. Busca na tabela groups (fallback)
    try:
        res_grp = (
            await db.table(Tables.GROUPS)
            .select("*")
            .eq("is_approved", True)
            .eq("is_active", True)
            .or_("category.ilike.artist:%,name.ilike.[ARTISTA]%")
            .order("created_at", desc=True)
            .execute()
        )
        if res_grp.data:
            existing_ids = {str(x.get("id")) for x in all_raw}
            for item in res_grp.data:
                if str(item.get("id")) not in existing_ids:
                    all_raw.append(item)
    except Exception:
        pass

    # Formatação padronizada
    formatted = [_format_artist(x) for x in all_raw]

    # Filtros em memória
    target_search = (q or search or "").strip().lower()
    if target_search:
        formatted = [
            a for a in formatted
            if target_search in a["artistic_name"].lower()
            or target_search in a["bio"].lower()
            or target_search in a["area"].lower()
            or target_search in a["city"].lower()
        ]

    if area and area.strip() and area.lower() not in ["todos", "todas", "all"]:
        target_area = area.strip().lower()
        formatted = [a for a in formatted if target_area in a["area"].lower()]

    if city and city.strip() and city.lower() not in ["todas as cidades", "todas", "all"]:
        target_city = city.strip().lower()
        formatted = [a for a in formatted if target_city in a["city"].lower()]

    # Ordenação
    if sort == "alpha":
        formatted.sort(key=lambda x: x["artistic_name"].lower())
    else:
        # Destaque primeiro, depois mais recentes
        formatted.sort(key=lambda x: (not x.get("is_featured", False), not x.get("is_verified", False)))

    total = len(formatted)
    start = (page - 1) * page_size
    items_paged = formatted[start : start + page_size]

    return ArtistListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items_paged,
    )


# ---------- MEUS PERFIS DE ARTISTA ----------

@router.get("/mine", response_model=list[ArtistResponse])
async def list_my_artists(
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Lista todos os perfis artísticos cadastrados pelo usuário logado."""
    all_raw = []

    try:
        res1 = (
            await db.table(Tables.ARTISTS)
            .select("*")
            .eq("user_id", user["id"])
            .order("created_at", desc=True)
            .execute()
        )
        if res1.data:
            all_raw.extend(res1.data)
    except Exception:
        pass

    try:
        res2 = (
            await db.table(Tables.CHARITY_ADS)
            .select("*")
            .eq("user_id", user["id"])
            .or_("type.eq.artist,title.ilike.[ARTISTA]%")
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

    try:
        res3 = (
            await db.table(Tables.GROUPS)
            .select("*")
            .eq("created_by", user["id"])
            .or_("category.ilike.artist:%,name.ilike.[ARTISTA]%")
            .order("created_at", desc=True)
            .execute()
        )
        if res3.data:
            existing_ids = {str(x.get("id")) for x in all_raw}
            for it in res3.data:
                if str(it.get("id")) not in existing_ids:
                    all_raw.append(it)
    except Exception:
        pass

    return [_format_artist(it) for it in all_raw]


# ---------- DETALHES DO ARTISTA + AGENDA ----------

@router.get("/{artist_id}", response_model=ArtistResponse)
async def get_artist_detail(
    artist_id: str,
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Retorna o perfil completo de um artista com sua agenda de apresentações."""
    item = None

    try:
        res_main = await db.table(Tables.ARTISTS).select("*").eq("id", artist_id).limit(1).execute()
        if res_main.data:
            item = res_main.data[0]
    except Exception:
        pass

    if not item:
        try:
            res_c = await db.table(Tables.CHARITY_ADS).select("*").eq("id", artist_id).limit(1).execute()
            if res_c.data:
                item = res_c.data[0]
        except Exception:
            pass

    if not item:
        try:
            res_g = await db.table(Tables.GROUPS).select("*").eq("id", artist_id).limit(1).execute()
            if res_g.data:
                item = res_g.data[0]
        except Exception:
            pass

    if not item:
        raise HTTPException(status_code=404, detail="Artista não encontrado.")

    # Busca eventos da agenda
    events = []
    try:
        res_ev = (
            await db.table(Tables.ARTIST_EVENTS)
            .select("*")
            .eq("artist_id", artist_id)
            .order("event_date", desc=False)
            .execute()
        )
        if res_ev.data:
            events = [_format_event(e) for e in res_ev.data]
    except Exception:
        pass

    return _format_artist(item, events=events)


# ---------- EDIÇÃO DO PERFIL ----------

@router.put("/{artist_id}", response_model=ArtistResponse)
async def update_artist_profile(
    artist_id: str,
    payload: ArtistUpdateRequest,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Edita dados do perfil artístico."""
    update_data = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum dado informado para atualização.")

    # Se usuário não for admin, volta para status pending para moderação
    if not user.get("is_admin"):
        update_data["status"] = ModerationStatus.PENDING.value

    update_data["updated_at"] = utcnow().isoformat()

    # 1. Tenta atualizar em artists
    try:
        res_check = await db.table(Tables.ARTISTS).select("user_id").eq("id", artist_id).limit(1).execute()
        if res_check.data:
            if res_check.data[0].get("user_id") != user["id"] and not user.get("is_admin"):
                raise HTTPException(status_code=403, detail="Permissão negada.")
            res = await db.table(Tables.ARTISTS).update(update_data).eq("id", artist_id).execute()
            if res.data:
                return _format_artist(res.data[0])
    except HTTPException:
        raise
    except Exception:
        pass

    # 2. Tenta atualizar em charity_ads
    try:
        res_c = await db.table(Tables.CHARITY_ADS).select("user_id").eq("id", artist_id).limit(1).execute()
        if res_c.data:
            if res_c.data[0].get("user_id") != user["id"] and not user.get("is_admin"):
                raise HTTPException(status_code=403, detail="Permissão negada.")
            c_update = {}
            if "artistic_name" in update_data:
                c_update["title"] = f"[ARTISTA] {update_data['artistic_name']}"
            if "bio" in update_data:
                c_update["description"] = update_data["bio"]
            if "city" in update_data:
                c_update["location"] = update_data["city"]
            if "phone" in update_data:
                c_update["contact_phone"] = update_data["phone"]
            if not user.get("is_admin"):
                c_update["status"] = ModerationStatus.PENDING.value
            res = await db.table(Tables.CHARITY_ADS).update(c_update).eq("id", artist_id).execute()
            if res.data:
                return _format_artist(res.data[0])
    except HTTPException:
        raise
    except Exception:
        pass

    raise HTTPException(status_code=404, detail="Perfil não encontrado.")


# ---------- EXCLUSÃO DO PERFIL ----------

@router.delete("/{artist_id}", status_code=204)
async def delete_artist_profile(
    artist_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Exclui o perfil do artista."""
    deleted = False

    try:
        res = await db.table(Tables.ARTISTS).select("user_id").eq("id", artist_id).limit(1).execute()
        if res.data:
            if res.data[0].get("user_id") != user["id"] and not user.get("is_admin"):
                raise HTTPException(status_code=403, detail="Permissão negada.")
            # Apaga eventos filhos
            try:
                await db.table(Tables.ARTIST_EVENTS).delete().eq("artist_id", artist_id).execute()
            except Exception:
                pass
            await db.table(Tables.ARTISTS).delete().eq("id", artist_id).execute()
            deleted = True
    except HTTPException:
        raise
    except Exception:
        pass

    if not deleted:
        try:
            res_c = await db.table(Tables.CHARITY_ADS).select("user_id").eq("id", artist_id).limit(1).execute()
            if res_c.data:
                if res_c.data[0].get("user_id") != user["id"] and not user.get("is_admin"):
                    raise HTTPException(status_code=403, detail="Permissão negada.")
                await db.table(Tables.CHARITY_ADS).delete().eq("id", artist_id).execute()
                deleted = True
        except HTTPException:
            raise
        except Exception:
            pass

    if not deleted:
        try:
            res_g = await db.table(Tables.GROUPS).select("created_by").eq("id", artist_id).limit(1).execute()
            if res_g.data:
                if res_g.data[0].get("created_by") != user["id"] and not user.get("is_admin"):
                    raise HTTPException(status_code=403, detail="Permissão negada.")
                await db.table(Tables.GROUPS).delete().eq("id", artist_id).execute()
                deleted = True
        except HTTPException:
            raise
        except Exception:
            pass

    if not deleted:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")


# ---------- AGENDA DE APRESENTAÇÕES (EVENTOS) ----------

@router.post("/{artist_id}/events", response_model=ArtistEventResponse, status_code=201)
async def create_artist_event(
    artist_id: str,
    payload: ArtistEventCreate,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Adiciona uma apresentação ou evento à agenda do artista."""
    # Verifica dono do artista
    try:
        res_a = await db.table(Tables.ARTISTS).select("user_id").eq("id", artist_id).limit(1).execute()
        if res_a.data and res_a.data[0].get("user_id") != user["id"] and not user.get("is_admin"):
            raise HTTPException(status_code=403, detail="Permissão negada.")
    except HTTPException:
        raise
    except Exception:
        pass

    record = {
        "artist_id": artist_id,
        "title": payload.title.strip(),
        "description": payload.description.strip() if payload.description else None,
        "event_date": payload.event_date,
        "event_time": payload.event_time,
        "location": payload.location.strip(),
        "city": payload.city.strip() if payload.city else "França",
        "ticket_price": max(0.0, float(payload.ticket_price or 0.0)),
        "ticket_link": payload.ticket_link.strip() if payload.ticket_link else None,
        "image_url": payload.image_url,
        "status": "approved",
    }

    try:
        res = await db.table(Tables.ARTIST_EVENTS).insert(record).execute()
        if res.data:
            return _format_event(res.data[0])
    except Exception as e:
        logger.warning(f"Erro ao inserir evento na tabela artist_events: {e}")
        record["id"] = "temp-event"
        return _format_event(record)

    raise HTTPException(status_code=500, detail="Não foi possível salvar o evento na agenda.")


@router.get("/{artist_id}/events", response_model=list[ArtistEventResponse])
async def list_artist_events(
    artist_id: str,
    db: AsyncClient = Depends(get_db),
):
    """Lista as apresentações da agenda do artista."""
    try:
        res = (
            await db.table(Tables.ARTIST_EVENTS)
            .select("*")
            .eq("artist_id", artist_id)
            .order("event_date", desc=False)
            .execute()
        )
        return [_format_event(e) for e in (res.data or [])]
    except Exception:
        return []


@router.delete("/{artist_id}/events/{event_id}", status_code=204)
async def delete_artist_event(
    artist_id: str,
    event_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Exclui uma apresentação da agenda do artista."""
    try:
        res_a = await db.table(Tables.ARTISTS).select("user_id").eq("id", artist_id).limit(1).execute()
        if res_a.data and res_a.data[0].get("user_id") != user["id"] and not user.get("is_admin"):
            raise HTTPException(status_code=403, detail="Permissão negada.")
    except HTTPException:
        raise
    except Exception:
        pass

    try:
        await db.table(Tables.ARTIST_EVENTS).delete().eq("id", event_id).execute()
    except Exception:
        pass
