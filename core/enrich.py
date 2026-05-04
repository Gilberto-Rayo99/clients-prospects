"""Enriquecimiento de datos de contacto: scrape web → Outscraper → Hunter."""
from __future__ import annotations

import html as html_lib
import logging
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import config

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Emails ofuscados: "info [arroba] dominio.com", "info (at) dominio.com",
# "info AT dominio DOT com", etc.
OBFUSCATED_EMAIL_REGEX = re.compile(
    r"([a-zA-Z0-9._%+\-]+)\s*"
    r"(?:\[arroba\]|\(arroba\)|\[at\]|\(at\)|\s+at\s+|\s+arroba\s+|&#64;)"
    r"\s*([a-zA-Z0-9.\-]+)\s*"
    r"(?:\[punto\]|\(punto\)|\[dot\]|\(dot\)|\s+dot\s+|\s+punto\s+|\.)"
    r"\s*([a-zA-Z]{2,})",
    re.IGNORECASE,
)

# Emails escritos como "info AT example DOT com" sin separadores intermedios
SPACED_AT_REGEX = re.compile(
    r"\b([a-zA-Z0-9._%+\-]+)\s+(?:AT|ARROBA)\s+([a-zA-Z0-9.\-]+)\s+(?:DOT|PUNTO)\s+([a-zA-Z]{2,})\b",
    re.IGNORECASE,
)

# WhatsApp en el HTML: wa.me/521555..., api.whatsapp.com/send?phone=...
WHATSAPP_REGEX = re.compile(
    r"(?:wa\.me/|api\.whatsapp\.com/send\?phone=|whatsapp\.com/send/\?phone=)(\+?\d{10,15})",
    re.IGNORECASE,
)

# Copyright "© 2018", "Copyright 2019", "&copy; 2020"
COPYRIGHT_YEAR_REGEX = re.compile(
    r"(?:©|&copy;|copyright|copyrights?|todos\s+los\s+derechos)\s*"
    r"(?:reservados?\s*)?[©&;a-z]*\s*(\d{4})(?:\s*[-–]\s*(\d{4}))?",
    re.IGNORECASE,
)

# Redes sociales
SOCIAL_PATTERNS = {
    "facebook":  re.compile(r"https?://(?:www\.)?(?:facebook|fb)\.com/([a-zA-Z0-9._\-]+)"),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/([a-zA-Z0-9._\-]+)"),
    "twitter":   re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/([a-zA-Z0-9._\-]+)"),
    "tiktok":    re.compile(r"https?://(?:www\.)?tiktok\.com/@([a-zA-Z0-9._\-]+)"),
    "linkedin":  re.compile(r"https?://(?:www\.)?linkedin\.com/(?:in|company)/([a-zA-Z0-9._\-]+)"),
    "youtube":   re.compile(r"https?://(?:www\.)?youtube\.com/(?:c/|channel/|user/|@)([a-zA-Z0-9._\-]+)"),
}

# Emails a ignorar (típicos de plantillas / placeholders / servicios técnicos)
EMAIL_BLACKLIST = (
    # Dominios placeholder
    "example.com", "example.org", "example.net",
    "domain.com", "yourdomain.com", "tudominio.com", "midominio.com",
    "test.com", "tutest.com",
    # Servicios técnicos / hosting / tracking
    "sentry.io", "wixpress.com", "godaddy.com", "namecheap.com",
    "wordpress.com", "automattic.com", "googlemail.com",
    "google-analytics.com", "doubleclick.net", "googletagmanager.com",
    "cloudflare.com", "amazonaws.com", "hubspot.com",
    # Direcciones técnicas
    "no-reply", "noreply", "donotreply",
    "webmaster@", "postmaster@", "abuse@", "hostmaster@",
)

# Locales del email a rechazar (cualquier @cualquier-dominio con estos prefijos)
EMAIL_LOCAL_BLACKLIST = (
    "usuario", "tucorreo", "tu-correo", "tucontacto", "ejemplo",
    "youremail", "your-email", "your_email", "user", "username",
    "email", "correo", "mail", "tunombre", "yourname", "name",
    "ventas-empresa", "info-aqui", "demo", "sample",
)

# Páginas a visitar buscando email/contacto cuando no aparece en home
CONTACT_PATHS = (
    "/", "/contacto", "/contacto.html", "/contact", "/contact-us",
    "/contactanos", "/contáctanos", "/about", "/about-us",
    "/nosotros", "/quienes-somos", "/aviso-de-privacidad",
    "/aviso", "/privacidad", "/legal", "/footer",
)

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
}


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
# Scraping del sitio web del negocio (multi-página + ofuscado)
# ============================================================
def _is_email_valid(email: str) -> bool:
    e = email.strip().lower()
    if any(b in e for b in EMAIL_BLACKLIST):
        return False
    # Filtrar emails con extensiones de imagen (regex puede falsear con paths)
    if e.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico")):
        return False
    # Local part igual a algo placeholder
    local = e.split("@", 1)[0]
    if local in EMAIL_LOCAL_BLACKLIST:
        return False
    # Local part con caracteres raros del regex (algún match falso de URL)
    if local.endswith(("-2x", "-1x", "-x")):
        return False
    return True


def _extract_emails_from_text(text: str) -> list[str]:
    """Saca emails directos + ofuscados del texto. Devuelve lista única."""
    found: list[str] = []

    # 1) Emails directos
    for e in EMAIL_REGEX.findall(text):
        e = e.strip().lower()
        if _is_email_valid(e) and e not in found:
            found.append(e)

    # 2) Ofuscados con [arroba] / (at) / etc.
    for m in OBFUSCATED_EMAIL_REGEX.finditer(text):
        e = f"{m.group(1)}@{m.group(2)}.{m.group(3)}".lower()
        if _is_email_valid(e) and e not in found:
            found.append(e)

    # 3) Espaciados "info AT dominio DOT com"
    for m in SPACED_AT_REGEX.finditer(text):
        e = f"{m.group(1)}@{m.group(2)}.{m.group(3)}".lower()
        if _is_email_valid(e) and e not in found:
            found.append(e)

    return found


def _extract_whatsapp_from_text(text: str) -> str | None:
    m = WHATSAPP_REGEX.search(text)
    if not m:
        return None
    raw = m.group(1).lstrip("+")
    # Quitar prefijo MX si está
    if raw.startswith("521") and len(raw) == 13:
        raw = raw[2:]
    elif raw.startswith("52") and len(raw) == 12:
        raw = raw[2:]
    return raw if len(raw) >= 10 else None


def _extract_socials_from_text(text: str) -> dict[str, str]:
    """Devuelve {plataforma: url} con la primera coincidencia por plataforma."""
    out: dict[str, str] = {}
    for platform, pat in SOCIAL_PATTERNS.items():
        m = pat.search(text)
        if not m:
            continue
        handle = m.group(1).lower()
        # Filtrar handles genéricos que no son del negocio
        if handle in ("share", "sharer", "intent", "tr", "p", "home", "watch"):
            continue
        out[platform] = m.group(0)
    return out


def _extract_latest_copyright_year(text: str) -> int | None:
    """Devuelve el año más alto encontrado en avisos de copyright."""
    years: list[int] = []
    for m in COPYRIGHT_YEAR_REGEX.finditer(text):
        # Si hay rango "2018-2020", quedarse con el segundo
        y2 = m.group(2) or m.group(1)
        try:
            y = int(y2)
            if 2000 <= y <= datetime.now().year + 1:
                years.append(y)
        except (TypeError, ValueError):
            continue
    return max(years) if years else None


def _decode_html_entities(text: str) -> str:
    """Decodifica entidades HTML como &#64; (que es @)."""
    try:
        return html_lib.unescape(text)
    except Exception:
        return text


def _fetch_page(url: str, timeout: int = 6) -> str | None:
    """Hace GET y devuelve el texto HTML, o None si falla."""
    import requests

    try:
        r = requests.get(url, timeout=timeout, headers=REQUEST_HEADERS, allow_redirects=True)
        if r.status_code >= 400:
            return None
        return _decode_html_entities(r.text)
    except Exception as e:
        logger.debug("No pude obtener %s: %s", url, e)
        return None


def _scrape_website(start_url: str, max_pages: int = 4) -> dict:
    """Crawl ligero del sitio del negocio. Devuelve emails, whatsapp, redes, copyright.

    Estrategia:
      1. Visitar la home del sitio.
      2. Visitar hasta N rutas comunes de contacto (/contacto, /about, ...).
      3. Acumular hallazgos.

    Returns:
        {
          "emails": [...],
          "whatsapp": str | None,
          "social_links": {...},
          "last_copyright_year": int | None,
          "is_outdated_web": bool,
          "pages_fetched": int,
        }
    """
    parsed = urlparse(start_url)
    if not parsed.scheme:
        start_url = "https://" + start_url
        parsed = urlparse(start_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    emails: list[str] = []
    whatsapp: str | None = None
    socials: dict[str, str] = {}
    copyright_years: list[int] = []
    pages_fetched = 0
    visited: set[str] = set()

    # Visitar home siempre primero
    candidate_urls = [start_url]
    for path in CONTACT_PATHS:
        u = urljoin(base, path)
        if u not in candidate_urls:
            candidate_urls.append(u)

    for url in candidate_urls:
        if url in visited or pages_fetched >= max_pages:
            continue
        visited.add(url)
        text = _fetch_page(url)
        if not text:
            continue
        pages_fetched += 1

        # Acumular hallazgos
        for e in _extract_emails_from_text(text):
            if e not in emails:
                emails.append(e)
        if not whatsapp:
            whatsapp = _extract_whatsapp_from_text(text)
        for platform, link in _extract_socials_from_text(text).items():
            socials.setdefault(platform, link)
        y = _extract_latest_copyright_year(text)
        if y:
            copyright_years.append(y)

        # Cortar temprano si ya tenemos suficiente
        if emails and whatsapp and socials:
            break

    last_year = max(copyright_years) if copyright_years else None
    current_year = datetime.now().year
    is_outdated = bool(last_year and (current_year - last_year) >= config.OUTDATED_YEAR_THRESHOLD)

    return {
        "emails": emails,
        "whatsapp": whatsapp,
        "social_links": socials,
        "last_copyright_year": last_year,
        "is_outdated_web": is_outdated,
        "pages_fetched": pages_fetched,
    }


def _scrape_emails_from_website(url: str, timeout: int = 6) -> list[str]:
    """Compat: devuelve solo la lista de emails del scrape completo."""
    return _scrape_website(url).get("emails", [])


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
    enriched.setdefault("social_links", {})

    # 1) Scrape multi-página del sitio del negocio (si tiene)
    website = business.get("website")
    scraped: dict = {}
    if website:
        try:
            scraped = _scrape_website(website)
            logger.info(
                "Scrape %s: emails=%d, whatsapp=%s, redes=%s, copyright=%s, páginas=%d",
                website, len(scraped.get("emails", [])),
                bool(scraped.get("whatsapp")),
                list((scraped.get("social_links") or {}).keys()),
                scraped.get("last_copyright_year"),
                scraped.get("pages_fetched", 0),
            )
        except Exception as e:
            logger.warning("Scrape falló para %s: %s", website, e)
            scraped = {}

        # Aplicar hallazgos del scrape
        emails = scraped.get("emails") or []
        if emails:
            enriched["email"] = emails[0]
            enriched["enrich_source"] = "scrape"

        # Mergear redes (sin sobrescribir si Outscraper ya dio algo después)
        for platform, link in (scraped.get("social_links") or {}).items():
            enriched["social_links"].setdefault(platform, link)

        # WhatsApp del HTML: solo si no había teléfono o si es distinto
        wa = scraped.get("whatsapp")
        if wa and not enriched.get("phone"):
            enriched["phone"] = "+52 " + wa
            enriched["phone_source"] = "scrape_whatsapp"

        # Detectar web desactualizada
        if scraped.get("is_outdated_web"):
            enriched["is_outdated_web"] = True
            enriched["last_copyright_year"] = scraped.get("last_copyright_year")

        if enriched.get("email"):
            return enriched

    # 2) Outscraper
    out = _outscraper_lookup(business)
    if out.get("email"):
        enriched["email"] = out["email"]
        for platform, link in (out.get("social_links") or {}).items():
            if link:
                enriched["social_links"].setdefault(platform, link)
        enriched["enrich_source"] = out.get("source", "outscraper")
        return enriched

    # 3) Hunter.io
    hu = _hunter_lookup(business)
    if hu.get("email"):
        enriched["email"] = hu["email"]
        enriched["enrich_source"] = hu.get("source", "hunter")
        return enriched

    # 4) Nada → email queda None pero pueden quedar redes/whatsapp del scrape
    enriched.setdefault("email", None)
    enriched.setdefault("enrich_source", None)
    return enriched
