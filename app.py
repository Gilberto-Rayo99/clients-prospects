"""Streamlit app — Prospector Web (RAIO Development)."""
from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

import config
from core.contact import suggest_contact_channel
from core.enrich import enrich_contact
from core.landing import generate_landing
from core.score import calculate_score
from core.search import search_businesses

config.setup_logging()
logger = logging.getLogger(__name__)


# ============================================================
# Page setup
# ============================================================
st.set_page_config(
    page_title="Prospector Web — RAIO Development",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# State
# ============================================================
if "prospects" not in st.session_state:
    st.session_state["prospects"] = []
if "last_search" not in st.session_state:
    st.session_state["last_search"] = None
if "preview_landing" not in st.session_state:
    st.session_state["preview_landing"] = None  # (name, html)


# ============================================================
# Helpers
# ============================================================
def _process_prospects(prospects: list[dict]) -> list[dict]:
    """Enriquece (email + redes), calcula score y canal, ordena por score."""
    out = []
    for b in prospects:
        b = enrich_contact(b)
        b["score"] = calculate_score(b)
        contact = suggest_contact_channel(b)
        b["contact_channel"] = contact["channel"]
        b["contact_value"] = contact["value"]
        out.append(b)
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


def _find_prospect_index(place_id: str) -> int | None:
    for i, p in enumerate(st.session_state["prospects"]):
        if p.get("place_id") == place_id:
            return i
    return None


CHANNEL_ICON = {
    "email": "📧",
    "whatsapp": "💬",
    "facebook": "📘",
    "visit": "🚶",
}


def _score_color(score: int) -> str:
    if score >= 8:
        return "🟢"
    if score >= 6:
        return "🟡"
    return "🔴"


# ============================================================
# Sidebar
# ============================================================
with st.sidebar:
    st.title("🎯 Prospector Web")
    st.caption(f"**{config.AGENCY_NAME}**")

    if config.USE_MOCK_DATA:
        st.info("🧪 Modo DEMO activo (datos de prueba). Configura las API keys en `.env` y desactiva `USE_MOCK_DATA` para usar datos reales.")

    st.markdown("---")
    st.subheader("Parámetros de búsqueda")

    zone = st.text_input("Zona / colonia", value="Coyoacán, CDMX")
    radius_km = st.slider("Radio (km)", min_value=1, max_value=30, value=5)
    category = st.selectbox("Categoría", config.CATEGORIES, index=0)

    web_filter_label = st.radio(
        "Filtrar por estado de web",
        options=list(config.FILTER_OPTIONS.values()),
        index=0,
    )
    web_filter_key = next(
        k for k, v in config.FILTER_OPTIONS.items() if v == web_filter_label
    )

    st.markdown("---")
    search_btn = st.button("🔍 Buscar prospectos", use_container_width=True, type="primary")
    clear_btn = st.button("🧹 Limpiar resultados", use_container_width=True)


# ============================================================
# Main
# ============================================================
st.title("Prospectos encontrados")

if clear_btn:
    st.session_state["prospects"] = []
    st.session_state["last_search"] = None
    st.session_state["preview_landing"] = None
    st.rerun()

if search_btn:
    with st.spinner("Buscando y enriqueciendo negocios..."):
        try:
            raw = search_businesses(zone, radius_km, category, web_filter_key)
            st.session_state["prospects"] = _process_prospects(raw)
            st.session_state["last_search"] = {
                "zone": zone,
                "radius_km": radius_km,
                "category": category,
                "filter": web_filter_label,
            }
            st.session_state["preview_landing"] = None
        except Exception as e:
            logger.exception("Falló la búsqueda")
            st.error(f"Error al buscar: {e}")

prospects: list[dict] = st.session_state["prospects"]

if not prospects:
    st.info("Configura los parámetros en el sidebar y pulsa **Buscar prospectos** para empezar.")
    st.stop()

# ===== Métricas =====
total = len(prospects)
sin_web = sum(1 for p in prospects if not p.get("website"))
con_email = sum(1 for p in prospects if p.get("email"))
con_landing = sum(1 for p in prospects if p.get("landing_path"))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total encontrados", total)
c2.metric("Sin web", sin_web)
c3.metric("Con email", con_email)
c4.metric("Landings generadas", con_landing)

if st.session_state.get("last_search"):
    s = st.session_state["last_search"]
    st.caption(
        f"Última búsqueda: **{s['category']}** en _{s['zone']}_ "
        f"(radio {s['radius_km']} km, filtro: {s['filter']})"
    )

st.markdown("---")

# ===== Preview de landing (si hay una activa) =====
if st.session_state["preview_landing"]:
    name, html = st.session_state["preview_landing"]
    with st.container(border=True):
        col_t, col_x = st.columns([10, 1])
        with col_t:
            st.markdown(f"### 🌐 Vista previa: **{name}**")
        with col_x:
            if st.button("✕", key="close_preview"):
                st.session_state["preview_landing"] = None
                st.rerun()
        st.components.v1.html(html, height=720, scrolling=True)
    st.markdown("---")

# ===== Tabla =====
rows = []
for p in prospects:
    rows.append({
        "": _score_color(p["score"]),
        "Score": p["score"],
        "Nombre": p["name"],
        "Categoría": p.get("category", ""),
        "⭐": p.get("rating") or "—",
        "Reseñas": p.get("reviews_count") or 0,
        "Web": "❌" if not p.get("website") else "⚠️",
        "Email": "✅" if p.get("email") else "—",
        "Canal": f"{CHANNEL_ICON.get(p['contact_channel'], '?')} {p['contact_channel']}",
        "Landing": "✅" if p.get("landing_path") else "—",
    })

df = pd.DataFrame(rows)
st.dataframe(df, hide_index=True, use_container_width=True)

# ===== Detalle por prospecto =====
st.markdown("### Detalles y acciones")

for i, p in enumerate(prospects):
    with st.expander(f"{_score_color(p['score'])} **{p['name']}** — Score {p['score']}/10"):
        col_l, col_r = st.columns([2, 1])
        with col_l:
            st.markdown(f"**Dirección:** {p.get('address', '—')}")
            st.markdown(f"**Teléfono:** {p.get('phone') or '—'}")
            st.markdown(f"**Web:** {p.get('website') or '_(sin web)_'}")
            st.markdown(f"**Email:** {p.get('email') or '_(no encontrado)_'}")
            if p.get("social_links"):
                links = " · ".join(
                    f"[{k}]({v})" for k, v in p["social_links"].items() if v
                )
                if links:
                    st.markdown(f"**Redes:** {links}")
            st.markdown(f"**Rating:** {p.get('rating') or '—'} ⭐ ({p.get('reviews_count', 0)} reseñas)")
            st.markdown(f"**Canal sugerido:** {CHANNEL_ICON.get(p['contact_channel'], '')} `{p['contact_channel']}` → {p['contact_value']}")
            if p.get("maps_url"):
                st.markdown(f"[📍 Ver en Google Maps]({p['maps_url']})")
            if p.get("landing_path"):
                st.markdown(f"📄 Landing guardada en: `{p['landing_path']}`")

        with col_r:
            place_id = p.get("place_id", f"idx_{i}")
            if st.button("🌐 Generar landing", key=f"land_{place_id}", use_container_width=True):
                with st.spinner(f"Generando landing para {p['name']}..."):
                    try:
                        html, path = generate_landing(p)
                        idx = _find_prospect_index(place_id)
                        if idx is not None:
                            st.session_state["prospects"][idx]["landing_path"] = path
                            st.session_state["prospects"][idx]["landing_html"] = html
                        st.session_state["preview_landing"] = (p["name"], html)
                        st.success("Landing generada")
                        st.rerun()
                    except Exception as e:
                        logger.exception("Falló la generación de landing")
                        st.error(f"Error: {e}")

            if p.get("landing_html") or p.get("landing_path"):
                if st.button("👁️ Ver landing", key=f"view_{place_id}", use_container_width=True):
                    html = p.get("landing_html")
                    if not html and p.get("landing_path"):
                        from pathlib import Path
                        html = Path(p["landing_path"]).read_text(encoding="utf-8")
                    st.session_state["preview_landing"] = (p["name"], html)
                    st.rerun()

            st.button("📄 Generar PDF", key=f"pdf_{place_id}", disabled=True,
                      help="Próxima etapa", use_container_width=True)

st.markdown("---")
st.caption("Etapa 2 — Búsqueda + enrich + landing. Próximamente: exports Excel/PDF.")
