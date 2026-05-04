"""Streamlit app — Prospector Web (RAIO Development)."""
from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

import config
from core.contact import suggest_contact_channel
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


# ============================================================
# Helpers
# ============================================================
def _enrich_in_place(prospects: list[dict]) -> list[dict]:
    """Agrega score y canal de contacto a cada prospecto."""
    out = []
    for b in prospects:
        b = dict(b)
        b["score"] = calculate_score(b)
        contact = suggest_contact_channel(b)
        b["contact_channel"] = contact["channel"]
        b["contact_value"] = contact["value"]
        out.append(b)
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


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
    st.rerun()

if search_btn:
    with st.spinner("Buscando negocios..."):
        try:
            raw = search_businesses(zone, radius_km, category, web_filter_key)
            st.session_state["prospects"] = _enrich_in_place(raw)
            st.session_state["last_search"] = {
                "zone": zone,
                "radius_km": radius_km,
                "category": category,
                "filter": web_filter_label,
            }
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
        "Web": "❌" if not p.get("website") else "⚠️" if p["score"] >= 6 and p.get("website") else "✅",
        "Canal": f"{CHANNEL_ICON.get(p['contact_channel'], '?')} {p['contact_channel']}",
        "Teléfono": p.get("phone") or "—",
        "Dirección": p.get("address", ""),
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
            st.markdown(f"**Rating:** {p.get('rating') or '—'} ⭐ ({p.get('reviews_count', 0)} reseñas)")
            st.markdown(f"**Canal sugerido:** {CHANNEL_ICON.get(p['contact_channel'], '')} `{p['contact_channel']}` → {p['contact_value']}")
            if p.get("maps_url"):
                st.markdown(f"[📍 Ver en Google Maps]({p['maps_url']})")
        with col_r:
            st.button("🌐 Generar landing", key=f"land_{i}", disabled=True, help="Próxima etapa")
            st.button("📄 Generar PDF", key=f"pdf_{i}", disabled=True, help="Próxima etapa")

st.markdown("---")
st.caption("Etapa 1 — MVP. Próximamente: enriquecimiento de email, landing con Claude y exports Excel/PDF.")
