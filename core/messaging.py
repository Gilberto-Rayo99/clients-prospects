"""Genera mensajes de WhatsApp/email a partir de plantillas."""
from __future__ import annotations

import logging
import re
from urllib.parse import quote

import config

logger = logging.getLogger(__name__)


def _short_address(address: str | None) -> str:
    """Primera parte de la dirección, sin código postal ni 'Ciudad de México'."""
    if not address:
        return ""
    parts = address.split(",")
    return parts[0].strip() if parts else address


def _clean_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if digits.startswith(config.COUNTRY_PHONE_PREFIX) and len(digits) > 10:
        digits = digits[len(config.COUNTRY_PHONE_PREFIX):]
    return digits or None


def render_message(template_key: str, client: dict, landing_url: str = "") -> str:
    """Rellena la plantilla con datos del cliente.

    Args:
        template_key: clave de WHATSAPP_TEMPLATES
        client: registro del cliente
        landing_url: URL pública (Netlify) — si está vacía, deja un placeholder
    """
    template = config.WHATSAPP_TEMPLATES.get(template_key)
    if not template:
        return ""

    landing_text = landing_url.strip() if landing_url.strip() else "[PEGAR_LINK_NETLIFY_AQUÍ]"

    return template.format(
        nombre=client.get("name", ""),
        categoria=client.get("category", ""),
        rating=client.get("rating") or "—",
        reviews=client.get("reviews_count", 0),
        agencia=config.AGENCY_NAME,
        tu_nombre=config.YOUR_NAME,
        direccion_corta=_short_address(client.get("address")),
        landing_url=landing_text,
    )


def whatsapp_url(client: dict, message: str) -> str | None:
    """Genera URL wa.me con mensaje pre-cargado (URL-encoded).

    Devuelve None si el cliente no tiene teléfono.
    """
    phone = _clean_phone(client.get("phone"))
    if not phone:
        return None
    encoded = quote(message)
    return f"https://wa.me/{config.COUNTRY_PHONE_PREFIX}{phone}?text={encoded}"
