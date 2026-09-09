"""Schemas de grupos parceiros, anúncios de urgência e de caridade."""

from pydantic import BaseModel, Field

from app.models import GroupPlatform, UrgentType


# ---------- Grupos parceiros ----------

class GroupCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    platform: GroupPlatform
    link: str = Field(min_length=10, max_length=500)
    city: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)


class GroupResponse(BaseModel):
    id: str
    name: str
    platform: str
    link: str
    logo_url: str | None = None
    city: str
    category: str
    description: str | None = None
    status: str
    created_at: str | None = None


# ---------- Anúncios de urgência ----------

class UrgentAdResponse(BaseModel):
    id: str
    user_id: str
    type: str
    title: str
    description: str
    city: str
    contact_phone: str
    image_url: str | None = None
    document_url: str | None = None
    badge: str = "URGENTE"
    status: str
    expires_at: str | None = None
    created_at: str | None = None


# ---------- Anúncios de caridade ----------

class CharityAdResponse(BaseModel):
    id: str
    user_id: str
    title: str
    description: str
    city: str
    contact_phone: str
    image_url: str | None = None
    image_url_2: str | None = None
    badge: str = "CARIDADE"
    status: str
    created_at: str | None = None


# ---------- Lugares & Passeios Turísticos (Férias e Lazer) ----------

class TourismSpotResponse(BaseModel):
    id: str
    user_id: str
    title: str
    description: str
    city: str
    category: str | None = "passeio"
    address: str | None = None
    google_maps_url: str | None = None
    tips: str | None = None
    image_url: str | None = None
    image_url_2: str | None = None
    badge: str = "PASSEIO"
    status: str
    created_at: str | None = None


# ---------- Espaço Pet & Cachorros (Escolas, Parques, Encontros) ----------

class PetPostResponse(BaseModel):
    id: str
    user_id: str
    title: str
    description: str
    city: str
    category: str | None = "parque"  # parque, escola_canina, encontro_pet, adestramento, veterinario
    address: str | None = None
    google_maps_url: str | None = None
    contact_phone: str | None = None
    meetup_date: str | None = None
    tips: str | None = None
    image_url: str | None = None
    image_url_2: str | None = None
    badge: str = "PET"
    status: str
    created_at: str | None = None


# ---------- Bate-papo / Comentários por Anúncio (Passeios & Pet) ----------

class ItemCommentCreateRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class ItemCommentResponse(BaseModel):
    id: str
    target_id: str
    target_type: str  # "tourism" ou "pet"
    user_id: str
    user_name: str | None = "Brasileiro(a)"
    message: str
    created_at: str | None = None


class ItemCommentListResponse(BaseModel):
    target_id: str
    target_type: str
    total: int
    items: list[ItemCommentResponse]

