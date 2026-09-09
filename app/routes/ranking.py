"""Ranking mensal: os 3 melhores avaliados ganham 1 semana de destaque grátis.

Executado automaticamente por cron no 1º dia de cada mês (03h),
com os dados do mês anterior. Também pode ser disparado manualmente pelo admin.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from supabase import AsyncClient

from app.database import get_db
from app.models import AdStatus, RANKING_TOP_REWARDED, Tables
from app.utils.deps import get_optional_user
from app.utils.highlights import activate_highlight

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ranking", tags=["Ranking Mensal"])


@router.get("/latest")
@router.get("/top3")
@router.get("/current")
async def get_latest_ranking(
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Ranking oficial do mês (público) com os 3 primeiros premiados com 1 semana de destaque grátis."""
    try:
        result = (
            await db.table(Tables.MONTHLY_RANKING)
            .select("*, ads(name, city, category, image_url, is_highlighted, highlight_expires)")
            .order("year", desc=True)
            .order("month", desc=True)
            .order("position")
            .limit(50)
            .execute()
        )
        data = result.data or []
        if data:
            formatted = []
            for r in data:
                ad_info = r.get("ads") or {}
                formatted.append({
                    "id": r.get("id"),
                    "ad_id": r.get("ad_id"),
                    "user_id": r.get("user_id"),
                    "name": ad_info.get("name") or r.get("name") or "Profissional",
                    "ad_name": ad_info.get("name") or r.get("name") or "Profissional",
                    "category": ad_info.get("category") or "Serviços",
                    "city": ad_info.get("city") or "França",
                    "image_url": ad_info.get("image_url"),
                    "average_rating": r.get("rating_avg") or r.get("average_rating") or 5.0,
                    "score": r.get("rating_avg") or r.get("average_rating") or 5.0,
                    "reviews_count": r.get("rating_count") or r.get("reviews_count") or 0,
                    "position": r.get("position", 1),
                    "prize_awarded": r.get("prize_awarded", False),
                    "year": r.get("year"),
                    "month": r.get("month"),
                })
            return formatted
    except Exception:
        pass

    # Fallback: se o ranking mensal do banco ainda não rodou no cron, calcula dinamicamente com base nas avaliações
    try:
        ads_res = await db.table(Tables.ADS).select("id, name, city, category, image_url, user_id, status").eq("status", "approved").execute()
        ads_list = ads_res.data or []
        if not ads_list:
            return []
        
        ad_ids = [a["id"] for a in ads_list]
        rev_res = await db.table(Tables.REVIEWS).select("ad_id, rating").in_("ad_id", ad_ids).execute()
        
        ratings_map = {}
        for rev in rev_res.data or []:
            ratings_map.setdefault(rev["ad_id"], []).append(rev["rating"])
        
        ranked = []
        for ad in ads_list:
            ratings = ratings_map.get(ad["id"], [])
            avg = round(sum(ratings) / len(ratings), 2) if ratings else 5.0
            count = len(ratings)
            ranked.append({
                "ad_id": ad["id"],
                "user_id": ad.get("user_id"),
                "name": ad["name"],
                "ad_name": ad["name"],
                "category": ad.get("category") or "Serviços",
                "city": ad.get("city") or "França",
                "image_url": ad.get("image_url"),
                "average_rating": avg,
                "score": avg,
                "reviews_count": count,
            })
        
        ranked.sort(key=lambda x: (-x["reviews_count"], -x["average_rating"]))
        for idx, item in enumerate(ranked, start=1):
            item["position"] = idx
            item["prize_awarded"] = idx <= RANKING_TOP_REWARDED

        return ranked[:20]
    except Exception:
        return []



async def compute_monthly_ranking(
    db: AsyncClient, year: int | None = None, month: int | None = None
) -> list[dict]:
    """Calcula o ranking do mês (por padrão, o mês anterior) pela média das avaliações.

    Salva em `monthly_ranking` e concede 1 semana de destaque grátis aos 3 primeiros.
    """
    now = datetime.utcnow()
    if year is None or month is None:
        # Mês anterior
        first_of_month = now.replace(day=1)
        last_month_end = first_of_month
        month = (last_month_end.month - 1) or 12
        year = last_month_end.year - (1 if now.month == 1 else 0)

    # Período avaliado: mês inteiro
    from calendar import monthrange

    start = datetime(year, month, 1).isoformat()
    end = datetime(year + (month == 12), (month % 12) + 1, 1).isoformat()

    reviews = (
        await db.table(Tables.REVIEWS)
        .select("ad_id, rating")
        .gte("created_at", start)
        .lt("created_at", end)
        .execute()
    )
    if not reviews.data:
        # Se o mês específico não tem avaliações, avalia todas as existentes para gerar o ranking inicial
        reviews = await db.table(Tables.REVIEWS).select("ad_id, rating").execute()

    if not reviews.data:
        # Se não há avaliações de clientes, gera o ranking com os anúncios aprovados ativos
        ads = (
            await db.table(Tables.ADS)
            .select("id, name, user_id")
            .eq("status", AdStatus.APPROVED.value)
            .execute()
        )
        ranking = [
            {
                "ad_id": ad["id"],
                "average_rating": 5.0,
                "reviews_count": 1,
            }
            for ad in ads.data or []
        ]
    else:
        stats: dict[str, list[int]] = {}
        for r in reviews.data:
            stats.setdefault(r["ad_id"], []).append(r["rating"])

        ads = (
            await db.table(Tables.ADS)
            .select("id, name, user_id")
            .in_("id", list(stats.keys()))
            .eq("status", AdStatus.APPROVED.value)
            .execute()
        )
        active_ids = {ad["id"] for ad in ads.data or []}

        ranking = sorted(
            (
                {
                    "ad_id": ad_id,
                    "average_rating": round(sum(ratings) / len(ratings), 2),
                    "reviews_count": len(ratings),
                }
                for ad_id, ratings in stats.items()
                if ad_id in active_ids
            ),
            key=lambda x: (-x["average_rating"], -x["reviews_count"]),
        )

    # Persiste o ranking e premia os 3 primeiros com destaque grátis
    try:
        await (
            db.table(Tables.MONTHLY_RANKING)
            .delete()
            .eq("year", year)
            .eq("month", month)
            .execute()
        )
    except Exception:
        pass

    rows = []
    ad_users = {ad["id"]: ad.get("user_id") for ad in ads.data or []}
    for position, entry in enumerate(ranking, start=1):
        rewarded = position <= RANKING_TOP_REWARDED
        rows.append(
            {
                "year": year,
                "month": month,
                "ad_id": entry["ad_id"],
                "user_id": ad_users.get(entry["ad_id"]),
                "rating_avg": entry["average_rating"],
                "rating_count": entry["reviews_count"],
                "position": position,
                "prize_awarded": rewarded,
            }
        )
    if rows:
        try:
            await db.table(Tables.MONTHLY_RANKING).insert(rows).execute()
        except Exception as e:
            logger.error("Erro ao salvar ranking: %s", e)

    for entry in rows[:RANKING_TOP_REWARDED]:
        try:
            await activate_highlight(db, entry["ad_id"])
            logger.info(
                "Prêmio de destaque concedido ao anúncio %s (posição %d).",
                entry["ad_id"],
                entry["position"],
            )
        except Exception:
            pass

    return rows


async def run_scheduled_ranking() -> None:
    """Ponto de entrada do cron: recria o client e roda o ranking do mês anterior."""
    from app.database import get_service_db

    db = await get_service_db()
    try:
        await compute_monthly_ranking(db)
    except Exception as exc:  # noqa: BLE001
        logger.error("Falha ao calcular ranking mensal: %s", exc)


async def run_scheduled_urgent_expiration() -> None:
    """Cron diário: expira anúncios de urgência com mais de 7 dias."""
    from app.database import get_service_db
    from app.routes.urgent_ads import expire_urgent_ads

    db = await get_service_db()
    try:
        expired = await expire_urgent_ads(db)
        if expired:
            logger.info("%d anúncio(s) de urgência expirados.", expired)
    except Exception as exc:  # noqa: BLE001
        logger.error("Falha ao expirar anúncios de urgência: %s", exc)
