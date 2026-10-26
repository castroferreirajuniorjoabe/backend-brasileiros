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


INVALID_TRANSLATION_SNIPPETS = (
    "PLEASE SELECT TWO DISTINCT LANGUAGES",
    "MYMEMORY WARNING",
    "INVALID TARGET LANGUAGE",
    "QUERY LENGTH LIMIT EXCEEDED",
)


def translate_text(text: str, target_lang: str, source_lang: str = "auto") -> str:
    """
    Traduz um texto para o idioma desejado (pt, fr, en) com auto-detecção do idioma original.
    Se o idioma destino for português (pt), retorna o texto original intacto,
    pois os anúncios do portal são cadastrados em português.
    Utiliza Google GTX com fallback seguro para MyMemory.
    Cacheia em memória para desempenho imediato.
    """
    if not text or not str(text).strip():
        return text

    target = _clean_lang(target_lang)
    raw_text = str(text).strip()

    # Se o destino for PT ou o idioma de origem for igual ao destino, não traduz nada
    if target == "pt" or (source_lang and source_lang.lower() == target):
        return raw_text

    cache_key = f"{source_lang}->{target}:{raw_text}"
    if cache_key in _TRANSLATION_CACHE:
        cached = _TRANSLATION_CACHE[cache_key]
        if not any(snippet in cached for snippet in INVALID_TRANSLATION_SNIPPETS):
            return cached

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
                    cleaned_trans = translated.strip()
                    if not any(snippet in cleaned_trans for snippet in INVALID_TRANSLATION_SNIPPETS):
                        _TRANSLATION_CACHE[cache_key] = cleaned_trans
                        return cleaned_trans
    except Exception as e:
        logger.warning(f"[Translate] Google GTX failed for '{raw_text[:30]}...': {e}")

    # Fallback: MyMemory API (requer par de idiomas explícito, não usar 'autodetect')
    try:
        quoted = urllib.parse.quote(raw_text[:450].strip())
        pair = f"pt|{target}"
        url = f"https://api.mymemory.translated.net/get?q={quoted}&langpair={pair}"
        resp = requests.get(url, timeout=2.5)
        if resp.status_code == 200:
            res_data = resp.json()
            translated = res_data.get("responseData", {}).get("translatedText")
            if translated and not any(snippet in str(translated) for snippet in INVALID_TRANSLATION_SNIPPETS):
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
    Se o idioma destino for 'pt', preserva o texto original cadastrado sem tradução.
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

    # Se for português, não altera título nem descrição
    if target == "pt":
        item["title"] = original_title
        item["description"] = original_desc
        return item

    # Traduz título para FR ou EN
    if original_title:
        translated_title = translate_text(original_title, target)
        item["title"] = translated_title if translated_title else original_title

    # Traduz descrição para FR ou EN
    if original_desc:
        translated_desc = translate_text(original_desc, target)
        item["description"] = translated_desc if translated_desc else original_desc

    return item

