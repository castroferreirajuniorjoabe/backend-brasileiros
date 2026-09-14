"""Constantes de domínio: nomes de tabelas e enums de status."""

from enum import Enum


class Tables:
    USERS = "users"
    ADS = "ads"
    REVIEWS = "reviews"
    GROUPS = "groups"
    URGENT_ADS = "urgent_ads"
    CHARITY_ADS = "charity_ads"
    TOURISM_SPOTS = "tourism_spots"
    PET_POSTS = "pet_posts"
    ITEM_COMMENTS = "item_comments"
    GIFT_CODES = "gift_codes"
    REPORTS = "reports"
    PAYMENTS = "payments"
    MONTHLY_RANKING = "monthly_ranking"
    EDIT_HISTORY = "edit_history"
    ADMINS = "admins"
    NOTIFICATIONS = "notifications"


class AdType(str, Enum):
    SERVICE = "service"      # Anúncio comercial / profissional fixo (não expira)
    EVENT = "event"          # Evento ou festa temporária (com data específica, expira após realização)


class AdStatus(str, Enum):
    PENDING = "pending"      # aguardando moderação
    APPROVED = "approved"    # visível
    REJECTED = "rejected"
    DELETED = "deleted"      # soft delete
    EXPIRED = "expired"      # expirado (eventos passados)


class ModerationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class UrgentType(str, Enum):
    LOST_OBJECT = "lost_object"          # objeto perdido
    MISSING_PERSON = "missing_person"    # pessoa desaparecida


class GroupPlatform(str, Enum):
    WHATSAPP = "whatsapp"
    FACEBOOK = "facebook"


class ReportStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ReportTargetType(str, Enum):
    AD = "ad"
    REVIEW = "review"
    GROUP = "group"
    URGENT_AD = "urgent_ad"
    CHARITY_AD = "charity_ad"
    USER = "user"


class GiftCodeType(str, Enum):
    HIGHLIGHT = "highlight"   # destaque grátis
    REFERRAL = "referral"     # indicação de anunciante


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


# Regras de negócio
MAX_AD_EDITS_PER_WEEK = 2
MAX_AD_EDITS_PER_MONTH = 2
URGENT_AD_EXPIRATION_DAYS = 7
CHARITY_ADS_PER_WEEK = 1
HIGHLIGHT_DURATION_DAYS = 7
RANKING_TOP_REWARDED = 3

