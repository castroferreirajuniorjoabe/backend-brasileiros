"""Rotas para Associações e Parceiros: cadastro, listagem, listagem do usuário e moderação."""

from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from supabase import AsyncClient

from app.database import get_db
from app.models import ModerationStatus, Tables
from app.schemas.associations import AssociationCreateRequest, AssociationResponse
from app.utils import image as image_utils
from app.utils.deps import get_admin_user, get_current_user, get_optional_user
from app.utils.security import utcnow

router = APIRouter(prefix="/associations", tags=["Associações e Parceiros"])


def _format_association(item: dict) -> dict:
    """Normaliza campos da associação para o schema de resposta."""
    a = dict(item)
    a["type"] = a.get("type") or "cultural"
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
        name = (body.get("name") or "").strip()
        description = (body.get("description") or "").strip()
        city = (body.get("city") or "").strip()
        assoc_type = (body.get("type") or "cultural").strip()
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
        if logo and hasattr(logo, "filename") and logo.filename:
            try:
                logo_url = await image_utils.upload_image(logo, folder="associations")
            except Exception:
                pass

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

    # Tentativas resilientes de inserção no banco de dados
    insert_attempts = [
        full_record,
        # Sem redes sociais / campos opcionais se colunas não existirem
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
        # Mínimo essencial
        {
            "user_id": user["id"],
            "name": name,
            "description": description,
            "city": city,
            "type": assoc_type,
            "status": initial_status,
        }
    ]

    result = None
    last_error = None
    for attempt in insert_attempts:
        try:
            result = await db.table(Tables.ASSOCIATIONS).insert(attempt).execute()
            if result and result.data:
                break
        except Exception as e:
            last_error = e

    if not result or not result.data:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao cadastrar associação no banco: {str(last_error)}"
        )

    return _format_association(result.data[0])


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

        result = await query.order("created_at", desc=True).execute()
        return [_format_association(item) for item in (result.data or [])]
    except Exception:
        # Fallback gracioso se a tabela ainda não tiver sido criada
        return []


@router.get("/mine", response_model=list[AssociationResponse])
async def list_my_associations(
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Lista todas as associações cadastradas pelo usuário logado (pendentes, aprovadas e rejeitadas)."""
    try:
        result = (
            await db.table(Tables.ASSOCIATIONS)
            .select("*")
            .eq("user_id", user["id"])
            .order("created_at", desc=True)
            .execute()
        )
        return [_format_association(item) for item in (result.data or [])]
    except Exception:
        return []


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
        if not result.data:
            raise HTTPException(status_code=404, detail="Associação não encontrada.")
        return _format_association(result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{association_id}", status_code=204)
async def delete_association(
    association_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Remove uma associação. Apenas o criador ou administradores podem apagar."""
    try:
        existing = (
            await db.table(Tables.ASSOCIATIONS)
            .select("*")
            .eq("id", association_id)
            .limit(1)
            .execute()
        )
        if not existing.data:
            raise HTTPException(status_code=404, detail="Associação não encontrada.")

        item = existing.data[0]
        is_owner = item.get("user_id") == user["id"]
        is_admin = bool(user.get("is_admin"))

        if not is_owner and not is_admin:
            raise HTTPException(status_code=403, detail="Sem permissão para excluir esta associação.")

        await db.table(Tables.ASSOCIATIONS).delete().eq("id", association_id).execute()
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        if not result.data:
            raise HTTPException(status_code=404, detail="Associação não encontrada.")
        return _format_association(result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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

    try:
        result = (
            await db.table(Tables.ASSOCIATIONS)
            .update({
                "status": ModerationStatus.REJECTED.value,
                "rejection_reason": reason or "Não atende aos critérios das diretrizes comunitárias."
            })
            .eq("id", association_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Associação não encontrada.")
        return _format_association(result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
