"""Avaliações de anúncios: nota 1–5 + comentário, média calculada automaticamente."""

from fastapi import APIRouter, Depends, HTTPException
from supabase import AsyncClient

from app.database import get_db
from app.models import AdStatus, Tables
from app.schemas.ads import ReviewCreateRequest, ReviewListResponse, ReviewResponse
from app.utils.deps import get_current_user, get_optional_user

router = APIRouter(prefix="/ads/{ad_id}/reviews", tags=["Avaliações"])


async def _get_ad(db: AsyncClient, ad_id: str) -> dict:
    result = (
        await db.table(Tables.ADS).select("id, user_id, status").eq("id", ad_id).limit(1).execute()
    )
    if not result.data or result.data[0]["status"] == AdStatus.DELETED.value:
        raise HTTPException(status_code=404, detail="Anúncio não encontrado.")
    return result.data[0]


@router.post("", response_model=ReviewResponse, status_code=201)
async def create_review(
    ad_id: str,
    payload: ReviewCreateRequest,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Cria avaliação (nota 1 a 5 + comentário). Uma avaliação por usuário por anúncio."""
    ad = await _get_ad(db, ad_id)
    if ad["user_id"] == user["id"]:
        raise HTTPException(status_code=400, detail="Você não pode avaliar seu próprio anúncio.")

    existing = (
        await db.table(Tables.REVIEWS)
        .select("id")
        .eq("ad_id", ad_id)
        .eq("user_id", user["id"])
        .limit(1)
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=409, detail="Você já avaliou este anúncio.")

    result = await db.table(Tables.REVIEWS).insert(
        {
            "ad_id": ad_id,
            "user_id": user["id"],
            "rating": payload.rating,
            "comment": payload.comment,
        }
    ).execute()
    review = result.data[0]
    review["user_name"] = user.get("name")
    return review


@router.get("", response_model=ReviewListResponse)
async def list_reviews(
    ad_id: str,
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Lista avaliações de um anúncio com a média calculada (público)."""
    await _get_ad(db, ad_id)
    result = (
        await db.table(Tables.REVIEWS)
        .select("*, users(name)")
        .eq("ad_id", ad_id)
        .order("created_at", desc=True)
        .execute()
    )
    items: list[dict] = []
    ratings: list[int] = []
    for r in result.data or []:
        r["user_name"] = (r.pop("users", None) or {}).get("name")
        ratings.append(r["rating"])
        items.append(r)
    average = round(sum(ratings) / len(ratings), 2) if ratings else None
    return ReviewListResponse(average_rating=average, total=len(items), items=items)


@router.delete("/{review_id}", status_code=204)
async def delete_review(
    ad_id: str,
    review_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Apaga avaliação (autor ou admin)."""
    result = (
        await db.table(Tables.REVIEWS)
        .select("user_id")
        .eq("id", review_id)
        .eq("ad_id", ad_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada.")
    if result.data[0]["user_id"] != user["id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Sem permissão para apagar esta avaliação.")
    await db.table(Tables.REVIEWS).delete().eq("id", review_id).execute()
    return None
