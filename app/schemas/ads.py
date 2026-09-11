"""Schemas de anúncios comerciais e avaliações."""

from pydantic import BaseModel, Field, HttpUrl


# ---------- Anúncios ----------

class AdUpdateRequest(BaseModel):
    """Campos editáveis de um anúncio (limite de 2 edições/mês, com moderação)."""
    name: str | None = Field(default=None, min_length=2, max_length=200)
    address: str | None = None
    city: str | None = None
    category: str | None = None
    phone: str | None = None
    landline_phone: str | None = None
    email: str | None = None
    description: str | None = None
    website: HttpUrl | None = None
    instagram: str | None = None
    facebook: HttpUrl | None = None
    opening_hours: str | None = None


class AdResponse(BaseModel):
    id: str
    user_id: str
    name: str
    address: str
    city: str
    category: str
    phone: str
    landline_phone: str | None = None
    email: str
    description: str
    image_url: str
    website: str | None = None
    instagram: str | None = None
    facebook: str | None = None
    opening_hours: str | None = None
    image_url_2: str | None = None
    status: str
    is_highlighted: bool = False
    highlight_until: str | None = None
    average_rating: float | None = None
    reviews_count: int = 0
    created_at: str | None = None


class AdListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AdResponse]


class RejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


# ---------- Avaliações ----------

class ReviewCreateRequest(BaseModel):
    rating: int = Field(ge=1, le=5, description="Nota de 1 a 5")
    comment: str | None = Field(default=None, max_length=1000)


class ReviewResponse(BaseModel):
    id: str
    ad_id: str
    user_id: str
    user_name: str | None = None
    rating: int
    comment: str | None = None
    created_at: str | None = None


class ReviewListResponse(BaseModel):
    average_rating: float | None
    total: int
    items: list[ReviewResponse]
