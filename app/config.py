"""Configurações da aplicação (Pydantic Settings / python-dotenv)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_NAME: str = "Brasileiros na França"
    ENVIRONMENT: str = "development"
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"

    # JWT
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 dias

    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str

    # Stripe (destaque €2/semana)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    HIGHLIGHT_PRICE_CENTS: int = 200  # €2
    HIGHLIGHT_CURRENCY: str = "eur"

    # SMTP (verificação de email)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""

    # Twilio (verificação de telefone por SMS)
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""

    # Cloudinary (upload de imagens)
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
