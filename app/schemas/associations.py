"""Schemas para cadastro e listagem de Associações e Parceiros na França."""

from pydantic import BaseModel, Field


class AssociationCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200, description="Nome da associação")
    description: str = Field(min_length=10, max_length=5000, description="Descrição das atividades e serviços")
    city: str = Field(min_length=2, max_length=120, description="Cidade ou região")
    type: str = Field(default="cultural", max_length=100, description="Tipo da associação (ex: cultural, social, esportiva, religiosa)")
    address: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=150)
    website: str | None = Field(default=None, max_length=300)
    instagram: str | None = Field(default=None, max_length=300)
    facebook: str | None = Field(default=None, max_length=300)
    logo_url: str | None = Field(default=None, max_length=1000)


class AssociationResponse(BaseModel):
    id: str
    user_id: str | None = None
    name: str
    description: str
    city: str
    type: str = "cultural"
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    instagram: str | None = None
    facebook: str | None = None
    logo_url: str | None = None
    status: str = "pending"
    rejection_reason: str | None = None
    created_at: str | None = None
