"""Configuración global del proyecto. Carga .env y expone constantes."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ===== Paths =====
BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / "outputs"
LANDINGS_DIR = OUTPUTS_DIR / "landings"
EXCEL_DIR = OUTPUTS_DIR / "excel"
PDF_DIR = OUTPUTS_DIR / "pdf"

for _d in (LANDINGS_DIR, EXCEL_DIR, PDF_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ===== API Keys =====
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
OUTSCRAPER_API_KEY = os.getenv("OUTSCRAPER_API_KEY", "").strip()
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()

# ===== Agencia =====
AGENCY_NAME = os.getenv("AGENCY_NAME", "RAIO Development")
AGENCY_PHONE = os.getenv("AGENCY_PHONE", "")
AGENCY_EMAIL = os.getenv("AGENCY_EMAIL", "")
AGENCY_WEBSITE = os.getenv("AGENCY_WEBSITE", "")

# ===== Modo mock =====
USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "true").lower() in ("true", "1", "yes")

# ===== Modelo Claude =====
CLAUDE_MODEL = "claude-sonnet-4-5"

# ===== Constantes UI / negocio =====
COUNTRY_PHONE_PREFIX = "52"  # México

CATEGORIES = [
    "Restaurantes",
    "Cafeterías",
    "Estéticas y barberías",
    "Talleres mecánicos",
    "Tiendas de abarrotes",
    "Consultorios dentales",
    "Gimnasios",
    "Veterinarias",
    "Lavanderías",
    "Florerías",
    "Panaderías",
    "Otros",
]

FILTER_OPTIONS = {
    "no_web": "Sin página web",
    "outdated": "Web desactualizada",
    "all": "Todos",
}

DOMAINS_NOT_REAL_WEB = (
    "facebook.com",
    "fb.com",
    "instagram.com",
    "wix.com",
    "wixsite.com",
    "blogspot.com",
    "blogger.com",
    "wordpress.com",
    "google.com",
    "linktr.ee",
)

OUTDATED_YEAR_THRESHOLD = 3  # años desde último copyright

STATUS_OPTIONS = ["Pendiente", "Contactado", "Propuesta enviada", "Cerrado"]


# ===== Logging =====
def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def has_key(name: str) -> bool:
    """Devuelve True si la API key dada está configurada (no vacía)."""
    return bool(os.getenv(name, "").strip())
