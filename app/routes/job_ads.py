"""Módulo de Vagas e Anúncios de Emprego: Contato direto sem burocracia."""

import json
from typing import Optional
from fastapi import APIRouter, Depends, Form, HTTPException, Query
from supabase import AsyncClient

from app.database import get_db
from app.models import ModerationStatus, Tables
from app.schemas.community import JobAdResponse
from app.utils.deps import get_current_user, get_optional_user

router = APIRouter(prefix="/job-ads", tags=["Vagas & Empregos"])

JOB_PREFIX = "job_ad:"


def _format_job_ad(record: dict) -> dict:
    """Padroniza o retorno do anúncio de emprego independente do storage usado."""
    ad_id = record.get("id")
    user_id = record.get("user_id") or ""
    title = record.get("title") or record.get("name") or "Vaga de Emprego"
    city = record.get("city") or record.get("location") or "França"
    description = record.get("description") or ""
    contract_type = record.get("contract_type") or "CDI"
    email = record.get("email")
    whatsapp = record.get("whatsapp") or record.get("phone") or record.get("contact_phone")
    phone = record.get("phone") or record.get("contact_phone")
    landline_phone = record.get("landline_phone")
    status = record.get("status") or "approved"
    created_at = record.get("created_at")

    # Se estiver empacotado no formato comunitário do grupo
    category = record.get("category") or ""
    if category.startswith(JOB_PREFIX):
        try:
            raw_meta = category[len(JOB_PREFIX):]
            meta = json.loads(raw_meta)
            contract_type = meta.get("contract_type", contract_type)
            email = meta.get("email", email)
            whatsapp = meta.get("whatsapp", whatsapp)
            phone = meta.get("phone", phone)
            landline_phone = meta.get("landline_phone", landline_phone)
        except Exception:
            pass

    return {
        "id": str(ad_id),
        "user_id": str(user_id),
        "title": title.replace("[EMPREGO] ", "").strip(),
        "city": city,
        "contract_type": contract_type,
        "description": description,
        "email": email,
        "whatsapp": whatsapp,
        "phone": phone,
        "landline_phone": landline_phone,
        "badge": "EMPREGO",
        "status": status,
        "created_at": created_at,
    }


@router.post("", response_model=JobAdResponse, status_code=201)
async def create_job_ad(
    title: str = Form(...),
    city: str = Form(...),
    contract_type: str = Form(...),  # CDI, CDD, Intérim, Freelance, Stage, Outro
    description: str = Form(...),
    email: Optional[str] = Form(None),
    whatsapp: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    landline_phone: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Cria um anúncio de emprego com contato direto (WhatsApp, Email ou Telefone)."""
    clean_title = title.strip()
    clean_city = city.strip()
    clean_contract = contract_type.strip()
    clean_desc = description.strip()
    clean_email = email.strip() if email and email.strip() else None
    clean_whatsapp = whatsapp.strip() if whatsapp and whatsapp.strip() else None
    clean_phone = phone.strip() if phone and phone.strip() else None
    clean_landline = landline_phone.strip() if landline_phone and landline_phone.strip() else None

    if not clean_email and not clean_whatsapp and not clean_phone and not clean_landline:
        raise HTTPException(
            status_code=422,
            detail="Informe pelo menos um meio de contato (WhatsApp, E-mail ou Telefone).",
        )

    # Inserção direta no schema comunitário da tabela GROUPS
    meta_json = json.dumps({
        "contract_type": clean_contract,
        "email": clean_email,
        "whatsapp": clean_whatsapp,
        "phone": clean_phone,
        "landline_phone": clean_landline,
    })

    main_contact = clean_whatsapp or clean_phone or clean_landline or clean_email or ""
    contact_link = f"https://wa.me/{clean_whatsapp.replace('+', '').replace(' ', '')}" if clean_whatsapp else (f"mailto:{clean_email}" if clean_email else f"tel:{clean_phone or clean_landline}")

    group_record = {
        "created_by": user["id"],
        "name": f"[EMPREGO] {clean_title}",
        "city": clean_city,
        "category": f"{JOB_PREFIX}{meta_json}",
        "platform": "whatsapp" if clean_whatsapp else "facebook",
        "invite_link": contact_link,
        "description": clean_desc,
        "is_approved": True,
        "is_active": True,
        "status": ModerationStatus.APPROVED.value,
    }

    try:
        res = await db.table(Tables.GROUPS).insert(group_record).execute()
        if res.data:
            return _format_job_ad(res.data[0])
    except Exception as e:
        # Fallback 1: sem coluna status
        try:
            record_fallback = dict(group_record)
            record_fallback.pop("status", None)
            res = await db.table(Tables.GROUPS).insert(record_fallback).execute()
            if res.data:
                return _format_job_ad(res.data[0])
        except Exception:
            pass
        # Fallback 2: tabela charity_ads como alternativa se groups falhar
        try:
            charity_record = {
                "user_id": user["id"],
                "type": "job",
                "title": f"[EMPREGO] {clean_title}",
                "description": f"Tipo de Contrato: {clean_contract}\n\n{clean_desc}\n\n[META_JOB]{meta_json}[/META_JOB]",
                "location": clean_city,
                "contact_phone": clean_whatsapp or clean_phone or clean_landline or "",
                "status": ModerationStatus.APPROVED.value,
            }
            res = await db.table(Tables.CHARITY_ADS).insert(charity_record).execute()
            if res.data:
                return _format_job_ad(res.data[0])
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Erro ao salvar vaga de emprego: {str(e)}")


@router.get("", response_model=list[JobAdResponse])
async def list_job_ads(
    city: Optional[str] = Query(None),
    contract_type: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Lista todas as vagas de emprego ativas com filtros por cidade, contrato e palavra-chave."""
    job_ads = []

    # 1. Busca dos registros da tabela groups com prefixo job_ad:
    try:
        query = (
            db.table(Tables.GROUPS)
            .select("*")
            .ilike("category", f"{JOB_PREFIX}%")
            .eq("status", ModerationStatus.APPROVED.value)
        )
        if city:
            query = query.ilike("city", f"%{city}%")
        res = await query.order("created_at", desc=True).execute()
        for item in res.data or []:
            job_ads.append(_format_job_ad(item))
    except Exception:
        pass

    # 2. Busca também do fallback de charity_ads se houver
    try:
        res_charity = (
            await db.table(Tables.CHARITY_ADS)
            .select("*")
            .ilike("title", "[EMPREGO]%")
            .eq("status", ModerationStatus.APPROVED.value)
            .order("created_at", desc=True)
            .execute()
        )
        for item in res_charity.data or []:
            job_ads.append(_format_job_ad(item))
    except Exception:
        pass

    # Filtros em memória para garantir consistência
    filtered = []
    for job in job_ads:
        if city and city.lower() not in job["city"].lower():
            continue
        if contract_type and contract_type.lower() != job["contract_type"].lower():
            continue
        if q:
            term = q.lower()
            if (
                term not in job["title"].lower()
                and term not in job["description"].lower()
                and term not in job["city"].lower()
            ):
                continue
        filtered.append(job)

    return filtered


@router.get("/{job_id}", response_model=JobAdResponse)
async def get_job_ad(
    job_id: str,
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Retorna detalhes de uma vaga específica."""
    try:
        res = await db.table(Tables.GROUPS).select("*").eq("id", job_id).limit(1).execute()
        if res.data:
            return _format_job_ad(res.data[0])
    except Exception:
        pass

    try:
        res = await db.table(Tables.CHARITY_ADS).select("*").eq("id", job_id).limit(1).execute()
        if res.data:
            return _format_job_ad(res.data[0])
    except Exception:
        pass

    raise HTTPException(status_code=404, detail="Vaga de emprego não encontrada.")


@router.delete("/{job_id}", status_code=204)
async def delete_job_ad(
    job_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Exclui anúncio de emprego (apenas o criador ou administrador)."""
    try:
        res = await db.table(Tables.GROUPS).select("*").eq("id", job_id).limit(1).execute()
        if res.data:
            owner_id = res.data[0].get("created_by") or res.data[0].get("user_id")
            if owner_id != user["id"] and not user.get("is_admin"):
                raise HTTPException(status_code=403, detail="Sem permissão.")
            await db.table(Tables.GROUPS).delete().eq("id", job_id).execute()
            return None
    except HTTPException:
        raise
    except Exception:
        pass

    try:
        res = await db.table(Tables.CHARITY_ADS).select("user_id").eq("id", job_id).limit(1).execute()
        if res.data:
            if res.data[0]["user_id"] != user["id"] and not user.get("is_admin"):
                raise HTTPException(status_code=403, detail="Sem permissão.")
            await db.table(Tables.CHARITY_ADS).delete().eq("id", job_id).execute()
            return None
    except HTTPException:
        raise
    except Exception:
        pass

    raise HTTPException(status_code=404, detail="Anúncio não encontrado.")
