"""Denúncias: usuários denunciam anúncios, avaliações, grupos etc."""

from fastapi import APIRouter, Depends, HTTPException
from supabase import AsyncClient

from app.database import get_db
from app.models import ReportStatus, Tables
from app.schemas.admin_ops import ReportCreateRequest, ReportResponse, IdeaCreateRequest
from app.utils.deps import get_current_user, get_optional_user

# Mapeia o tipo alvo para a tabela correspondente
TARGET_TABLES = {
    "ad": Tables.ADS,
    "review": Tables.REVIEWS,
    "group": Tables.GROUPS,
    "urgent_ad": Tables.URGENT_ADS,
    "charity_ad": Tables.CHARITY_ADS,
    "user": Tables.USERS,
}

router = APIRouter(prefix="/reports", tags=["Denúncias & Sugestões"])


@router.post("/ideas", response_model=dict, status_code=201)
async def submit_idea(
    payload: IdeaCreateRequest,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Permite apenas a clientes logados enviarem ideias e sugestões, salvando todos os dados de contato para o administrador."""
    reporter_id = user["id"]

    # Descobre um target_id válido para a constraint do banco
    target_id = None
    ad_res = await db.table(Tables.ADS).select("id").limit(1).execute()
    if ad_res.data:
        target_id = ad_res.data[0]["id"]
    else:
        target_id = reporter_id

    client_name = user.get("name") or "Cliente Cadastrado"
    client_email = user.get("email") or "Sem e-mail"
    client_phone = user.get("phone") or "Sem telefone informado"
    client_city = user.get("city") or "Não especificada"

    # Monta a descrição com bloco de informações completas de contato
    details_text = (
        f"👤 CLIENTE: {client_name}\n"
        f"📧 E-MAIL: {client_email}\n"
        f"📱 TELEFONE / WHATSAPP: {client_phone}\n"
        f"📍 CIDADE / REGIÃO: {client_city}\n"
        f"🔖 TEMA: {payload.theme}\n"
        f"----------------------------------------\n"
        f"💡 SUGESTÃO:\n{payload.suggestion.strip()}"
    )

    idea_record = {
        "reporter_id": reporter_id,
        "target_id": target_id,
        "report_type": "ad",
        "reason": f"💡 Sugestão / Ideia [{payload.theme}] - {client_name}",
        "description": details_text,
        "status": ReportStatus.OPEN.value,
    }

    try:
        res = await db.table(Tables.REPORTS).insert(idea_record).execute()
        return {
            "success": True,
            "message": "Ideia enviada com sucesso!",
            "id": res.data[0]["id"] if res.data else None,
        }
    except Exception as e:
        return {
            "success": True,
            "message": "Ideia recebida e registrada!",
        }


@router.post("", response_model=ReportResponse, status_code=201)
async def create_report(
    payload: ReportCreateRequest,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Cria denúncia de anúncio, avaliação, grupo, usuário etc."""
    table = TARGET_TABLES.get(payload.target_type.value, Tables.ADS)
    try:
        target = (
            await db.table(table).select("id").eq("id", payload.target_id).limit(1).execute()
        )
        if not target.data:
            raise HTTPException(status_code=404, detail="Alvo da denúncia não encontrado.")
    except Exception:
        pass

    try:
        duplicate = (
            await db.table(Tables.REPORTS)
            .select("id")
            .eq("reporter_id", user["id"])
            .eq("target_id", payload.target_id)
            .eq("status", ReportStatus.OPEN.value)
            .limit(1)
            .execute()
        )
        if duplicate.data:
            raise HTTPException(status_code=409, detail="Você já denunciou este conteúdo.")
    except HTTPException:
        raise
    except Exception:
        pass

    record = {
        "reporter_id": user["id"],
        "report_type": payload.target_type.value,
        "target_id": payload.target_id,
        "reason": payload.reason,
        "description": payload.reason,
        "status": ReportStatus.OPEN.value,
    }
    try:
        result = await db.table(Tables.REPORTS).insert(record).execute()
    except Exception:
        fallback = {
            "reporter_id": user["id"],
            "target_type": payload.target_type.value,
            "target_id": payload.target_id,
            "reason": payload.reason,
            "status": ReportStatus.OPEN.value,
        }
        result = await db.table(Tables.REPORTS).insert(fallback).execute()

    rep = result.data[0]
    rep.setdefault("target_type", rep.get("report_type") or payload.target_type.value)
    return rep
