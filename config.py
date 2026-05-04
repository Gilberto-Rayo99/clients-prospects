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
    "Inmobiliarias",
    "Otros",
]

# Tier de categorías por rentabilidad como prospecto (ROI de la web).
# - gold: ticket alto, cliente potencial paga $5-15k por landing fácil
# - silver: ticket medio-alto, vendible con buen pitch
# - bronze: ticket medio, urgencia menor
# - low: ticket bajo, web justifica menos su costo
CATEGORY_TIERS: dict[str, str] = {
    "Consultorios dentales":  "gold",
    "Veterinarias":           "gold",
    "Inmobiliarias":          "gold",
    "Estéticas y barberías":  "silver",
    "Talleres mecánicos":     "silver",
    "Gimnasios":              "silver",
    "Restaurantes":           "bronze",
    "Cafeterías":             "bronze",
    "Florerías":              "bronze",
    "Panaderías":             "bronze",
    "Tiendas de abarrotes":   "low",
    "Lavanderías":            "low",
    "Otros":                  "bronze",
}

TIER_BONUS: dict[str, int] = {
    "gold":   2,
    "silver": 1,
    "bronze": 0,
    "low":   -1,
}

TIER_LABEL: dict[str, str] = {
    "gold":   "🥇 Top",
    "silver": "🥈 Bueno",
    "bronze": "🥉 Medio",
    "low":    "⛔ Bajo",
}

# Presets del filtro inteligente
SMART_FILTERS = {
    "all":       "Todos",
    "top":       "🎯 Top prospects (recomendado)",
    "premium":   "💰 Alta cotización (sólo gold/silver)",
    "urgent":    "🔥 Urgentes (web fea o sin web)",
}

# ============================================================
# Plantillas de mensajes WhatsApp / email
# ============================================================
# Variables disponibles que se sustituyen automáticamente:
#   {nombre}           — nombre del negocio
#   {categoria}        — categoría
#   {rating}           — rating (4.6)
#   {reviews}          — número de reseñas
#   {agencia}          — config.AGENCY_NAME
#   {tu_nombre}        — config.YOUR_NAME (defínelo en .env)
#   {direccion_corta}  — primera parte de la dirección
#   {landing_url}      — placeholder para que pegues el link Netlify (PEGAR DESPUÉS)

WHATSAPP_TEMPLATES = {
    "inicial_sin_web": (
        "Hola {nombre} 👋\n\n"
        "Soy {tu_nombre} de {agencia}. Vi su negocio en Google Maps y me llamó la atención "
        "que tienen {rating}★ con {reviews} reseñas — están haciendo un excelente trabajo.\n\n"
        "Noté que aún no tienen una página web propia. Le hice una propuesta visual GRATIS "
        "para que vea cómo se vería {nombre} con web profesional 👇\n\n"
        "{landing_url}\n\n"
        "Si le gusta, podemos platicar del costo. Si no, queda como ejemplo.\n"
        "¿Qué le parece?"
    ),
    "inicial_web_desactualizada": (
        "Hola {nombre} 👋\n\n"
        "Soy {tu_nombre} de {agencia}. Vi su negocio en Maps con {rating}★ y {reviews} reseñas. "
        "Echo un ojo a su sitio actual y noté que se podría modernizar bastante.\n\n"
        "Le hice una propuesta visual GRATIS de cómo se vería renovado 👇\n\n"
        "{landing_url}\n\n"
        "Si le interesa platicar del costo, ¡bienvenido! Si no, le queda el ejemplo."
    ),
    "follow_up_sin_respuesta": (
        "Hola {nombre}, le escribí hace unos días sobre la propuesta de página web 🙂\n\n"
        "Sé que tiene mucho trabajo. ¿Le late que platiquemos 5 min para resolver dudas? "
        "Sin compromiso.\n\n"
        "{tu_nombre} — {agencia}"
    ),
    "post_llamada_propuesta": (
        "Hola {nombre}, gracias por la llamada 👋\n\n"
        "Como acordamos, le adjunto la cotización formal en PDF. Cualquier duda me dice y "
        "ajustamos.\n\n"
        "Saludos,\n{tu_nombre} — {agencia}"
    ),
    "agradecimiento_visita": (
        "Hola {nombre}, gracias por recibirme hoy 🙏\n\n"
        "Le dejo aquí el link de la demo que vio en persona, por si quiere mostrársela a "
        "su equipo:\n\n"
        "{landing_url}\n\n"
        "Cualquier cosa estoy al pendiente.\n{tu_nombre} — {agencia}"
    ),
}

WHATSAPP_TEMPLATE_LABELS = {
    "inicial_sin_web":              "🆕 Inicial — negocio sin web",
    "inicial_web_desactualizada":   "🆕 Inicial — web desactualizada",
    "follow_up_sin_respuesta":      "🔁 Follow-up sin respuesta",
    "post_llamada_propuesta":       "📋 Post-llamada con cotización",
    "agradecimiento_visita":        "🤝 Agradecimiento de visita",
}

# ============================================================
# Pipeline de seguimiento (estados detallados)
# ============================================================
PIPELINE_STAGES = [
    ("Pendiente",          "⚪", 0),
    ("Mensaje enviado",    "📤", 1),
    ("Respondió",          "💬", 2),
    ("Llamada/visita",     "📞", 3),
    ("Propuesta enviada",  "📋", 4),
    ("Negociación",        "🤝", 5),
    ("Cerrado",            "✅", 6),
    ("Descartado",         "❌", -1),
]

PIPELINE_STAGE_NAMES = [s[0] for s in PIPELINE_STAGES]


# ============================================================
# Datos del usuario (consultor / dueño de la agencia)
# ============================================================
import os as _os
YOUR_NAME = _os.getenv("YOUR_NAME", "Gilberto Rayo")

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
