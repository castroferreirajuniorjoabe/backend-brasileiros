"""Schemas Pydantic para a seção 'Dúvidas de Regularização 🇧🇷🇫🇷'."""

from typing import List, Optional
from pydantic import BaseModel, Field


class RegulationUserSummary(BaseModel):
    id: str
    name: Optional[str] = "Membro da Comunidade"
    avatar_url: Optional[str] = None
    city: Optional[str] = "França"
    is_verified: bool = False
    badge: Optional[str] = None  # 'Especialista', 'Colaborador', etc.


class RegulationReplyCreate(BaseModel):
    content: str = Field(min_length=2, max_length=5000)


class RegulationReplyUpdate(BaseModel):
    content: str = Field(min_length=2, max_length=5000)


class RegulationReplyResponse(BaseModel):
    id: str
    post_id: str
    user_id: str
    user: Optional[RegulationUserSummary] = None
    content: str
    likes_count: int = 0
    has_liked: bool = False
    is_best_answer: bool = False
    status: str = "active"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class RegulationPostBase(BaseModel):
    type: Optional[str] = Field(default="question", description="'question' ou 'tip'")
    post_type: Optional[str] = None
    category: str = Field(default="vistos", description="Categoria específica")
    title: str = Field(min_length=3, max_length=200)
    content: str = Field(min_length=10, max_length=10000)
    images: Optional[List[str]] = []


class RegulationPostCreate(RegulationPostBase):
    pass


class RegulationPostUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    images: Optional[List[str]] = None


class RegulationPostResponse(BaseModel):
    id: str
    user_id: str
    user: Optional[RegulationUserSummary] = None
    type: str = "question"  # 'question' | 'tip'
    category: str = "vistos"
    title: str
    content: str
    images: List[str] = []
    likes_count: int = 0
    replies_count: int = 0
    views_count: int = 0
    has_liked: bool = False
    is_solved: bool = False
    best_reply_id: Optional[str] = None
    best_reply: Optional[RegulationReplyResponse] = None
    status: str = "active"  # 'active', 'pending', 'hidden', 'deleted'
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    replies: List[RegulationReplyResponse] = []


class RegulationPostListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[RegulationPostResponse]


class RegulationLikeToggleResponse(BaseModel):
    has_liked: bool
    likes_count: int
    message: str


class RegulationReportCreate(BaseModel):
    target_type: str = Field(..., description="'post' ou 'reply'")
    target_id: str
    reason: str = Field(..., min_length=3, max_length=100)
    details: Optional[str] = Field(None, max_length=1000)


class RegulationReportResponse(BaseModel):
    id: str
    user_id: str
    user: Optional[RegulationUserSummary] = None
    target_type: str
    target_id: str
    target_title: Optional[str] = None
    target_content: Optional[str] = None
    reason: str
    details: Optional[str] = None
    status: str = "pending"
    created_at: Optional[str] = None
