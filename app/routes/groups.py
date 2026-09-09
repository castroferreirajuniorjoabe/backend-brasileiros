"""Grupos parceiros (WhatsApp/Facebook): cadastro, listagem e aprovação."""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from supabase import AsyncClient

from app.database import get_db
from app.models import GroupPlatform, ModerationStatus, Tables
from app.schemas.community import GroupResponse
from app.utils import image as image_utils
from app.utils.deps import get_current_user, get_optional_user

router = APIRouter(prefix="/groups", tags=["Grupos Parceiros"])


def _format_group(group: dict) -> dict:
    g = dict(group)
    g["link"] = g.get("invite_link") or g.get("link") or ""
    g["status"] = "approved" if g.get("is_approved") else (g.get("status") or "pending")
    return g


@router.post("", response_model=GroupResponse, status_code=201)
async def create_group(
    request: Request,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Cadastra grupo parceiro (WhatsApp, Facebook ou Telegram)."""
    # Suporta JSON (application/json) ou multipart/form-data
    content_type = request.headers.get("content-type", "")
    logo_url = None
    if "application/json" in content_type:
        body = await request.json()
        name = body.get("name")
        platform_raw = body.get("platform", "whatsapp")
        link = body.get("link") or body.get("invite_link")
        city = body.get("city") or "Toda a França"
        category = body.get("category") or "Comunidade"
        description = body.get("description")
    else:
        form = await request.form()
        name = form.get("name")
        platform_raw = form.get("platform", "whatsapp")
        link = form.get("link") or form.get("invite_link")
        city = form.get("city") or "Toda a França"
        category = form.get("category") or "Comunidade"
        description = form.get("description")
        logo = form.get("logo")
        if logo and hasattr(logo, "filename") and logo.filename:
            try:
                logo_url = await image_utils.upload_image(logo, folder="groups")
            except Exception:
                logo_url = None

    if not name or not link:
        raise HTTPException(status_code=422, detail="Nome e link do grupo são obrigatórios.")

    try:
        platform_val = GroupPlatform(platform_raw.lower()).value
    except Exception:
        platform_val = "whatsapp"

    existing = (
        await db.table(Tables.GROUPS)
        .select("*")
        .eq("invite_link", link)
        .limit(1)
        .execute()
    )
    if existing.data:
        update_fields = {
            "name": name,
            "platform": platform_val,
            "city": city,
            "category": category,
            "description": description,
            "is_approved": True,
            "is_active": True,
        }
        if logo_url:
            update_fields["logo_url"] = logo_url
        upd = await db.table(Tables.GROUPS).update(update_fields).eq("id", existing.data[0]["id"]).execute()
        return _format_group(upd.data[0] if upd.data else existing.data[0])

    record = {
        "name": name,
        "platform": platform_val,
        "invite_link": link,
        "city": city,
        "category": category,
        "description": description,
        "logo_url": logo_url,
        "is_approved": True,  # Aprovado diretamente para visualização imediata
        "is_active": True,
        "created_by": user["id"],
    }
    result = await db.table(Tables.GROUPS).insert(record).execute()
    return _format_group(result.data[0])


@router.get("", response_model=list[GroupResponse])
async def list_groups(
    city: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    platform: Optional[GroupPlatform] = Query(None),
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Lista grupos aprovados com filtros (público). Exclui estritamente mensagens e itens de Chegando na França e Bate-papo."""
    try:
        query = (
            db.table(Tables.GROUPS)
            .select("*")
            .or_("is_approved.eq.true,is_active.eq.true")
            .not_.like("category", "chat:%")
            .not_.like("category", "arrival_%")
            .not_.like("category", "comment_%")
            .not_.like("invite_link", "chat://%")
            .not_.like("invite_link", "comment://%")
            .not_.like("invite_link", "likes:%")
        )
        if city:
            query = query.ilike("city", f"%{city}%")
        if category:
            query = query.eq("category", category)
        if platform:
            query = query.eq("platform", platform.value)
        result = await query.order("created_at", desc=True).execute()
        return [_format_group(g) for g in result.data or []]
    except Exception:
        try:
            query = db.table(Tables.GROUPS).select("*").order("created_at", desc=True)
            result = await query.execute()
            items = []
            for g in result.data or []:
                cat = g.get("category") or ""
                inv = g.get("invite_link") or ""
                if cat.startswith("chat:") or cat.startswith("arrival_") or cat.startswith("comment_"):
                    continue
                if inv.startswith("chat://") or inv.startswith("comment://") or inv.startswith("likes:"):
                    continue
                if city and city.lower() not in (g.get("city") or "").lower():
                    continue
                if category and g.get("category") != category:
                    continue
                if platform and g.get("platform") != platform.value:
                    continue
                items.append(_format_group(g))
            return items
        except Exception:
            return []


@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: str,
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    result = (
        await db.table(Tables.GROUPS).select("*").eq("id", group_id).limit(1).execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Grupo não encontrado.")
    return _format_group(result.data[0])


@router.delete("/{group_id}", status_code=204)
async def delete_group(
    group_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Remove grupo (dono ou admin)."""
    result = (
        await db.table(Tables.GROUPS).select("user_id").eq("id", group_id).limit(1).execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Grupo não encontrado.")
    if result.data[0]["user_id"] != user["id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Sem permissão.")
    await db.table(Tables.GROUPS).delete().eq("id", group_id).execute()
    return None
