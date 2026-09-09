"""Envio de emails transacionais (verificação de conta) via SMTP assíncrono."""

import logging
from email.message import EmailMessage

import aiosmtplib

from app.config import settings

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, html_body: str) -> bool:
    """Envia email HTML. Retorna True em caso de sucesso."""
    if not settings.SMTP_HOST:
        logger.warning("SMTP não configurado — email para %s não enviado.", to)
        return False

    message = EmailMessage()
    message["From"] = settings.SMTP_FROM or settings.SMTP_USER
    message["To"] = to
    message["Subject"] = subject
    message.set_content("Seu cliente de email não suporta HTML.")
    message.add_alternative(html_body, subtype="html")

    try:
        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER or None,
            password=settings.SMTP_PASSWORD or None,
            start_tls=True,
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Falha ao enviar email para %s: %s", to, exc)
        return False


async def send_verification_email(to: str, name: str, token: str) -> bool:
    """Envia o link de verificação de email com token."""
    link = f"{settings.FRONTEND_URL}/verificar-email?token={token}"
    html = f"""
    <h2>Bem-vindo(a) ao Brasileiros na França, {name}!</h2>
    <p>Clique no botão abaixo para confirmar seu email:</p>
    <p>
      <a href="{link}" style="background:#009739;color:#fff;padding:12px 24px;
         border-radius:6px;text-decoration:none;font-weight:bold">
         Verificar meu email
      </a>
    </p>
    <p>Ou copie este link: <a href="{link}">{link}</a></p>
    <p><small>Se você não criou esta conta, ignore este email.</small></p>
    """
    return await send_email(to, "Confirme seu email — Brasileiros na França", html)
