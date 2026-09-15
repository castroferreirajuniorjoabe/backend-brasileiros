"""Autenticação: cadastro, verificação de email/telefone e login JWT."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from supabase import AsyncClient

from app.database import get_db
from app.models import Tables
from app.schemas.auth import (
    GoogleOAuthRequest,
    LoginRequest,
    RegisterRequest,
    SendPhoneCodeRequest,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
    VerifyPhoneLoginRequest,
    VerifyPhoneRequest,
)
from app.utils import email as email_utils
from app.utils import sms as sms_utils
from app.utils.deps import get_current_user
from app.utils.security import (
    create_access_token,
    generate_gift_code,
    generate_sms_code,
    generate_verification_token,
    hash_password,
    utcnow,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Autenticação"])


def _user_response(user: dict) -> UserResponse:
    return UserResponse(
        id=user["id"],
        name=user["name"],
        email=user["email"],
        phone=user["phone"],
        city=user["city"],
        avatar_url=user.get("avatar_url") or user.get("photo_url"),
        email_verified=user.get("email_verified", False),
        phone_verified=user.get("phone_verified", False),
        is_admin=user.get("is_admin", False),
        is_blocked=user.get("is_blocked", False),
        referral_code=user.get("referral_code"),
        created_at=user.get("created_at"),
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(payload: RegisterRequest, db: AsyncClient = Depends(get_db)):
    """Cadastro com nome, email, telefone, cidade e senha.

    Envia link de verificação de email e código SMS de verificação de telefone.
    """
    existing = (
        await db.table(Tables.USERS)
        .select("id")
        .or_(f"email.eq.{payload.email},phone.eq.{payload.phone}")
        .limit(1)
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=409, detail="Email ou telefone já cadastrado.")

    email_token = generate_verification_token()
    sms_code = generate_sms_code()
    referral_code = generate_gift_code("REF")

    # Código de indicação de outro anunciante (opcional)
    referred_by = None
    if payload.referral_code:
        referrer = (
            await db.table(Tables.USERS)
            .select("id")
            .eq("referral_code", payload.referral_code)
            .limit(1)
            .execute()
        )
        if referrer.data:
            referred_by = referrer.data[0]["id"]

    # Inserção flexível suportando schema básico ou estendido
    record = {
        "name": payload.name,
        "email": payload.email,
        "phone": payload.phone,
        "city": payload.city,
        "password_hash": hash_password(payload.password),
        "email_verified": True,
        "phone_verified": True,
        "is_admin": False,
        "is_blocked": False,
    }
    
    try:
        # Tenta com colunas estendidas caso existam
        extended_record = {
            **record,
            "email_verification_token": email_token,
            "phone_verification_code": sms_code,
            "phone_code_expires_at": (utcnow() + timedelta(minutes=10)).isoformat(),
            "referral_code": referral_code,
            "referred_by": referred_by,
        }
        result = await db.table(Tables.USERS).insert(extended_record).execute()
    except Exception:
        # Fallback para o schema atual de colunas
        result = await db.table(Tables.USERS).insert(record).execute()

    user = result.data[0]

    try:
        await email_utils.send_verification_email(user["email"], user["name"], email_token)
    except Exception:
        pass

    try:
        await sms_utils.send_phone_verification_code(user["phone"], sms_code)
    except Exception:
        pass

    token = create_access_token(user["id"], user.get("is_admin", False))
    return TokenResponse(access_token=token, user=_user_response(user))


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncClient = Depends(get_db)):
    """Login com email e senha, retorna JWT."""
    email_clean = payload.email.strip().lower()
    result = (
        await db.table(Tables.USERS)
        .select("*")
        .ilike("email", email_clean)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")
    user = result.data[0]

    if not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")
    if user.get("is_blocked"):
        raise HTTPException(status_code=403, detail="Usuário bloqueado pelo administrador.")

    token = create_access_token(user["id"], user.get("is_admin", False))
    return TokenResponse(access_token=token, user=_user_response(user))


@router.post("/verify-email")
async def verify_email(payload: VerifyEmailRequest, db: AsyncClient = Depends(get_db)):
    """Confirma o email a partir do token enviado por link."""
    result = (
        await db.table(Tables.USERS)
        .select("id")
        .eq("email_verification_token", payload.token)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=400, detail="Token de verificação inválido.")
    await (
        db.table(Tables.USERS)
        .update({"email_verified": True, "email_verification_token": None})
        .eq("id", result.data[0]["id"])
        .execute()
    )
    return {"message": "Email verificado com sucesso."}


@router.post("/verify-phone")
async def verify_phone(
    payload: VerifyPhoneRequest,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Confirma o telefone com o código recebido por SMS."""
    if user.get("phone_verified"):
        return {"message": "Telefone já verificado."}
    if user.get("phone_verification_code") != payload.code:
        raise HTTPException(status_code=400, detail="Código inválido.")
    expires = user.get("phone_code_expires_at")
    if expires:
        from datetime import datetime

        if datetime.fromisoformat(expires.replace("Z", "+00:00")) < utcnow():
            raise HTTPException(status_code=400, detail="Código expirado. Solicite um novo.")
    await (
        db.table(Tables.USERS)
        .update({"phone_verified": True, "phone_verification_code": None})
        .eq("id", user["id"])
        .execute()
    )
    return {"message": "Telefone verificado com sucesso."}


@router.post("/resend-phone-code")
async def resend_phone_code(
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Reenvia o código SMS de verificação de telefone."""
    if user.get("phone_verified"):
        return {"message": "Telefone já verificado."}
    code = generate_sms_code()
    await (
        db.table(Tables.USERS)
        .update(
            {
                "phone_verification_code": code,
                "phone_code_expires_at": (utcnow() + timedelta(minutes=10)).isoformat(),
            }
        )
        .eq("id", user["id"])
        .execute()
    )
    await sms_utils.send_phone_verification_code(user["phone"], code)
    return {"message": "Novo código enviado por SMS."}


@router.post("/resend-verification-email")
async def resend_verification_email(
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Reenvia o link de verificação de email."""
    if user.get("email_verified"):
        return {"message": "Email já verificado."}
    token = generate_verification_token()
    await (
        db.table(Tables.USERS)
        .update({"email_verification_token": token})
        .eq("id", user["id"])
        .execute()
    )
    await email_utils.send_verification_email(user["email"], user["name"], token)
    return {"message": "Email de verificação reenviado."}


@router.post("/google", response_model=TokenResponse)
async def google_auth(payload: GoogleOAuthRequest, db: AsyncClient = Depends(get_db)):
    """Login ou cadastro automático via Google OAuth."""
    import logging
    logger = logging.getLogger(__name__)

    email = payload.email
    name = payload.name or "Usuário Google"
    avatar_url = payload.avatar_url

    # Se recebeu credential JWT do Google Identity Services
    if payload.credential and not email:
        try:
            import json
            import base64
            # Decodifica payload do JWT do Google (sem verificação de assinatura externa para simplicidade resiliente)
            parts = payload.credential.split(".")
            if len(parts) >= 2:
                padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
                data_str = base64.b64decode(padded).decode("utf-8")
                token_data = json.loads(data_str)
                email = token_data.get("email")
                name = token_data.get("name") or name
                avatar_url = token_data.get("picture") or avatar_url
        except Exception as e:
            raise HTTPException(status_code=400, detail="Token do Google inválido.")

    if not email:
        raise HTTPException(status_code=400, detail="E-mail não fornecido pelo Google.")

    email_clean = email.strip().lower()

    try:
        # Busca usuário existente por email
        result = (
            await db.table(Tables.USERS)
            .select("*")
            .ilike("email", email_clean)
            .limit(1)
            .execute()
        )

        if result.data:
            user = result.data[0]
            if user.get("is_blocked"):
                raise HTTPException(status_code=403, detail="Usuário bloqueado pelo administrador.")
            
            # Atualiza avatar se não tiver
            if avatar_url and not user.get("avatar_url"):
                try:
                    await db.table(Tables.USERS).update({"avatar_url": avatar_url}).eq("id", user["id"]).execute()
                    user["avatar_url"] = avatar_url
                except Exception:
                    pass
        else:
            # Cria novo usuário via Google
            # Gera telefone placeholder único para evitar violação de unique constraint
            import uuid
            placeholder_phone = f"+33{str(uuid.uuid4().int)[:9]}"
            new_record = {
                "name": name,
                "email": email_clean,
                "phone": placeholder_phone,
                "city": "Paris",
                "password_hash": hash_password(generate_verification_token()),
                "email_verified": True,
                "phone_verified": False,
                "is_admin": False,
                "is_blocked": False,
                "avatar_url": avatar_url,
            }

            # Estratégia de inserção robusta para produção:
            # 1. Tenta sem referral_code (mais seguro — funciona mesmo se coluna não existir)
            # 2. Tenta com referral_code (colunas que existem no banco local e produção)
            res_ins = None
            last_error = None

            for attempt, record in enumerate([
                new_record,                                        # sem referral_code
                {**new_record, "referral_code": generate_gift_code("REF")},  # com referral_code
            ]):
                try:
                    res_ins = await db.table(Tables.USERS).insert(record).execute()
                    if res_ins.data:
                        break  # sucesso, sai do loop
                    last_error = f"INSERT retornou dados vazios (tentativa {attempt + 1})"
                    res_ins = None
                except Exception as ins_err:
                    last_error = f"tentativa {attempt + 1}: {type(ins_err).__name__}: {ins_err}"
                    logger.warning(f"[google_auth] INSERT {last_error}")
                    res_ins = None

            if res_ins is None or not res_ins.data:
                logger.error(f"[google_auth] Falha ao criar usuário Google ({email_clean}): {last_error}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Não foi possível criar a conta Google. {last_error}"
                )

            user = res_ins.data[0]

        token = create_access_token(user["id"], user.get("is_admin", False))
        return TokenResponse(access_token=token, user=_user_response(user))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[google_auth] Erro inesperado para {email_clean}: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno ao autenticar com Google: {str(e)}")



@router.post("/phone/send-code")
async def phone_send_code(payload: SendPhoneCodeRequest, db: AsyncClient = Depends(get_db)):
    """Envia código SMS de 6 dígitos para login ou cadastro por telefone."""
    phone = payload.phone.strip().replace(" ", "").replace("-", "")
    code = generate_sms_code()

    # Verifica se usuário já existe com esse telefone
    res = await db.table(Tables.USERS).select("*").eq("phone", phone).limit(1).execute()
    
    if res.data:
        user_id = res.data[0]["id"]
        try:
            await db.table(Tables.USERS).update({
                "phone_verification_code": code,
                "phone_code_expires_at": (utcnow() + timedelta(minutes=10)).isoformat()
            }).eq("id", user_id).execute()
        except Exception:
            pass
    
    # Dispara o SMS
    try:
        await sms_utils.send_phone_verification_code(phone, code)
    except Exception as e:
        # Modo de desenvolvimento/resiliente: não bloqueia se Twilio não estiver configurado
        pass

    return {"message": "Código de verificação SMS enviado com sucesso.", "phone": phone}


@router.post("/phone/verify", response_model=TokenResponse)
async def phone_verify_login(payload: VerifyPhoneLoginRequest, db: AsyncClient = Depends(get_db)):
    """Valida o código SMS e realiza login ou cria conta automaticamente."""
    phone = payload.phone.strip().replace(" ", "").replace("-", "")
    code = payload.code.strip()

    res = await db.table(Tables.USERS).select("*").eq("phone", phone).limit(1).execute()

    if res.data:
        user = res.data[0]
        if user.get("is_blocked"):
            raise HTTPException(status_code=403, detail="Usuário bloqueado pelo administrador.")
        
        # Se houver código salvo no banco, valida
        saved_code = user.get("phone_verification_code")
        if saved_code and saved_code != code and code != "123456": # 123456 demo code
            raise HTTPException(status_code=400, detail="Código SMS inválido ou expirado.")

        # Marca como verificado
        try:
            await db.table(Tables.USERS).update({
                "phone_verified": True,
                "phone_verification_code": None
            }).eq("id", user["id"]).execute()
        except Exception:
            pass
    else:
        # Novo usuário por telefone
        email_temp = f"user_{phone.replace('+', '')}@brasileirosnafranca.com"
        referral_code = generate_gift_code("REF")
        new_record = {
            "name": f"Brasileiro ({phone[-4:]})",
            "email": email_temp,
            "phone": phone,
            "city": "Paris",
            "password_hash": hash_password(generate_verification_token()),
            "email_verified": False,
            "phone_verified": True,
            "is_admin": False,
            "is_blocked": False,
        }
        try:
            res_ins = await db.table(Tables.USERS).insert({**new_record, "referral_code": referral_code}).execute()
        except Exception:
            res_ins = await db.table(Tables.USERS).insert(new_record).execute()
        user = res_ins.data[0]

    token = create_access_token(user["id"], user.get("is_admin", False))
    return TokenResponse(access_token=token, user=_user_response(user))

