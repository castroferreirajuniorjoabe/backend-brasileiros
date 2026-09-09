"""Pagamentos com Stripe: checkout do destaque (€2/semana) + webhook."""

import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from supabase import AsyncClient

from app.config import settings
from app.database import get_db
from app.models import AdStatus, PaymentStatus, Tables
from app.schemas.admin_ops import CheckoutRequest, CheckoutResponse, PaymentResponse
from app.utils.deps import get_current_user
from app.utils.highlights import activate_highlight
from app.utils.security import utcnow

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter(prefix="/payments", tags=["Pagamentos"])


@router.post("/highlight/{ad_id}")
async def activate_highlight_direct(
    ad_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Ativação direta e gratuita do destaque do anúncio (€0) para o usuário autenticado."""
    ad = (
        await db.table(Tables.ADS)
        .select("id, user_id, name, status")
        .eq("id", ad_id)
        .limit(1)
        .execute()
    )
    if not ad.data:
        raise HTTPException(status_code=404, detail="Anúncio não encontrado.")
    if ad.data[0]["user_id"] != user["id"] and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="O anúncio precisa ser seu.")

    await activate_highlight(db, ad_id)
    return {
        "success": True,
        "message": "Destaque gratuito ativado com sucesso!",
        "is_highlighted": True,
        "ad_id": ad_id,
    }


@router.post("/checkout", response_model=CheckoutResponse, status_code=201)
async def create_checkout_session(
    payload: CheckoutRequest,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Cria sessão de checkout do Stripe para destaque de anúncio (€2/semana)."""
    ad = (
        await db.table(Tables.ADS)
        .select("id, user_id, name, status")
        .eq("id", payload.ad_id)
        .limit(1)
        .execute()
    )
    if not ad.data:
        raise HTTPException(status_code=404, detail="Anúncio não encontrado.")
    if ad.data[0]["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="O anúncio precisa ser seu.")
    if ad.data[0]["status"] != AdStatus.APPROVED.value:
        raise HTTPException(status_code=400, detail="O anúncio precisa estar aprovado.")

    try:
        import asyncio

        session = await asyncio.to_thread(
            stripe.checkout.Session.create,
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": settings.HIGHLIGHT_CURRENCY,
                        "unit_amount": settings.HIGHLIGHT_PRICE_CENTS,
                        "product_data": {
                            "name": f"Destaque no carrossel — {ad.data[0]['name']}",
                            "description": "1 semana de destaque no Brasileiros na França",
                        },
                    },
                    "quantity": 1,
                }
            ],
            success_url=f"{settings.FRONTEND_URL}/pagamento/sucesso?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_URL}/pagamento/cancelado",
            metadata={"ad_id": payload.ad_id, "user_id": user["id"]},
            customer_email=user["email"],
        )
    except stripe.StripeError as exc:
        logger.error("Erro no Stripe: %s", exc)
        raise HTTPException(status_code=502, detail="Falha ao criar sessão de pagamento.") from exc

    # Registra o pagamento como pendente
    await db.table(Tables.PAYMENTS).insert(
        {
            "user_id": user["id"],
            "ad_id": payload.ad_id,
            "amount_cents": settings.HIGHLIGHT_PRICE_CENTS,
            "currency": settings.HIGHLIGHT_CURRENCY,
            "status": PaymentStatus.PENDING.value,
            "stripe_session_id": session.id,
        }
    ).execute()

    return CheckoutResponse(checkout_url=session.url, session_id=session.id)


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, db: AsyncClient = Depends(get_db)):
    """Webhook do Stripe: confirma o pagamento e ativa o destaque automaticamente."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise HTTPException(status_code=400, detail="Assinatura do webhook inválida.") from exc

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        ad_id = session.get("metadata", {}).get("ad_id")
        session_id = session.get("id")

        if ad_id:
            await (
                db.table(Tables.PAYMENTS)
                .update({"status": PaymentStatus.PAID.value, "paid_at": utcnow().isoformat()})
                .eq("stripe_session_id", session_id)
                .execute()
            )
            await activate_highlight(db, ad_id)
            logger.info("Destaque ativado para o anúncio %s (sessão %s).", ad_id, session_id)

    elif event["type"] in ("checkout.session.expired", "payment_intent.payment_failed"):
        session = event["data"]["object"]
        session_id = session.get("id") or session.get("latest_charge")
        if session_id:
            await (
                db.table(Tables.PAYMENTS)
                .update({"status": PaymentStatus.FAILED.value})
                .eq("stripe_session_id", session_id)
                .execute()
            )

    return {"received": True}


@router.get("/mine", response_model=list[PaymentResponse])
async def list_my_payments(
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Histórico de pagamentos do usuário autenticado."""
    result = (
        await db.table(Tables.PAYMENTS)
        .select("*")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []
