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


def _pagespeed_pitch_for(client: dict) -> str:
    """Si el cliente tiene web y PageSpeed cacheado, devuelve la frase de venta.
    NUNCA llama al API desde aquí (read_only=True) — esta función la invocan
    los reruns de Streamlit en cada render, así que un API call sería desastre."""
    url = client.get("website")
    if not url:
        return "[sin web — esta plantilla aplica solo a negocios con sitio]"
    try:
        from core import pagespeed
        data = pagespeed.get_score(url, read_only=True)
        pitch = pagespeed.sales_pitch(data)
        if pitch:
            return pitch
    except Exception as e:
        logger.debug("pagespeed pitch falló: %s", e)
    return "[corre PageSpeed primero desde la sección Datos del cliente]"


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
        pagespeed_pitch=_pagespeed_pitch_for(client),
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
