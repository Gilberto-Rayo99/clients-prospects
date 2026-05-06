"""Configuración global del proyecto. Carga .env y expone constantes."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


# ============================================================
# Bootstrap de Streamlit Secrets → os.environ
# ============================================================
# En Streamlit Cloud, las keys del panel "Secrets" viven en `st.secrets` pero
# NO siempre se inyectan automáticamente a `os.environ` antes de que este
# módulo lea los valores con `os.getenv`. Soportamos:
#   - flat:           GEMINI_API_KEY = "abc"
#   - nested:         [secrets]\n  GEMINI_API_KEY = "abc"
# Iteramos un nivel de anidación por si el usuario puso una sección.
_SECRETS_LOADED: dict[str, str] = {}


def _hydrate_env_from_streamlit_secrets() -> None:
    try:
        import streamlit as st  # type: ignore
    except Exception:
        return
    try:
        for k in list(st.secrets.keys()):
            v = st.secrets[k]
            if isinstance(v, (str, int, float, bool)):
                _SECRETS_LOADED[k] = str(v)
                if not os.environ.get(k):
                    os.environ[k] = str(v)
            else:
                # Posible sección anidada (Mapping). Intentar iterar sus keys.
                try:
                    for sk in list(v.keys()):
                        sv = v[sk]
                        if isinstance(sv, (str, int, float, bool)):
                            _SECRETS_LOADED[sk] = str(sv)
                            if not os.environ.get(sk):
                                os.environ[sk] = str(sv)
                except Exception:
                    pass
    except Exception:
        pass


_hydrate_env_from_streamlit_secrets()


def _secret(name: str, default: str = "") -> str:
    """Lee un secret con prioridad: os.environ → st.secrets (flat o nested).

    Robusto contra el caso en que `st.secrets` no estuvo disponible al cargar
    config (la rehidratación de arriba quedó vacía). Cada llamada vuelve a
    intentarlo, así que un acceso tardío sí ve los secrets.
    """
    v = os.environ.get(name, "").strip()
    if v:
        return v
    if name in _SECRETS_LOADED:
        return _SECRETS_LOADED[name].strip()
    # Reintento en caliente por si st.secrets aparece después
    try:
        import streamlit as st  # type: ignore

        try:
            sv = st.secrets[name]
            if isinstance(sv, (str, int, float, bool)):
                return str(sv).strip()
        except Exception:
            pass
        # nested
        try:
            for k in list(st.secrets.keys()):
                section = st.secrets[k]
                try:
                    sv = section[name]
                    if isinstance(sv, (str, int, float, bool)):
                        return str(sv).strip()
                except Exception:
                    continue
        except Exception:
            pass
    except Exception:
        pass
    return default


def secrets_diagnostic() -> dict:
    """Devuelve qué keys está viendo el config — útil para debug en UI."""
    info = {
        "loaded_from_secrets": sorted(_SECRETS_LOADED.keys()),
        "env_has_gemini": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
        "gemini_via_secret_fn": bool(_secret("GEMINI_API_KEY")),
    }
    try:
        import streamlit as st  # type: ignore

        info["st_secrets_top_keys"] = sorted(list(st.secrets.keys()))
    except Exception as e:
        info["st_secrets_top_keys"] = f"<unavailable: {e}>"
    return info


# ===== Paths =====
BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / "outputs"
LANDINGS_DIR = OUTPUTS_DIR / "landings"
EXCEL_DIR = OUTPUTS_DIR / "excel"
PDF_DIR = OUTPUTS_DIR / "pdf"

for _d in (LANDINGS_DIR, EXCEL_DIR, PDF_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ===== API Keys =====
GOOGLE_PLACES_API_KEY = _secret("GOOGLE_PLACES_API_KEY")
OUTSCRAPER_API_KEY = _secret("OUTSCRAPER_API_KEY")
HUNTER_API_KEY = _secret("HUNTER_API_KEY")
GEMINI_API_KEY = _secret("GEMINI_API_KEY")
PAGESPEED_API_KEY = _secret("PAGESPEED_API_KEY")  # opcional, sube cuota a 25k/día
NETLIFY_API_TOKEN = _secret("NETLIFY_API_TOKEN")
APP_PASSWORD = _secret("APP_PASSWORD")

# ===== Supabase =====
SUPABASE_URL = _secret("SUPABASE_URL")
SUPABASE_ANON_KEY = _secret("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = _secret("SUPABASE_SERVICE_KEY")

# ===== Agencia =====
AGENCY_NAME = os.getenv("AGENCY_NAME", "RAIO Development")
AGENCY_PHONE = os.getenv("AGENCY_PHONE", "")
AGENCY_EMAIL = os.getenv("AGENCY_EMAIL", "")
AGENCY_WEBSITE = os.getenv("AGENCY_WEBSITE", "")

# ===== Modo mock =====
USE_MOCK_DATA = os.getenv("USE_MOCK_DATA", "true").lower() in ("true", "1", "yes")

# ===== Gemini Image (Nano Banana) =====
GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"
GEMINI_DAILY_BUDGET = 95           # margen sobre el límite gratuito de 100/día
GEMINI_IMAGES_PER_LANDING = 8      # 1 hero + 4 servicio + 3 galería

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
        "Hola, buenos dias! Soy {tu_nombre} de {agencia}.\n\n"
        "Vi el negocio *{nombre}* en Google Maps, tienen {rating} estrellas con {reviews} "
        "resenas. Muy buen trabajo, felicidades.\n\n"
        "Note que aun no tienen pagina web propia. Les prepare una demo GRATIS de como "
        "podria verse su negocio en internet:\n\n"
        "{landing_url}\n\n"
        "La inversion arranca en *$3,000 pesos*, el precio final depende de lo que "
        "necesiten (secciones extra, dominio propio, correo profesional, etc.).\n\n"
        "Si les gusta la demo platicamos sin compromiso. Que les parece?"
    ),
    "inicial_web_desactualizada": (
        "Hola, buenos dias! Soy {tu_nombre} de {agencia}.\n\n"
        "Vi *{nombre}* en Maps con {rating} estrellas y {reviews} resenas. "
        "Vi su sitio actual y creo que se puede modernizar bastante para que "
        "les traiga mas clientes.\n\n"
        "Les prepare una propuesta visual GRATIS de como quedaria renovado:\n\n"
        "{landing_url}\n\n"
        "La inversion arranca en *$3,000 pesos* y sube segun los extras que "
        "necesiten. Sin compromiso, si les late platicamos."
    ),
    "inicial_pagespeed_critico": (
        "Hola, buenos dias! Soy {tu_nombre} de {agencia}.\n\n"
        "Vi *{nombre}* en Maps con {rating} estrellas y {reviews} resenas. "
        "Reviso su sitio web y note algo importante:\n\n"
        "{pagespeed_pitch}\n\n"
        "Les prepare una version GRATIS de como podria verse renovado y rapido:\n\n"
        "{landing_url}\n\n"
        "La inversion arranca en *$3,000 pesos*. Sin compromiso, si les late "
        "platicamos como subir esos numeros y atraer mas clientes desde Google."
    ),
    "follow_up_sin_respuesta": (
        "Hola! Les escribi hace unos dias sobre la propuesta de pagina web para *{nombre}*.\n\n"
        "Se que tienen mucho trabajo. Si tienen 5 minutos con gusto les explico como "
        "funciona y cuanto cobraria exactamente.\n\n"
        "Sin compromiso. Saludos, {tu_nombre} - {agencia}"
    ),
    "post_llamada_propuesta": (
        "Hola! Gracias por la llamada.\n\n"
        "Como acordamos les envio la cotizacion formal con todos los detalles. "
        "Cualquier duda me dicen y ajustamos lo que sea.\n\n"
        "Saludos, {tu_nombre} - {agencia}"
    ),
    "agradecimiento_visita": (
        "Hola! Gracias por recibirme hoy.\n\n"
        "Les dejo el link de la demo que vimos en persona, por si quieren mostrarsela "
        "a alguien mas del equipo:\n\n"
        "{landing_url}\n\n"
        "Cualquier cosa estoy al pendiente. Saludos, {tu_nombre} - {agencia}"
    ),
}

WHATSAPP_TEMPLATE_LABELS = {
    "inicial_sin_web":              "🆕 Inicial — negocio sin web",
    "inicial_web_desactualizada":   "🆕 Inicial — web desactualizada",
    "inicial_pagespeed_critico":    "⚡ Inicial — web lenta (PageSpeed)",
    "follow_up_sin_respuesta":      "🔁 Follow-up sin respuesta",
    "post_llamada_propuesta":       "📋 Post-llamada con cotización",
    "agradecimiento_visita":        "🤝 Agradecimiento de visita",
}

# ============================================================
# Pipeline de seguimiento (estados detallados)
# ============================================================
PIPELINE_STAGES = [
    ("Pendiente",          "⚪", 0),
    ("Falta landing",      "🖼", 1),
    ("Mensaje listo",      "📲", 2),
    ("Mensaje enviado",    "📤", 3),
    ("Respondió",          "💬", 4),
    ("Llamada/visita",     "📞", 5),
    ("Propuesta enviada",  "📋", 6),
    ("Negociación",        "🤝", 7),
    ("Cerrado",            "✅", 8),
    ("Sin teléfono",       "📵", -1),
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
    return bool(_secret(name))
