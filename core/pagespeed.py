"""PageSpeed Insights — score real de Google para webs de prospectos.

Free tier: 25,000 queries/día con API key (sin tarjeta de crédito requerida).
Sin key funciona con cuota muy reducida — suficiente para uso ocasional.

Uso típico:
    data = get_score("https://example.com")  # cacheado 30 días
    # → {"mobile_score": 23, "desktop_score": 65, "mobile_lcp": 4.2, ...}

    pitch = sales_pitch(data)
    # → "Tu web saca 23/100 en velocidad móvil…"
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import requests

import config
from core import app_kv

logger = logging.getLogger(__name__)

API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
CACHE_TTL_DAYS = 30
FAILURE_CACHE_TTL_SECONDS = 3600  # 1h — evita spam si la API está caída/deshabilitada
TIMEOUT_SECONDS = 60  # PageSpeed puede tardar 30-50s, sobre todo sitios pesados


def _cache_key(url: str) -> str:
    return f"pagespeed:{url.lower().strip().rstrip('/')}"


def _is_fresh(cached: dict) -> bool:
    ts = cached.get("fetched_at") or 0
    ttl = (FAILURE_CACHE_TTL_SECONDS if cached.get("failed")
           else CACHE_TTL_DAYS * 86400)
    return (time.time() - ts) < ttl


def _interpret_error(e: Exception) -> str:
    """Mensaje human-friendly según el código HTTP."""
    if isinstance(e, requests.HTTPError) and e.response is not None:
        code = e.response.status_code
        if code == 403:
            return ("403 Forbidden — la API no está habilitada en tu proyecto. "
                    "Habilítala en https://console.cloud.google.com/apis/library/"
                    "pagespeedonline.googleapis.com (botón Enable).")
        if code == 400:
            return "400 Bad Request — la URL puede ser inválida o no accesible públicamente."
        if code == 429:
            return "429 Too Many Requests — superaste el límite por minuto. Espera 60s."
        return f"HTTP {code}"
    return str(e)[:200]


def get_score(
    url: Optional[str],
    force_refresh: bool = False,
    read_only: bool = False,
) -> Optional[dict]:
    """Trae el score de PageSpeed para una URL.

    Args:
        url: URL del sitio.
        force_refresh: si True, ignora cache y vuelve a llamar.
        read_only: si True, NUNCA llama al API. Solo devuelve cache si existe.
            Úsalo en caminos de render (mensajes WhatsApp, listas, etc.) donde
            no queremos disparar llamadas costosas en cada rerun.

    Returns:
        dict con scores, o None si no hay datos. Si la última llamada falló
        y el fallo está en cache (TTL 1h), también devuelve None — no reintentamos.
    """
    if not url or not url.startswith(("http://", "https://")):
        return None

    cache_key = _cache_key(url)
    if not force_refresh:
        cached = app_kv.get(cache_key)
        if isinstance(cached, dict) and _is_fresh(cached):
            # Si el cache es de un fallo, no devolvemos datos pero tampoco reintentamos
            if cached.get("failed"):
                return None
            return cached

    if read_only:
        # No hay cache válido y nos pidieron no llamar al API
        return None

    result: dict = {"url": url, "fetched_at": int(time.time())}
    try:
        for strategy in ("mobile", "desktop"):
            params = {
                "url": url,
                "strategy": strategy,
                "category": "performance",
            }
            if config.PAGESPEED_API_KEY:
                params["key"] = config.PAGESPEED_API_KEY
            r = requests.get(API_URL, params=params, timeout=TIMEOUT_SECONDS)
            r.raise_for_status()
            data = r.json()
            lh = data.get("lighthouseResult", {})
            cats = lh.get("categories", {})
            audits = lh.get("audits", {})

            perf = cats.get("performance", {}).get("score")
            result[f"{strategy}_score"] = int(round(perf * 100)) if perf is not None else None

            # FCP / LCP en segundos (vienen en ms)
            for metric_audit, key in (("first-contentful-paint", "fcp"),
                                       ("largest-contentful-paint", "lcp")):
                v = audits.get(metric_audit, {}).get("numericValue")
                if v is not None:
                    result[f"{strategy}_{key}"] = round(v / 1000.0, 1)

        app_kv.set(cache_key, result)
        return result
    except Exception as e:
        msg = _interpret_error(e)
        logger.warning("PageSpeed falló para %s: %s", url, msg)
        # Cachear el fallo brevemente para no spamear el API en cada rerun
        app_kv.set(cache_key, {
            "url": url,
            "fetched_at": int(time.time()),
            "failed": True,
            "error": msg,
        })
        return None


def last_error_for(url: Optional[str]) -> Optional[str]:
    """Devuelve el mensaje de error de la última llamada (si hubo) para una URL."""
    if not url:
        return None
    cached = app_kv.get(_cache_key(url))
    if isinstance(cached, dict) and cached.get("failed"):
        return cached.get("error")
    return None


def severity_label(mobile_score: Optional[int]) -> str:
    if mobile_score is None:
        return "—"
    if mobile_score < 50:
        return "🔴 crítico"
    if mobile_score < 80:
        return "🟡 mejorable"
    return "🟢 bueno"


def sales_pitch(score_data: Optional[dict]) -> Optional[str]:
    """Devuelve una frase de venta basada en el score, o None si no aplica
    (sin datos o score bueno → no vale la pena mencionarlo)."""
    if not score_data:
        return None
    m = score_data.get("mobile_score")
    if m is None:
        return None
    if m < 50:
        return (
            f"Tu sitio actual saca *{m}/100* en velocidad móvil según Google "
            "(PageSpeed Insights). Eso afecta directamente tu posición en "
            "búsquedas locales y la tasa de personas que se quedan a comprar."
        )
    if m < 80:
        return (
            f"Tu sitio saca {m}/100 en velocidad móvil de Google. Mejorable "
            "para subir conversión y SEO local."
        )
    return None
