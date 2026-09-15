"""Ponto de entrada da API — Brasileiros na França."""

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.admin.router import router as admin_router
from app.config import settings
from app.utils import image as image_utils
from app.routes import (
    ads,
    arrival_guide,
    artists,
    associations,
    auth,
    charity_ads,
    gift_codes,
    groups,
    item_comments,
    job_ads,
    moving_sales,
    news_carousel,
    notifications,
    payments,
    pet_posts,
    ranking,
    regulation,
    reports,
    reviews,
    tourism_spots,
    urgent_ads,
    users,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Cron: ranking mensal no 1º dia de cada mês às 03h
    scheduler.add_job(
        ranking.run_scheduled_ranking,
        CronTrigger(day=1, hour=3, minute=0),
        id="monthly_ranking",
        replace_existing=True,
    )
    # Cron diário: expirar anúncios de urgência com mais de 7 dias
    scheduler.add_job(
        ranking.run_scheduled_urgent_expiration,
        CronTrigger(hour=4, minute=0),
        id="expire_urgent_ads",
        replace_existing=True,
    )
    # Cron diário: expirar eventos cuja data já passou (+24h)
    scheduler.add_job(
        ads.run_scheduled_event_expiration,
        CronTrigger(hour=4, minute=30),
        id="expire_passed_events",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler iniciado (ranking mensal + expiração de urgências + expiração de eventos passados).")
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title=settings.APP_NAME,
    description="API da comunidade Brasileiros na França: anúncios, avaliações, "
    "grupos, urgências, caridade, destaques pagos e ranking mensal.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://frontend-brasileiros.onrender.com",
        "https://brasileirosnafranca.com",
    ] if settings.FRONTEND_URL != "*" else ["*"],
    allow_origin_regex=r"^https://.*(\.onrender\.com|\.netlify\.app)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────────────────────
# Handler global: garante que erros 500 não-tratados retornem
# JSON com CORS correto (sem ele, o navegador bloqueia a resposta
# e o frontend só vê "Network Error" em vez da mensagem real).
# ──────────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    import traceback
    logger.error(
        f"[UNHANDLED] {request.method} {request.url.path} → "
        f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
    )
    return JSONResponse(
        status_code=500,
        content={"detail": f"Erro interno do servidor: {type(exc).__name__}: {exc}"},
    )


@app.api_route("/", methods=["GET", "HEAD"], tags=["Sistema"])
async def root():
    return {
        "status": "online",
        "app": settings.APP_NAME,
        "docs": "/docs",
        "health": "/health"
    }


@app.api_route("/health", methods=["GET", "HEAD"], tags=["Sistema"])
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME}


@app.post("/upload", tags=["Upload"])
async def upload_file_generic(file: UploadFile = File(...)):
    """Upload genérico de imagens para o Supabase Storage."""
    url = await image_utils.upload_image(file, folder="community")
    return {"url": url, "filename": file.filename}


# Rotas públicas + autenticadas
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(notifications.router)
app.include_router(ads.router)
app.include_router(reviews.router)
app.include_router(groups.router)
app.include_router(associations.router)
app.include_router(urgent_ads.router)
app.include_router(charity_ads.router)
app.include_router(tourism_spots.router)
app.include_router(pet_posts.router)
app.include_router(item_comments.router)
app.include_router(job_ads.router)
app.include_router(moving_sales.router)
app.include_router(artists.router)
app.include_router(regulation.router)
app.include_router(news_carousel.router)
app.include_router(arrival_guide.router)
app.include_router(gift_codes.router)
app.include_router(reports.router)
app.include_router(payments.router)
app.include_router(ranking.router)

# Rotas administrativas
app.include_router(admin_router)
