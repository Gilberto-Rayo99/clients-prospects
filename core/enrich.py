"""Enriquecimiento de datos de contacto: scrape web → Outscraper → Hunter."""
from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import config

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Emails a ignorar (típicos de plantillas / placeholders)
EMAIL_BLACKLIST = (
    "example.com", "domain.com", "yourdomain.com", "test.com",
    "sentry.io", "wixpress.com",
)


# ============================================================
# Mock determinista — para desarrollo
# ============================================================
_MOCK_ENRICH_BY_PLACE: dict[str, dict] = {
    "mock_001": {  # Tacos El Compa — sin web → no email
        "email": None,
        "social_links": {"facebook": "https://www.facebook.com/tacoselcompa"},
        "source": "mock",
    },
    "mock_002": {  # Estética Glamour — facebook
        "email": "contacto@esteticaglamour.mx",
        "social_links": {
            "facebook": "https://www.facebook.com/esteticaglamour",
            "instagram": "https://instagram.com/esteticaglamour",
        },
        "source": "mock",
    },
    "mock_003": {  # Taller Don Beto — sin web
        "email": None,
        "social_links": {},
        "source": "mock",
    },
    "mock_004": {  # Café La Esquina — wix
        "email": "hola@cafelaesquina.com",
        "social_links": {"instagram": "https://instagram.com/cafelaesquina"},
        "source": "mock",
    },
    "mock_005": {  # Abarrotes Doña Mary
        "email": None,
        "social_links": {},
        "source": "mock",
    },
    "mock_006": {  # Dental Sonrisa — web real
        "email": "citas@dentalsonrisa.com",
        "social_links": {
            "facebook": "https://www.facebook.com/dentalsonrisa",
            "instagram": "https://instagram.com/dentalsonrisa",
        },
        "source": "mock",
    },
    "mock_007": {  # FuerzaMax
        "email": "info@fuerzamax.mx",
        "social_links": {"instagram": "https://instagram.com/fuerzamax"},
        "source": "mock",
    },
    "mock_008": {  # Veterinaria — blogspot
        "email": None,
        "social_links": {"facebook": "https://www.facebook.com/patitasfelices"},
        "source": "mock",
    },
    "mock_009": {  # Lavandería
        "email": None,
        "social_links": {},
        "source": "mock",
    },
    "mock_010": {  # Florería
        "email": None,
        "social_links": {"instagram": "https://instagram.com/floreriamargaritas"},
        "source": "mock",
    },
    "mock_011": {  # Panadería
        "email": None,
        "social_links": {},
        "source": "mock",
    },
    "mock_012": {  # Barbería — instagram
        "email": "agenda@barberiathedon.mx",
        "social_links": {"instagram": "https://instagram.com/barberiathedon"},
        "source": "mock",
    },
}


# ============================================================
# Scraping del sitio web del negocio
# ============================================================
def _scrape_emails_from_website(url: str, timeout: int = 6) -> list[str]:
    """Hace GET al sitio y extrae emails con regex."""
    import requests

    try:
        r = requests.get(url, timeout=timeout, headers={
            "User-Agent": "Mozilla/5.0 (compatible; ProspectorBot/1.0)",
        })
        r.raise_for_status()
    except Exception as e:
        logger.warning("No pude obtener %s: %s", url, e)
        return []

    found = EMAIL_REGEX.findall(r.text)
    cleaned = []
    for e in found:
        e = e.strip().lower()
        if any(b in e for b in EMAIL_BLACKLIST):
            continue
        if e not in cleaned:
            cleaned.append(e)
    return cleaned


# ============================================================
# Outscraper (real)
# ============================================================
def _outscraper_lookup(business: dict) -> dict:
    """Busca emails y redes sociales con Outscraper. Devuelve {} si falla."""
    if not config.OUTSCRAPER_API_KEY:
        return {}
    try:
        from outscraper import ApiClient
    except ImportError:
        logger.warning("Paquete 'outscraper' no instalado")
        return {}

    try:
        client = ApiClient(api_key=config.OUTSCRAPER_API_KEY)
        domain = _domain_from_url(business.get("website")) or business.get("name", "")
        resp = client.emails_and_contacts([domain])
        if resp and isinstance(resp, list) and resp[0]:
            entry = resp[0]
            emails = entry.get("emails") or []
            socials = entry.get("socials") or {}
            return {
                "email": emails[0] if emails else None,
                "social_links": {
                    "facebook": socials.get("facebook"),
                    "instagram": socials.get("instagram"),
                },
                "source": "outscraper",
            }
    except Exception as e:
        logger.warning("Outscraper falló: %s", e)
    return {}


# ============================================================
# Hunter.io (real)
# ============================================================
def _hunter_lookup(business: dict) -> dict:
    """Domain Search en Hunter.io."""
    if not config.HUNTER_API_KEY:
        return {}
    domain = _domain_from_url(business.get("website"))
    if not domain:
        return {}
    try:
        import requests
        r = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "api_key": config.HUNTER_API_KEY},
            timeout=8,
        )
        r.raise_for_status()
        data = r.json().get("data", {})
        emails = data.get("emails", [])
        if emails:
            return {
                "email": emails[0].get("value"),
                "social_links": {},
                "source": "hunter",
            }
    except Exception as e:
        logger.warning("Hunter.io falló: %s", e)
    return {}


def _domain_from_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(url).netloc.lower().replace("www.", "")
        return host or None
    except Exception:
        return None


# ============================================================
# Punto de entrada
# ============================================================
def enrich_contact(business: dict) -> dict:
    """Devuelve copia del business enriquecido con email + social_links + contact_channel.

    Nunca lanza excepción: si todo falla, devuelve email=None.
    """
    enriched = dict(business)

    # ---------- Modo MOCK ----------
    if config.USE_MOCK_DATA:
        mock = _MOCK_ENRICH_BY_PLACE.get(business.get("place_id"), {})
        enriched["email"] = mock.get("email")
        enriched["social_links"] = mock.get("social_links", {})
        enriched["enrich_source"] = "mock"
        return enriched

    # ---------- Pipeline real ----------
    # 1) Scrape de la web del negocio (si tiene)
    website = business.get("website")
    if website:
        emails = _scrape_emails_from_website(website)
        if emails:
            enriched["email"] = emails[0]
            enriched["social_links"] = enriched.get("social_links", {}) or {}
            enriched["enrich_source"] = "scrape"
            return enriched

    # 2) Outscraper
    out = _outscraper_lookup(business)
    if out.get("email"):
        enriched["email"] = out["email"]
        enriched["social_links"] = out.get("social_links", {}) or {}
        enriched["enrich_source"] = out.get("source", "outscraper")
        return enriched

    # 3) Hunter.io
    hu = _hunter_lookup(business)
    if hu.get("email"):
        enriched["email"] = hu["email"]
        enriched["social_links"] = enriched.get("social_links", {}) or {}
        enriched["enrich_source"] = hu.get("source", "hunter")
        return enriched

    # 4) Nada → solo dejamos email None
    enriched["email"] = None
    enriched["social_links"] = enriched.get("social_links", {}) or {}
    enriched["enrich_source"] = None
    return enriched
