from typing import Optional
from datetime import date, time, datetime
from pydantic import BaseModel, Field

class ConsulatePostCreate(BaseModel):
    consulate: str = Field(pattern="^(paris|marseille)$")
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(min_length=10)
    event_date: Optional[date] = None
    event_time: Optional[time] = None
    location: Optional[str] = None
    category: str = "evento"
    image_url: Optional[str] = None
    official_link: Optional[str] = None

class ConsulatePostUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=150)
    description: Optional[str] = Field(None, min_length=10)
    event_date: Optional[date] = None
    event_time: Optional[time] = None
    location: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    official_link: Optional[str] = None

class ConsulatePostResponse(BaseModel):
    id: str
    user_id: str
    consulate: str
    title: str
    description: str
    event_date: Optional[date] = None
    event_time: Optional[time] = None
    location: Optional[str] = None
    category: str
    image_url: Optional[str] = None
    official_link: Optional[str] = None
    is_official: bool
    status: str
    created_at: datetime
    updated_at: datetime
