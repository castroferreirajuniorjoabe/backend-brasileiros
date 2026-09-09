"""Denúncias: usuários denunciam anúncios, avaliações, grupos etc."""

from fastapi import APIRouter, Depends, HTTPException
from supabase import AsyncClient

from app.database import get_db
from app.models import ReportStatus, Tables
from app.schemas.admin_ops import ReportCreateRequest, ReportResponse
from app.utils.deps import get_current_user

# Mapeia o tipo alvo para a tabela correspondente
TARGET_TABLES = {
    "ad": Tables.ADS,
    "review": Tables.REVIEWS,
    "group": Tables.GROUPS,
    "urgent_ad": Tables.URGENT_ADS,
    "charity_ad": Tables.CHARITY_ADS,
    "user": Tables.USERS,
}

router = APIRouter(prefix="/reports", tags=["Denúncias"])


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
