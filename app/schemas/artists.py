"""Schemas Pydantic para a seção 'Artistas Brasileiros' (Espaço do Artista)."""

from typing import List, Optional
from pydantic import BaseModel, Field


class ArtistEventBase(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    description: Optional[str] = Field(None, max_length=2000)
    event_date: Optional[str] = None  # YYYY-MM-DD
    event_time: Optional[str] = None  # HH:MM
    location: str = Field(min_length=2, max_length=200)
    city: str = Field(default="França", max_length=100)
    ticket_price: Optional[float] = 0.0
    ticket_link: Optional[str] = None
    image_url: Optional[str] = None


class ArtistEventCreate(ArtistEventBase):
    pass


class ArtistEventResponse(ArtistEventBase):
    id: str
    artist_id: str
    status: str = "approved"
    created_at: Optional[str] = None


class ArtistBase(BaseModel):
    artistic_name: str = Field(min_length=2, max_length=150)
    area: str = Field(default="Música")  # Música, Dança, Teatro, Artes Visuais, Literatura, Cinema, Circo, Artesanato, Arte Digital, Outros
    bio: str = Field(min_length=10, max_length=5000)
    city: str = Field(default="França")
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    youtube: Optional[str] = None
    tiktok: Optional[str] = None
    website: Optional[str] = None
    phone: str = Field(min_length=3, max_length=50)
    email: str = Field(min_length=5, max_length=150)
    whatsapp: Optional[str] = None


class ArtistCreate(ArtistBase):
    pass


class ArtistUpdateRequest(BaseModel):
    artistic_name: Optional[str] = None
    area: Optional[str] = None
    bio: Optional[str] = None
    city: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    youtube: Optional[str] = None
    tiktok: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    whatsapp: Optional[str] = None


class ArtistResponse(ArtistBase):
    id: str
    user_id: str
    profile_image: Optional[str] = None
    gallery_images: List[str] = []
    is_featured: bool = False
    is_verified: bool = False
    status: str = "pending"  # pending, approved, rejected
    rejection_reason: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    events: List[ArtistEventResponse] = []


class ArtistListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[ArtistResponse]
