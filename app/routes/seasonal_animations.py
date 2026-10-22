"""Rotas e persistência para Animações Sazonais (Halloween, Natal, etc.)."""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from app.utils.deps import get_admin_user
from app.utils import image as image_utils

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/seasonal-animations",
    tags=["Animações Sazonais"],
)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
CONFIG_FILE = os.path.join(DATA_DIR, "seasonal_config.json")

# Temas padrão e configurações iniciais seguras
DEFAULT_CONFIG = {
    "themes": [
        {
            "id": "halloween",
            "name": "Halloween",
            "icon": "🎃",
            "is_active": False,
            "start_date": "2026-10-20T00:00:00",
            "end_date": "2026-11-03T23:59:59",
            "intensity": "medium",  # "low", "medium", "high"
            "repeat_interval": 60,   # segundos entre re-aparições
            "initial_delay": 10,     # atraso inicial antes de aparecer
            "display_duration": 7,   # segundos visível
            "position": "bottom-right",  # "bottom-right", "bottom-left", "top-right", "top-left"
            "animation_type": "css_canvas",  # "css_canvas" | "video"
            "asset_url": "",        # url da imagem/mini vídeo se houver
            "title": "Feliz Halloween! 🦇",
            "subtitle": "Doces ou Travessuras na comunidade!",
            "css_effect": "spooky_sparkles"  # efeito de partículas canvas/css
        },
        {
            "id": "outubro_rosa",
            "name": "Outubro Rosa",
            "icon": "🌸",
            "is_active": False,
            "start_date": "2026-10-01T00:00:00",
            "end_date": "2026-10-31T23:59:59",
            "intensity": "medium",
            "repeat_interval": 60,
            "initial_delay": 10,
            "display_duration": 6,
            "position": "bottom-right",
            "animation_type": "css_canvas",
            "asset_url": "",
            "title": "Outubro Rosa 🎗️",
            "subtitle": "Conscientização e prevenção ao câncer de mama.",
            "css_effect": "pink_ribbons"
        },
        {
            "id": "natal",
            "name": "Natal",
            "icon": "🎄",
            "is_active": False,
            "start_date": "2026-12-01T00:00:00",
            "end_date": "2026-12-26T23:59:59",
            "intensity": "medium",
            "repeat_interval": 60,
            "initial_delay": 10,
            "display_duration": 7,
            "position": "bottom-right",
            "animation_type": "css_canvas",
            "asset_url": "",
            "title": "Joyeux Noël & Boas Festas! ❄️",
            "subtitle": "A magia do Natal com a comunidade brasileira na França.",
            "css_effect": "falling_snow"
        },
        {
            "id": "ano_novo",
            "name": "Ano Novo",
            "icon": "🥂",
            "is_active": False,
            "start_date": "2026-12-28T00:00:00",
            "end_date": "2027-01-05T23:59:59",
            "intensity": "medium",
            "repeat_interval": 60,
            "initial_delay": 10,
            "display_duration": 7,
            "position": "bottom-right",
            "animation_type": "css_canvas",
            "asset_url": "",
            "title": "Bonne Année! Feliz Ano Novo! ✨",
            "subtitle": "Que este novo ano traga saúde, conquistas e prosperidade!",
            "css_effect": "golden_confetti"
        },
        {
            "id": "quatorze_julho",
            "name": "14 de Julho (Fête Nationale)",
            "icon": "🇫🇷",
            "is_active": False,
            "start_date": "2026-07-12T00:00:00",
            "end_date": "2026-07-16T23:59:59",
            "intensity": "medium",
            "repeat_interval": 60,
            "initial_delay": 10,
            "display_duration": 6,
            "position": "bottom-right",
            "animation_type": "css_canvas",
            "asset_url": "",
            "title": "14 Juillet - Fête Nationale! 🎆",
            "subtitle": "Liberté, Égalité, Fraternité.",
            "css_effect": "tricolore_burst"
        },
        {
            "id": "pascoa",
            "name": "Páscoa",
            "icon": "🐰",
            "is_active": False,
            "start_date": "2026-03-25T00:00:00",
            "end_date": "2026-04-10T23:59:59",
            "intensity": "medium",
            "repeat_interval": 60,
            "initial_delay": 10,
            "display_duration": 6,
            "position": "bottom-right",
            "animation_type": "css_canvas",
            "asset_url": "",
            "title": "Feliz Páscoa! Joyeuses Pâques! 🍫",
            "subtitle": "Renovação e união para você e sua família.",
            "css_effect": "easter_sparkles"
        },
        {
            "id": "datas_nacionais",
            "name": "Datas Nacionais & Brasil",
            "icon": "🇧🇷",
            "is_active": False,
            "start_date": "2026-09-01T00:00:00",
            "end_date": "2026-09-08T23:59:59",
            "intensity": "medium",
            "repeat_interval": 60,
            "initial_delay": 10,
            "display_duration": 6,
            "position": "bottom-right",
            "animation_type": "css_canvas",
            "asset_url": "",
            "title": "Orgulho Brasileiro! 💚💛",
            "subtitle": "Celebrando nossas raízes brasileiras na França.",
            "css_effect": "verde_amarelo"
        },
        {
            "id": "eventos_sociais",
            "name": "Eventos Sociais e Solidariedade",
            "icon": "🤝",
            "is_active": False,
            "start_date": "2026-01-01T00:00:00",
            "end_date": "2026-12-31T23:59:59",
            "intensity": "low",
            "repeat_interval": 120,
            "initial_delay": 15,
            "display_duration": 6,
            "position": "bottom-right",
            "animation_type": "css_canvas",
            "asset_url": "",
            "title": "Ação Social & Apoio Mútuo 💙",
            "subtitle": "Juntos somos mais fortes na França.",
            "css_effect": "gentle_hearts"
        }
    ]
}


def _ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
        except Exception as e:
            logger.error("Erro ao criar pasta data: %s", e)


def load_config() -> Dict[str, Any]:
    """Carrega configuração do arquivo JSON ou retorna a padrão."""
    _ensure_data_dir()
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Garantir integridade de campos mínimos
            if not isinstance(data, dict) or "themes" not in data:
                return DEFAULT_CONFIG
            return data
    except Exception as e:
        logger.error("Erro ao carregar seasonal_config.json: %s", e)
        return DEFAULT_CONFIG


def save_config(config: Dict[str, Any]) -> None:
    """Salva as configurações em seasonal_config.json."""
    _ensure_data_dir()
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Erro ao salvar seasonal_config.json: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao persistir configurações sazonais.")


class SeasonalTheme(BaseModel):
    id: str
    name: str
    icon: Optional[str] = "✨"
    is_active: bool = False
    start_date: str
    end_date: str
    intensity: str = Field(default="medium", description="low, medium, high")
    repeat_interval: int = Field(default=60, description="Segundos entre re-exibições")
    initial_delay: int = Field(default=10, description="Atraso inicial em segundos")
    display_duration: int = Field(default=7, description="Duração da exibição em segundos")
    position: str = Field(default="bottom-right", description="bottom-right, bottom-left, top-right, top-left")
    animation_type: str = Field(default="css_canvas", description="css_canvas ou video")
    asset_url: Optional[str] = ""
    title: Optional[str] = ""
    subtitle: Optional[str] = ""
    css_effect: Optional[str] = "spooky_sparkles"


class SeasonalConfigUpdate(BaseModel):
    themes: List[SeasonalTheme]


@router.get("", summary="Retorna os temas sazonais ativos no momento (Público)")
async def get_active_seasonal_animations():
    """Retorna a lista de temas ativos para exibição no frontend."""
    cfg = load_config()
    return {"themes": cfg.get("themes", [])}


@router.get("/admin", summary="Retorna todas as configurações para a área de admin")
async def get_admin_seasonal_config(admin: dict = Depends(get_admin_user)):
    """Retorna todos os temas cadastrados para edição no painel de administração."""
    return load_config()


@router.post("/admin", summary="Salva configurações de temas sazonais (Admin)")
async def update_seasonal_config(data: SeasonalConfigUpdate, admin: dict = Depends(get_admin_user)):
    """Persiste a lista atualizada de animações sazonais."""
    cfg = {"themes": [t.dict() for t in data.themes]}
    save_config(cfg)
    return {"status": "success", "message": "Configurações sazonais salvas com sucesso!", "data": cfg}


@router.post("/upload", summary="Upload de imagem ou mini vídeo para animações sazonais (Admin)")
async def upload_seasonal_asset(file: UploadFile = File(...), admin: dict = Depends(get_admin_user)):
    """Upload de imagens (jpeg/png/webp/gif) ou vídeos leves (mp4/webm) para animações."""
    allowed_types = {
        "image/jpeg", "image/png", "image/webp", "image/gif", "image/svg+xml",
        "video/mp4", "video/webm", "video/quicktime"
    }
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Formato não suportado: {file.content_type}. Use imagens (png, webp, gif, jpg) ou vídeos curtos (mp4, webm)."
        )

    # Reutiliza o upload seguro para GCS
    try:
        url = await image_utils._upload(file, "seasonal_assets", allowed_types, "arquivo de animação")
        return {"url": url, "filename": file.filename}
    except Exception as e:
        logger.error("Erro no upload de asset sazonal: %s", e)
        raise HTTPException(status_code=500, detail=f"Erro ao salvar arquivo: {str(e)}")
