"""Schemas para Igrejas Brasileiras na França."""

from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional

# --- Church Profile ---

class ChurchCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    denomination: str
    description: Optional[str] = Field(None, max_length=1000)
    address: str
    city: str
    postal_code: Optional[str] = None
    country: Optional[str] = "France"
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    youtube: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    services_offered: Optional[List[str]] = []
    languages: Optional[List[str]] = []
    profile_image: str
    banner_image: Optional[str] = None

class ChurchUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    denomination: Optional[str] = None
    description: Optional[str] = Field(None, max_length=1000)
    address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    youtube: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    services_offered: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    profile_image: Optional[str] = None
    banner_image: Optional[str] = None

class ChurchResponse(BaseModel):
    id: str
    user_id: str
    name: str
    denomination: str
    description: Optional[str] = None
    address: str
    city: str
    postal_code: Optional[str] = None
    country: Optional[str] = "France"
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    youtube: Optional[str] = None
    profile_image: str
    banner_image: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    services_offered: Optional[List[str]] = []
    languages: Optional[List[str]] = []
    is_verified: bool = False
    is_featured: bool = False
    status: str
    rejection_reason: Optional[str] = None
    created_at: str
    updated_at: str

# --- Church Schedule ---

class ChurchScheduleCreate(BaseModel):
    day_of_week: str
    time: str
    type: str
    language: Optional[str] = None
    celebrant: Optional[str] = None
    notes: Optional[str] = None
    order_index: Optional[int] = 0

class ChurchScheduleResponse(BaseModel):
    id: str
    church_id: str
    day_of_week: str
    time: str
    type: str
    language: Optional[str] = None
    celebrant: Optional[str] = None
    notes: Optional[str] = None
    order_index: int

# --- Church Events ---

class ChurchEventCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str
    event_date: str
    event_time: Optional[str] = None
    location: str
    type: str
    registration_link: Optional[HttpUrl] = None

class ChurchEventResponse(BaseModel):
    id: str
    church_id: str
    title: str
    description: str
    event_date: str
    event_time: Optional[str] = None
    location: str
    image_url: Optional[str] = None
    type: str
    registration_link: Optional[str] = None
    status: str
    created_at: str

# --- Church Groups ---

class ChurchGroupCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    description: Optional[str] = None
    group_type: str
    meeting_day: Optional[str] = None
    meeting_time: Optional[str] = None
    leader_name: Optional[str] = None
    contact: Optional[str] = None

class ChurchGroupResponse(BaseModel):
    id: str
    church_id: str
    name: str
    description: Optional[str] = None
    group_type: str
    meeting_day: Optional[str] = None
    meeting_time: Optional[str] = None
    leader_name: Optional[str] = None
    contact: Optional[str] = None
    created_at: str

# --- Church Leaders ---

class ChurchLeaderCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    role: str
    bio: Optional[str] = None
    languages: Optional[List[str]] = []
    office_hours: Optional[str] = None
    whatsapp: Optional[str] = None
    order_index: Optional[int] = 0

class ChurchLeaderResponse(BaseModel):
    id: str
    church_id: str
    name: str
    role: str
    bio: Optional[str] = None
    photo_url: Optional[str] = None
    languages: Optional[List[str]] = []
    office_hours: Optional[str] = None
    whatsapp: Optional[str] = None
    order_index: int
    created_at: str

# --- Church Social Services ---

class ChurchSocialServiceCreate(BaseModel):
    service_name: str = Field(..., min_length=2, max_length=150)
    description: Optional[str] = None
    how_to_access: Optional[str] = None
    responsible_name: Optional[str] = None
    contact: Optional[str] = None
    order_index: Optional[int] = 0

class ChurchSocialServiceResponse(BaseModel):
    id: str
    church_id: str
    service_name: str
    description: Optional[str] = None
    how_to_access: Optional[str] = None
    responsible_name: Optional[str] = None
    contact: Optional[str] = None
    order_index: int
    created_at: str
