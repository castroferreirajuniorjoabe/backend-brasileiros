"""Schemas para a seção 'Mudança & Vendas' (Desapegos e Vendas de Itens Pessoais)."""

from typing import Optional
from pydantic import BaseModel, Field


class MovingSaleCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=150, description="Título do anúncio")
    description: str = Field(min_length=10, max_length=5000, description="Descrição detalhada do item")
    category: str = Field(default="Móveis", max_length=80, description="Categoria do objeto")
    condition: str = Field(default="usado", max_length=30, description="Estado: novo, seminovo, usado")
    price: float = Field(default=0.0, ge=0, description="Preço em Euros (0 para Doação/Grátis)")
    city: str = Field(min_length=2, max_length=100, description="Cidade ou região")
    address: Optional[str] = Field(default=None, max_length=250, description="Endereço para retirada (opcional)")
    phone: str = Field(min_length=6, max_length=40, description="Telefone de contato / WhatsApp")


class MovingSaleUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=150)
    description: Optional[str] = Field(default=None, min_length=10, max_length=5000)
    category: Optional[str] = Field(default=None, max_length=80)
    condition: Optional[str] = Field(default=None, max_length=30)
    price: Optional[float] = Field(default=None, ge=0)
    city: Optional[str] = Field(default=None, min_length=2, max_length=100)
    address: Optional[str] = Field(default=None, max_length=250)
    phone: Optional[str] = Field(default=None, min_length=6, max_length=40)
    is_available: Optional[bool] = None


class MovingSaleResponse(BaseModel):
    id: str
    user_id: str
    title: str
    description: str
    category: str = "Móveis"
    condition: str = "usado"
    price: float = 0.0
    city: str
    address: Optional[str] = None
    phone: str
    images: list[str] = []
    status: str = "pending"
    rejection_reason: Optional[str] = None
    is_available: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    user_name: Optional[str] = None
    user_avatar: Optional[str] = None


class MovingSaleListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[MovingSaleResponse]
