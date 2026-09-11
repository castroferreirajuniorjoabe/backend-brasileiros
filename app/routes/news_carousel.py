"""Módulo do Carrossel de Novidades & Patrocínios (Exclusivo Administrador)."""

import json
from typing import Optional
from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile, File
from supabase import AsyncClient

from app.database import get_db
from app.models import ModerationStatus, Tables
from app.schemas.community import NewsCarouselItem
from app.utils import image as image_utils
from app.utils.deps import get_admin_user, get_optional_user

router = APIRouter(prefix="/news-carousel", tags=["Carrossel de Novidades (Admin)"])

CAROUSEL_PREFIX = "news_banner:"


def _format_news_item(record: dict) -> dict:
    """Padroniza o retorno do item de carrossel."""
    item_id = record.get("id")
    title = record.get("name") or record.get("title") or "Novidade"
    description = record.get("description") or ""
    image_url = record.get("logo_url") or record.get("image_url") or "/assets/bg_hero_modern.jpg"
    link_url = record.get("invite_link") or record.get("link")
    category = record.get("category") or ""
    created_at = record.get("created_at")

    subtitle = description
    button_text = "Saiba Mais"
    badge_tag = "Novidade"
    is_active = record.get("status") == ModerationStatus.APPROVED.value or bool(record.get("is_active", True))
    order_index = 0

    if category.startswith(CAROUSEL_PREFIX):
        try:
            raw_meta = category[len(CAROUSEL_PREFIX):]
            meta = json.loads(raw_meta)
            subtitle = meta.get("subtitle", subtitle)
            button_text = meta.get("button_text", button_text)
            badge_tag = meta.get("badge_tag", badge_tag)
            is_active = meta.get("is_active", is_active)
            order_index = meta.get("order_index", order_index)
        except Exception:
            pass

    return {
        "id": str(item_id),
        "title": title.replace("[NOVIDADE] ", "").strip(),
        "subtitle": subtitle,
        "image_url": image_url,
        "link_url": link_url if link_url and link_url != "#" else None,
        "button_text": button_text,
        "badge_tag": badge_tag,
        "is_active": is_active,
        "order_index": order_index,
        "created_at": created_at,
    }


@router.get("", response_model=list[NewsCarouselItem])
async def list_active_news(
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Lista todos os banners ativos para o carrossel na Home (público)."""
    items = []
    try:
        res = (
            await db.table(Tables.GROUPS)
            .select("*")
            .ilike("category", f"{CAROUSEL_PREFIX}%")
            .execute()
        )
        for row in res.data or []:
            item = _format_news_item(row)
            if item["is_active"]:
                items.append(item)
    except Exception:
        pass

    # Ordena pelo índice de ordenação se definido
    items.sort(key=lambda x: x.get("order_index", 0))
    return items


@router.get("/all", response_model=list[NewsCarouselItem])
async def list_all_news_admin(
    user: dict = Depends(get_admin_user),
    db: AsyncClient = Depends(get_db),
):
    """Lista todos os banners (ativos e inativos) para o painel de administração."""
    items = []
    try:
        res = (
            await db.table(Tables.GROUPS)
            .select("*")
            .ilike("category", f"{CAROUSEL_PREFIX}%")
            .order("created_at", desc=True)
            .execute()
        )
        for row in res.data or []:
            items.append(_format_news_item(row))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar novidades: {str(e)}")

    items.sort(key=lambda x: x.get("order_index", 0))
    return items


@router.post("", response_model=NewsCarouselItem, status_code=201)
async def create_news_banner(
    title: str = Form(...),
    subtitle: Optional[str] = Form(None),
    link_url: Optional[str] = Form(None),
    button_text: Optional[str] = Form("Saiba Mais"),
    badge_tag: Optional[str] = Form("Novidades Chegando"),
    is_active: bool = Form(True),
    order_index: int = Form(0),
    image: Optional[UploadFile] = File(None),
    image_url_direct: Optional[str] = Form(None),
    admin: dict = Depends(get_admin_user),
    db: AsyncClient = Depends(get_db),
):
    """Cria um novo banner de novidade/patrocínio (Exclusivo Administrador)."""
    image_url = None
    if image and image.filename:
        image_url = await image_utils.upload_image(image, folder="banners")
    elif image_url_direct and image_url_direct.strip():
        image_url = image_url_direct.strip()
    else:
        image_url = "/assets/bg_hero_modern.jpg"

    meta_json = json.dumps({
        "subtitle": subtitle.strip() if subtitle else None,
        "button_text": button_text.strip() if button_text else "Saiba Mais",
        "badge_tag": badge_tag.strip() if badge_tag else "Novidades Chegando",
        "is_active": is_active,
        "order_index": order_index,
    })

    record = {
        "created_by": admin["id"],
        "name": f"[NOVIDADE] {title.strip()}",
        "city": "França",
        "category": f"{CAROUSEL_PREFIX}{meta_json}",
        "platform": "whatsapp",
        "invite_link": link_url.strip() if link_url and link_url.strip() else f"banner:{admin['id']}",
        "logo_url": image_url,
        "description": subtitle.strip() if subtitle else "",
        "is_approved": True,
        "is_active": is_active,
        "status": ModerationStatus.APPROVED.value if is_active else ModerationStatus.PENDING.value,
    }

    try:
        res = await db.table(Tables.GROUPS).insert(record).execute()
        if res.data:
            return _format_news_item(res.data[0])
    except Exception as e:
        # Fallback if status column is not present
        try:
            record_fallback = dict(record)
            record_fallback.pop("status", None)
            res = await db.table(Tables.GROUPS).insert(record_fallback).execute()
            if res.data:
                return _format_news_item(res.data[0])
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Erro ao salvar banner: {str(e)}")

    raise HTTPException(status_code=500, detail="Erro desconhecido ao cadastrar banner.")


@router.put("/{banner_id}", response_model=NewsCarouselItem)
async def update_news_banner(
    banner_id: str,
    title: Optional[str] = Form(None),
    subtitle: Optional[str] = Form(None),
    link_url: Optional[str] = Form(None),
    button_text: Optional[str] = Form(None),
    badge_tag: Optional[str] = Form(None),
    is_active: Optional[bool] = Form(None),
    order_index: Optional[int] = Form(None),
    image: Optional[UploadFile] = File(None),
    image_url_direct: Optional[str] = Form(None),
    admin: dict = Depends(get_admin_user),
    db: AsyncClient = Depends(get_db),
):
    """Atualiza um banner existente (Exclusivo Administrador)."""
    res = await db.table(Tables.GROUPS).select("*").eq("id", banner_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Banner não encontrado.")

    existing = res.data[0]
    current_formatted = _format_news_item(existing)

    final_title = title.strip() if title else current_formatted["title"]
    final_subtitle = subtitle.strip() if subtitle is not None else current_formatted["subtitle"]
    final_link = link_url.strip() if link_url is not None else current_formatted["link_url"]
    final_btn = button_text.strip() if button_text else current_formatted["button_text"]
    final_badge = badge_tag.strip() if badge_tag else current_formatted["badge_tag"]
    final_active = is_active if is_active is not None else current_formatted["is_active"]
    final_order = order_index if order_index is not None else current_formatted["order_index"]

    final_image = current_formatted["image_url"]
    if image and image.filename:
        final_image = await image_utils.upload_image(image, folder="banners")
    elif image_url_direct and image_url_direct.strip():
        final_image = image_url_direct.strip()

    meta_json = json.dumps({
        "subtitle": final_subtitle,
        "button_text": final_btn,
        "badge_tag": final_badge,
        "is_active": final_active,
        "order_index": final_order,
    })

    update_payload = {
        "name": f"[NOVIDADE] {final_title}",
        "category": f"{CAROUSEL_PREFIX}{meta_json}",
        "invite_link": final_link.strip() if final_link and final_link.strip() else f"banner:{admin['id']}",
        "logo_url": final_image,
        "description": final_subtitle or "",
        "is_approved": True,
        "is_active": final_active,
        "status": ModerationStatus.APPROVED.value if final_active else ModerationStatus.PENDING.value,
    }

    try:
        updated = await db.table(Tables.GROUPS).update(update_payload).eq("id", banner_id).execute()
        if updated.data:
            return _format_news_item(updated.data[0])
    except Exception as e:
        # Fallback if status column is not present
        try:
            update_fallback = dict(update_payload)
            update_fallback.pop("status", None)
            updated = await db.table(Tables.GROUPS).update(update_fallback).eq("id", banner_id).execute()
            if updated.data:
                return _format_news_item(updated.data[0])
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar banner: {str(e)}")

    raise HTTPException(status_code=500, detail="Erro ao salvar alterações do banner.")


@router.delete("/{banner_id}", status_code=204)
async def delete_news_banner(
    banner_id: str,
    admin: dict = Depends(get_admin_user),
    db: AsyncClient = Depends(get_db),
):
    """Exclui um banner de novidade (Exclusivo Administrador)."""
    try:
        await db.table(Tables.GROUPS).delete().eq("id", banner_id).execute()
        return None
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao apagar banner: {str(e)}")
