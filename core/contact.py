"""Determina el canal de contacto óptimo para un prospecto."""
from __future__ import annotations

import logging
import re

import config

logger = logging.getLogger(__name__)


def _clean_phone(phone: str | None) -> str | None:
    """Devuelve el teléfono solo con dígitos, quitando código de país +52."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if digits.startswith(config.COUNTRY_PHONE_PREFIX) and len(digits) > 10:
        digits = digits[len(config.COUNTRY_PHONE_PREFIX):]
    return digits or None


def suggest_contact_channel(business: dict) -> dict:
    """Devuelve {'channel': str, 'value': str} con el mejor canal disponible.

    Prioridad: email > whatsapp > facebook > visit
    """
    email = (business.get("email") or "").strip()
    if email:
        return {"channel": "email", "value": email}

    phone_clean = _clean_phone(business.get("phone"))
    if phone_clean:
        wa_url = f"https://wa.me/{config.COUNTRY_PHONE_PREFIX}{phone_clean}"
        return {"channel": "whatsapp", "value": wa_url}

    socials = business.get("social_links") or {}
    fb = socials.get("facebook")
    if fb:
        return {"channel": "facebook", "value": fb}

    return {"channel": "visit", "value": business.get("address", "")}
