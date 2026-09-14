"""Rotas para Associações e Parceiros: cadastro, listagem, listagem do usuário e moderação.
Implementa armazenamento resiliente com fallback automático caso a tabela dedicada ainda não tenha sido criada no Supabase."""

import logging
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from supabase import AsyncClient

from app.database import get_db
from app.models import ModerationStatus, Tables
from app.schemas.associations import AssociationCreateRequest, AssociationResponse
from app.utils import image as image_utils
from app.utils.deps import get_admin_user, get_current_user, get_optional_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/associations", tags=["Associações e Parceiros"])


def _format_association(item: dict) -> dict:
    """Normaliza campos da associação para o schema de resposta Pydantic."""
    a = dict(item)
    cat = a.get("category") or ""
    assoc_type = a.get("type")
    if not assoc_type and cat.startswith("association:"):
        assoc_type = cat.replace("association:", "").strip()
    
    a["id"] = str(a.get("id"))
    a["type"] = assoc_type or "cultural"
    
    # Se veio de fallback (tabela groups)
    if "is_approved" in a:
        if a.get("is_approved") is True:
            a["status"] = "approved"
        elif a.get("is_active") is False:
            a["status"] = "rejected"
        else:
            a["status"] = "pending"
            
    if "created_by" in a and not a.get("user_id"):
        a["user_id"] = str(a.get("created_by"))
        
    if "invite_link" in a and not a.get("website"):
        link = a.get("invite_link") or ""
        if link.startswith("http") and not link.startswith("https://brasileirosnafranca.com/association"):
            a["website"] = link
        elif link.startswith("mailto:"):
            a["email"] = link.replace("mailto:", "")
        elif link.startswith("tel:"):
            a["phone"] = link.replace("tel:", "")

    a["status"] = a.get("status") or "pending"
    return a


@router.post("", response_model=AssociationResponse, status_code=201)
async def create_association(
    request: Request,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Cadastra uma nova associação/parceiro institucional."""
    content_type = request.headers.get("content-type", "")
    logo_url = None

    if "application/json" in content_type:
        body = await request.json()
        name = str(body.get("name") or "").strip()
        description = str(body.get("description") or "").strip()
        city = str(body.get("city") or "").strip()
        assoc_type = str(body.get("type") or "cultural").strip()
        address = body.get("address")
        phone = body.get("phone")
        email = body.get("email")
        website = body.get("website")
        instagram = body.get("instagram")
        facebook = body.get("facebook")
        logo_url = body.get("logo_url")
    else:
        form = await request.form()
        name = str(form.get("name") or "").strip()
        description = str(form.get("description") or "").strip()
        city = str(form.get("city") or "").strip()
        assoc_type = str(form.get("type") or "cultural").strip()
        address = form.get("address")
        phone = form.get("phone")
        email = form.get("email")
        website = form.get("website")
        instagram = form.get("instagram")
        facebook = form.get("facebook")
        logo_url = form.get("logo_url")
        
        logo = form.get("logo")
        if logo and hasattr(logo, "filename") and logo.filename and len(str(logo.filename).strip()) > 0:
            try:
                logo_url = await image_utils.upload_image(logo, folder="associations")
            except Exception as img_err:
                logger.warning(f"Não foi possível fazer upload do logo: {img_err}")
                logo_url = None

    if not name or not description or not city:
        raise HTTPException(
            status_code=422,
            detail="Nome, descrição e cidade/região são obrigatórios para cadastrar uma associação."
        )

    # Status inicial: aprovado se for admin, ou pendente para moderação
    is_admin = bool(user.get("is_admin"))
    initial_status = ModerationStatus.APPROVED.value if is_admin else ModerationStatus.PENDING.value

    full_record = {
        "user_id": user["id"],
        "name": name,
        "description": description,
        "city": city,
        "type": assoc_type,
        "address": address,
        "phone": phone,
        "email": email,
        "website": website,
        "instagram": instagram,
        "facebook": facebook,
        "logo_url": logo_url,
        "status": initial_status,
        "rejection_reason": None,
    }

    # Tentativa 1: Inserção na tabela dedicada `associations`
    insert_attempts = [
        full_record,
        {
            "user_id": user["id"],
            "name": name,
            "description": description,
            "city": city,
            "type": assoc_type,
            "address": address,
            "phone": phone,
            "email": email,
            "website": website,
            "logo_url": logo_url,
            "status": initial_status,
        },
        {
            "user_id": user["id"],
            "name": name,
            "description": description,
            "city": city,
            "type": assoc_type,
            "status": initial_status,
        }
    ]

    for attempt in insert_attempts:
        try:
            result = await db.table(Tables.ASSOCIATIONS).insert(attempt).execute()
            if result and result.data:
                return _format_association(result.data[0])
        except Exception as e:
            logger.debug(f"Tentativa de insert em associations falhou: {e}")

    # Tentativa 2 (Fallback resiliente): Se a tabela `associations` ainda não existe no Supabase,
    # armazena com segurança na tabela `groups` com categoria `association:<tipo>`
    try:
        contact_link = website or (f"mailto:{email}" if email else None) or (f"tel:{phone}" if phone else None) or f"https://brasileirosnafranca.com/association/{uuid.uuid4().hex[:8]}"
        group_fallback = {
            "name": name,
            "platform": "whatsapp",
            "invite_link": contact_link,
            "city": city,
            "category": f"association:{assoc_type}",
            "description": description,
            "logo_url": logo_url,
            "is_approved": is_admin,
            "is_active": True,
            "created_by": user["id"],
        }
        res_group = await db.table(Tables.GROUPS).insert(group_fallback).execute()
        if res_group and res_group.data:
            item = _format_association(res_group.data[0])
            item["address"] = address
            item["phone"] = phone
            item["email"] = email
            item["website"] = website
            item["instagram"] = instagram
            item["facebook"] = facebook
            return item
    except Exception as e_grp:
        logger.error(f"Fallback em groups também falhou: {e_grp}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao cadastrar associação no banco: {str(e_grp)}"
        )


@router.get("", response_model=list[AssociationResponse])
async def list_associations(
    city: Optional[str] = Query(None, description="Filtro por cidade ou região"),
    type: Optional[str] = Query(None, description="Filtro por tipo de associação"),
    search: Optional[str] = Query(None, description="Busca por nome, descrição ou cidade"),
    q: Optional[str] = Query(None, description="Alias para busca"),
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Lista associações aprovadas (público)."""
    items = []

    # 1. Busca na tabela principal associations
    try:
        query = (
            db.table(Tables.ASSOCIATIONS)
            .select("*")
            .eq("status", ModerationStatus.APPROVED.value)
        )
        if city and city.strip() and city.lower() != "todas as cidades e vilas":
            query = query.ilike("city", f"%{city.strip()}%")
        if type and type.strip() and type.lower() != "todos os tipos":
            query = query.ilike("type", f"%{type.strip()}%")
        search_term = (search or q or "").strip()
        if search_term:
            query = query.or_(
                f"name.ilike.%{search_term}%,"
                f"description.ilike.%{search_term}%,"
                f"city.ilike.%{search_term}%"
            )
        res = await query.order("created_at", desc=True).execute()
        if res.data:
            items.extend([_format_association(it) for it in res.data])
    except Exception:
        pass

    # 2. Busca registros salvos no fallback (groups com category association:*)
    try:
        q_grp = (
            db.table(Tables.GROUPS)
            .select("*")
            .ilike("category", "association:%")
            .eq("is_approved", True)
        )
        if city and city.strip() and city.lower() != "todas as cidades e vilas":
            q_grp = q_grp.ilike("city", f"%{city.strip()}%")
        if type and type.strip() and type.lower() != "todos os tipos":
            q_grp = q_grp.ilike("category", f"association:%{type.strip()}%")
        search_term = (search or q or "").strip()
        if search_term:
            q_grp = q_grp.or_(
                f"name.ilike.%{search_term}%,"
                f"description.ilike.%{search_term}%,"
                f"city.ilike.%{search_term}%"
            )
        res_grp = await q_grp.order("created_at", desc=True).execute()
        for it in (res_grp.data or []):
            if not any(existing["id"] == str(it["id"]) for existing in items):
                items.append(_format_association(it))
    except Exception:
        pass

    return items


@router.get("/mine", response_model=list[AssociationResponse])
async def list_my_associations(
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Lista todas as associações cadastradas pelo usuário logado."""
    items = []

    # 1. Busca na tabela associations
    try:
        res = (
            await db.table(Tables.ASSOCIATIONS)
            .select("*")
            .eq("user_id", user["id"])
            .order("created_at", desc=True)
            .execute()
        )
        if res.data:
            items.extend([_format_association(it) for it in res.data])
    except Exception:
        pass

    # 2. Busca na tabela groups de fallback
    try:
        res_grp = (
            await db.table(Tables.GROUPS)
            .select("*")
            .ilike("category", "association:%")
            .eq("created_by", user["id"])
            .order("created_at", desc=True)
            .execute()
        )
        for it in (res_grp.data or []):
            if not any(existing["id"] == str(it["id"]) for existing in items):
                items.append(_format_association(it))
    except Exception:
        pass

    return items


@router.get("/{association_id}", response_model=AssociationResponse)
async def get_association(
    association_id: str,
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Obtém detalhes de uma associação."""
    try:
        result = (
            await db.table(Tables.ASSOCIATIONS)
            .select("*")
            .eq("id", association_id)
            .limit(1)
            .execute()
        )
        if result.data:
            return _format_association(result.data[0])
    except Exception:
        pass

    try:
        res_grp = (
            await db.table(Tables.GROUPS)
            .select("*")
            .eq("id", association_id)
            .limit(1)
            .execute()
        )
        if res_grp.data:
            return _format_association(res_grp.data[0])
    except Exception:
        pass

    raise HTTPException(status_code=404, detail="Associação não encontrada.")


@router.delete("/{association_id}", status_code=204)
async def delete_association(
    association_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Remove uma associação. Apenas o criador ou administradores podem apagar."""
    is_admin = bool(user.get("is_admin"))

    # Tenta apagar de associations
    try:
        existing = (
            await db.table(Tables.ASSOCIATIONS)
            .select("*")
            .eq("id", association_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            item = existing.data[0]
            if item.get("user_id") != user["id"] and not is_admin:
                raise HTTPException(status_code=403, detail="Sem permissão para excluir esta associação.")
            await db.table(Tables.ASSOCIATIONS).delete().eq("id", association_id).execute()
            return None
    except HTTPException:
        raise
    except Exception:
        pass

    # Tenta apagar de groups fallback
    try:
        existing_grp = (
            await db.table(Tables.GROUPS)
            .select("*")
            .eq("id", association_id)
            .limit(1)
            .execute()
        )
        if existing_grp.data:
            item = existing_grp.data[0]
            if item.get("created_by") != user["id"] and not is_admin:
                raise HTTPException(status_code=403, detail="Sem permissão para excluir esta associação.")
            await db.table(Tables.GROUPS).delete().eq("id", association_id).execute()
            return None
    except HTTPException:
        raise
    except Exception:
        pass

    raise HTTPException(status_code=404, detail="Associação não encontrada.")


@router.post("/{association_id}/approve", response_model=AssociationResponse)
async def approve_association(
    association_id: str,
    admin: dict = Depends(get_admin_user),
    db: AsyncClient = Depends(get_db),
):
    """Aprova uma associação cadastrada (Admin)."""
    try:
        result = (
            await db.table(Tables.ASSOCIATIONS)
            .update({"status": ModerationStatus.APPROVED.value, "rejection_reason": None})
            .eq("id", association_id)
            .execute()
        )
        if result.data:
            return _format_association(result.data[0])
    except Exception:
        pass

    try:
        res_grp = (
            await db.table(Tables.GROUPS)
            .update({"is_approved": True, "is_active": True})
            .eq("id", association_id)
            .execute()
        )
        if res_grp.data:
            return _format_association(res_grp.data[0])
    except Exception:
        pass

    raise HTTPException(status_code=404, detail="Associação não encontrada.")


@router.post("/{association_id}/reject", response_model=AssociationResponse)
async def reject_association(
    association_id: str,
    request: Request,
    admin: dict = Depends(get_admin_user),
    db: AsyncClient = Depends(get_db),
):
    """Rejeita uma associação cadastrada (Admin)."""
    reason = None
    try:
        body = await request.json()
        reason = body.get("reason")
    except Exception:
        pass

    reason_text = reason or "Não atende aos critérios das diretrizes comunitárias."

    try:
        result = (
            await db.table(Tables.ASSOCIATIONS)
            .update({
                "status": ModerationStatus.REJECTED.value,
                "rejection_reason": reason_text
            })
            .eq("id", association_id)
            .execute()
        )
        if result.data:
            return _format_association(result.data[0])
    except Exception:
        pass

    try:
        res_grp = (
            await db.table(Tables.GROUPS)
            .update({"is_approved": False, "is_active": False})
            .eq("id", association_id)
            .execute()
        )
        if res_grp.data:
            item = _format_association(res_grp.data[0])
            item["rejection_reason"] = reason_text
            return item
    except Exception:
        pass

    raise HTTPException(status_code=404, detail="Associação não encontrada.")
