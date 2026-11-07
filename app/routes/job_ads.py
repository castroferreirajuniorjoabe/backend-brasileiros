"""Módulo de Vagas e Anúncios de Emprego: Contato direto sem burocracia."""

import json
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Form, HTTPException, Query
from supabase import AsyncClient

from app.database import get_db
from app.models import ModerationStatus, Tables
from app.schemas.community import JobAdResponse
from app.utils.deps import get_current_user, get_optional_user
from app.utils.translation import translate_job_fields, translate_job_list

router = APIRouter(prefix="/job-ads", tags=["Vagas & Empregos"])

JOB_PREFIX = "job_ad:"


def unwrap_link(url: Optional[str]) -> Optional[str]:
    """Extrai a URL original de redirecionadores (Facebook l.php, Google url, etc.)."""
    if not url:
        return None
    url = url.strip()
    if not url:
        return None
    if not url.startswith("http://") and not url.startswith("https://"):
        url = f"https://{url}"

    import urllib.parse
    try:
        if "facebook.com/l.php" in url:
            parsed = urllib.parse.urlparse(url)
            qs = urllib.parse.parse_qs(parsed.query)
            if "u" in qs:
                target = qs["u"][0]
                sub_parsed = urllib.parse.urlparse(target)
                sub_qs = urllib.parse.parse_qs(sub_parsed.query)
                sub_qs.pop("fbclid", None)
                sub_qs.pop("__tn__", None)
                sub_qs.pop("h", None)
                new_query = urllib.parse.urlencode(sub_qs, doseq=True)
                return urllib.parse.urlunparse((
                    sub_parsed.scheme, sub_parsed.netloc, sub_parsed.path,
                    sub_parsed.params, new_query, sub_parsed.fragment
                )).rstrip("?")
        if "google.com/url" in url:
            parsed = urllib.parse.urlparse(url)
            qs = urllib.parse.parse_qs(parsed.query)
            if "q" in qs: return qs["q"][0]
            if "url" in qs: return qs["url"][0]
    except Exception:
        pass
    return url


def _has_valid_digits(val: Optional[str]) -> bool:
    if not val:
        return False
    import re
    return len(re.sub(r"\D", "", str(val))) >= 6


def _format_job_ad(record: dict) -> dict:
    """Padroniza o retorno do anúncio de emprego independente do storage usado."""
    import re

    ad_id = record.get("id")
    user_id = record.get("user_id") or record.get("created_by") or ""
    title = record.get("title") or record.get("name") or "Vaga de Emprego"
    city = record.get("city") or record.get("location") or "França"
    description = record.get("description") or ""
    contract_type = record.get("contract_type") or "CDI"
    email = record.get("email")
    whatsapp = record.get("whatsapp")
    phone = record.get("phone") or record.get("contact_phone")
    landline_phone = record.get("landline_phone")
    status = record.get("status") or "approved"
    raw_created = record.get("created_at")
    created_at = None
    if raw_created is not None:
        if hasattr(raw_created, "isoformat"):
            created_at = raw_created.isoformat()
        else:
            created_at = str(raw_created)
    image_url = record.get("logo_url") or record.get("image_url")

    # Se estiver empacotado no formato comunitário do grupo
    category = record.get("category") or ""
    application_url = None
    if category.startswith(JOB_PREFIX):
        try:
            raw_meta = category[len(JOB_PREFIX):]
            meta = json.loads(raw_meta)
            contract_type = meta.get("contract_type", contract_type)
            email = meta.get("email", email)
            whatsapp = meta.get("whatsapp", whatsapp)
            phone = meta.get("phone", phone)
            landline_phone = meta.get("landline_phone", landline_phone)
            application_url = meta.get("application_url") or meta.get("link")
            if not image_url and meta.get("image_url"):
                image_url = meta.get("image_url")
        except Exception:
            pass

    if description:
        if not whatsapp:
            m_wa = re.search(r'(?:💬\s*WhatsApp|WhatsApp)\s*:\s*([^\n\r]+)', description, re.IGNORECASE)
            if m_wa and _has_valid_digits(m_wa.group(1)):
                whatsapp = m_wa.group(1).strip()
        if not phone:
            m_ph = re.search(r'(?:📞\s*Telefone(?:\s*Celular)?|Telefone\s*Celular|Celular|Telefone)\s*:\s*([^\n\r]+)', description, re.IGNORECASE)
            if m_ph and _has_valid_digits(m_ph.group(1)):
                phone = m_ph.group(1).strip()
        if not landline_phone:
            m_ll = re.search(r'(?:☎️\s*Telefone\s*Fixo|Telefone\s*Fixo|Fixo)\s*:\s*([^\n\r]+)', description, re.IGNORECASE)
            if m_ll and _has_valid_digits(m_ll.group(1)):
                landline_phone = m_ll.group(1).strip()
        if not email:
            m_em = re.search(r'(?:✉️\s*E-mail|E-mail|Email)\s*:\s*([^\s\n\r]+@[^\s\n\r]+)', description, re.IGNORECASE)
            if m_em:
                email = m_em.group(1).strip()

    if whatsapp and not _has_valid_digits(whatsapp):
        whatsapp = None
    if phone and not _has_valid_digits(phone):
        phone = None
    if landline_phone and not _has_valid_digits(landline_phone):
        landline_phone = None

    if not application_url and description:
        match = re.search(r'(?:Link do Anúncio|Link da vaga|\[LINK)[\s\S]*?(https?://\S+)', description, re.IGNORECASE)
        if match:
            application_url = match.group(1).rstrip(']').strip()

    if application_url:
        application_url = unwrap_link(application_url)

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
        "application_url": application_url,
        "link": application_url,
        "image_url": image_url,
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
    application_url: Optional[str] = Form(None),
    link: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Cria um anúncio de emprego com contato direto (WhatsApp, Email ou Telefone) e link opcional de anúncio externo."""
    clean_title = title.strip()
    clean_city = city.strip()
    clean_contract = contract_type.strip()
    clean_desc = description.strip()
    clean_email = email.strip() if email and email.strip() else None
    clean_whatsapp = whatsapp.strip() if whatsapp and whatsapp.strip() else None
    clean_phone = phone.strip() if phone and phone.strip() else None
    clean_landline = landline_phone.strip() if landline_phone and landline_phone.strip() else None

    raw_link = application_url or link
    clean_link = unwrap_link(raw_link)

    if clean_whatsapp and not _has_valid_digits(clean_whatsapp):
        clean_whatsapp = None
    if clean_phone and not _has_valid_digits(clean_phone):
        clean_phone = None
    if clean_landline and not _has_valid_digits(clean_landline):
        clean_landline = None

    if not clean_email and not clean_whatsapp and not clean_phone and not clean_landline and not clean_link:
        raise HTTPException(
            status_code=422,
            detail="Informe pelo menos um meio de contato (WhatsApp, E-mail, Telefone ou Link da Vaga).",
        )

    # Inserção direta no schema comunitário da tabela GROUPS
    meta_dict = {
        "contract_type": clean_contract,
        "email": clean_email,
        "whatsapp": clean_whatsapp,
        "phone": clean_phone,
        "landline_phone": clean_landline,
    }
    if clean_link:
        meta_dict["application_url"] = clean_link
        meta_dict["link"] = clean_link

    meta_json = json.dumps(meta_dict)

    main_contact = clean_whatsapp or clean_phone or clean_landline or clean_email or clean_link or ""
    contact_link = clean_link if clean_link else (f"https://wa.me/{clean_whatsapp.replace('+', '').replace(' ', '')}" if clean_whatsapp else (f"mailto:{clean_email}" if clean_email else f"tel:{clean_phone or clean_landline}"))

    group_record = {
        "created_by": user.get("id"),
        "name": f"[EMPREGO] {clean_title}",
        "city": clean_city,
        "category": f"{JOB_PREFIX}{meta_json}",
        "platform": "whatsapp" if clean_whatsapp else "facebook",
        "invite_link": contact_link or "https://brasileirosnafranca.com/empregos",
        "description": clean_desc,
        "is_approved": True,
        "is_active": True,
    }

    try:
        res = await db.table(Tables.GROUPS).insert(group_record).execute()
        if res.data:
            return _format_job_ad(res.data[0])
        raise HTTPException(status_code=500, detail="Não foi possível salvar o anúncio de emprego.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar vaga de emprego: {str(e)}")


@router.get("", response_model=list[JobAdResponse])
async def list_job_ads(
    city: Optional[str] = Query(None),
    contract_type: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    lang: Optional[str] = Query(None, description="Idioma desejado para tradução automática (ex: pt, fr, en)"),
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Lista todas as vagas de emprego ativas com filtros por cidade, contrato, palavra-chave e tradução para o idioma do usuário."""
    job_ads = []

    # Busca dos registros da tabela groups com prefixo job_ad:
    try:
        query = (
            db.table(Tables.GROUPS)
            .select("*")
            .ilike("category", f"{JOB_PREFIX}%")
            .or_("is_approved.eq.true,is_active.eq.true")
        )
        if city:
            query = query.ilike("city", f"%{city}%")
        res = await query.order("created_at", desc=True).execute()
        for item in res.data or []:
            job_ads.append(_format_job_ad(item))
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Erro ao buscar vagas de emprego na tabela GROUPS: {e}", exc_info=True)

    # Ordena explicitamente para garantir que novas vagas com created_at venham no topo
    job_ads.sort(key=lambda x: x.get("created_at") or "", reverse=True)

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

    # Tradução automática ultra rápida em lote usando ThreadPoolExecutor
    if lang and lang.lower() != "pt":
        filtered = translate_job_list(filtered, lang)
    else:
        for job in filtered:
            job["original_title"] = job.get("title")
            job["original_description"] = job.get("description")
            job["translated_lang"] = "pt"

    return filtered


@router.get("/{job_id}", response_model=JobAdResponse)
async def get_job_ad(
    job_id: str,
    lang: Optional[str] = Query(None, description="Idioma desejado para tradução (ex: pt, fr, en)"),
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Retorna detalhes de uma vaga específica com suporte a tradução de idioma."""
    try:
        res = await db.table(Tables.GROUPS).select("*").eq("id", job_id).limit(1).execute()
        if res.data:
            formatted = _format_job_ad(res.data[0])
            if lang:
                formatted = translate_job_fields(formatted, lang)
            else:
                formatted["original_title"] = formatted.get("title")
                formatted["original_description"] = formatted.get("description")
                formatted["translated_lang"] = "pt"
            return formatted
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

    raise HTTPException(status_code=404, detail="Anúncio não encontrado.")
