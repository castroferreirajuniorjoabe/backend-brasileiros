"""Clientes assíncronos do Supabase.

- service client (service_role): bypassa RLS — usar em operações administrativas
  e tudo o que o backend precisa garantir (o backend é a camada de autorização).
- anon client: respeita RLS — disponível caso alguma operação precise respeitar
  as políticas diretamente.
"""
from typing import Optional

from supabase import AsyncClient, acreate_client

from app.config import settings

_service_client: Optional[AsyncClient] = None
_anon_client: Optional[AsyncClient] = None


async def get_service_db() -> AsyncClient:
    """Cliente com service_role (acesso total — usar com cuidado)."""
    global _service_client
    if _service_client is None:
        _service_client = await acreate_client(
            settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY
        )
    return _service_client


async def get_anon_db() -> AsyncClient:
    """Cliente com anon key (respeita RLS)."""
    global _anon_client
    if _anon_client is None:
        _anon_client = await acreate_client(
            settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY
        )
    return _anon_client


# Dependência padrão das rotas: o backend controla a autorização via JWT próprio,
# então usamos o service client e validamos permissões no código.
async def get_db() -> AsyncClient:
    return await get_service_db()
