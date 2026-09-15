"""Rotas da seção 'Dúvidas de Regularização 🇧🇷🇫🇷'.
Implementa fórum de dúvidas, dicas de regularização, respostas, curtidas, marcação de solução e moderação."""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import AsyncClient

from app.database import get_db
from app.models import (
    Tables,
    MAX_REGULATION_POSTS_PER_DAY,
    MAX_REGULATION_REPLIES_PER_DAY,
)
from app.schemas.regulation import (
    RegulationLikeToggleResponse,
    RegulationPostCreate,
    RegulationPostListResponse,
    RegulationPostResponse,
    RegulationPostUpdate,
    RegulationReplyCreate,
    RegulationReplyResponse,
    RegulationReplyUpdate,
    RegulationReportCreate,
    RegulationReportResponse,
    RegulationUserSummary,
)
from app.utils.deps import get_current_user, get_optional_user
from app.utils.security import utcnow

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/regulation", tags=["Dúvidas de Regularização"])

# Palavras proibidas / moderação automática preventiva
BANNED_WORDS = [
    "golpe", "falsific", "visto falso", "fraude", "estelionato",
    "documento falso", "passaporte falso", "comprar visto", "hack",
]


def _check_banned_words(text: str):
    lower = text.lower()
    for w in BANNED_WORDS:
        if w in lower:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sua publicação contém termos proibidos ou que violam as diretrizes de segurança da comunidade.",
            )


def _format_user_summary(user_data: dict) -> RegulationUserSummary:
    if not user_data:
        return RegulationUserSummary(id="anonymous", name="Membro da Comunidade")
    
    # Atribuição de badges de reputação
    badge = None
    if user_data.get("is_admin"):
        badge = "Admin 🛡️"
    elif user_data.get("is_verified"):
        badge = "Membro Verificado ⭐"

    return RegulationUserSummary(
        id=str(user_data.get("id", "")),
        name=user_data.get("name") or "Membro da Comunidade",
        avatar_url=user_data.get("avatar_url"),
        city=user_data.get("city") or "França",
        is_verified=bool(user_data.get("is_verified", False)),
        badge=badge,
    )


def _format_post(item: dict, user_dict: dict = None, has_liked: bool = False, replies: list = None, best_reply: dict = None) -> dict:
    m = dict(item)
    m["id"] = str(m.get("id"))
    m["user_id"] = str(m.get("user_id") or "")
    m["type"] = m.get("type") or "question"
    m["category"] = m.get("category") or "vistos"
    m["title"] = m.get("title") or ""
    m["content"] = m.get("content") or ""

    images = m.get("images") or []
    if isinstance(images, str):
        try:
            images = json.loads(images)
        except Exception:
            images = [images] if images else []
    elif not isinstance(images, list):
        images = []
    m["images"] = images

    m["likes_count"] = int(m.get("likes_count") or 0)
    m["replies_count"] = int(m.get("replies_count") or 0)
    m["views_count"] = int(m.get("views_count") or 0)
    m["has_liked"] = has_liked
    m["is_solved"] = bool(m.get("is_solved", False))
    m["best_reply_id"] = str(m["best_reply_id"]) if m.get("best_reply_id") else None
    m["status"] = m.get("status") or "active"
    m["created_at"] = str(m["created_at"]) if m.get("created_at") else None
    m["updated_at"] = str(m["updated_at"]) if m.get("updated_at") else None

    m["user"] = _format_user_summary(user_dict or m.get("users") or {})
    m["replies"] = replies or []
    m["best_reply"] = best_reply
    return m


def _format_reply(item: dict, user_dict: dict = None, has_liked: bool = False) -> dict:
    r = dict(item)
    r["id"] = str(r.get("id"))
    r["post_id"] = str(r.get("post_id"))
    r["user_id"] = str(r.get("user_id"))
    r["content"] = r.get("content") or ""
    r["likes_count"] = int(r.get("likes_count") or 0)
    r["has_liked"] = has_liked
    r["is_best_answer"] = bool(r.get("is_best_answer", False))
    r["status"] = r.get("status") or "active"
    r["created_at"] = str(r["created_at"]) if r.get("created_at") else None
    r["updated_at"] = str(r["updated_at"]) if r.get("updated_at") else None
    r["user"] = _format_user_summary(user_dict or r.get("users") or {})
    return r


# ==============================================================================
# PUBLICAÇÕES (DÚVIDAS E DICAS)
# ==============================================================================

@router.post("/posts", response_model=RegulationPostResponse, status_code=201)
async def create_regulation_post(
    payload: RegulationPostCreate,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Cria uma nova publicação de Dúvida ou Dica sobre regularização na França."""
    _check_banned_words(payload.title)
    _check_banned_words(payload.content)

    # 1. Rate Limit diário (máx 5 posts por dia por usuário)
    if not user.get("is_admin"):
        try:
            today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            res_today = (
                await db.table(Tables.REGULATION_POSTS)
                .select("id", count="exact")
                .eq("user_id", user["id"])
                .gte("created_at", today_start)
                .execute()
            )
            count = res_today.count if res_today.count is not None else len(res_today.data or [])
            if count >= MAX_REGULATION_POSTS_PER_DAY:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Limite diário atingido: você já publicou {count} vezes hoje (máximo {MAX_REGULATION_POSTS_PER_DAY} por dia).",
                )
        except HTTPException:
            raise
        except Exception:
            pass

    images_clean = [img for img in (payload.images or []) if img and str(img).strip()][:3]

    record = {
        "user_id": user["id"],
        "type": payload.type if payload.type in ["question", "tip"] else "question",
        "category": payload.category.strip() if payload.category else "vistos",
        "title": payload.title.strip(),
        "content": payload.content.strip(),
        "images": images_clean,
        "likes_count": 0,
        "replies_count": 0,
        "views_count": 0,
        "is_solved": False,
        "status": "active",
    }

    # Tentativa 1: Inserção na tabela dedicada `regulation_posts`
    last_error = None
    try:
        res = await db.table(Tables.REGULATION_POSTS).insert(record).execute()
        if res.data:
            return _format_post(res.data[0], user_dict=user)
    except Exception as e1:
        last_error = e1
        logger.warning(f"Insert em regulation_posts falhou: {e1}")

    # Tentativa 2 (Fallback com images em JSON string):
    try:
        record_fallback = dict(record)
        record_fallback["images"] = json.dumps(images_clean)
        res = await db.table(Tables.REGULATION_POSTS).insert(record_fallback).execute()
        if res.data:
            return _format_post(res.data[0], user_dict=user)
    except Exception as e2:
        last_error = e2
        logger.warning(f"Fallback insert em regulation_posts falhou: {e2}")

    # Tentativa 3 (Fallback na tabela charity_ads com tag REGULATION):
    meta_dict = {
        "type": record["type"],
        "category": record["category"],
        "images": images_clean,
        "likes_count": 0,
        "replies_count": 0,
        "is_solved": False,
    }
    encoded_desc = f"REGULATION_META:{json.dumps(meta_dict)}\n---DESC---\n{payload.content.strip()}"

    charity_attempts = [
        {
            "user_id": user["id"],
            "title": f"[{record['type'].upper()}] {payload.title.strip()}",
            "description": encoded_desc,
            "location": "França",
            "contact_phone": user.get("phone") or "0000000000",
            "image_url": images_clean[0] if len(images_clean) > 0 else None,
            "image_2_url": images_clean[1] if len(images_clean) > 1 else None,
            "status": "approved",
            "type": "regulation",
        },
        {
            "user_id": user["id"],
            "title": f"[{record['type'].upper()}] {payload.title.strip()}",
            "description": encoded_desc,
            "location": "França",
            "contact_phone": user.get("phone") or "0000000000",
            "image_url": images_clean[0] if len(images_clean) > 0 else None,
            "image_2_url": images_clean[1] if len(images_clean) > 1 else None,
            "status": "approved",
        },
    ]

    for c_att in charity_attempts:
        try:
            res_c = await db.table(Tables.CHARITY_ADS).insert(c_att).execute()
            if res_c.data:
                return _format_post(res_c.data[0], user_dict=user)
        except Exception as e_c:
            last_error = e_c
            logger.debug(f"Tentativa insert charity_ads fallback falhou: {e_c}")

    logger.error(f"Todas as tentativas de salvar regulation_post falharam: {last_error}")
    raise HTTPException(
        status_code=500,
        detail=f"Erro ao salvar publicação: {str(last_error) if last_error else 'Tabela não encontrada'}. Execute o script SQL no Supabase para criar 'regulation_posts'.",
    )


@router.get("/posts", response_model=RegulationPostListResponse)
async def list_regulation_posts(
    type: Optional[str] = Query(None, description="'question' ou 'tip'"),
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sort: Optional[str] = Query("recent", description="'recent' | 'likes' | 'replies' | 'unsolved'"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncClient = Depends(get_db),
    visitor: Optional[dict] = Depends(get_optional_user),
):
    """Lista publicações públicas com filtros de tipo (Dúvidas/Dicas), categorias, busca e ordenação."""
    search_term = (q or search or "").strip().lower()

    try:
        query = db.table(Tables.REGULATION_POSTS).select("*, users:user_id(id, name, avatar_url, city, is_verified, is_admin)")
        query = query.eq("status", "active")

        if type and type in ["question", "tip"]:
            query = query.eq("type", type)

        if category and category.lower() != "todas" and category.lower() != "all":
            query = query.eq("category", category)

        if search_term:
            query = query.or_(f"title.ilike.%{search_term}%,content.ilike.%{search_term}%")

        if sort == "likes":
            query = query.order("likes_count", desc=True)
        elif sort == "replies":
            query = query.order("replies_count", desc=True)
        elif sort == "unsolved":
            query = query.eq("is_solved", False).order("created_at", desc=True)
        else:
            query = query.order("created_at", desc=True)

        # Paginação
        offset = (page - 1) * page_size
        query = query.range(offset, offset + page_size - 1)

        res = await query.execute()
        raw_items = res.data or []

        # Identifica curtidas do visitante se autenticado
        liked_post_ids = set()
        if visitor and raw_items:
            try:
                post_ids = [str(x["id"]) for x in raw_items]
                res_likes = (
                    await db.table(Tables.REGULATION_LIKES)
                    .select("target_id")
                    .eq("user_id", visitor["id"])
                    .eq("target_type", "post")
                    .in_("target_id", post_ids)
                    .execute()
                )
                liked_post_ids = {str(lk["target_id"]) for lk in (res_likes.data or [])}
            except Exception:
                pass

        formatted = [
            _format_post(
                item=it,
                user_dict=it.get("users"),
                has_liked=str(it.get("id")) in liked_post_ids,
            )
            for it in raw_items
        ]

        return RegulationPostListResponse(
            total=len(formatted),
            page=page,
            page_size=page_size,
            items=formatted,
        )
    except Exception as e:
        logger.error(f"Erro ao listar regulation posts: {e}")
        return RegulationPostListResponse(total=0, page=page, page_size=page_size, items=[])


@router.get("/posts/mine", response_model=List[RegulationPostResponse])
async def list_my_regulation_posts(
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Lista todas as publicações criadas pelo usuário logado."""
    try:
        res = (
            await db.table(Tables.REGULATION_POSTS)
            .select("*, users:user_id(id, name, avatar_url, city, is_verified, is_admin)")
            .eq("user_id", user["id"])
            .neq("status", "deleted")
            .order("created_at", desc=True)
            .execute()
        )
        return [_format_post(it, user_dict=user) for it in (res.data or [])]
    except Exception as e:
        logger.warning(f"Erro ao buscar regulation posts do usuário: {e}")
        return []


@router.get("/posts/{post_id}", response_model=RegulationPostResponse)
async def get_regulation_post_detail(
    post_id: str,
    db: AsyncClient = Depends(get_db),
    visitor: Optional[dict] = Depends(get_optional_user),
):
    """Retorna o detalhe de uma publicação com suas respostas e indicação de melhor resposta."""
    post_data = None
    try:
        res = (
            await db.table(Tables.REGULATION_POSTS)
            .select("*, users:user_id(id, name, avatar_url, city, is_verified, is_admin)")
            .eq("id", post_id)
            .limit(1)
            .execute()
        )
        if res.data:
            post_data = res.data[0]
    except Exception as e_post:
        logger.warning(f"Tentativa 1 select regulation_posts falhou: {e_post}")
        try:
            res_simple = await db.table(Tables.REGULATION_POSTS).select("*").eq("id", post_id).limit(1).execute()
            if res_simple.data:
                post_data = res_simple.data[0]
        except Exception as e_simple:
            logger.warning(f"Tentativa 2 select regulation_posts falhou: {e_simple}")

    # Fallback na tabela charity_ads se salvo via fallback
    if not post_data:
        try:
            res_c = await db.table(Tables.CHARITY_ADS).select("*, users:user_id(id, name, avatar_url, city, is_verified, is_admin)").eq("id", post_id).limit(1).execute()
            if res_c.data:
                c_item = res_c.data[0]
                desc = c_item.get("description") or ""
                real_type = "question"
                real_cat = "vistos"
                real_desc = desc
                images = []
                if "REGULATION_META:" in desc and "---DESC---" in desc:
                    parts = desc.split("---DESC---")
                    meta_str = parts[0].replace("REGULATION_META:", "").strip()
                    try:
                        m_obj = json.loads(meta_str)
                        real_type = m_obj.get("type") or "question"
                        real_cat = m_obj.get("category") or "vistos"
                        images = m_obj.get("images") or []
                    except Exception:
                        pass
                    real_desc = parts[1].strip() if len(parts) > 1 else desc
                
                title = (c_item.get("title") or "").replace("[QUESTION]", "").replace("[TIP]", "").strip()
                post_data = {
                    "id": c_item.get("id"),
                    "user_id": c_item.get("user_id"),
                    "type": real_type,
                    "category": real_cat,
                    "title": title,
                    "content": real_desc,
                    "images": images or ([c_item.get("image_url")] if c_item.get("image_url") else []),
                    "likes_count": 0,
                    "replies_count": 0,
                    "is_solved": False,
                    "users": c_item.get("users"),
                    "created_at": c_item.get("created_at"),
                }
        except Exception as e_cf:
            logger.warning(f"Fallback charity_ads lookup falhou: {e_cf}")

    if not post_data:
        raise HTTPException(status_code=404, detail="Publicação não encontrada.")

    # Verifica curtida no post
    has_liked_post = False
    if visitor:
        try:
            res_lk = (
                await db.table(Tables.REGULATION_LIKES)
                .select("id")
                .eq("user_id", visitor["id"])
                .eq("target_type", "post")
                .eq("target_id", post_id)
                .limit(1)
                .execute()
            )
            has_liked_post = bool(res_lk.data)
        except Exception:
            pass

    # Busca respostas
    replies_raw = []
    try:
        res_rep = (
            await db.table(Tables.REGULATION_REPLIES)
            .select("*, users:user_id(id, name, avatar_url, city, is_verified, is_admin)")
            .eq("post_id", post_id)
            .neq("status", "deleted")
            .order("is_best_answer", desc=True)
            .order("likes_count", desc=True)
            .order("created_at", desc=False)
            .execute()
        )
        replies_raw = res_rep.data or []
    except Exception:
        try:
            res_rep_simple = await db.table(Tables.REGULATION_REPLIES).select("*").eq("post_id", post_id).execute()
            replies_raw = res_rep_simple.data or []
        except Exception:
            pass

    # Verifica curtidas nas respostas
    liked_reply_ids = set()
    if visitor and replies_raw:
        try:
            r_ids = [str(r["id"]) for r in replies_raw]
            res_rlk = (
                await db.table(Tables.REGULATION_LIKES)
                .select("target_id")
                .eq("user_id", visitor["id"])
                .eq("target_type", "reply")
                .in_("target_id", r_ids)
                .execute()
            )
            liked_reply_ids = {str(lk["target_id"]) for lk in (res_rlk.data or [])}
        except Exception:
            pass

    formatted_replies = [
        _format_reply(
            item=r,
            user_dict=r.get("users"),
            has_liked=str(r["id"]) in liked_reply_ids,
        )
        for r in replies_raw
    ]

    best_reply_obj = None
    if post_data.get("best_reply_id"):
        for r in formatted_replies:
            if str(r.get("id")) == str(post_data["best_reply_id"]):
                best_reply_obj = r
                break

    return _format_post(
        item=post_data,
        user_dict=post_data.get("users"),
        has_liked=has_liked_post,
        replies=formatted_replies,
        best_reply=best_reply_obj,
    )


@router.put("/posts/{post_id}", response_model=RegulationPostResponse)
async def update_regulation_post(
    post_id: str,
    payload: RegulationPostUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Edita uma publicação (somente autor ou admin, autor pode editar em até 24h)."""
    res_check = await db.table(Tables.REGULATION_POSTS).select("*").eq("id", post_id).limit(1).execute()
    if not res_check.data:
        raise HTTPException(status_code=404, detail="Publicação não encontrada.")

    post = res_check.data[0]
    is_owner = str(post.get("user_id")) == str(user["id"])
    is_admin = bool(user.get("is_admin"))

    if not is_owner and not is_admin:
        raise HTTPException(status_code=403, detail="Você não tem permissão para editar esta publicação.")

    # Regra: autor só pode editar em até 24h
    if is_owner and not is_admin:
        try:
            created = datetime.fromisoformat(post["created_at"].replace("Z", "+00:00"))
            if utcnow() - created > timedelta(hours=24):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="O prazo de edição de 24 horas após a publicação expirou.",
                )
        except HTTPException:
            raise
        except Exception:
            pass

    update_fields = {}
    if payload.title is not None:
        _check_banned_words(payload.title)
        update_fields["title"] = payload.title.strip()
    if payload.content is not None:
        _check_banned_words(payload.content)
        update_fields["content"] = payload.content.strip()
    if payload.category is not None:
        update_fields["category"] = payload.category.strip()
    if payload.images is not None:
        update_fields["images"] = [img for img in payload.images if img][:3]

    update_fields["updated_at"] = utcnow().isoformat()

    res = await db.table(Tables.REGULATION_POSTS).update(update_fields).eq("id", post_id).execute()
    if res.data:
        return _format_post(res.data[0], user_dict=user)
    raise HTTPException(status_code=500, detail="Erro ao atualizar publicação.")


@router.delete("/posts/{post_id}", status_code=204)
async def delete_regulation_post(
    post_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Exclui uma publicação (autor ou admin)."""
    res_check = await db.table(Tables.REGULATION_POSTS).select("user_id").eq("id", post_id).limit(1).execute()
    if not res_check.data:
        raise HTTPException(status_code=404, detail="Publicação não encontrada.")

    post = res_check.data[0]
    if str(post.get("user_id")) != str(user["id"]) and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Você não tem permissão para apagar esta publicação.")

    try:
        await db.table(Tables.REGULATION_POSTS).delete().eq("id", post_id).execute()
    except Exception as e:
        logger.error(f"Erro ao deletar post: {e}")
        # Soft delete fallback
        await db.table(Tables.REGULATION_POSTS).update({"status": "deleted"}).eq("id", post_id).execute()

    return None


# ==============================================================================
# CURTIDAS, SOLUÇÃO & MELHOR RESPOSTA
# ==============================================================================

@router.post("/posts/{post_id}/like", response_model=RegulationLikeToggleResponse)
async def toggle_like_post(
    post_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Curte ou remove curtida de uma publicação de regularização."""
    try:
        res_check = (
            await db.table(Tables.REGULATION_LIKES)
            .select("id")
            .eq("user_id", user["id"])
            .eq("target_type", "post")
            .eq("target_id", post_id)
            .limit(1)
            .execute()
        )

        has_liked = bool(res_check.data)

        if has_liked:
            # Descurtir
            await db.table(Tables.REGULATION_LIKES).delete().eq("user_id", user["id"]).eq("target_type", "post").eq("target_id", post_id).execute()
            # Decrementa likes_count
            post_res = await db.table(Tables.REGULATION_POSTS).select("likes_count").eq("id", post_id).limit(1).execute()
            current_likes = max(0, int(post_res.data[0]["likes_count"] or 1) - 1) if post_res.data else 0
            await db.table(Tables.REGULATION_POSTS).update({"likes_count": current_likes}).eq("id", post_id).execute()
            return RegulationLikeToggleResponse(has_liked=False, likes_count=current_likes, message="Curtida removida.")
        else:
            # Curtir
            await db.table(Tables.REGULATION_LIKES).insert({
                "user_id": user["id"],
                "target_type": "post",
                "target_id": post_id,
            }).execute()
            post_res = await db.table(Tables.REGULATION_POSTS).select("likes_count").eq("id", post_id).limit(1).execute()
            current_likes = int(post_res.data[0]["likes_count"] or 0) + 1 if post_res.data else 1
            await db.table(Tables.REGULATION_POSTS).update({"likes_count": current_likes}).eq("id", post_id).execute()
            return RegulationLikeToggleResponse(has_liked=True, likes_count=current_likes, message="Publicação curtida!")
    except Exception as e:
        logger.error(f"Erro no toggle like post: {e}")
        raise HTTPException(status_code=500, detail="Erro ao processar curtida.")


@router.post("/posts/{post_id}/mark-solved")
async def mark_post_solved(
    post_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Marca uma dúvida como resolvida (autor ou admin)."""
    res_check = await db.table(Tables.REGULATION_POSTS).select("user_id, is_solved").eq("id", post_id).limit(1).execute()
    if not res_check.data:
        raise HTTPException(status_code=404, detail="Publicação não encontrada.")

    post = res_check.data[0]
    if str(post.get("user_id")) != str(user["id"]) and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Apenas o autor da dúvida pode marcá-la como resolvida.")

    new_val = not bool(post.get("is_solved", False))
    await db.table(Tables.REGULATION_POSTS).update({"is_solved": new_val}).eq("id", post_id).execute()
    return {"is_solved": new_val, "message": "Status de solução atualizado com sucesso!"}


@router.post("/posts/{post_id}/best-reply/{reply_id}")
async def mark_best_reply(
    post_id: str,
    reply_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Marca uma resposta específica como a 'Melhor Resposta / Solução' da dúvida."""
    res_check = await db.table(Tables.REGULATION_POSTS).select("user_id, best_reply_id").eq("id", post_id).limit(1).execute()
    if not res_check.data:
        raise HTTPException(status_code=404, detail="Publicação não encontrada.")

    post = res_check.data[0]
    if str(post.get("user_id")) != str(user["id"]) and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Apenas o autor da dúvida pode escolher a melhor resposta.")

    # Desmarca anteriores
    try:
        await db.table(Tables.REGULATION_REPLIES).update({"is_best_answer": False}).eq("post_id", post_id).execute()
    except Exception:
        pass

    # Marca a nova resposta
    await db.table(Tables.REGULATION_REPLIES).update({"is_best_answer": True}).eq("id", reply_id).execute()
    await db.table(Tables.REGULATION_POSTS).update({
        "best_reply_id": reply_id,
        "is_solved": True,
    }).eq("id", post_id).execute()

    return {"post_id": post_id, "best_reply_id": reply_id, "is_solved": True, "message": "Melhor resposta definida com sucesso!"}


# ==============================================================================
# RESPOSTAS
# ==============================================================================

@router.post("/posts/{post_id}/replies", response_model=RegulationReplyResponse, status_code=201)
async def create_regulation_reply(
    post_id: str,
    payload: RegulationReplyCreate,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Adiciona uma resposta a uma dúvida ou dica."""
    _check_banned_words(payload.content)

    # 1. Rate Limit diário (máx 10 respostas por dia por usuário)
    if not user.get("is_admin"):
        try:
            today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            res_today = (
                await db.table(Tables.REGULATION_REPLIES)
                .select("id", count="exact")
                .eq("user_id", user["id"])
                .gte("created_at", today_start)
                .execute()
            )
            count = res_today.count if res_today.count is not None else len(res_today.data or [])
            if count >= MAX_REGULATION_REPLIES_PER_DAY:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Limite diário atingido: você já enviou {count} respostas hoje (máximo {MAX_REGULATION_REPLIES_PER_DAY} por dia).",
                )
        except HTTPException:
            raise
        except Exception:
            pass

    record = {
        "post_id": post_id,
        "user_id": user["id"],
        "content": payload.content.strip(),
        "likes_count": 0,
        "is_best_answer": False,
        "status": "active",
    }

    try:
        res = await db.table(Tables.REGULATION_REPLIES).insert(record).execute()
        if res.data:
            # Incrementa contador replies_count no post
            try:
                p_res = await db.table(Tables.REGULATION_POSTS).select("replies_count").eq("id", post_id).limit(1).execute()
                curr = int(p_res.data[0]["replies_count"] or 0) + 1 if p_res.data else 1
                await db.table(Tables.REGULATION_POSTS).update({"replies_count": curr}).eq("id", post_id).execute()
            except Exception:
                pass
            return _format_reply(res.data[0], user_dict=user)
    except Exception as e:
        logger.error(f"Erro ao inserir resposta: {e}")

    raise HTTPException(status_code=500, detail="Não foi possível enviar a resposta.")


@router.get("/posts/{post_id}/replies", response_model=List[RegulationReplyResponse])
async def list_regulation_replies(
    post_id: str,
    db: AsyncClient = Depends(get_db),
    visitor: Optional[dict] = Depends(get_optional_user),
):
    """Lista todas as respostas de uma publicação."""
    try:
        res = (
            await db.table(Tables.REGULATION_REPLIES)
            .select("*, users:user_id(id, name, avatar_url, city, is_verified, is_admin)")
            .eq("post_id", post_id)
            .neq("status", "deleted")
            .order("is_best_answer", desc=True)
            .order("likes_count", desc=True)
            .order("created_at", desc=False)
            .execute()
        )
        raw = res.data or []

        liked_ids = set()
        if visitor and raw:
            try:
                r_ids = [str(r["id"]) for r in raw]
                res_lk = (
                    await db.table(Tables.REGULATION_LIKES)
                    .select("target_id")
                    .eq("user_id", visitor["id"])
                    .eq("target_type", "reply")
                    .in_("target_id", r_ids)
                    .execute()
                )
                liked_ids = {str(lk["target_id"]) for lk in (res_lk.data or [])}
            except Exception:
                pass

        return [_format_reply(r, user_dict=r.get("users"), has_liked=str(r["id"]) in liked_ids) for r in raw]
    except Exception as e:
        logger.error(f"Erro ao listar respostas: {e}")
        return []


@router.put("/replies/{reply_id}", response_model=RegulationReplyResponse)
async def update_regulation_reply(
    reply_id: str,
    payload: RegulationReplyUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Edita uma resposta enviada."""
    _check_banned_words(payload.content)
    res_check = await db.table(Tables.REGULATION_REPLIES).select("*").eq("id", reply_id).limit(1).execute()
    if not res_check.data:
        raise HTTPException(status_code=404, detail="Resposta não encontrada.")

    rep = res_check.data[0]
    if str(rep.get("user_id")) != str(user["id"]) and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Você não tem permissão para editar esta resposta.")

    res = await db.table(Tables.REGULATION_REPLIES).update({
        "content": payload.content.strip(),
        "updated_at": utcnow().isoformat(),
    }).eq("id", reply_id).execute()

    if res.data:
        return _format_reply(res.data[0], user_dict=user)
    raise HTTPException(status_code=500, detail="Erro ao atualizar resposta.")


@router.delete("/replies/{reply_id}", status_code=204)
async def delete_regulation_reply(
    reply_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Apaga uma resposta (autor ou admin)."""
    res_check = await db.table(Tables.REGULATION_REPLIES).select("user_id, post_id").eq("id", reply_id).limit(1).execute()
    if not res_check.data:
        raise HTTPException(status_code=404, detail="Resposta não encontrada.")

    rep = res_check.data[0]
    if str(rep.get("user_id")) != str(user["id"]) and not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Você não tem permissão para apagar esta resposta.")

    try:
        await db.table(Tables.REGULATION_REPLIES).delete().eq("id", reply_id).execute()
        # Decrementa replies_count
        if rep.get("post_id"):
            p_res = await db.table(Tables.REGULATION_POSTS).select("replies_count").eq("id", rep["post_id"]).limit(1).execute()
            curr = max(0, int(p_res.data[0]["replies_count"] or 1) - 1) if p_res.data else 0
            await db.table(Tables.REGULATION_POSTS).update({"replies_count": curr}).eq("id", rep["post_id"]).execute()
    except Exception as e:
        logger.error(f"Erro ao apagar resposta: {e}")
        await db.table(Tables.REGULATION_REPLIES).update({"status": "deleted"}).eq("id", reply_id).execute()

    return None


@router.post("/replies/{reply_id}/like", response_model=RegulationLikeToggleResponse)
async def toggle_like_reply(
    reply_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Curte ou remove curtida de uma resposta."""
    try:
        res_check = (
            await db.table(Tables.REGULATION_LIKES)
            .select("id")
            .eq("user_id", user["id"])
            .eq("target_type", "reply")
            .eq("target_id", reply_id)
            .limit(1)
            .execute()
        )

        has_liked = bool(res_check.data)

        if has_liked:
            await db.table(Tables.REGULATION_LIKES).delete().eq("user_id", user["id"]).eq("target_type", "reply").eq("target_id", reply_id).execute()
            rep_res = await db.table(Tables.REGULATION_REPLIES).select("likes_count").eq("id", reply_id).limit(1).execute()
            current_likes = max(0, int(rep_res.data[0]["likes_count"] or 1) - 1) if rep_res.data else 0
            await db.table(Tables.REGULATION_REPLIES).update({"likes_count": current_likes}).eq("id", reply_id).execute()
            return RegulationLikeToggleResponse(has_liked=False, likes_count=current_likes, message="Curtida removida da resposta.")
        else:
            await db.table(Tables.REGULATION_LIKES).insert({
                "user_id": user["id"],
                "target_type": "reply",
                "target_id": reply_id,
            }).execute()
            rep_res = await db.table(Tables.REGULATION_REPLIES).select("likes_count").eq("id", reply_id).limit(1).execute()
            current_likes = int(rep_res.data[0]["likes_count"] or 0) + 1 if rep_res.data else 1
            await db.table(Tables.REGULATION_REPLIES).update({"likes_count": current_likes}).eq("id", reply_id).execute()
            return RegulationLikeToggleResponse(has_liked=True, likes_count=current_likes, message="Resposta curtida!")
    except Exception as e:
        logger.error(f"Erro no toggle like reply: {e}")
        raise HTTPException(status_code=500, detail="Erro ao processar curtida na resposta.")


# ==============================================================================
# DENÚNCIAS & MODERAÇÃO ADMIN
# ==============================================================================

@router.post("/reports", response_model=dict, status_code=201)
async def report_regulation_content(
    payload: RegulationReportCreate,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Envia uma denúncia de conteúdo impróprio (publicação ou resposta)."""
    try:
        res = await db.table(Tables.REGULATION_REPORTS).insert({
            "user_id": user["id"],
            "target_type": payload.target_type,
            "target_id": payload.target_id,
            "reason": payload.reason.strip(),
            "details": payload.details.strip() if payload.details else None,
            "status": "pending",
        }).execute()
        return {"success": True, "message": "Denúncia enviada à moderação para análise. Obrigado por ajudar a manter a comunidade segura!"}
    except Exception as e:
        logger.warning(f"Erro ao salvar denúncia em regulation_reports: {e}")
        # Fallback na tabela reports geral
        try:
            await db.table(Tables.REPORTS).insert({
                "user_id": user["id"],
                "target_type": f"regulation_{payload.target_type}",
                "target_id": payload.target_id,
                "reason": payload.reason.strip(),
                "details": payload.details,
                "status": "open",
            }).execute()
            return {"success": True, "message": "Denúncia registrada com sucesso."}
        except Exception:
            pass
        return {"success": True, "message": "Denúncia recebida pela moderação."}


@router.get("/admin/reports", response_model=List[RegulationReportResponse])
async def list_regulation_reports_admin(
    status_filter: Optional[str] = Query("pending"),
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Lista denúncias da seção de regularização (somente Admin)."""
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores.")

    try:
        query = db.table(Tables.REGULATION_REPORTS).select("*, users:user_id(id, name, avatar_url, city, is_verified, is_admin)")
        if status_filter:
            query = query.eq("status", status_filter)
        query = query.order("created_at", desc=True)
        res = await query.execute()
        reports = res.data or []
        formatted = []
        for r in reports:
            formatted.append(RegulationReportResponse(
                id=str(r.get("id")),
                user_id=str(r.get("user_id")),
                user=_format_user_summary(r.get("users") or {}),
                target_type=r.get("target_type") or "post",
                target_id=str(r.get("target_id")),
                reason=r.get("reason") or "Denúncia",
                details=r.get("details"),
                status=r.get("status") or "pending",
                created_at=str(r.get("created_at")),
            ))
        return formatted
    except Exception as e:
        logger.warning(f"Erro ao buscar reports em regulation_reports: {e}")
        return []


@router.post("/admin/reports/{report_id}/resolve")
async def resolve_regulation_report_admin(
    report_id: str,
    action: str = Query("resolve", description="'resolve' | 'dismiss' | 'delete_target'"),
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Resolve ou rejeita uma denúncia e opcionalmente remove o conteúdo denunciado (Admin)."""
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores.")

    try:
        res = await db.table(Tables.REGULATION_REPORTS).select("*").eq("id", report_id).limit(1).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Denúncia não encontrada.")

        rep = res.data[0]
        if action == "delete_target":
            target_type = rep.get("target_type")
            target_id = rep.get("target_id")
            if target_type == "post":
                await db.table(Tables.REGULATION_POSTS).update({"status": "deleted"}).eq("id", target_id).execute()
            elif target_type == "reply":
                await db.table(Tables.REGULATION_REPLIES).update({"status": "deleted"}).eq("id", target_id).execute()

        new_status = "resolved" if action in ["resolve", "delete_target"] else "dismissed"
        await db.table(Tables.REGULATION_REPORTS).update({"status": new_status}).eq("id", report_id).execute()
        return {"success": True, "status": new_status, "message": "Denúncia processada com sucesso!"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao resolver denúncia: {e}")
        raise HTTPException(status_code=500, detail="Erro ao processar denúncia.")
