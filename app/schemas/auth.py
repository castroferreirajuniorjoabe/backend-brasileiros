"""Schemas de autenticação e usuários."""

from pydantic import BaseModel, EmailStr, Field


# ---------- Autenticação ----------

class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=8, max_length=20, description="Formato internacional, ex.: +33612345678")
    city: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=6, max_length=72)
    referral_code: str | None = Field(default=None, description="Código de indicação de outro anunciante")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class VerifyEmailRequest(BaseModel):
    token: str


class VerifyPhoneRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class ResendPhoneCodeRequest(BaseModel):
    pass  # usa o usuário autenticado


# ---------- Usuários ----------

class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    phone: str
    city: str
    avatar_url: str | None = None
    email_verified: bool = False
    phone_verified: bool = False
    is_admin: bool = False
    is_blocked: bool = False
    referral_code: str | None = None
    created_at: str | None = None


class UserUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, min_length=8, max_length=20)
    city: str | None = Field(default=None, min_length=2, max_length=120)
    avatar_url: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)


TokenResponse.model_rebuild()
