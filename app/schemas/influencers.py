"""Schemas para Influencers Brasileiros na França."""

from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional

# --- Influencer Profile ---

class InfluencerCreate(BaseModel):
    artistic_name: str = Field(..., min_length=2, max_length=100)
    real_name: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=500)
    area: str
    city: str
    instagram: Optional[str] = None
    tiktok: Optional[str] = None
    youtube: Optional[str] = None
    twitter: Optional[str] = None
    other_social: Optional[str] = None
    followers_count: Optional[int] = 0
    languages: Optional[List[str]] = []
    partnership_types: Optional[List[str]] = []
    average_price: Optional[str] = None
    whatsapp: Optional[str] = None
    email: str
    website: Optional[str] = None
    profile_image: str
    banner_image: Optional[str] = None

class InfluencerUpdate(BaseModel):
    artistic_name: Optional[str] = Field(None, min_length=2, max_length=100)
    real_name: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=500)
    area: Optional[str] = None
    city: Optional[str] = None
    instagram: Optional[str] = None
    tiktok: Optional[str] = None
    youtube: Optional[str] = None
    twitter: Optional[str] = None
    other_social: Optional[str] = None
    followers_count: Optional[int] = None
    languages: Optional[List[str]] = None
    partnership_types: Optional[List[str]] = None
    average_price: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    profile_image: Optional[str] = None
    banner_image: Optional[str] = None

class InfluencerResponse(BaseModel):
    id: str
    user_id: str
    artistic_name: str
    real_name: Optional[str] = None
    bio: Optional[str] = None
    area: str
    city: str
    profile_image: str
    banner_image: Optional[str] = None
    instagram: Optional[str] = None
    tiktok: Optional[str] = None
    youtube: Optional[str] = None
    twitter: Optional[str] = None
    other_social: Optional[str] = None
    followers_count: Optional[int] = 0
    languages: Optional[List[str]] = []
    partnership_types: Optional[List[str]] = []
    average_price: Optional[str] = None
    whatsapp: Optional[str] = None
    email: str
    website: Optional[str] = None
    is_verified: bool = False
    is_featured: bool = False
    status: str
    rejection_reason: Optional[str] = None
    created_at: str
    updated_at: str

# --- Influencer Events ---

class InfluencerEventCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str
    event_date: str
    event_time: Optional[str] = None
    location: str
    city: Optional[str] = None
    registration_link: Optional[HttpUrl] = None
    type: str

class InfluencerEventResponse(BaseModel):
    id: str
    influencer_id: str
    title: str
    description: str
    event_date: str
    event_time: Optional[str] = None
    location: str
    city: Optional[str] = None
    image_url: Optional[str] = None
    registration_link: Optional[str] = None
    type: str
    status: str
    created_at: str

# --- Influencer Portfolio ---

class InfluencerPortfolioCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    media_type: Optional[str] = "image"
    brand_name: Optional[str] = None
    order_index: Optional[int] = 0

class InfluencerPortfolioResponse(BaseModel):
    id: str
    influencer_id: str
    title: str
    description: Optional[str] = None
    image_url: str
    media_type: str
    brand_name: Optional[str] = None
    order_index: int
    created_at: str

# --- Moderation ---
class RejectRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500)
