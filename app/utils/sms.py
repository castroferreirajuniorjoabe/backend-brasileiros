"""Envio de SMS (código de verificação de telefone) via Twilio."""

import logging

from app.config import settings

logger = logging.getLogger(__name__)


async def send_sms(to: str, body: str) -> bool:
    """Envia SMS via Twilio. Retorna True em caso de sucesso."""
    if not settings.TWILIO_ACCOUNT_SID:
        logger.warning("Twilio não configurado — SMS para %s não enviado.", to)
        return False
    try:
        from twilio.rest import Client

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        # A lib do Twilio é síncrona; em produção, rodar em thread pool.
        import asyncio

        await asyncio.to_thread(
            client.messages.create,
            body=body,
            from_=settings.TWILIO_FROM_NUMBER,
            to=to,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Falha ao enviar SMS para %s: %s", to, exc)
        return False


async def send_phone_verification_code(to: str, code: str) -> bool:
    body = f"Brasileiros na França: seu código de verificação é {code}. Válido por 10 minutos."
    return await send_sms(to, body)
