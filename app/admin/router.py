"""Rotas administrativas: moderação, estatísticas, denúncias, gift codes e gestão."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import AsyncClient

from app.database import get_db
from app.models import (
    AdStatus,
    ModerationStatus,
    PaymentStatus,
    ReportStatus,
    Tables,
)
from app.routes.ranking import compute_monthly_ranking
from app.schemas.admin_ops import (
    AdminStatsResponse,
    BlockUserRequest,
    GiftCodeCreateRequest,
    ReportResolveRequest,
    UserUpdateRequest,
)
from app.schemas.ads import RejectRequest as AdRejectRequest
from app.utils.deps import get_admin_user
from app.utils.notifications import create_notification
from app.utils.security import generate_gift_code, utcnow

router = APIRouter(
    prefix="/admin",
    tags=["Administração"],
    dependencies=[Depends(get_admin_user)],
)

# Tabelas moderáveis: (tabela, campo de status)
MODERATED = {
    "ads": (Tables.ADS, AdStatus),
    "groups": (Tables.GROUPS, ModerationStatus),
    "associations": (Tables.ASSOCIATIONS, ModerationStatus),
    "urgent-ads": (Tables.URGENT_ADS, ModerationStatus),
    "charity-ads": (Tables.CHARITY_ADS, ModerationStatus),
    "tourism-spots": (Tables.TOURISM_SPOTS, ModerationStatus),
    "pet-posts": (Tables.PET_POSTS, ModerationStatus),
    "arrival-guide": (Tables.GROUPS, ModerationStatus),
    "job-ads": (Tables.GROUPS, ModerationStatus),
    "jobs": (Tables.GROUPS, ModerationStatus),
    "moving-sales": (Tables.MOVING_SALES, ModerationStatus),
    "artists": (Tables.ARTISTS, ModerationStatus),
    "regulation-posts": (Tables.REGULATION_POSTS, ModerationStatus),
    "regulation_posts": (Tables.REGULATION_POSTS, ModerationStatus),
    "consulate_posts": (Tables.CONSULATE_POSTS, ModerationStatus),
}

# Tabelas gerenciáveis via endpoints genéricos
MANAGEABLE_TABLES = {
    "users": Tables.USERS,
    "ads": Tables.ADS,
    "reviews": Tables.REVIEWS,
    "groups": Tables.GROUPS,
    "associations": Tables.ASSOCIATIONS,
    "urgent_ads": Tables.URGENT_ADS,
    "charity_ads": Tables.CHARITY_ADS,
    "tourism_spots": Tables.TOURISM_SPOTS,
    "pet_posts": Tables.PET_POSTS,
    "item_comments": Tables.ITEM_COMMENTS,
    "gift_codes": Tables.GIFT_CODES,
    "reports": Tables.REPORTS,
    "payments": Tables.PAYMENTS,
    "monthly_ranking": Tables.MONTHLY_RANKING,
    "edit_history": Tables.EDIT_HISTORY,
    "admins": Tables.ADMINS,
    "job_ads": Tables.GROUPS,
    "jobs": Tables.GROUPS,
    "moving_sales": Tables.MOVING_SALES,
    "moving-sales": Tables.MOVING_SALES,
    "artists": Tables.ARTISTS,
    "artist_events": Tables.ARTIST_EVENTS,
    "regulation_posts": Tables.REGULATION_POSTS,
    "regulation-posts": Tables.REGULATION_POSTS,
    "regulation_replies": Tables.REGULATION_REPLIES,
    "regulation_reports": Tables.REGULATION_REPORTS,
    "consulate_posts": Tables.CONSULATE_POSTS,
}


# ---------- Estatísticas ----------

@router.get("/stats", response_model=AdminStatsResponse)
async def get_stats(db: AsyncClient = Depends(get_db)):
    """Estatísticas gerais do app."""

    async def count(table: str, **filters) -> int:
        try:
            query = db.table(table).select("id", count="exact")
            for field, value in filters.items():
                query = query.eq(field, value)
            result = await query.execute()
            return result.count or 0
        except Exception:
            return 0

    try:
        payments = (
            await db.table(Tables.PAYMENTS)
            .select("amount")
            .eq("status", PaymentStatus.PAID.value)
            .execute()
        )
        revenue = sum(int(float(p.get("amount", 0)) * 100) if isinstance(p.get("amount"), (int, float)) else p.get("amount_cents", 0) for p in payments.data or [])
    except Exception:
        revenue = 0

    return AdminStatsResponse(
        total_users=await count(Tables.USERS),
        blocked_users=await count(Tables.USERS, is_blocked=True),
        total_ads=await count(Tables.ADS),
        pending_ads=await count(Tables.ADS, status=AdStatus.PENDING.value),
        approved_ads=await count(Tables.ADS, status=AdStatus.APPROVED.value),
        highlighted_ads=await count(Tables.ADS, is_highlighted=True),
        total_reviews=await count(Tables.REVIEWS),
        total_groups=await count(Tables.GROUPS),
        pending_groups=await count(Tables.GROUPS, is_approved=False),
        active_urgent_ads=await count(Tables.URGENT_ADS, status=ModerationStatus.APPROVED.value),
        total_charity_ads=await count(Tables.CHARITY_ADS),
        open_reports=await count(Tables.REPORTS, status=ReportStatus.OPEN.value),
        total_payments=await count(Tables.PAYMENTS),
        revenue_cents=revenue,
    )


# ---------- Moderação (anúncios, grupos, urgência, caridade, vagas) ----------

@router.get("/moderation/{kind}")
async def list_pending(
    kind: str,
    status: Optional[str] = Query(None),
    db: AsyncClient = Depends(get_db),
):
    """Lista itens por status de cada tipo moderável."""
    if kind not in MODERATED:
        raise HTTPException(status_code=404, detail="Tipo inválido.")
    table, _ = MODERATED[kind]
    target_status = status or "pending"
    
    try:
        if kind in ["job-ads", "jobs"]:
            # Vagas de emprego salvas em GROUPS (category job_ad:...) ou CHARITY_ADS ([EMPREGO])
            try:
                query_grp = db.table(Tables.GROUPS).select("*").ilike("category", "job_ad:%")
                if target_status == "pending":
                    query_grp = query_grp.or_("is_approved.eq.false,is_approved.is.null")
                elif target_status == "approved":
                    query_grp = query_grp.eq("is_approved", True)
                elif target_status == "rejected":
                    query_grp = query_grp.eq("is_approved", False).eq("is_active", False)
                res1 = await query_grp.order("created_at", desc=True).execute()
                data1 = res1.data or []
            except Exception:
                data1 = []
            try:
                res2 = await db.table(Tables.CHARITY_ADS).select("*").ilike("title", "[EMPREGO]%").eq("status", target_status).order("created_at", desc=True).execute()
                data2 = res2.data or []
            except Exception:
                data2 = []
            return data1 + data2
        elif kind == "arrival-guide":
            query = db.table(table).select("*").or_("category.ilike.arrival_rec:%,category.ilike.arrival_test:%,category.ilike.arrival_chat:%")
            if target_status == "pending":
                query = query.or_("is_approved.eq.false,is_approved.is.null")
            elif target_status == "approved":
                query = query.eq("is_approved", True).eq("is_active", True)
            elif target_status == "rejected":
                query = query.eq("is_approved", False).eq("is_active", False)
            result = await query.order("created_at", desc=True).execute()
            return result.data or []
        elif kind == "groups":
            if target_status == "pending":
                result = await db.table(table).select("*").not_.like("category", "news_banner:%").not_.like("category", "job_ad:%").not_.like("category", "arrival_%").not_.like("category", "chat:%").not_.like("category", "comment_%").not_.like("name", "[NOVIDADE]%").not_.like("name", "[EMPREGO]%").not_.like("invite_link", "banner:%").not_.like("invite_link", "chat://%").not_.like("invite_link", "comment://%").not_.like("invite_link", "likes:%").or_("is_approved.eq.false,is_approved.is.null").order("created_at", desc=True).execute()
            else:
                result = await db.table(table).select("*").not_.like("category", "news_banner:%").not_.like("category", "job_ad:%").not_.like("category", "arrival_%").not_.like("category", "chat:%").not_.like("category", "comment_%").not_.like("name", "[NOVIDADE]%").not_.like("name", "[EMPREGO]%").not_.like("invite_link", "banner:%").not_.like("invite_link", "chat://%").not_.like("invite_link", "comment://%").not_.like("invite_link", "likes:%").eq("is_approved", True).order("created_at", desc=True).execute()
        elif kind == "charity-ads":
            # Exclui rigorosamente postagens de pets, passeios, empregos ou mudança salvos em charity_ads
            result = (
                await db.table(table)
                .select("*")
                .eq("status", target_status)
                .neq("type", "pet")
                .neq("type", "tourism")
                .neq("type", "moving_sale")
                .not_.like("title", "[PET%")
                .not_.like("title", "[PASSEIO%")
                .not_.like("title", "[EMPREGO%")
                .not_.like("title", "[MUDANÇA%")
                .order("created_at", desc=True)
                .execute()
            )
        elif kind == "moving-sales":
            all_raw = []
            # 1. Tabela dedicada moving_sales
            try:
                res1 = await db.table(table).select("*").eq("status", target_status).order("created_at", desc=True).execute()
                if res1.data:
                    all_raw.extend(res1.data)
            except Exception:
                pass

            # 2. Tabela charity_ads (fallback type=moving_sale ou title contendo MUDANÇA)
            try:
                res_c1 = await db.table(Tables.CHARITY_ADS).select("*").eq("type", "moving_sale").eq("status", target_status).order("created_at", desc=True).execute()
                if res_c1.data:
                    existing_ids = {str(x.get("id")) for x in all_raw}
                    for it in res_c1.data:
                        if str(it.get("id")) not in existing_ids:
                            all_raw.append(it)
            except Exception:
                pass

            try:
                res_c2 = await db.table(Tables.CHARITY_ADS).select("*").ilike("title", "%MUDAN%").eq("status", target_status).order("created_at", desc=True).execute()
                if res_c2.data:
                    existing_ids = {str(x.get("id")) for x in all_raw}
                    for it in res_c2.data:
                        if str(it.get("id")) not in existing_ids:
                            all_raw.append(it)
            except Exception:
                pass

            # 3. Tabela groups (fallback category moving_sale:% ou name contendo MUDANÇA)
            try:
                q_grp = db.table(Tables.GROUPS).select("*").or_("category.ilike.moving_sale:%,name.ilike.%MUDAN%")
                if target_status == "pending":
                    q_grp = q_grp.or_("is_approved.eq.false,is_approved.is.null")
                elif target_status == "approved":
                    q_grp = q_grp.eq("is_approved", True).eq("is_active", True)
                elif target_status == "rejected":
                    q_grp = q_grp.eq("is_approved", False).eq("is_active", False)
                res_g = await q_grp.order("created_at", desc=True).execute()
                if res_g.data:
                    existing_ids = {str(x.get("id")) for x in all_raw}
                    for it in res_g.data:
                        if str(it.get("id")) not in existing_ids:
                            all_raw.append(it)
            except Exception:
                pass

            try:
                from app.routes.moving_sales import _format_moving_sale
                return [_format_moving_sale(x) for x in all_raw]
            except Exception:
                return all_raw
        elif kind == "artists":
            all_raw = []
            # 1. Tabela dedicada artists
            try:
                res1 = await db.table(table).select("*").eq("status", target_status).order("created_at", desc=True).execute()
                if res1.data:
                    all_raw.extend(res1.data)
            except Exception:
                pass

            # 2. Tabela charity_ads (fallback type=artist ou title contendo ARTISTA)
            try:
                res_c1 = await db.table(Tables.CHARITY_ADS).select("*").eq("type", "artist").eq("status", target_status).order("created_at", desc=True).execute()
                if res_c1.data:
                    existing_ids = {str(x.get("id")) for x in all_raw}
                    for it in res_c1.data:
                        if str(it.get("id")) not in existing_ids:
                            all_raw.append(it)
            except Exception:
                pass

            try:
                res_c2 = await db.table(Tables.CHARITY_ADS).select("*").ilike("title", "%ARTISTA%").eq("status", target_status).order("created_at", desc=True).execute()
                if res_c2.data:
                    existing_ids = {str(x.get("id")) for x in all_raw}
                    for it in res_c2.data:
                        if str(it.get("id")) not in existing_ids:
                            all_raw.append(it)
            except Exception:
                pass

            # 3. Tabela groups (fallback category artist:% ou name contendo ARTISTA)
            try:
                q_grp = db.table(Tables.GROUPS).select("*").or_("category.ilike.artist:%,name.ilike.%ARTISTA%")
                if target_status == "pending":
                    q_grp = q_grp.or_("is_approved.eq.false,is_approved.is.null")
                elif target_status == "approved":
                    q_grp = q_grp.eq("is_approved", True).eq("is_active", True)
                elif target_status == "rejected":
                    q_grp = q_grp.eq("is_approved", False).eq("is_active", False)
                res_g = await q_grp.order("created_at", desc=True).execute()
                if res_g.data:
                    existing_ids = {str(x.get("id")) for x in all_raw}
                    for it in res_g.data:
                        if str(it.get("id")) not in existing_ids:
                            all_raw.append(it)
            except Exception:
                pass

            try:
                from app.routes.artists import _format_artist
                return [_format_artist(x) for x in all_raw]
            except Exception:
                return all_raw
        elif kind == "pet-posts":
            # Busca na tabela PET_POSTS ou registros com type=pet
            try:
                res1 = await db.table(table).select("*").eq("status", target_status).order("created_at", desc=True).execute()
                data1 = res1.data or []
            except Exception:
                data1 = []
            try:
                res2 = await db.table(Tables.CHARITY_ADS).select("*").eq("type", "pet").eq("status", target_status).order("created_at", desc=True).execute()
                data2 = res2.data or []
            except Exception:
                data2 = []
            return data1 + data2
        elif kind == "associations":
            try:
                res1 = await db.table(table).select("*").eq("status", target_status).order("created_at", desc=True).execute()
                data1 = res1.data or []
            except Exception:
                data1 = []
            try:
                q_grp = db.table(Tables.GROUPS).select("*").ilike("category", "association:%")
                if target_status == "pending":
                    q_grp = q_grp.or_("is_approved.eq.false,is_approved.is.null")
                elif target_status == "approved":
                    q_grp = q_grp.eq("is_approved", True).eq("is_active", True)
                elif target_status == "rejected":
                    q_grp = q_grp.eq("is_approved", False).eq("is_active", False)
                res2 = await q_grp.order("created_at", desc=True).execute()
                data2 = res2.data or []
            except Exception:
                data2 = []
            return data1 + data2
        elif kind == "tourism-spots":
            try:
                res1 = await db.table(table).select("*").eq("status", target_status).order("created_at", desc=True).execute()
                data1 = res1.data or []
            except Exception:
                data1 = []
            try:
                res2 = await db.table(Tables.CHARITY_ADS).select("*").eq("type", "tourism").eq("status", target_status).order("created_at", desc=True).execute()
                data2 = res2.data or []
            except Exception:
                data2 = []
            return data1 + data2
        elif kind in ["regulation-posts", "regulation_posts"]:
            all_raw = []
            try:
                res1 = await db.table(Tables.REGULATION_POSTS).select("*, users:user_id(id, name, avatar_url, city, is_verified, is_admin)").eq("status", target_status).order("created_at", desc=True).execute()
                if res1.data:
                    all_raw.extend(res1.data)
            except Exception:
                try:
                    res1_simple = await db.table(Tables.REGULATION_POSTS).select("*").eq("status", target_status).order("created_at", desc=True).execute()
                    if res1_simple.data:
                        all_raw.extend(res1_simple.data)
                except Exception:
                    pass

            # Fallback em CHARITY_ADS
            try:
                res_c = await db.table(Tables.CHARITY_ADS).select("*").ilike("description", "%REGULATION_META:%").eq("status", target_status).order("created_at", desc=True).execute()
                if res_c.data:
                    existing_ids = {str(x.get("id")) for x in all_raw}
                    for c_item in res_c.data:
                        if str(c_item.get("id")) not in existing_ids:
                            desc = c_item.get("description") or ""
                            real_type = "question"
                            real_cat = "vistos"
                            real_desc = desc
                            images = []
                            if "REGULATION_META:" in desc and "---DESC---" in desc:
                                parts = desc.split("---DESC---")
                                meta_str = parts[0].replace("REGULATION_META:", "").strip()
                                try:
                                    import json
                                    m_obj = json.loads(meta_str)
                                    real_type = m_obj.get("type") or "question"
                                    real_cat = m_obj.get("category") or "vistos"
                                    images = m_obj.get("images") or []
                                except Exception:
                                    pass
                                real_desc = parts[1].strip() if len(parts) > 1 else desc
                            title = (c_item.get("title") or "").replace("[QUESTION]", "").replace("[TIP]", "").replace("[DUVIDA]", "").replace("[DICA]", "").strip()
                            all_raw.append({
                                "id": c_item.get("id"),
                                "user_id": c_item.get("user_id"),
                                "type": real_type,
                                "category": real_cat,
                                "title": title,
                                "content": real_desc,
                                "images": images or ([c_item.get("image_url")] if c_item.get("image_url") else []),
                                "status": target_status,
                                "created_at": c_item.get("created_at"),
                            })
            except Exception:
                pass

            try:
                from app.routes.regulation import _format_post
                return [_format_post(x, user_dict=x.get("users")) for x in all_raw]
            except Exception:
                return all_raw
        else:
            result = await db.table(table).select("*").eq("status", target_status).order("created_at", desc=True).execute()
        return result.data or []
    except Exception:
        try:
            result = await db.table(table).select("*").order("created_at", desc=True).execute()
            return result.data or []
        except Exception:
            return []


@router.post("/moderation/{kind}/{item_id}/approve")
async def approve_item(kind: str, item_id: str, db: AsyncClient = Depends(get_db)):
    """Aprova um item pendente (anúncio, grupo, urgência, caridade, turismo, pet, chegada ou emprego)."""
    if kind not in MODERATED:
        raise HTTPException(status_code=404, detail="Tipo inválido.")
    table, status_enum = MODERATED[kind]
    try:
        if kind in ["groups", "arrival-guide"]:
            result = await db.table(table).update({"is_approved": True, "is_active": True, "status": "approved"}).eq("id", item_id).execute()
        elif kind in ["job-ads", "jobs"]:
            try:
                result = await db.table(Tables.GROUPS).update({"status": "approved", "is_approved": True, "is_active": True}).eq("id", item_id).execute()
                if not result.data:
                    result = await db.table(Tables.CHARITY_ADS).update({"status": "approved"}).eq("id", item_id).execute()
            except Exception:
                result = await db.table(Tables.CHARITY_ADS).update({"status": "approved"}).eq("id", item_id).execute()
        elif kind == "associations":
            try:
                result = await db.table(Tables.ASSOCIATIONS).update({"status": "approved", "rejection_reason": None}).eq("id", item_id).execute()
                if not result.data:
                    result = await db.table(Tables.GROUPS).update({"is_approved": True, "is_active": True}).eq("id", item_id).execute()
            except Exception:
                result = await db.table(Tables.GROUPS).update({"is_approved": True, "is_active": True}).eq("id", item_id).execute()
        elif kind == "moving-sales":
            try:
                result = await db.table(Tables.MOVING_SALES).update({"status": "approved", "is_available": True}).eq("id", item_id).execute()
                if not result.data:
                    result = await db.table(Tables.CHARITY_ADS).update({"status": "approved"}).eq("id", item_id).execute()
            except Exception:
                try:
                    result = await db.table(Tables.CHARITY_ADS).update({"status": "approved"}).eq("id", item_id).execute()
                except Exception:
                    result = None
            if not result or not result.data:
                try:
                    result = await db.table(Tables.GROUPS).update({"is_approved": True, "is_active": True}).eq("id", item_id).execute()
                except Exception:
                    pass
        elif kind == "artists":
            try:
                result = await db.table(Tables.ARTISTS).update({"status": "approved", "rejection_reason": None}).eq("id", item_id).execute()
                if not result.data:
                    result = await db.table(Tables.CHARITY_ADS).update({"status": "approved"}).eq("id", item_id).execute()
            except Exception:
                try:
                    result = await db.table(Tables.CHARITY_ADS).update({"status": "approved"}).eq("id", item_id).execute()
                except Exception:
                    result = None
            if not result or not result.data:
                try:
                    result = await db.table(Tables.GROUPS).update({"is_approved": True, "is_active": True}).eq("id", item_id).execute()
                except Exception:
                    pass
        elif kind in ["regulation-posts", "regulation_posts"]:
            try:
                result = await db.table(Tables.REGULATION_POSTS).update({"status": "approved", "rejection_reason": None}).eq("id", item_id).execute()
                if not result.data:
                    result = await db.table(Tables.CHARITY_ADS).update({"status": "approved"}).eq("id", item_id).execute()
            except Exception:
                try:
                    result = await db.table(Tables.CHARITY_ADS).update({"status": "approved"}).eq("id", item_id).execute()
                except Exception:
                    result = None
        else:
            result = await db.table(table).update({"status": status_enum.APPROVED.value}).eq("id", item_id).execute()
    except Exception:
        try:
            result = await db.table(table).update({"status": "approved"}).eq("id", item_id).execute()
        except Exception:
            result = await db.table(table).update({"is_approved": True, "is_active": True}).eq("id", item_id).execute()

    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    
    item_data = result.data[0]
    # Cria notificação para o dono do item se houver user_id
    item_user_id = item_data.get("user_id") or item_data.get("created_by")
    if item_user_id:
        item_title = item_data.get("name") or item_data.get("title") or "item"
        if kind in ["regulation-posts", "regulation_posts"]:
            link = f"/regularizacao/{item_id}"
        elif kind == "ads":
            link = f"/anuncio/{item_id}"
        else:
            link = f"/{kind}"
        await create_notification(
            db=db,
            user_id=item_user_id,
            title="Publicação Aprovada!",
            message=f"Sua publicação \"{item_title}\" foi aprovada e já está visível.",
            type="ad_approved",
            link=link,
        )

    return item_data


@router.post("/moderation/{kind}/{item_id}/reject")
async def reject_item(
    kind: str,
    item_id: str,
    payload: AdRejectRequest | None = None,
    db: AsyncClient = Depends(get_db),
):
    """Rejeita um item pendente, com motivo opcional."""
    if kind not in MODERATED:
        raise HTTPException(status_code=404, detail="Tipo inválido.")
    table, status_enum = MODERATED[kind]
    update = {}
    if kind in ["groups", "arrival-guide"]:
        update = {"is_approved": False, "is_active": False, "status": "rejected"}
    elif kind in ["job-ads", "jobs"]:
        update = {"status": "rejected", "is_approved": False, "is_active": False}
    else:
        update = {"status": status_enum.REJECTED.value}
    
    if payload and payload.reason:
        update["rejection_reason"] = payload.reason
    try:
        if kind in ["job-ads", "jobs"]:
            try:
                result = await db.table(Tables.GROUPS).update(update).eq("id", item_id).execute()
                if not result.data:
                    result = await db.table(Tables.CHARITY_ADS).update(update).eq("id", item_id).execute()
            except Exception:
                result = await db.table(Tables.CHARITY_ADS).update(update).eq("id", item_id).execute()
        elif kind == "associations":
            try:
                result = await db.table(Tables.ASSOCIATIONS).update(update).eq("id", item_id).execute()
                if not result.data:
                    result = await db.table(Tables.GROUPS).update({"is_approved": False, "is_active": False}).eq("id", item_id).execute()
            except Exception:
                result = await db.table(Tables.GROUPS).update({"is_approved": False, "is_active": False}).eq("id", item_id).execute()
        elif kind == "moving-sales":
            try:
                result = await db.table(Tables.MOVING_SALES).update(update).eq("id", item_id).execute()
                if not result.data:
                    result = await db.table(Tables.CHARITY_ADS).update(update).eq("id", item_id).execute()
            except Exception:
                try:
                    result = await db.table(Tables.CHARITY_ADS).update(update).eq("id", item_id).execute()
                except Exception:
                    result = None
            if not result or not result.data:
                try:
                    result = await db.table(Tables.GROUPS).update({"is_approved": False, "is_active": False}).eq("id", item_id).execute()
                except Exception:
                    pass
        elif kind == "artists":
            try:
                result = await db.table(Tables.ARTISTS).update(update).eq("id", item_id).execute()
                if not result.data:
                    result = await db.table(Tables.CHARITY_ADS).update(update).eq("id", item_id).execute()
            except Exception:
                try:
                    result = await db.table(Tables.CHARITY_ADS).update(update).eq("id", item_id).execute()
                except Exception:
                    result = None
            if not result or not result.data:
                try:
                    result = await db.table(Tables.GROUPS).update({"is_approved": False, "is_active": False}).eq("id", item_id).execute()
                except Exception:
                    pass
        elif kind in ["regulation-posts", "regulation_posts"]:
            try:
                result = await db.table(Tables.REGULATION_POSTS).update(update).eq("id", item_id).execute()
            except Exception:
                result = None
        else:
            result = await db.table(table).update(update).eq("id", item_id).execute()
    except Exception:
        update_fallback = {"status": "rejected"}
        if payload and payload.reason:
            update_fallback["rejection_reason"] = payload.reason
        result = await db.table(table).update(update_fallback).eq("id", item_id).execute()
    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    
    item_data = result.data[0]
    item_user_id = item_data.get("user_id") or item_data.get("created_by")
    if item_user_id:
        item_title = item_data.get("name") or item_data.get("title") or "item"
        reason_msg = f" Motivo: {payload.reason}" if payload and payload.reason else ""
        await create_notification(
            db=db,
            user_id=item_user_id,
            title="Publicação Não Aprovada",
            message=f"Sua publicação \"{item_title}\" não foi aprovada.{reason_msg}",
            type="ad_rejected",
            link="/painel",
        )

    return item_data


@router.delete("/moderation/{kind}/{item_id}", status_code=204)
async def delete_moderated_item(
    kind: str,
    item_id: str,
    db: AsyncClient = Depends(get_db),
):
    """Exclui permanentemente um item moderável (anúncio, urgência, caridade, etc.)."""
    return await admin_delete_record(table=kind, record_id=item_id, db=db)


# ---------- Usuários ----------


@router.get("/users")
async def list_users(
    search: Optional[str] = Query(None),
    blocked: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncClient = Depends(get_db),
):
    """Lista usuários com filtros (sem expor hashes de senha)."""
    try:
        query = db.table(Tables.USERS).select(
            "id, name, email, phone, city, email_verified, phone_verified, "
            "is_admin, is_blocked, block_reason, created_at",
            count="exact",
        )
        if search:
            query = query.or_(f"name.ilike.%{search}%,email.ilike.%{search}%")
        if blocked is not None:
            query = query.eq("is_blocked", blocked)
        start = (page - 1) * page_size
        result = await query.order("created_at", desc=True).range(start, start + page_size - 1).execute()
        return {"total": result.count or len(result.data or []), "items": result.data or []}
    except Exception as e:
        # Fallback query
        result = await db.table(Tables.USERS).select("*").order("created_at", desc=True).execute()
        items = result.data or []
        for it in items:
            it.pop("password_hash", None)
        return {"total": len(items), "items": items}



@router.post("/users/{user_id}/block")
async def block_user(
    user_id: str,
    payload: BlockUserRequest,
    db: AsyncClient = Depends(get_db),
):
    """Bloqueia ou desbloqueia um usuário."""
    is_blocked_val = payload.is_blocked if payload.is_blocked is not None else payload.blocked
    if is_blocked_val is None:
        is_blocked_val = True
    reason_val = payload.block_reason or payload.reason or ""

    update = {"is_blocked": is_blocked_val}
    if is_blocked_val:
        update["block_reason"] = reason_val
    else:
        update["block_reason"] = None

    result = (
        await db.table(Tables.USERS).update(update).eq("id", user_id).execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return {
        "message": "Usuário bloqueado." if is_blocked_val else "Usuário desbloqueado.",
        "user_id": user_id,
        "is_blocked": is_blocked_val,
    }


@router.put("/users/{user_id}")
async def update_user_admin(
    user_id: str,
    payload: UserUpdateRequest,
    db: AsyncClient = Depends(get_db),
):
    """Atualiza dados, papéis de admin ou status de verificação de um usuário."""
    update_data = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum dado informado para atualização.")
    
    result = await db.table(Tables.USERS).update(update_data).eq("id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    return result.data[0]



# ---------- Gift codes ----------

@router.post("/gift-codes", status_code=201)
async def generate_gift_codes(
    payload: GiftCodeCreateRequest,
    admin: dict = Depends(get_admin_user),
    db: AsyncClient = Depends(get_db),
):
    """Gera códigos promocionais (destaque grátis ou indicação)."""
    prefix = "REF" if payload.type.value == "referral" else "GIFT"
    rows = []
    for _ in range(payload.quantity):
        code_str = generate_gift_code(prefix)
        row = {
            "code": code_str,
            "type": "promo" if payload.type.value == "highlight" else payload.type.value,
            "creator_id": admin["id"],
            "duration_days": 7,
            "max_uses": payload.max_uses,
            "used_count": 0,
            "is_active": True,
            "expires_at": payload.expires_at,
        }
        rows.append(row)
    try:
        result = await db.table(Tables.GIFT_CODES).insert(rows).execute()
    except Exception:
        fallback = [
            {
                "code": r["code"],
                "type": payload.type.value,
                "max_uses": payload.max_uses,
                "uses_count": 0,
                "used_by": [],
                "active": True,
                "expires_at": payload.expires_at,
                "created_by": admin["id"],
            }
            for r in rows
        ]
        result = await db.table(Tables.GIFT_CODES).insert(fallback).execute()

    return {"generated": len(result.data), "codes": [r["code"] for r in result.data]}


@router.get("/gift-codes")
async def list_gift_codes(db: AsyncClient = Depends(get_db)):
    result = (
        await db.table(Tables.GIFT_CODES)
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


@router.post("/gift-codes/{code_id}/deactivate")
async def deactivate_gift_code(code_id: str, db: AsyncClient = Depends(get_db)):
    result = (
        await db.table(Tables.GIFT_CODES)
        .update({"active": False})
        .eq("id", code_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Código não encontrado.")
    return {"message": "Código desativado."}


# ---------- Denúncias ----------

@router.get("/reports")
async def list_reports(
    status: str = Query(ReportStatus.OPEN.value),
    db: AsyncClient = Depends(get_db),
):
    """Lista denúncias por status."""
    try:
        result = (
            await db.table(Tables.REPORTS)
            .select("*, users(name, email)")
            .eq("status", status)
            .order("created_at")
            .execute()
        )
        return result.data or []
    except Exception:
        try:
            result = (
                await db.table(Tables.REPORTS)
                .select("*")
                .eq("status", status)
                .order("created_at")
                .execute()
            )
            return result.data or []
        except Exception:
            return []



@router.post("/reports/{report_id}/resolve")
async def resolve_report(
    report_id: str,
    payload: ReportResolveRequest,
    db: AsyncClient = Depends(get_db),
):
    """Resolve ou descarta uma denúncia."""
    result = (
        await db.table(Tables.REPORTS)
        .update(
            {
                "status": payload.resolution,
                "resolution_note": payload.note,
                "resolved_at": utcnow().isoformat(),
            }
        )
        .eq("id", report_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Denúncia não encontrada.")
    return result.data[0]


# ---------- Ranking ----------

@router.post("/ranking/run")
async def run_ranking_manually(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    db: AsyncClient = Depends(get_db),
):
    """Dispara o cálculo do ranking mensal manualmente (padrão: mês anterior)."""
    rows = await compute_monthly_ranking(db, year=year, month=month)
    return {"ranked": len(rows), "top": rows[:3]}


@router.post("/consulate/posts/{post_id}/archive")
async def archive_consulate_post(post_id: str, db: AsyncClient = Depends(get_db)):
    res = await db.table(Tables.CONSULATE_POSTS).update({"status": "archived"}).eq("id", post_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Postagem não encontrada.")
    return {"message": "Postagem arquivada com sucesso.", "post": res.data[0]}

@router.post("/consulate/posts/{post_id}/unarchive")
async def unarchive_consulate_post(post_id: str, db: AsyncClient = Depends(get_db)):
    res = await db.table(Tables.CONSULATE_POSTS).update({"status": "active"}).eq("id", post_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Postagem não encontrada.")
    return {"message": "Postagem desarquivada com sucesso.", "post": res.data[0]}


# ---------- Listagem Genérica (Admin Dashboard) ----------

@router.get("/tables/{table}")
async def admin_list_table(
    table: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncClient = Depends(get_db),
):
    """Lista registros de qualquer tabela gerenciável."""
    if table not in MANAGEABLE_TABLES:
        raise HTTPException(status_code=404, detail="Tabela não gerenciável.")
    start = (page - 1) * page_size
    result = (
        await db.table(MANAGEABLE_TABLES[table])
        .select("*", count="exact")
        .range(start, start + page_size - 1)
        .execute()
    )
    return {"total": result.count or 0, "items": result.data or []}


@router.put("/tables/{table}/{record_id}")
async def admin_update_record(
    table: str,
    record_id: str,
    payload: dict,
    db: AsyncClient = Depends(get_db),
):
    """Edita um registro de qualquer tabela gerenciável com fallback automático."""
    if table not in MANAGEABLE_TABLES:
        raise HTTPException(status_code=404, detail="Tabela não gerenciável.")
    payload.pop("id", None)
    # Nunca permitir alterar hash de senha diretamente por aqui
    if table == "users":
        payload.pop("password_hash", None)
    if not payload:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar.")

    actual_table = MANAGEABLE_TABLES[table]
    result = None
    try:
        res = (
            await db.table(actual_table)
            .update(payload)
            .eq("id", record_id)
            .execute()
        )
        if res.data:
            result = res
    except Exception:
        pass

    if not result or not result.data:
        if table in ["moving_sales", "moving-sales"]:
            try:
                charity_payload = dict(payload)
                if "city" in charity_payload and "location" not in charity_payload:
                    charity_payload["location"] = charity_payload.pop("city")
                res_c = await db.table(Tables.CHARITY_ADS).update(charity_payload).eq("id", record_id).execute()
                if res_c.data:
                    result = res_c
            except Exception:
                pass

            if not result or not result.data:
                try:
                    res_g = await db.table(Tables.GROUPS).update(payload).eq("id", record_id).execute()
                    if res_g.data:
                        result = res_g
                except Exception:
                    pass

        elif table in ["artists"]:
            try:
                charity_payload = dict(payload)
                if "city" in charity_payload and "location" not in charity_payload:
                    charity_payload["location"] = charity_payload.pop("city")
                if "artistic_name" in charity_payload and "title" not in charity_payload:
                    charity_payload["title"] = f"[ARTISTA] {charity_payload.pop('artistic_name')}"
                if "bio" in charity_payload and "description" not in charity_payload:
                    charity_payload["description"] = charity_payload.pop("bio")
                if "phone" in charity_payload and "contact_phone" not in charity_payload:
                    charity_payload["contact_phone"] = charity_payload.pop("phone")
                res_c = await db.table(Tables.CHARITY_ADS).update(charity_payload).eq("id", record_id).execute()
                if res_c.data:
                    result = res_c
            except Exception:
                pass

            if not result or not result.data:
                try:
                    res_g = await db.table(Tables.GROUPS).update(payload).eq("id", record_id).execute()
                    if res_g.data:
                        result = res_g
                except Exception:
                    pass

        elif table in ["regulation_posts", "regulation-posts"]:
            try:
                reg_payload = dict(payload)
                if "content" not in reg_payload and "description" in reg_payload:
                    reg_payload["content"] = reg_payload.get("description")
                res_reg = await db.table(Tables.REGULATION_POSTS).update(reg_payload).eq("id", record_id).execute()
                if res_reg.data:
                    result = res_reg
            except Exception:
                pass

    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Registro não encontrado.")
    return result.data[0]


@router.delete("/tables/{table}/{record_id}", status_code=204)
async def admin_delete_record(
    table: str,
    record_id: str,
    db: AsyncClient = Depends(get_db),
):
    """Apaga um registro de qualquer tabela gerenciável, tratando dependências e chaves estrangeiras."""
    # Normaliza nomes de tabelas alternativos
    table_map = {
        "urgent_ads": Tables.URGENT_ADS,
        "urgent-ads": Tables.URGENT_ADS,
        "charity_ads": Tables.CHARITY_ADS,
        "charity-ads": Tables.CHARITY_ADS,
        "tourism_spots": Tables.TOURISM_SPOTS,
        "tourism-spots": Tables.TOURISM_SPOTS,
        "pet_posts": Tables.PET_POSTS,
        "pet-posts": Tables.PET_POSTS,
        "job_ads": Tables.GROUPS,
        "job-ads": Tables.GROUPS,
        "jobs": Tables.GROUPS,
        "arrival-guide": Tables.GROUPS,
        "arrival_guide": Tables.GROUPS,
        "moving_sales": Tables.MOVING_SALES,
        "moving-sales": Tables.MOVING_SALES,
        "artists": Tables.ARTISTS,
        "artist_events": Tables.ARTIST_EVENTS,
        "regulation_posts": Tables.REGULATION_POSTS,
        "regulation-posts": Tables.REGULATION_POSTS,
        "regulation_replies": Tables.REGULATION_REPLIES,
        "regulation_reports": Tables.REGULATION_REPORTS,
    }
    actual_table = table_map.get(table) or MANAGEABLE_TABLES.get(table) or table

    # 1. Se for exclusão de ANÚNCIO (ads), limpa registros filhos antes (avaliações, histórico, pagamentos)
    if actual_table == Tables.ADS:
        try:
            await db.table(Tables.REVIEWS).delete().eq("ad_id", record_id).execute()
        except Exception:
            pass
        try:
            await db.table(Tables.EDIT_HISTORY).delete().eq("ad_id", record_id).execute()
        except Exception:
            pass
        try:
            await db.table(Tables.PAYMENTS).delete().eq("ad_id", record_id).execute()
        except Exception:
            pass

    # 2. Se for exclusão de USUÁRIO (users), limpa anúncios, grupos, avaliações, etc.
    elif actual_table == Tables.USERS:
        try:
            await db.table(Tables.ADMINS).delete().eq("user_id", record_id).execute()
        except Exception:
            pass
        try:
            await db.table(Tables.NOTIFICATIONS).delete().eq("user_id", record_id).execute()
        except Exception:
            pass
        try:
            await db.table(Tables.REVIEWS).delete().eq("user_id", record_id).execute()
        except Exception:
            pass
        try:
            await db.table(Tables.GROUPS).delete().eq("created_by", record_id).execute()
        except Exception:
            pass
        try:
            await db.table(Tables.URGENT_ADS).delete().eq("user_id", record_id).execute()
        except Exception:
            pass
        try:
            await db.table(Tables.CHARITY_ADS).delete().eq("user_id", record_id).execute()
        except Exception:
            pass
        try:
            # Apaga anúncios próprios do usuário
            my_ads = await db.table(Tables.ADS).select("id").eq("user_id", record_id).execute()
            for a in my_ads.data or []:
                try:
                    await db.table(Tables.REVIEWS).delete().eq("ad_id", a["id"]).execute()
                    await db.table(Tables.EDIT_HISTORY).delete().eq("ad_id", a["id"]).execute()
                    await db.table(Tables.PAYMENTS).delete().eq("ad_id", a["id"]).execute()
                except Exception:
                    pass
            await db.table(Tables.ADS).delete().eq("user_id", record_id).execute()
        except Exception:
            pass

    # 3. Tenta apagar da tabela alvo principal
    deleted = False
    try:
        if actual_table == Tables.ARTISTS:
            try:
                await db.table(Tables.ARTIST_EVENTS).delete().eq("artist_id", record_id).execute()
            except Exception:
                pass
        res = await db.table(actual_table).delete().eq("id", record_id).execute()
        if res.data:
            deleted = True
    except Exception:
        pass

    # 4. Fallback especial para Turismo, Pets, Empregos, Mudança e Artistas
    if not deleted:
        if actual_table in [Tables.TOURISM_SPOTS, Tables.PET_POSTS, "tourism-spots", "pet-posts"]:
            try:
                res_c = await db.table(Tables.CHARITY_ADS).delete().eq("id", record_id).execute()
                if res_c.data:
                    deleted = True
            except Exception:
                pass
        elif actual_table in [Tables.MOVING_SALES, "moving_sales", "moving-sales"]:
            try:
                res_c = await db.table(Tables.CHARITY_ADS).delete().eq("id", record_id).execute()
                if res_c.data:
                    deleted = True
            except Exception:
                pass
            if not deleted:
                try:
                    res_g = await db.table(Tables.GROUPS).delete().eq("id", record_id).execute()
                    if res_g.data:
                        deleted = True
                except Exception:
                    pass
        elif actual_table in [Tables.ARTISTS, "artists"]:
            try:
                res_c = await db.table(Tables.CHARITY_ADS).delete().eq("id", record_id).execute()
                if res_c.data:
                    deleted = True
            except Exception:
                pass
            if not deleted:
                try:
                    res_g = await db.table(Tables.GROUPS).delete().eq("id", record_id).execute()
                    if res_g.data:
                        deleted = True
                except Exception:
                    pass
        elif actual_table in ["job_ads", "jobs", "job-ads", "arrival-guide", "arrival_guide"]:
            try:
                res_g = await db.table(Tables.GROUPS).delete().eq("id", record_id).execute()
                if res_g.data:
                    deleted = True
            except Exception:
                pass
            if not deleted:
                try:
                    res_c = await db.table(Tables.CHARITY_ADS).delete().eq("id", record_id).execute()
                    if res_c.data:
                        deleted = True
                except Exception:
                    pass

    return None

