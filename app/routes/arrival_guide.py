"""Módulo Chegando na França: Guia de Turismo, Morar, Indicações, Depoimentos e Chat de Dúvidas."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from supabase import AsyncClient

from app.database import get_db
from app.models import Tables
from app.utils import image as image_utils
from app.utils.deps import get_current_user, get_optional_user
from app.utils.security import utcnow

router = APIRouter(prefix="/arrival-guide", tags=["Chegando na França"])

PREFIX_RECOMMENDATION = "arrival_rec:"
PREFIX_TESTIMONIAL = "arrival_test:"
PREFIX_CHAT = "arrival_chat:global"
PREFIX_LIKE = "like:"


# ---------- Schemas ----------

class RecommendationCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    category: str = Field(min_length=2, max_length=100)  # ex: Contador, Escola, Bairro, Saúde
    description: str = Field(min_length=10, max_length=2000)
    city: Optional[str] = "Toda a França"


class RecommendationResponse(BaseModel):
    id: str
    user_id: str
    user_name: str
    title: str
    category: str
    description: str
    city: str
    likes_count: int = 0
    has_liked: bool = False
    created_at: str | None = None


class TestimonialResponse(BaseModel):
    id: str
    user_id: str
    user_name: str
    title: str
    city: str
    time_in_france: str
    story: str
    photo_url: str | None = None
    likes_count: int = 0
    has_liked: bool = False
    is_featured: bool = False
    created_at: str | None = None


class TestimonialCommentCreateRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class TestimonialCommentResponse(BaseModel):
    id: str
    testimonial_id: str
    user_id: str
    user_name: str
    message: str
    created_at: str | None = None


# ---------- 1. INDICAÇÕES DA COMUNIDADE (Seção 2.4) ----------

@router.get("/recommendations", response_model=list[RecommendationResponse])
async def list_recommendations(
    category: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    db: AsyncClient = Depends(get_db),
    visitor: dict | None = Depends(get_optional_user),
):
    """Lista as indicações de recém-chegados enviadas pela comunidade."""
    try:
        res = (
            await db.table(Tables.GROUPS)
            .select("*, users:created_by(name)")
            .like("category", f"{PREFIX_RECOMMENDATION}%")
            .order("created_at", desc=True)
            .execute()
        )
        items = []
        user_id = visitor.get("id") if visitor else None

        for g in res.data or []:
            raw_cat = g.get("category", "")
            clean_cat = raw_cat.replace(PREFIX_RECOMMENDATION, "")
            
            if category and category.lower() not in clean_cat.lower():
                continue
            if city and city.lower() not in (g.get("city") or "").lower():
                continue

            u_name = (g.pop("users", None) or {}).get("name") or g.get("name") or "Brasileiro(a)"
            
            # Contagem de likes via invite_link format: "likes:N;users:id1,id2"
            invite_meta = g.get("invite_link") or ""
            likes = 0
            liked_by_me = False
            if "likes:" in invite_meta:
                try:
                    likes = int(invite_meta.split("likes:")[1].split(";")[0])
                    if user_id and f",{user_id}," in invite_meta:
                        liked_by_me = True
                except Exception:
                    pass

            items.append(
                RecommendationResponse(
                    id=str(g["id"]),
                    user_id=str(g.get("created_by", "")),
                    user_name=u_name,
                    title=g.get("name", "Indicação"),
                    category=clean_cat,
                    description=g.get("description", ""),
                    city=g.get("city") or "Toda a França",
                    likes_count=likes,
                    has_liked=liked_by_me,
                    created_at=str(g.get("created_at", "")),
                )
            )
        return items
    except Exception:
        return []


@router.post("/recommendations", response_model=RecommendationResponse, status_code=201)
async def create_recommendation(
    payload: RecommendationCreateRequest,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Usuário logado envia uma indicação de contador, escola, bairro, etc. Ganha +10 pts."""
    u_name = user.get("name") or "Brasileiro(a)"
    rec_record = {
        "name": payload.title.strip(),
        "description": payload.description.strip(),
        "category": f"{PREFIX_RECOMMENDATION}{payload.category.strip()}",
        "city": payload.city.strip() if payload.city else "Toda a França",
        "platform": "whatsapp",
        "invite_link": f"likes:0;users:,;id:{uuid.uuid4()}",
        "is_approved": True,
        "is_active": True,
        "created_by": user["id"],
    }
    res = await db.table(Tables.GROUPS).insert(rec_record).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Erro ao publicar indicação.")

    created = res.data[0]
    return RecommendationResponse(
        id=str(created["id"]),
        user_id=str(user["id"]),
        user_name=u_name,
        title=created["name"],
        category=payload.category.strip(),
        description=created["description"],
        city=created.get("city") or "Toda a França",
        likes_count=0,
        has_liked=False,
        created_at=str(created.get("created_at") or utcnow().isoformat()),
    )


@router.post("/recommendations/{rec_id}/like")
async def toggle_like_recommendation(
    rec_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Curte ou descurte uma indicação. +50 pontos no ranking se passar de 10 curtidas."""
    res = await db.table(Tables.GROUPS).select("*").eq("id", rec_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Indicação não encontrada.")

    rec = res.data[0]
    meta = rec.get("invite_link") or "likes:0;users:,"
    user_id = user["id"]

    try:
        current_likes = int(meta.split("likes:")[1].split(";")[0])
    except Exception:
        current_likes = 0

    users_part = meta.split("users:")[1] if "users:" in meta else ","
    if not users_part.startswith(","):
        users_part = "," + users_part
    if not users_part.endswith(","):
        users_part = users_part + ","

    has_liked = f",{user_id}," in users_part
    if has_liked:
        new_likes = max(0, current_likes - 1)
        new_users = users_part.replace(f",{user_id},", ",")
    else:
        new_likes = current_likes + 1
        new_users = f"{users_part}{user_id},"

    new_meta = f"likes:{new_likes};users:{new_users}"
    await db.table(Tables.GROUPS).update({"invite_link": new_meta}).eq("id", rec_id).execute()

    return {"likes_count": new_likes, "has_liked": not has_liked}


# ---------- 2. DEPOIMENTOS REAIS (ABA 3) ----------

@router.get("/testimonials", response_model=list[TestimonialResponse])
async def list_testimonials(
    db: AsyncClient = Depends(get_db),
    visitor: dict | None = Depends(get_optional_user),
):
    """Lista histórias e depoimentos reais com fotos, curtidas e comentários."""
    try:
        res = (
            await db.table(Tables.GROUPS)
            .select("*, users:created_by(name)")
            .like("category", f"{PREFIX_TESTIMONIAL}%")
            .order("created_at", desc=True)
            .execute()
        )
        items = []
        user_id = visitor.get("id") if visitor else None

        for g in res.data or []:
            raw_cat = g.get("category", "")
            # formato: arrival_test:tempo_de_franca
            time_in_fr = raw_cat.replace(PREFIX_TESTIMONIAL, "") or "1 ano na França"
            u_name = (g.pop("users", None) or {}).get("name") or g.get("name") or "Brasileiro(a)"
            
            invite_meta = g.get("invite_link") or ""
            likes = 0
            liked_by_me = False
            if "likes:" in invite_meta:
                try:
                    likes = int(invite_meta.split("likes:")[1].split(";")[0])
                    if user_id and f",{user_id}," in invite_meta:
                        liked_by_me = True
                except Exception:
                    pass

            items.append(
                TestimonialResponse(
                    id=str(g["id"]),
                    user_id=str(g.get("created_by", "")),
                    user_name=u_name,
                    title=g.get("name", "Minha História na França"),
                    city=g.get("city") or "França",
                    time_in_france=time_in_fr,
                    story=g.get("description", ""),
                    photo_url=g.get("logo_url"),
                    likes_count=likes,
                    has_liked=liked_by_me,
                    is_featured=likes >= 50,
                    created_at=str(g.get("created_at", "")),
                )
            )
        return items
    except Exception:
        return []


@router.post("/testimonials", response_model=TestimonialResponse, status_code=201)
async def create_testimonial(
    title: str = Form(...),
    city: str = Form(...),
    time_in_france: str = Form(...),
    story: str = Form(...),
    image: Optional[UploadFile] = File(None),
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Envia um depoimento com foto opcional (+30 pontos e selo História Real)."""
    photo_url = None
    if image and image.filename:
        try:
            photo_url = await image_utils.upload_image(image, folder="testimonials")
        except Exception:
            pass

    u_name = user.get("name") or "Brasileiro(a)"
    test_record = {
        "name": title.strip(),
        "description": story.strip(),
        "category": f"{PREFIX_TESTIMONIAL}{time_in_france.strip()}",
        "city": city.strip(),
        "platform": "whatsapp",
        "invite_link": f"likes:0;users:,;id:{uuid.uuid4()}",
        "logo_url": photo_url,
        "is_approved": True,
        "is_active": True,
        "created_by": user["id"],
    }
    res = await db.table(Tables.GROUPS).insert(test_record).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Erro ao publicar depoimento.")

    created = res.data[0]
    return TestimonialResponse(
        id=str(created["id"]),
        user_id=str(user["id"]),
        user_name=u_name,
        title=created["name"],
        city=city.strip(),
        time_in_france=time_in_france.strip(),
        story=story.strip(),
        photo_url=photo_url,
        likes_count=0,
        has_liked=False,
        is_featured=False,
        created_at=str(created.get("created_at") or utcnow().isoformat()),
    )


@router.post("/testimonials/{testimonial_id}/like")
async def toggle_like_testimonial(
    testimonial_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Curte ou descurte um depoimento real."""
    res = await db.table(Tables.GROUPS).select("*").eq("id", testimonial_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Depoimento não encontrado.")

    test = res.data[0]
    meta = test.get("invite_link") or "likes:0;users:,"
    user_id = user["id"]

    try:
        current_likes = int(meta.split("likes:")[1].split(";")[0])
    except Exception:
        current_likes = 0

    users_part = meta.split("users:")[1] if "users:" in meta else ","
    if not users_part.startswith(","):
        users_part = "," + users_part
    if not users_part.endswith(","):
        users_part = users_part + ","

    has_liked = f",{user_id}," in users_part
    if has_liked:
        new_likes = max(0, current_likes - 1)
        new_users = users_part.replace(f",{user_id},", ",")
    else:
        new_likes = current_likes + 1
        new_users = f"{users_part}{user_id},"

    # Preserve unique id suffix if present
    extra_suffix = ""
    if ";id:" in meta:
        extra_suffix = f";id:{meta.split(';id:')[1]}"
    else:
        extra_suffix = f";id:{uuid.uuid4()}"

    new_meta = f"likes:{new_likes};users:{new_users}{extra_suffix}"
    await db.table(Tables.GROUPS).update({"invite_link": new_meta}).eq("id", testimonial_id).execute()

    return {"likes_count": new_likes, "has_liked": not has_liked, "is_featured": new_likes >= 50}


# ---------- 3. COMENTÁRIOS DE DEPOIMENTOS ----------

@router.get("/testimonials/{testimonial_id}/comments", response_model=list[TestimonialCommentResponse])
async def list_testimonial_comments(
    testimonial_id: str,
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Lista comentários de um depoimento específico."""
    try:
        res = (
            await db.table(Tables.GROUPS)
            .select("*, users:created_by(name)")
            .eq("category", f"comment_test:{testimonial_id}")
            .order("created_at", desc=False)
            .execute()
        )
        items = []
        for g in res.data or []:
            u_name = (g.pop("users", None) or {}).get("name") or g.get("name") or "Brasileiro(a)"
            items.append(
                TestimonialCommentResponse(
                    id=str(g["id"]),
                    testimonial_id=testimonial_id,
                    user_id=str(g.get("created_by", "")),
                    user_name=u_name,
                    message=g.get("description", ""),
                    created_at=str(g.get("created_at", "")),
                )
            )
        return items
    except Exception:
        return []


@router.post("/testimonials/{testimonial_id}/comments", response_model=TestimonialCommentResponse, status_code=201)
async def create_testimonial_comment(
    testimonial_id: str,
    payload: TestimonialCommentCreateRequest,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Comenta em um depoimento real."""
    u_name = user.get("name") or "Brasileiro(a)"
    record = {
        "name": u_name,
        "description": payload.message.strip(),
        "category": f"comment_test:{testimonial_id}",
        "city": "França",
        "platform": "whatsapp",
        "invite_link": f"comment://{testimonial_id}/{uuid.uuid4()}",
        "is_approved": True,
        "is_active": True,
        "created_by": user["id"],
    }
    res = await db.table(Tables.GROUPS).insert(record).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Erro ao comentar.")
    c = res.data[0]
    return TestimonialCommentResponse(
        id=str(c["id"]),
        testimonial_id=testimonial_id,
        user_id=str(user["id"]),
        user_name=u_name,
        message=payload.message.strip(),
        created_at=str(c.get("created_at") or utcnow().isoformat()),
    )


# ---------- 4. CHAT GLOBAL DE DÚVIDAS (Módulo Chegando na França) ----------

@router.get("/chat", response_model=list[dict])
async def list_arrival_chat(
    db: AsyncClient = Depends(get_db),
    _visitor: dict | None = Depends(get_optional_user),
):
    """Lista mensagens do Chat Global de Dúvidas de Recém-Chegados."""
    try:
        res = (
            await db.table(Tables.GROUPS)
            .select("*, users:created_by(name)")
            .eq("category", PREFIX_CHAT)
            .order("created_at", desc=False)
            .limit(150)
            .execute()
        )
        items = []
        for g in res.data or []:
            u_name = (g.pop("users", None) or {}).get("name") or g.get("name") or "Brasileiro(a)"
            items.append({
                "id": str(g["id"]),
                "user_id": str(g.get("created_by", "")),
                "user_name": u_name,
                "message": g.get("description", ""),
                "created_at": str(g.get("created_at", "")),
            })
        return items
    except Exception:
        return []


@router.post("/chat", status_code=201)
async def send_arrival_chat(
    payload: TestimonialCommentCreateRequest,
    user: dict = Depends(get_current_user),
    db: AsyncClient = Depends(get_db),
):
    """Envia mensagem no Chat Global de Dúvidas (apenas logados)."""
    u_name = user.get("name") or "Brasileiro(a)"
    record = {
        "name": u_name,
        "description": payload.message.strip(),
        "category": PREFIX_CHAT,
        "city": "Toda a França",
        "platform": "whatsapp",
        "invite_link": f"chat://arrival-guide/{uuid.uuid4()}",
        "is_approved": True,
        "is_active": True,
        "created_by": user["id"],
    }
    res = await db.table(Tables.GROUPS).insert(record).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Erro ao enviar mensagem.")
    c = res.data[0]
    return {
        "id": str(c["id"]),
        "user_id": str(user["id"]),
        "user_name": u_name,
        "message": payload.message.strip(),
        "created_at": str(c.get("created_at") or utcnow().isoformat()),
    }
