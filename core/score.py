"""Scoring de oportunidad para cada prospecto (1..10) con breakdown."""
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
    """Detecta web desactualizada por scrape (copyright viejo) o por dominio falso."""
    if business.get("is_outdated_web"):
        return True
    url = business.get("website")
    if not url:
        return False
    return not _is_real_website(url)


def calculate_score_breakdown(business: dict) -> tuple[int, list[tuple[str, int]]]:
    """Calcula el score y devuelve también el desglose explicado.

    Returns:
        (score_final, [(motivo, puntos), ...])
    """
    breakdown: list[tuple[str, int]] = []
    base = 1
    breakdown.append(("Base", base))
    score = base

    # ===== Estado de la web =====
    website = business.get("website")
    if not website:
        score += 4
        breakdown.append(("Sin web en absoluto", 4))
    elif _is_outdated_web(business):
        year = business.get("last_copyright_year")
        if year:
            breakdown.append((f"Web desactualizada (copyright {year})", 2))
        else:
            breakdown.append(("Web desactualizada (Wix/FB/redes)", 2))
        score += 2
    else:
        breakdown.append(("Tiene web propia funcional", 0))

    # ===== Rating =====
    rating = business.get("rating") or 0
    if rating >= 4.5:
        score += 2
        breakdown.append((f"Rating excelente ({rating}★)", 2))
    elif rating >= 4.0:
        score += 1
        breakdown.append((f"Rating bueno ({rating}★)", 1))
    elif rating < 3.5 and rating > 0:
        score -= 1
        breakdown.append((f"Rating bajo ({rating}★)", -1))

    # ===== Volumen de reseñas (proxy de tamaño/ingresos) =====
    reviews = business.get("reviews_count") or 0
    if reviews >= 500:
        score += 2
        breakdown.append((f"Muchísimas reseñas ({reviews})", 2))
    elif reviews >= 200:
        score += 1
        breakdown.append((f"Muchas reseñas ({reviews})", 1))
    elif reviews >= 50:
        score += 1
        breakdown.append((f"Reseñas suficientes ({reviews})", 1))
    elif reviews < 10 and reviews > 0:
        score -= 1
        breakdown.append((f"Pocas reseñas ({reviews}) — recién abierto", -1))

    # ===== Bonus por tier de categoría (ROI de la web) =====
    category = business.get("category") or "Otros"
    tier = config.CATEGORY_TIERS.get(category, "bronze")
    bonus = config.TIER_BONUS.get(tier, 0)
    if bonus != 0:
        label = config.TIER_LABEL.get(tier, tier)
        sign = "+" if bonus > 0 else ""
        breakdown.append((f"Categoría {label}", bonus))
        score += bonus

    # ===== Tiene teléfono (siempre se puede contactar) =====
    if business.get("phone"):
        score += 1
        breakdown.append(("Teléfono disponible", 1))

    # ===== Bonus si ya tenemos email =====
    if business.get("email"):
        score += 1
        breakdown.append(("Email encontrado", 1))

    # Clamp 1..10
    final = max(1, min(10, score))
    if final != score:
        breakdown.append((f"(ajustado a rango 1–10)", final - score))

    return final, breakdown


def calculate_score(business: dict) -> int:
    """Calcula el score 1..10 (versión sin breakdown, para compat)."""
    score, _ = calculate_score_breakdown(business)
    return score


def format_breakdown(breakdown: list[tuple[str, int]]) -> str:
    """Devuelve el breakdown en formato markdown para mostrar en la UI."""
    lines = []
    for label, pts in breakdown:
        if pts > 0:
            sign = f"+{pts}"
            color = "🟢"
        elif pts < 0:
            sign = f"{pts}"
            color = "🔴"
        else:
            sign = "0"
            color = "⚪"
        lines.append(f"- {color} **{label}**: {sign}")
    return "\n".join(lines)
