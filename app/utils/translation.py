"""Serviço de Tradução Automática Multilíngue (PT, FR, EN) com cache em memória e fallback robusto."""

import logging
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
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

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def _parse_clients5_response(data) -> Optional[str]:
    """Interpreta a resposta da API clients5.google.com."""
    try:
        if isinstance(data, list):
            parts = []
            for item in data:
                if isinstance(item, list) and len(item) > 0 and isinstance(item[0], str):
                    parts.append(item[0])
                elif isinstance(item, str):
                    parts.append(item)
            res = "".join(parts).strip()
            return res if res else None
        elif isinstance(data, str) and data.strip():
            return data.strip()
    except Exception:
        pass
    return None


def _translate_single_chunk(text: str, target: str, source: str = "auto") -> Optional[str]:
    """Traduz um pedaço de texto usando clients5 -> Google GTX -> MyMemory."""
    clean = text.strip()
    if not clean:
        return ""

    quoted = urllib.parse.quote(clean)

    # 1. Google Chrome Dict API (clients5) - Ultra rápida e sem truncamento
    try:
        url = f"https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl={source}&tl={target}&q={quoted}"
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=3.5)
        if resp.status_code == 200:
            parsed = _parse_clients5_response(resp.json())
            if parsed and not any(snip in parsed for snip in INVALID_TRANSLATION_SNIPPETS):
                return parsed
    except Exception as e:
        logger.debug(f"[Translate] clients5 failed for '{clean[:30]}': {e}")

    # 2. Google GTX API
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source}&tl={target}&dt=t&q={quoted}"
        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=3.5)
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                translated = "".join([part[0] for part in data[0] if part and part[0]])
                if translated and translated.strip():
                    cleaned_trans = translated.strip()
                    if not any(snippet in cleaned_trans for snippet in INVALID_TRANSLATION_SNIPPETS):
                        return cleaned_trans
    except Exception as e:
        logger.debug(f"[Translate] Google GTX failed for '{clean[:30]}': {e}")

    # 3. Fallback: MyMemory API (requer par de idiomas explícito pt|target)
    try:
        pair = f"pt|{target}"
        url = f"https://api.mymemory.translated.net/get?q={quoted}&langpair={pair}"
        resp = requests.get(url, timeout=3.0)
        if resp.status_code == 200:
            res_data = resp.json()
            translated = res_data.get("responseData", {}).get("translatedText")
            if translated and not any(snippet in str(translated) for snippet in INVALID_TRANSLATION_SNIPPETS):
                return str(translated).strip()
    except Exception as e:
        logger.debug(f"[Translate] MyMemory fallback failed: {e}")

    return None


def _chunk_text(text: str, max_chunk_len: int = 400) -> list[str]:
    """Divide textos longos por quebras de linha preservando a estrutura para APIs com limite de caracteres."""
    lines = text.split("\n")
    chunks = []
    current: list[str] = []
    current_len = 0
    for line in lines:
        if current_len + len(line) + 1 > max_chunk_len and current:
            chunks.append("\n".join(current))
            current = [line]
            current_len = len(line)
        else:
            current.append(line)
            current_len += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks


def translate_text(text: str, target_lang: str, source_lang: str = "auto") -> str:
    """
    Traduz um texto para o idioma desejado (pt, fr, en) com auto-detecção do idioma original.
    Se o idioma destino for português (pt), retorna o texto original intacto.
    Preserva a integridade do texto sem truncar textos longos.
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

    # Tenta traduzir o texto inteiro de uma vez
    translated = _translate_single_chunk(raw_text, target, source_lang)
    if translated:
        _TRANSLATION_CACHE[cache_key] = translated
        return translated

    # Se falhou e o texto é longo, tenta traduzir por blocos/parágrafos sem perder nada
    if len(raw_text) > 400:
        chunks = _chunk_text(raw_text, max_chunk_len=350)
        translated_chunks = []
        for c in chunks:
            chunk_trans = _translate_single_chunk(c, target, source_lang)
            translated_chunks.append(chunk_trans if chunk_trans else c)
        full_res = "\n".join(translated_chunks)
        _TRANSLATION_CACHE[cache_key] = full_res
        return full_res

    # Se falhar tudo, devolve o texto original
    return text


CITY_LOCALIZATIONS = {
    "Outro Local / Digitar Manualmente": {
        "fr": "Autre Ville / Saisie Manuelle",
        "en": "Other Location / Enter Manually",
    }
}

CONTRACT_LOCALIZATIONS = {
    "Outro": {
        "fr": "Autre",
        "en": "Other",
    }
}


def translate_job_fields(job_dict: dict, target_lang: str, translate_desc: bool = True) -> dict:
    """
    Traduz os campos dinâmicos de um anúncio de emprego:
    - title
    - description (se translate_desc for True)
    - city (se genérico)
    - contract_type
    Preserva todos os outros campos intactos.
    """
    target = _clean_lang(target_lang)

    item = dict(job_dict)
    original_title = item.get("title") or ""
    original_desc = item.get("description") or ""

    item["original_title"] = original_title
    item["original_description"] = original_desc
    item["translated_lang"] = target

    if target == "pt":
        item["title"] = original_title
        item["description"] = original_desc
        return item

    # Tradução de cidade genérica se aplicável
    city = item.get("city")
    if city and city in CITY_LOCALIZATIONS and target in CITY_LOCALIZATIONS[city]:
        item["city"] = CITY_LOCALIZATIONS[city][target]

    # Tradução do tipo de contrato se aplicável
    contract = item.get("contract_type")
    if contract and contract in CONTRACT_LOCALIZATIONS and target in CONTRACT_LOCALIZATIONS[contract]:
        item["contract_type"] = CONTRACT_LOCALIZATIONS[contract][target]

    if original_title:
        translated_title = translate_text(original_title, target)
        item["title"] = translated_title if translated_title else original_title

    if translate_desc and original_desc:
        translated_desc = translate_text(original_desc, target)
        item["description"] = translated_desc if translated_desc else original_desc

    return item


def translate_job_list(job_list: list[dict], target_lang: str) -> list[dict]:
    """
    Traduz em paralelo múltiplos anúncios de forma ultra rápida com ThreadPoolExecutor.
    Traduz títulos e resumos das vagas em paralelo garantindo resposta em sub-segundos.
    """
    target = _clean_lang(target_lang)
    if target == "pt" or not job_list:
        for job in job_list:
            job["original_title"] = job.get("title")
            job["original_description"] = job.get("description")
            job["translated_lang"] = "pt"
        return job_list

    def _worker(job):
        try:
            return translate_job_fields(job, target, translate_desc=True)
        except Exception:
            return job

    with ThreadPoolExecutor(max_workers=10) as executor:
        return list(executor.map(_worker, job_list))
