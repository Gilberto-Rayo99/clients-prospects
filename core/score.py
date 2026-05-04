"""Scoring de oportunidad para cada prospecto (1..10)."""
from __future__ import annotations

import logging
from urllib.parse import urlparse

import config

logger = logging.getLogger(__name__)


def _is_real_website(url: str | None) -> bool:
    if not url:
        return False
    try:
        host = urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return False
    if not host:
        return False
    return not any(host.endswith(d) for d in config.DOMAINS_NOT_REAL_WEB)


def _is_outdated_web(business: dict) -> bool:
    """Heurística de web desactualizada.

    Tres caminos:
      1. El scraper detectó copyright viejo (`is_outdated_web=True`).
      2. El "sitio" es realmente una landing Wix/Blogspot/Facebook/etc.
      3. (default) no es desactualizada.
    """
    if business.get("is_outdated_web"):
        return True
    url = business.get("website")
    if not url:
        return False
    return not _is_real_website(url)


def calculate_score(business: dict) -> int:
    """Calcula score de oportunidad 1..10 según criterios del CLAUDE.md."""
    score = 1
    website = business.get("website")

    if not website:
        score += 4
    elif _is_outdated_web(business):
        score += 2

    rating = business.get("rating") or 0
    if rating >= 4.0:
        score += 2

    if (business.get("reviews_count") or 0) > 20:
        score += 1

    if business.get("phone"):
        score += 1

    return max(1, min(10, score))
