"""Schemas de gift codes, denúncias, pagamentos e administração."""

from pydantic import BaseModel, Field

from app.models import GiftCodeType, ReportTargetType


# ---------- Gift codes ----------

class GiftCodeCreateRequest(BaseModel):
    type: GiftCodeType = GiftCodeType.HIGHLIGHT
    quantity: int = Field(default=1, ge=1, le=100)
    max_uses: int = Field(default=1, ge=1)
    expires_at: str | None = None


class GiftCodeRedeemRequest(BaseModel):
    code: str = Field(min_length=4, max_length=50)
    ad_id: str = Field(description="Anúncio que receberá o destaque grátis")


class GiftCodeResponse(BaseModel):
    id: str
    code: str
    type: str
    max_uses: int
    uses_count: int
    active: bool
    expires_at: str | None = None
    created_at: str | None = None


# ---------- Denúncias ----------

class ReportCreateRequest(BaseModel):
    target_type: ReportTargetType
    target_id: str
    reason: str = Field(min_length=5, max_length=1000)


class ReportResolveRequest(BaseModel):
    resolution: str = Field(default="resolved", pattern="^(resolved|dismissed)$")
    note: str | None = Field(default=None, max_length=1000)


class ReportResponse(BaseModel):
    id: str
    reporter_id: str
    target_type: str
    target_id: str
    reason: str
    status: str
    resolution_note: str | None = None
    created_at: str | None = None


# ---------- Pagamentos ----------

class CheckoutRequest(BaseModel):
    ad_id: str = Field(description="Anúncio a ser destacado por €2/semana")


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class PaymentResponse(BaseModel):
    id: str
    user_id: str
    ad_id: str
    amount_cents: int
    currency: str
    status: str
    stripe_session_id: str | None = None
    created_at: str | None = None


# ---------- Administração ----------

class AdminStatsResponse(BaseModel):
    total_users: int
    blocked_users: int
    total_ads: int
    pending_ads: int
    approved_ads: int
    highlighted_ads: int
    total_reviews: int
    total_groups: int
    pending_groups: int
    active_urgent_ads: int
    total_charity_ads: int
    open_reports: int
    total_payments: int
    revenue_cents: int


class BlockUserRequest(BaseModel):
    blocked: bool | None = None
    is_blocked: bool | None = None
    reason: str | None = Field(default=None, max_length=500)
    block_reason: str | None = Field(default=None, max_length=500)


class UserUpdateRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    is_admin: bool | None = None
    is_blocked: bool | None = None
    email_verified: bool | None = None
    phone_verified: bool | None = None
    block_reason: str | None = None

