"""Serviço de Tradução Automática Multilíngue (PT, FR, EN) com cache em memória."""

import logging
import urllib.parse
from typing import Optional
import requests

logger = logging.getLogger(__name__)

# Cache simples em memória para evitar chamadas de rede repetidas
_TRANSLATION_CACHE: dict[str, str] = {}


def _clean_lang(lang: Optional[str]) -> str:
    """Normaliza o código do idioma (pt, fr, en)."""
    if not lang:
        return "pt"
    clean = lang.lower().strip().split("-")[0].split("_")[0]
    return clean if clean in ("pt", "fr", "en") else "pt"


def translate_text(text: str, target_lang: str, source_lang: str = "auto") -> str:
    """
    Traduz um texto para o idioma desejado (pt, fr, en) com auto-detecção do idioma original.
    Utiliza Google GTX com fallback seguro para MyMemory.
    Cacheia em memória para desempenho imediato.
    """
    if not text or not str(text).strip():
        return text

    target = _clean_lang(target_lang)
    raw_text = str(text).strip()
    cache_key = f"{source_lang}->{target}:{raw_text}"
    if cache_key in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[cache_key]

    # Google GTX endpoint (envia o texto completo de uma única vez para máxima velocidade)
    try:
        quoted = urllib.parse.quote(raw_text)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source_lang}&tl={target}&dt=t&q={quoted}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                translated = "".join([part[0] for part in data[0] if part and part[0]])
                if translated and translated.strip():
                    _TRANSLATION_CACHE[cache_key] = translated.strip()
                    return translated.strip()
    except Exception as e:
        logger.warning(f"[Translate] Google GTX failed for '{raw_text[:30]}...': {e}")

    # Fallback: MyMemory API
    try:
        quoted = urllib.parse.quote(raw_text[:450].strip())
        pair = f"autodetect|{target}"
        url = f"https://api.mymemory.translated.net/get?q={quoted}&langpair={pair}"
        resp = requests.get(url, timeout=2.5)
        if resp.status_code == 200:
            res_data = resp.json()
            translated = res_data.get("responseData", {}).get("translatedText")
            if translated and not str(translated).startswith("MYMEMORY WARNING"):
                _TRANSLATION_CACHE[cache_key] = str(translated).strip()
                return str(translated).strip()
    except Exception as e:
        logger.warning(f"[Translate] MyMemory fallback failed: {e}")

    # Se falhar tudo, devolve o texto original
    return text


def translate_job_fields(job_dict: dict, target_lang: str) -> dict:
    """
    Traduz os campos dinâmicos de um anúncio de emprego:
    - title
    - description
    Preserva todos os outros campos intactos (IDs, contatos, telefones, links, etc).
    """
    target = _clean_lang(target_lang)
    
    # Faz uma cópia rasa do dicionário
    item = dict(job_dict)
    original_title = item.get("title") or ""
    original_desc = item.get("description") or ""

    # Adiciona metadados úteis para o front-end
    item["original_title"] = original_title
    item["original_description"] = original_desc
    item["translated_lang"] = target

    # Traduz título
    if original_title:
        item["title"] = translate_text(original_title, target)

    # Traduz descrição de uma única vez (preserva quebras de linha nativamente no Google GTX)
    if original_desc:
        item["description"] = translate_text(original_desc, target)

    return item
