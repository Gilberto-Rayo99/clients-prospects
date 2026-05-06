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
TIMEOUT_SECONDS = 60  # PageSpeed puede tardar 30-50s, sobre todo sitios pesados


def _cache_key(url: str) -> str:
    return f"pagespeed:{url.lower().strip().rstrip('/')}"


def _is_fresh(cached: dict) -> bool:
    ts = cached.get("fetched_at") or 0
    return (time.time() - ts) < CACHE_TTL_DAYS * 86400


def get_score(url: Optional[str], force_refresh: bool = False) -> Optional[dict]:
    """Trae el score de PageSpeed para una URL.

    Returns:
        dict con `mobile_score`, `desktop_score` (0-100), `mobile_lcp`,
        `mobile_fcp` en segundos, `fetched_at` timestamp, `url`. None si no
        se pudo obtener.
    """
    if not url or not url.startswith(("http://", "https://")):
        return None

    cache_key = _cache_key(url)
    if not force_refresh:
        cached = app_kv.get(cache_key)
        if isinstance(cached, dict) and _is_fresh(cached):
            return cached

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
    except requests.HTTPError as e:
        logger.warning("PageSpeed HTTP %s para %s: %s",
                       e.response.status_code if e.response else "?", url, e)
        return None
    except Exception as e:
        logger.warning("PageSpeed falló para %s: %s", url, e)
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
