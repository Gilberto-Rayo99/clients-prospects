"""Streamlit app — Prospector Web (RAIO Development)."""
from __future__ import annotations

import io
import logging
import re
import zipfile
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path

import streamlit as st

import config
from core import clients_store
from core.contact import suggest_contact_channel
from core.enrich import enrich_contact
from core.html_validator import validate_html
from core.landing import generate_landing
from core.landing_prompt import build_landing_prompt, build_short_summary
from core.messaging import render_message, whatsapp_url
from core.score import calculate_score, calculate_score_breakdown, format_breakdown
from core.search import search_businesses
from export.excel import export_to_excel
from export.pdf_proposal import generate_pdf_proposal

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
# Login gate
# ============================================================
_APP_PASSWORD = config.APP_PASSWORD

if _APP_PASSWORD:
    import secrets as _secrets

    st.session_state.setdefault("authenticated", False)

    if not st.session_state["authenticated"]:
        st.set_page_config(page_title="Prospector Web — Acceso", page_icon="🔒", layout="centered")
        st.markdown("## 🔒 Prospector Web")
        pwd = st.text_input("Contraseña", type="password", placeholder="Ingresa la contraseña...")
        if st.button("Entrar", type="primary", use_container_width=True):
            # compare_digest evita timing attacks (compara siempre todos los bytes)
            if _secrets.compare_digest(pwd or "", _APP_PASSWORD):
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta.")
        st.stop()


# ============================================================
# State
# ============================================================
st.session_state.setdefault("prospects", [])
st.session_state.setdefault("last_search", None)
st.session_state.setdefault("preview_landing", None)
st.session_state.setdefault("editing_client_id", None)
st.session_state.setdefault("_clients_cache", None)


# ============================================================
# Helpers
# ============================================================
def _save_landing_and_optionally_publish(client_id: str, html: str, auto_publish: bool) -> None:
    """Guarda la landing y, si `auto_publish`, la sube a Netlify de un golpe.

    Diseñado para reducir el flujo manual: subir HTML → guardar → ir a tab
    Automation → publicar. Ahora todo en un click si NETLIFY_API_TOKEN existe.
    """
    cli = clients_store.save_landing_html(client_id, html)
    if not cli:
        st.error("No pude guardar la landing.")
        return

    if not auto_publish:
        st.success("Landing guardada.")
        return

    if not config.NETLIFY_API_TOKEN:
        st.warning("Landing guardada (sin Netlify token configurado, no se publicó).")
        return

    try:
        from core import netlify as _netlify
        with st.spinner("Publicando en Netlify..."):
            res = _netlify.publish_html(html, cli.get("name", ""), site_id=cli.get("netlify_site_id"))
        clients_store.update(
            client_id,
            netlify_url=res["url"],
            netlify_site_id=res["site_id"],
            netlify_deploy_at=datetime.now().isoformat(timespec="seconds"),
        )
        st.success(f"✅ Guardada y publicada: {res['url']}")
    except Exception as e:
        logger.exception("Auto-publish Netlify falló")
        st.warning(f"Landing guardada, pero falló Netlify: {e}")


def _process_prospects(prospects: list[dict]) -> list[dict]:
    """Enriquece + scorea prospectos en paralelo.

    El cuello de botella es `enrich_contact` (HTTP a webs + APIs externas):
    I/O-bound, así que un ThreadPool acelera mucho. 8 workers es seguro:
    los APIs externos lo soportan y el GIL no estorba en I/O.
    """
    import concurrent.futures

    if not prospects:
        return []

    def _enrich_one(b: dict) -> dict:
        try:
            b = enrich_contact(b)
        except Exception:
            logger.exception("enrich_contact falló para %s", b.get("name"))
        try:
            score, breakdown = calculate_score_breakdown(b)
            b["score"] = score
            b["score_breakdown"] = breakdown
        except Exception:
            logger.exception("score falló para %s", b.get("name"))
            b.setdefault("score", 0)
            b.setdefault("score_breakdown", {})
        try:
            contact = suggest_contact_channel(b)
            b["contact_channel"] = contact["channel"]
            b["contact_value"] = contact["value"]
        except Exception:
            logger.exception("contact falló para %s", b.get("name"))
        return b

    workers = min(8, max(1, len(prospects)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        # map preserva el orden de entrada (no importa, ordenamos al final)
        out = list(pool.map(_enrich_one, prospects))

    out.sort(key=lambda x: x.get("score", 0), reverse=True)
    return out


def _apply_smart_filter(prospects: list[dict], smart_filter: str) -> list[dict]:
    """Aplica el preset del filtro inteligente."""
    if smart_filter == "all":
        return prospects
    if smart_filter == "top":
        return [
            p for p in prospects
            if config.CATEGORY_TIERS.get(p.get("category", "Otros")) in ("gold", "silver")
            and (p.get("score") or 0) >= 7
            and (p.get("rating") or 0) >= 4.0
        ]
    if smart_filter == "premium":
        return [
            p for p in prospects
            if config.CATEGORY_TIERS.get(p.get("category", "Otros")) in ("gold", "silver")
        ]
    if smart_filter == "urgent":
        return [
            p for p in prospects
            if not p.get("website") or p.get("is_outdated_web")
            or (p.get("website") and config.CATEGORY_TIERS.get(p.get("category", "Otros")) != "low")
            and not _looks_like_real_modern_web(p)
        ]
    return prospects


def _looks_like_real_modern_web(p: dict) -> bool:
    """Heurística: web propia y no marcada como desactualizada."""
    url = p.get("website")
    if not url:
        return False
    if p.get("is_outdated_web"):
        return False
    bad = ("facebook.com", "instagram.com", "wix.com", "blogspot.com")
    return not any(b in url.lower() for b in bad)


CHANNEL_ICON = {
    "email": "📧",
    "whatsapp": "💬",
    "facebook": "📘",
    "visit": "🚶",
}

STATUS_BADGE = {
    "Pendiente": "⚪",
    "Contactado": "🔵",
    "Propuesta enviada": "🟡",
    "Negociación": "🟠",
    "Cerrado": "🟢",
    "Descartado": "⚫",
}


def _score_color(score: int | None) -> str:
    if not score:
        return "⚪"
    if score >= 8:
        return "🟢"
    if score >= 6:
        return "🟡"
    return "🔴"


def _refresh():
    st.session_state["_clients_cache"] = None
    st.rerun()


def _clients() -> list[dict]:
    """Devuelve clientes desde caché en session_state. Solo llama a Supabase una vez por sesión."""
    if st.session_state["_clients_cache"] is None:
        st.session_state["_clients_cache"] = clients_store.list_all()
    return st.session_state["_clients_cache"]


def _saved_place_ids() -> set:
    return {c.get("place_id") for c in _clients() if c.get("place_id")}


def _fuzzy_match_client(filename: str, clients: list[dict]) -> tuple[dict | None, float]:
    """Encuentra el cliente cuyo nombre es más parecido al nombre del archivo HTML."""
    stem = re.sub(r"\.(html?|htm)$", "", filename, flags=re.IGNORECASE)
    stem = re.sub(r"[^a-z0-9]+", " ", stem.lower()).strip()

    best_client: dict | None = None
    best_score = 0.0
    for c in clients:
        cname = re.sub(r"[^a-z0-9]+", " ", c.get("name", "").lower()).strip()
        score = SequenceMatcher(None, stem, cname).ratio()
        if score > best_score:
            best_score = score
            best_client = c

    return (best_client, best_score) if best_score >= 0.35 else (None, 0.0)


@st.dialog("Mensaje enviado")
def _dialog_enviado(client_id: str, name: str) -> None:
    """Popup de confirmación al marcar mensaje como enviado."""
    st.success(f"Mensaje marcado como enviado para **{name}**.")
    st.markdown(
        "El estado cambio a **Mensaje enviado**.\n\n"
        "Recuerda anotar cualquier detalle importante en las *Notas* del cliente."
    )
    if st.button("Cerrar", type="primary", use_container_width=True):
        clients_store.update(client_id, estado="Mensaje enviado")
        st.rerun()


# ============================================================
# Sidebar
# ============================================================
with st.sidebar:
    st.title("🎯 Prospector Web")
    st.caption(f"**{config.AGENCY_NAME}**")
    n_clients = len(_clients())
    st.metric("👥 Clientes guardados", n_clients)

    if config.USE_MOCK_DATA:
        st.info("🧪 Modo DEMO. Configura las API keys en `.env` y `USE_MOCK_DATA=false` para datos reales.")

    st.markdown("---")
    st.subheader("Búsqueda")

    zone = st.text_input("Zona / colonia", value="Coyoacán, CDMX")
    radius_km = st.slider("Radio (km)", 1, 30, 5)

    # Filtro inteligente arriba (preset)
    smart_filter_label = st.radio(
        "🎯 Filtro inteligente",
        options=list(config.SMART_FILTERS.values()),
        index=1,  # Top prospects por defecto
        help=(
            "**Top prospects**: solo categorías rentables (gold/silver) "
            "con score ≥7 y rating ≥4.0\n\n"
            "**Alta cotización**: solo categorías gold + silver "
            "(consultorios, veterinarias, inmobiliarias, estéticas, gimnasios…)\n\n"
            "**Urgentes**: negocios con web fea o sin web — venta más rápida"
        ),
    )
    smart_filter_key = next(
        k for k, v in config.SMART_FILTERS.items() if v == smart_filter_label
    )

    # Categoría: lista normal + opción "todas las gold/silver"
    cat_options = config.CATEGORIES.copy()
    if smart_filter_key in ("top", "premium"):
        # Mostrar tier al lado de cada categoría
        cat_options = [
            f"{c}  {config.TIER_LABEL.get(config.CATEGORY_TIERS.get(c, 'bronze'), '')}"
            for c in config.CATEGORIES
        ]
        cat_options.insert(0, "— Todas las recomendadas —")
        cat_label = st.selectbox("Categoría", cat_options)
        if cat_label.startswith("—"):
            category = None  # se interpreta como "todas las del tier"
        else:
            # quitar el sufijo de tier
            category = cat_label.split("  ")[0]
    else:
        category = st.selectbox("Categoría", config.CATEGORIES)

    web_filter_label = st.radio(
        "Filtro web",
        options=list(config.FILTER_OPTIONS.values()),
        index=0,
    )
    web_filter_key = next(
        k for k, v in config.FILTER_OPTIONS.items() if v == web_filter_label
    )

    search_btn = st.button("🔍 Buscar prospectos", use_container_width=True, type="primary")
    clear_btn = st.button("🧹 Limpiar resultados", use_container_width=True)


# ============================================================
# Acciones globales
# ============================================================
if clear_btn:
    st.session_state["prospects"] = []
    st.session_state["last_search"] = None
    st.session_state["preview_landing"] = None
    _refresh()

if search_btn:
    with st.spinner("Buscando y enriqueciendo negocios..."):
        try:
            # Si category es None → buscar en todas las categorías recomendadas
            if category is None:
                target_cats = [
                    c for c in config.CATEGORIES
                    if config.CATEGORY_TIERS.get(c) in ("gold", "silver")
                ]
                raw = []
                seen_ids = set()
                for cat in target_cats:
                    results = search_businesses(zone, radius_km, cat, web_filter_key)
                    for r in results:
                        pid = r.get("place_id")
                        if pid and pid not in seen_ids:
                            seen_ids.add(pid)
                            raw.append(r)
                cat_label_for_state = "Todas las recomendadas"
            else:
                raw = search_businesses(zone, radius_km, category, web_filter_key)
                cat_label_for_state = category

            processed = _process_prospects(raw)
            total_raw = len(processed)
            processed = _apply_smart_filter(processed, smart_filter_key)
            if total_raw > 0 and len(processed) == 0:
                st.warning(
                    f"Se encontraron **{total_raw} negocios** pero el filtro "
                    f"**{smart_filter_label}** los eliminó todos (probable causa: todos "
                    f"tienen página web o score bajo). Cambia el filtro a **'Todos'** en "
                    f"el sidebar y busca de nuevo."
                )
            st.session_state["prospects"] = processed
            st.session_state["last_search"] = {
                "zone": zone, "radius_km": radius_km,
                "category": cat_label_for_state, "filter": web_filter_label,
                "smart": smart_filter_label,
            }
            st.session_state["preview_landing"] = None
        except Exception as e:
            logger.exception("Falló la búsqueda")
            st.error(f"Error al buscar: {e}")


# ============================================================
# TABS
# ============================================================
tab_search, tab_clients, tab_export, tab_automation, tab_help = st.tabs([
    "🔍 Buscar prospectos",
    f"👥 Mis clientes ({n_clients})",
    "📤 Exportar",
    "🚀 Automatización",
    "❓ Ayuda",
])


# ============================================================
# TAB 1 — BUSCAR
# ============================================================
with tab_search:
    prospects: list[dict] = st.session_state["prospects"]

    if not prospects:
        st.info("Configura los parámetros en el sidebar y pulsa **Buscar prospectos** para empezar.")
    else:
        total = len(prospects)
        sin_web = sum(1 for p in prospects if not p.get("website"))
        con_email = sum(1 for p in prospects if p.get("email"))
        ya_guardados = sum(1 for p in prospects if p.get("place_id") in _saved_place_ids())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", total)
        c2.metric("Sin web", sin_web)
        c3.metric("Con email", con_email)
        c4.metric("Ya guardados", ya_guardados)

        if st.session_state.get("last_search"):
            s = st.session_state["last_search"]
            st.caption(f"Última búsqueda: **{s['category']}** en _{s['zone']}_ "
                       f"({s['radius_km']} km, {s['filter']})")

        st.markdown("---")

        # ===== Filtros locales (afectan tabla + detalles) =====
        with st.container(border=True):
            st.markdown("**🔎 Filtrar resultados**")
            f1, f2, f3 = st.columns([2, 1, 1])
            with f1:
                search_text = st.text_input(
                    "Buscar por nombre o categoría",
                    value="",
                    key="local_search",
                    placeholder="taquería, dental, etc.",
                )
            with f2:
                min_score = st.slider("Score mínimo", 1, 10, 1, key="local_min_score")
            with f3:
                hide_saved = st.checkbox(
                    "Ocultar guardados",
                    value=False,
                    key="local_hide_saved",
                )
            f4, f5, f6 = st.columns(3)
            with f4:
                only_with_email = st.checkbox("Solo con email", key="local_email")
            with f5:
                only_with_phone = st.checkbox("Solo con teléfono", key="local_phone")
            with f6:
                only_no_web = st.checkbox("Solo sin web", key="local_no_web")

        # Aplicar filtros locales
        def _matches(p: dict) -> bool:
            if min_score and (p.get("score") or 0) < min_score:
                return False
            if hide_saved and p.get("place_id") in _saved_place_ids():
                return False
            if only_with_email and not p.get("email"):
                return False
            if only_with_phone and not p.get("phone"):
                return False
            if only_no_web and p.get("website"):
                return False
            if search_text:
                q = search_text.lower().strip()
                hay = " ".join([
                    p.get("name", ""), p.get("category", ""),
                    p.get("address", ""),
                ]).lower()
                if q not in hay:
                    return False
            return True

        filtered_prospects = [p for p in prospects if _matches(p)]
        if len(filtered_prospects) != len(prospects):
            st.caption(f"Mostrando **{len(filtered_prospects)}** de {len(prospects)} prospectos")

        if not filtered_prospects:
            st.warning("Ningún prospecto coincide con los filtros. Ajusta los criterios arriba.")
        else:
            # Tabla
            rows = []
            for p in filtered_prospects:
                saved = p.get("place_id") in _saved_place_ids()
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
                    "Guardado": "✅" if saved else "—",
                })
            st.dataframe(rows, hide_index=True, use_container_width=True)

            # ===== Guardado en lote =====
            _saved = _saved_place_ids()
            no_guardados = [
                p for p in filtered_prospects
                if p.get("place_id") not in _saved
            ]
            if no_guardados:
                with st.container(border=True):
                    st.markdown(f"**📥 Guardar en lote** _(de los {len(no_guardados)} no guardados)_")

                    # Filtro por canal de contacto
                    _canal_opts = {
                        "📲 WhatsApp": "whatsapp",
                        "📧 Email": "email",
                        "🚶 Visita": "visit",
                    }
                    _canales_sel = st.multiselect(
                        "Filtrar por canal de contacto",
                        options=list(_canal_opts.keys()),
                        default=list(_canal_opts.keys()),
                        key="bulk_canal_filter",
                        help="Selecciona uno o varios canales para filtrar qué prospectos guardar.",
                    )
                    _canales_val = {_canal_opts[k] for k in _canales_sel}
                    no_guardados = [
                        p for p in no_guardados
                        if p.get("contact_channel", "whatsapp") in _canales_val
                    ] if _canales_val else no_guardados

                    bl_col1, bl_col2, bl_col3 = st.columns(3)

                    # Botón 1: todos los visibles no guardados
                    with bl_col1:
                        if st.button(
                            f"💾 Todos los visibles ({len(no_guardados)})",
                            key="bulk_all_visible",
                            use_container_width=True,
                            type="primary",
                        ):
                            count = 0
                            for p in no_guardados:
                                clients_store.save_from_business(p)
                                count += 1
                            st.toast(f"✅ {count} clientes guardados")
                            _refresh()

                    # Botón 2: solo gold + silver (top tier)
                    top_tier = [
                        p for p in no_guardados
                        if config.CATEGORY_TIERS.get(p.get("category", "Otros"))
                        in ("gold", "silver")
                    ]
                    with bl_col2:
                        if st.button(
                            f"🥇 Solo Top tier ({len(top_tier)})",
                            key="bulk_top_tier",
                            use_container_width=True,
                            disabled=not top_tier,
                        ):
                            for p in top_tier:
                                clients_store.save_from_business(p)
                            st.toast(f"✅ {len(top_tier)} clientes top guardados")
                            _refresh()

                    # Botón 3: solo sin web
                    no_web = [p for p in no_guardados if not p.get("website")]
                    with bl_col3:
                        if st.button(
                            f"🌐 Solo sin web ({len(no_web)})",
                            key="bulk_no_web",
                            use_container_width=True,
                            disabled=not no_web,
                        ):
                            for p in no_web:
                                clients_store.save_from_business(p)
                            st.toast(f"✅ {len(no_web)} sin web guardados")
                            _refresh()

                    # Botón 4: por score mínimo (slider + botón)
                    bl_col4, bl_col5 = st.columns([2, 1])
                    with bl_col4:
                        bulk_score = st.slider(
                            "Score mínimo para guardar",
                            min_value=1, max_value=10, value=8,
                            key="bulk_min_score",
                        )
                    with bl_col5:
                        by_score = [
                            p for p in no_guardados
                            if (p.get("score") or 0) >= bulk_score
                        ]
                        st.write("")  # alinear vertical
                        if st.button(
                            f"🎯 Score ≥ {bulk_score} ({len(by_score)})",
                            key="bulk_by_score",
                            use_container_width=True,
                            disabled=not by_score,
                        ):
                            for p in by_score:
                                clients_store.save_from_business(p)
                            st.toast(f"✅ {len(by_score)} con score ≥ {bulk_score} guardados")
                            _refresh()

            st.markdown("### Detalles")
            iter_prospects = filtered_prospects

        # Si está vacío salimos sin renderizar detalles
        if not filtered_prospects:
            iter_prospects = []

        for i, p in enumerate(iter_prospects):
            saved = p.get("place_id") in _saved_place_ids()
            place_id_top = p.get("place_id", f"idx_{i}")
            badge = " · ✅ guardado" if saved else ""

            # ===== Acciones rápidas (sin abrir el expander) =====
            qa_l, qa_r = st.columns([4, 1])
            with qa_l:
                st.markdown(
                    f"{_score_color(p['score'])} **{p['name']}** — "
                    f"Score {p['score']}/10 · {p.get('category', '')}{badge}"
                )
            with qa_r:
                if saved:
                    if st.button("📂 Abrir cliente", key=f"qopen_{place_id_top}",
                                 use_container_width=True):
                        existing = next(
                            (c for c in _clients()
                             if c.get("place_id") == p.get("place_id")),
                            None,
                        )
                        if existing:
                            st.session_state["editing_client_id"] = existing["id"]
                            st.toast("Abriendo en Mis clientes")
                            _refresh()
                else:
                    if st.button("💾 Guardar", key=f"qsave_{place_id_top}",
                                 type="primary", use_container_width=True):
                        cli = clients_store.save_from_business(p)
                        st.session_state["editing_client_id"] = cli["id"]
                        st.toast(f"✅ {cli['name']} guardado")
                        _refresh()

            with st.expander(f"Ver detalles · {p['name']}"):
                col_l, col_r = st.columns([2, 1])
                with col_l:
                    st.markdown(f"**Dirección:** {p.get('address', '—')}")
                    st.markdown(f"**Teléfono:** {p.get('phone') or '—'}")
                    st.markdown(f"**Web:** {p.get('website') or '_(sin web)_'}")
                    st.markdown(f"**Email:** {p.get('email') or '_(no encontrado)_'}")
                    if p.get("social_links"):
                        links = " · ".join(f"[{k}]({v})" for k, v in p["social_links"].items() if v)
                        if links:
                            st.markdown(f"**Redes:** {links}")
                    st.markdown(f"**Rating:** {p.get('rating') or '—'} ⭐ ({p.get('reviews_count', 0)} reseñas)")
                    cat_tier = config.CATEGORY_TIERS.get(p.get("category", "Otros"), "bronze")
                    st.markdown(f"**Categoría:** {p.get('category')} {config.TIER_LABEL.get(cat_tier, '')}")
                    st.markdown(f"**Canal sugerido:** {CHANNEL_ICON.get(p['contact_channel'], '')} `{p['contact_channel']}` → {p['contact_value']}")
                    if p.get("maps_url"):
                        st.markdown(f"[📍 Ver en Google Maps]({p['maps_url']})")

                    # Breakdown del score
                    if p.get("score_breakdown"):
                        with st.expander(f"🧮 Cómo se calculó el score ({p['score']}/10)"):
                            st.markdown(format_breakdown(p["score_breakdown"]))

                with col_r:
                    place_id = p.get("place_id", f"idx_{i}")
                    if saved:
                        st.success("Ya está en tus clientes guardados.")
                        if st.button("📂 Abrir en 'Mis clientes'", key=f"open_{place_id}", use_container_width=True):
                            existing = next(
                                (c for c in _clients() if c.get("place_id") == p.get("place_id")),
                                None,
                            )
                            if existing:
                                st.session_state["editing_client_id"] = existing["id"]
                                st.toast("Abriendo en pestaña Mis clientes")
                                _refresh()
                    else:
                        if st.button("💾 Guardar como cliente", key=f"save_{place_id}",
                                     type="primary", use_container_width=True):
                            cli = clients_store.save_from_business(p)
                            st.session_state["editing_client_id"] = cli["id"]
                            st.success(f"✅ Guardado: {cli['name']}")
                            _refresh()


# ============================================================
# TAB 2 — MIS CLIENTES
# ============================================================
with tab_clients:
    all_clients = _clients()

    if not all_clients:
        st.info("Aún no has guardado clientes. Ve a la pestaña **🔍 Buscar prospectos** y guarda los que te interesen.")
    else:
        # ---- 🔔 Banner de follow-ups pendientes ----
        from core import followups as _followups
        _pending_fu = _followups.get_pending(all_clients)
        if _pending_fu:
            _counts = _followups.summary_counts(_pending_fu)
            _icon = "🔥" if _counts["urgentes"] + _counts["rezagados"] > 0 else "🔔"
            with st.expander(
                f"{_icon} **{_counts['total']} cliente(s) necesitan follow-up** — "
                f"📅 {_counts['agendados']} agendados · "
                f"⏰ {_counts['urgentes']} urgentes · "
                f"🐢 {_counts['rezagados']} rezagados",
                expanded=(_counts["agendados"] > 0 or _counts["rezagados"] > 0),
            ):
                st.caption(
                    "Click en *Abrir* para saltar al cliente y mandar el follow-up. "
                    "La plantilla sugerida ya viene seleccionada según el motivo."
                )
                for fu in _pending_fu[:15]:
                    _prio_icon = {1: "📅", 2: "⏰", 3: "🐢"}.get(fu["priority"], "•")
                    _cols = st.columns([1, 4, 3, 1])
                    _cols[0].write(_prio_icon)
                    _cols[1].markdown(f"**{fu['name']}** _(estado: {fu.get('estado', 'Pendiente')})_")
                    _cols[2].caption(fu["reason"])
                    if _cols[3].button("Abrir", key=f"fu_open_{fu['id']}"):
                        st.session_state["editing_client_id"] = fu["id"]
                        # Si la plantilla existe, dejarla pre-seleccionada
                        if fu.get("template"):
                            st.session_state[f"tpl_{fu['id']}"] = config.WHATSAPP_TEMPLATE_LABELS.get(
                                fu["template"], None
                            )
                        st.rerun()
                if len(_pending_fu) > 15:
                    st.caption(f"… y {len(_pending_fu) - 15} más. Filtra por estado abajo para verlos.")
            st.markdown("---")

        # ---- Filtros ----
        f1, f2, f3 = st.columns([2, 2, 1])
        with f1:
            filter_estado = st.multiselect(
                "Estado",
                options=clients_store.CLIENT_STATUSES,
                default=[],
                placeholder="Todos",
            )
        with f2:
            filter_score = st.slider("Score mínimo", 1, 10, 1)
        with f3:
            order_by = st.selectbox("Ordenar", ["Score ↓", "Más recientes", "Nombre"])

        filtered = list(all_clients)
        if filter_estado:
            filtered = [c for c in filtered if c.get("estado") in filter_estado]
        filtered = [c for c in filtered if (c.get("score") or 0) >= filter_score]

        if order_by == "Score ↓":
            filtered.sort(key=lambda c: c.get("score") or 0, reverse=True)
        elif order_by == "Más recientes":
            filtered.sort(key=lambda c: c.get("fecha_modificado") or "", reverse=True)
        else:
            filtered.sort(key=lambda c: (c.get("name") or "").lower())

        st.caption(f"Mostrando **{len(filtered)}** de {len(all_clients)} clientes")
        st.markdown("---")

        # ---- Selector de cliente ----
        if filtered:
            options = {
                f"{_score_color(c.get('score'))} {STATUS_BADGE.get(c.get('estado'), '')} {c['name']} — {c.get('category', '')}": c["id"]
                for c in filtered
            }
            current_id = st.session_state.get("editing_client_id")
            current_label = next((k for k, v in options.items() if v == current_id), None)
            label = st.selectbox(
                "Selecciona un cliente para editar",
                options=list(options.keys()),
                index=list(options.keys()).index(current_label) if current_label in options else 0,
                key="client_selector",
            )
            sel_id = options[label]
            st.session_state["editing_client_id"] = sel_id

            cli = clients_store.get(sel_id)
            if cli:
                st.markdown("---")

                # ===== Header del cliente =====
                col_h1, col_h2 = st.columns([3, 1])
                with col_h1:
                    st.markdown(f"## {cli['name']}")
                    st.caption(f"{cli.get('category', '')} · {cli.get('address', '')}")
                with col_h2:
                    if st.button("🗑️ Eliminar cliente", key=f"del_{sel_id}", use_container_width=True):
                        clients_store.delete(sel_id)
                        st.session_state["editing_client_id"] = None
                        st.toast("Cliente eliminado")
                        _refresh()

                # ===== Grid: datos + seguimiento =====
                col_left, col_right = st.columns(2)

                with col_left:
                    st.markdown("### 📋 Datos del negocio")
                    st.markdown(f"**📞 Teléfono:** {cli.get('phone') or '—'}")
                    st.markdown(f"**✉️ Email:** {cli.get('email') or '—'}")
                    st.markdown(f"**🌐 Web actual:** {cli.get('website') or '_(sin web)_'}")
                    st.markdown(f"**⭐ Rating:** {cli.get('rating') or '—'} ({cli.get('reviews_count', 0)} reseñas)")
                    st.markdown(f"**📊 Score:** {cli.get('score', '—')}/10")
                    st.markdown(f"**📡 Canal sugerido:** {CHANNEL_ICON.get(cli.get('contact_channel', ''), '')} `{cli.get('contact_channel')}` → {cli.get('contact_value')}")
                    if cli.get("maps_url"):
                        st.markdown(f"[📍 Google Maps]({cli['maps_url']})")
                    if cli.get("social_links"):
                        links = " · ".join(f"[{k}]({v})" for k, v in cli["social_links"].items() if v)
                        if links:
                            st.markdown(f"**Redes:** {links}")

                    # ===== ⚡ PageSpeed Insights =====
                    if cli.get("website"):
                        from core import pagespeed as _ps
                        _ps_data = _ps.get_score(cli["website"])  # cacheado 30d
                        st.markdown("**⚡ PageSpeed Google:**")
                        if _ps_data:
                            _m, _d = _ps_data.get("mobile_score"), _ps_data.get("desktop_score")
                            _lcp = _ps_data.get("mobile_lcp")
                            st.markdown(
                                f"- 📱 Móvil: **{_m}/100** {_ps.severity_label(_m)}"
                                + (f" · LCP {_lcp}s" if _lcp else "")
                            )
                            st.markdown(
                                f"- 💻 Desktop: **{_d}/100** {_ps.severity_label(_d)}"
                            )
                            if _m is not None and _m < 80:
                                st.caption(
                                    "💡 Tip: usa la plantilla `⚡ Inicial — web lenta (PageSpeed)` "
                                    "para mencionarlo en el WhatsApp."
                                )
                        else:
                            st.caption("_(no analizado todavía)_")
                        if st.button(
                            "🔄 Analizar con PageSpeed (~30s)",
                            key=f"ps_refresh_{sel_id}",
                            help="Llama a PageSpeed Insights de Google. Cache 30 días.",
                        ):
                            with st.spinner("Consultando PageSpeed Insights..."):
                                _new = _ps.get_score(cli["website"], force_refresh=True)
                                if _new:
                                    st.success(f"Listo · móvil {_new.get('mobile_score')}/100")
                                else:
                                    st.error("PageSpeed no devolvió datos. Intenta más tarde.")
                                _refresh()

                with col_right:
                    st.markdown("### 📌 Seguimiento")
                    _current_estado = cli.get("estado", "Pendiente")
                    _estado_options = clients_store.CLIENT_STATUSES
                    _estado_idx = (
                        _estado_options.index(_current_estado)
                        if _current_estado in _estado_options else 0
                    )
                    new_estado = st.selectbox(
                        "Estado",
                        options=_estado_options,
                        index=_estado_idx,
                        key=f"estado_{sel_id}",
                    )
                    next_default = None
                    if cli.get("fecha_proximo_contacto"):
                        try:
                            next_default = date.fromisoformat(cli["fecha_proximo_contacto"])
                        except Exception:
                            next_default = None
                    new_proxima = st.date_input(
                        "Próximo contacto",
                        value=next_default,
                        key=f"prox_{sel_id}",
                        format="YYYY-MM-DD",
                    )
                    new_precio = st.number_input(
                        "Precio cotizado (MXN)",
                        min_value=0.0,
                        value=float(cli.get("precio_cotizado") or 0.0),
                        step=500.0,
                        key=f"precio_{sel_id}",
                    )
                    new_notas = st.text_area(
                        "Notas",
                        value=cli.get("notas") or "",
                        height=120,
                        key=f"notas_{sel_id}",
                    )
                    if st.button("💾 Guardar cambios", key=f"savechg_{sel_id}",
                                 type="primary", use_container_width=True):
                        clients_store.update(
                            sel_id,
                            estado=new_estado,
                            fecha_proximo_contacto=new_proxima.isoformat() if new_proxima else None,
                            precio_cotizado=new_precio if new_precio > 0 else None,
                            notas=new_notas,
                        )
                        st.success("Cambios guardados")
                        _refresh()

                # ===== Pipeline visual =====
                st.markdown("---")
                st.markdown("### 📊 Pipeline")
                stage_idx = next(
                    (i for i, (name, _, _) in enumerate(config.PIPELINE_STAGES)
                     if name == cli.get("estado", "Pendiente")),
                    0,
                )
                # Si está descartado, no mostrar barra
                stage_meta = config.PIPELINE_STAGES[stage_idx]
                if stage_meta[2] < 0:
                    st.error(f"❌ Cliente descartado")
                else:
                    progress_stages = [s for s in config.PIPELINE_STAGES if s[2] >= 0]
                    progress_pct = stage_meta[2] / max(1, max(s[2] for s in progress_stages))
                    st.progress(progress_pct)
                    cols = st.columns(len(progress_stages))
                    for i, (name, icon, idx) in enumerate(progress_stages):
                        with cols[i]:
                            mark = "✅" if idx <= stage_meta[2] else "⚪"
                            st.caption(f"{mark} {icon} {name}")

                # ===== Mensajes WhatsApp =====
                st.markdown("---")
                st.markdown("### 💬 Mensaje WhatsApp")

                phone_clean = cli.get("phone")
                if not phone_clean:
                    st.warning("Este cliente no tiene teléfono — no se puede mandar WhatsApp.")
                else:
                    col_t1, col_t2 = st.columns([2, 1])
                    with col_t1:
                        # Sugerir plantilla por defecto según estado del cliente
                        if cli.get("estado") in ("Mensaje enviado",) and not cli.get("respondio"):
                            default_tpl = "follow_up_sin_respuesta"
                        elif cli.get("website"):
                            # Si tenemos PageSpeed crítico cacheado, prioriza esa plantilla
                            try:
                                from core import pagespeed as _ps_tpl
                                _ps_tpl_data = _ps_tpl.get_score(cli["website"])
                                if _ps_tpl_data and (_ps_tpl_data.get("mobile_score") or 100) < 50:
                                    default_tpl = "inicial_pagespeed_critico"
                                else:
                                    default_tpl = "inicial_web_desactualizada"
                            except Exception:
                                default_tpl = "inicial_web_desactualizada"
                        else:
                            default_tpl = "inicial_sin_web"

                        tpl_keys = list(config.WHATSAPP_TEMPLATES.keys())
                        tpl_labels = [config.WHATSAPP_TEMPLATE_LABELS[k] for k in tpl_keys]
                        idx = tpl_keys.index(default_tpl) if default_tpl in tpl_keys else 0
                        tpl_label = st.selectbox(
                            "Plantilla",
                            options=tpl_labels,
                            index=idx,
                            key=f"tpl_{sel_id}",
                        )
                        tpl_key = tpl_keys[tpl_labels.index(tpl_label)]
                    with col_t2:
                        landing_url_input = st.text_input(
                            "URL Netlify",
                            value=cli.get("netlify_url") or "",
                            placeholder="https://xxx.netlify.app",
                            key=f"netlify_{sel_id}",
                            help="Se rellena automáticamente si ya publicaste en Netlify. También puedes pegarlo manualmente.",
                        )

                    rendered = render_message(tpl_key, cli, landing_url_input)
                    # NOTA: sin `key=` a propósito — si lo ponemos, Streamlit
                    # cachea el valor en session_state y no se refresca cuando
                    # cambias plantilla o URL Netlify.
                    st.text_area(
                        "Mensaje generado (cópialo manualmente o usa el botón de WhatsApp)",
                        value=rendered,
                        height=220,
                    )

                    col_wa1, col_wa2 = st.columns(2)
                    with col_wa1:
                        wa_url = whatsapp_url(cli, rendered)
                        if wa_url:
                            st.link_button(
                                "📲 Abrir WhatsApp con mensaje",
                                wa_url,
                                use_container_width=True,
                                type="primary",
                            )
                    with col_wa2:
                        if st.button("✅ Marcar como enviado", key=f"sent_{sel_id}",
                                     use_container_width=True):
                            _dialog_enviado(sel_id, cli.get("name", ""))

                # ===== Landing =====
                st.markdown("---")
                st.markdown("### 🎨 Landing del cliente")

                tab_prompt, tab_html, tab_preview, tab_auto = st.tabs([
                    "📋 Prompt para Claude",
                    "📥 Cargar HTML",
                    "👁️ Vista previa",
                    "⚡ Generar automático (mock)",
                ])

                with tab_prompt:
                    st.caption(
                        "Dos formas de generar la landing en claude.ai:\n\n"
                        "**🅰️ Rápida (sin imágenes a medida):** copia el prompt de abajo, "
                        "pégalo en claude.ai, copia el HTML que te devuelva, súbelo "
                        "en la pestaña **📥 Cargar HTML**. Las imágenes serán de Unsplash.\n\n"
                        "**🅱️ Premium (con imágenes generadas):** descarga el paquete `.zip` "
                        "(prompt + imágenes hechas a medida con Gemini Nano Banana). "
                        "Descomprímelo, sube todos los archivos a claude.ai en un chat, "
                        "y el HTML que te dé usará esas fotos reales del giro."
                    )

                    # ===== 🅱️ Paquete con imágenes Gemini =====
                    st.markdown("##### 🅱️ Paquete premium (prompt + imágenes Gemini)")
                    pkg_state_key = f"landing_pkg_{sel_id}"

                    if not config.GEMINI_API_KEY:
                        st.info(
                            "ℹ️ Sin `GEMINI_API_KEY`. El paquete se genera con prompt+Unsplash "
                            "(sin imágenes a medida). Para fotos generadas necesitas key + "
                            "**paid tier** en https://aistudio.google.com/ → Settings → Plan. "
                            "Costo: ~$0.039 USD/img × 8 imgs = ~$0.31 USD por paquete."
                        )
                    # Si ya hay un error reciente de cuota, mostrarlo
                    from core import images as _img_mod_indiv
                    _last_err_indiv = _img_mod_indiv.last_error()
                    if _last_err_indiv and "cuota" in _last_err_indiv.lower():
                        st.error(f"⚠️ {_last_err_indiv}")

                    # Botón "Generar" SIEMPRE visible (incluso sin key — devolverá zip
                    # sin imágenes pero con el prompt v2). Layout en stack (no columnas)
                    # para que el download nunca se corte ni se esconda.
                    if st.button(
                        "📦 Generar paquete (~1-2 min con Gemini, instantáneo sin)",
                        key=f"genpkg_{sel_id}",
                        type="primary",
                        use_container_width=True,
                    ):
                        with st.spinner("Generando imágenes con Gemini y empaquetando..."):
                            try:
                                from core.landing import export_landing_package
                                zip_bytes, meta = export_landing_package(cli)
                                st.session_state[pkg_state_key] = {
                                    "bytes": zip_bytes,
                                    "meta": meta,
                                }
                                if meta["images_generated"]:
                                    st.success(
                                        f"✅ {meta['images_generated']} imágenes generadas. "
                                        f"Quedan **{meta['remaining_today']}** hoy."
                                    )
                                else:
                                    st.info(
                                        "ℹ️ Sin imágenes Gemini. El zip incluye el prompt "
                                        "con instrucciones de Unsplash."
                                    )
                            except Exception as e:
                                logger.exception("Falló export_landing_package")
                                st.error(f"Error: {e}")

                    # Botón de descarga: SIEMPRE renderizado en su propia fila
                    pkg = st.session_state.get(pkg_state_key)
                    if pkg and pkg.get("bytes"):
                        st.download_button(
                            f"⬇️ Descargar zip ({len(pkg['bytes']) // 1024} KB)",
                            data=pkg["bytes"],
                            file_name=f"{pkg['meta']['slug']}_landing_package.zip",
                            mime="application/zip",
                            key=f"dlpkg_{sel_id}",
                            use_container_width=True,
                        )
                        st.caption(
                            f"📦 {pkg['meta'].get('images_generated', 0)} imágenes · "
                            f"slug `{pkg['meta'].get('slug')}`"
                        )
                    else:
                        st.caption("ℹ️ Click en **Generar paquete** primero — el botón de descarga aparecerá aquí.")

                    st.markdown("---")

                    # ===== 🅰️ Prompt rápido (texto plano) =====
                    st.markdown("##### 🅰️ Prompt rápido (Unsplash)")
                    prompt_text = build_landing_prompt(cli)
                    # Sin `key=` a propósito — si la ponemos, Streamlit cachea el valor
                    # inicial y no se refresca cuando el cliente cambia (nombre, datos…).
                    st.text_area("Prompt", value=prompt_text, height=380)
                    st.caption(f"💡 Longitud: **{len(prompt_text):,}** caracteres · Cliente: **{cli['name']}**")
                    with st.expander("📦 Datos del negocio en JSON (opcional, para proyectos custom)"):
                        st.code(build_short_summary(cli), language="json")

                with tab_html:
                    st.caption("Sube el archivo `.html` standalone que descargaste de claude.ai. Si prefieres, también puedes pegar el HTML manualmente más abajo.")

                    uploaded = st.file_uploader(
                        "Subir archivo HTML",
                        type=["html", "htm"],
                        key=f"upload_{sel_id}",
                        accept_multiple_files=False,
                        help="Arrastra el archivo o haz clic para seleccionarlo.",
                    )

                    if uploaded is not None:
                        try:
                            html_content = uploaded.read().decode("utf-8", errors="replace")
                        except Exception as e:
                            st.error(f"No pude leer el archivo: {e}")
                            html_content = ""

                        if html_content:
                            ok, msg = validate_html(html_content)
                            st.caption(f"Archivo: **{uploaded.name}** · {len(html_content):,} caracteres")
                            if ok:
                                st.success(f"✅ {msg}")
                                _auto_pub = st.checkbox(
                                    "🚀 Auto-publicar a Netlify al guardar",
                                    value=bool(config.NETLIFY_API_TOKEN),
                                    key=f"autopub_upload_{sel_id}",
                                    disabled=not config.NETLIFY_API_TOKEN,
                                    help="Requiere NETLIFY_API_TOKEN configurado.",
                                )
                                if st.button("💾 Guardar landing", key=f"saveupload_{sel_id}",
                                             type="primary", use_container_width=True):
                                    _save_landing_and_optionally_publish(sel_id, html_content, _auto_pub)
                                    _refresh()
                            else:
                                st.error(f"❌ {msg}")

                    with st.expander("✏️ Pegar HTML manualmente (alternativa)"):
                        pasted = st.text_area(
                            "HTML",
                            value="",
                            height=240,
                            key=f"paste_{sel_id}",
                            placeholder="<!DOCTYPE html>\n<html lang=\"es\">\n  ...\n</html>",
                        )
                        _auto_pub_paste = st.checkbox(
                            "🚀 Auto-publicar a Netlify al guardar",
                            value=bool(config.NETLIFY_API_TOKEN),
                            key=f"autopub_paste_{sel_id}",
                            disabled=not config.NETLIFY_API_TOKEN,
                        )
                        if st.button("✅ Validar y guardar (pegado)", key=f"savehtml_{sel_id}",
                                     use_container_width=True):
                            ok, msg = validate_html(pasted)
                            if not ok:
                                st.error(f"❌ {msg}")
                            else:
                                _save_landing_and_optionally_publish(sel_id, pasted, _auto_pub_paste)
                                _refresh()

                    if cli.get("landing_html"):
                        st.markdown("---")
                        if st.button(
                            "🗑️ Eliminar landing actual",
                            key=f"dellanding_{sel_id}",
                            use_container_width=True,
                        ):
                            clients_store.update(sel_id, landing_html=None, landing_path=None)
                            st.toast("Landing eliminada")
                            _refresh()

                with tab_preview:
                    if cli.get("landing_html"):
                        st.caption(f"Archivo: `{cli.get('landing_path')}`")
                        st.components.v1.html(cli["landing_html"], height=720, scrolling=True)
                        st.download_button(
                            "⬇️ Descargar HTML",
                            data=cli["landing_html"].encode("utf-8"),
                            file_name=f"{cli['name']}.html",
                            mime="text/html",
                            key=f"dlhtml_{sel_id}",
                        )
                    else:
                        st.info("Aún no hay landing cargada para este cliente.")

                with tab_auto:
                    st.caption("Genera una landing usando el mock de la app (siempre gratis, sin Claude). Útil para tener un placeholder rápido.")
                    if st.button("⚡ Generar landing mock", key=f"genmock_{sel_id}", use_container_width=True):
                        with st.spinner("Generando..."):
                            try:
                                html, path = generate_landing(cli)
                                clients_store.save_landing_html(sel_id, html)
                                st.success(f"✅ Generada en `{path}`")
                                _refresh()
                            except Exception as e:
                                logger.exception("Falló mock landing")
                                st.error(f"Error: {e}")

                # ===== PDF =====
                st.markdown("---")
                st.markdown("### 📄 PDF de propuesta")
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    if st.button("📄 Generar PDF", key=f"genpdf_{sel_id}",
                                 type="primary", use_container_width=True):
                        with st.spinner("Generando PDF..."):
                            try:
                                pdf_path = generate_pdf_proposal(cli, cli.get("landing_path"))
                                clients_store.update(sel_id, pdf_path=pdf_path)
                                st.success(f"✅ Guardado: `{pdf_path}`")
                                _refresh()
                            except Exception as e:
                                logger.exception("Falló PDF")
                                st.error(f"Error: {e}")
                with col_p2:
                    if cli.get("pdf_path") and Path(cli["pdf_path"]).exists():
                        with open(cli["pdf_path"], "rb") as f:
                            st.download_button(
                                "⬇️ Descargar PDF",
                                data=f.read(),
                                file_name=Path(cli["pdf_path"]).name,
                                mime="application/pdf",
                                key=f"dlpdf_{sel_id}",
                                use_container_width=True,
                            )


# ============================================================
# TAB 3 — EXPORTAR
# ============================================================
with tab_export:
    all_clients = _clients()
    if not all_clients:
        st.info("Aún no hay clientes guardados para exportar.")
    else:
        st.markdown(f"### Exportar **{len(all_clients)}** clientes guardados")

        col_e1, col_e2 = st.columns(2)
        with col_e1:
            if st.button("📊 Exportar a Excel", type="primary", use_container_width=True):
                with st.spinner("Generando Excel..."):
                    try:
                        path = export_to_excel(all_clients)
                        with open(path, "rb") as f:
                            data = f.read()
                        st.success(f"✅ `{path}`")
                        st.download_button(
                            "⬇️ Descargar Excel",
                            data=data,
                            file_name=Path(path).name,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    except Exception as e:
                        logger.exception("Falló Excel")
                        st.error(f"Error: {e}")

        with col_e2:
            if st.button("📄 Generar PDFs de todos", use_container_width=True):
                progress = st.progress(0, text="Generando PDFs...")
                ok, fail = 0, 0
                for i, c in enumerate(all_clients, start=1):
                    try:
                        pdf_path = generate_pdf_proposal(c, c.get("landing_path"))
                        clients_store.update(c["id"], pdf_path=pdf_path)
                        ok += 1
                    except Exception:
                        logger.exception("Falló PDF para %s", c.get("name"))
                        fail += 1
                    progress.progress(i / len(all_clients), text=f"{i}/{len(all_clients)}")
                progress.empty()
                st.success(f"✅ {ok} PDFs generados en `{config.PDF_DIR}`" + (f" ({fail} fallaron)" if fail else ""))

        st.markdown("---")
        st.markdown("### 🔢 Recalcular scores")
        st.caption(
            "Si cambiaste el algoritmo de scoring (CATEGORY_TIERS, pesos…), los clientes "
            "guardados quedan con el score viejo. Este botón los recalcula y actualiza en la DB."
        )
        if st.button("🔄 Recalcular scores de todos", use_container_width=True, key="recompute_scores"):
            from core.score import calculate_score_breakdown
            updated, unchanged, failed = 0, 0, 0
            progress_s = st.progress(0, text="Recalculando…")
            for i, c in enumerate(all_clients, start=1):
                try:
                    new_score, _ = calculate_score_breakdown(c)
                    if new_score != c.get("score"):
                        clients_store.update(c["id"], score=new_score)
                        updated += 1
                    else:
                        unchanged += 1
                except Exception:
                    logger.exception("Falló recálculo de score para %s", c.get("name"))
                    failed += 1
                progress_s.progress(i / len(all_clients), text=f"{i}/{len(all_clients)}")
            progress_s.empty()
            msg = f"✅ {updated} actualizados · {unchanged} sin cambios"
            if failed:
                msg += f" · {failed} fallaron"
            st.success(msg)
            _refresh()

        st.markdown("---")
        st.markdown("### Prompts de Claude")
        st.caption(
            "Genera un archivo `.txt` por cliente con el prompt listo para pegar en claude.ai. "
            "Filtra por estado y descarga solo los que necesitas."
        )

        _all_estados = sorted({c.get("estado") or "Pendiente" for c in all_clients})
        _estados_prompt = st.multiselect(
            "Filtrar por estado",
            options=_all_estados,
            default=_all_estados,
            key="zip_estados_filter",
            help="Selecciona los estados que quieres incluir en el ZIP.",
        )

        _clientes_zip = [c for c in all_clients if (c.get("estado") or "Pendiente") in _estados_prompt]
        st.caption(f"Se incluirán **{len(_clientes_zip)}** de {len(all_clients)} clientes.")

        if st.button(
            f"📋 Exportar prompts de Claude — {len(_clientes_zip)} clientes (ZIP)",
            use_container_width=True,
            disabled=not _clientes_zip,
        ):
            def _slugify(name: str) -> str:
                s = (name or "cliente").lower()
                s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
                return s or "cliente"

            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for cli in _clientes_zip:
                    prompt = build_landing_prompt(cli)
                    estado = re.sub(r"[^a-z0-9]+", "_", (cli.get("estado") or "pendiente").lower()).strip("_")
                    filename = f"{_slugify(cli['name'])}__{estado}.txt"
                    zf.writestr(filename, prompt)
            buf.seek(0)
            st.download_button(
                "⬇️ Descargar ZIP de prompts",
                data=buf,
                file_name=f"prompts_claude_{date.today().strftime('%Y%m%d')}.zip",
                mime="application/zip",
                use_container_width=True,
            )

        # ============================================================
        # 📦 Paquetes PREMIUM en lote (prompt + imágenes Gemini, en paralelo)
        # ============================================================
        st.markdown("---")
        st.markdown("### 📦 Paquetes premium en lote (con imágenes Gemini)")

        if not config.GEMINI_API_KEY:
            st.info(
                "ℹ️ Sin `GEMINI_API_KEY`. El lote genera prompts con instrucciones "
                "de Unsplash (sin fotos a medida). Para fotos generadas: key + "
                "**paid tier** en https://aistudio.google.com/ (~$0.039/img)."
            )
            with st.expander("🔍 Diagnóstico de Secrets (debug)"):
                st.json(config.secrets_diagnostic())
                st.caption(
                    "Si `st_secrets_top_keys` muestra `['GEMINI_API_KEY', ...]` pero "
                    "`gemini_via_secret_fn` es `false`, el valor está vacío o tiene "
                    "comillas/espacios extra. El formato correcto en Streamlit Cloud "
                    "Secrets es exactamente:\n\n"
                    "`GEMINI_API_KEY = \"AIza...\"` (sin punto y coma, sin espacios alrededor del =)"
                )

        from core import images as _img_mod

        # Si la última generación falló (lote anterior con 0 imgs), mostrarlo
        _last_err = _img_mod.last_error()
        if _last_err and config.GEMINI_API_KEY:
            st.error(
                f"⚠️ Última llamada a Gemini falló: `{_last_err}`. "
                "El siguiente intento limpia este aviso si tiene éxito."
            )

        _restante = _img_mod.remaining_today() if config.GEMINI_API_KEY else 0
        _por_paquete = config.GEMINI_IMAGES_PER_LANDING
        _max_pkgs_cuota = (_restante // _por_paquete) if (_por_paquete > 0 and config.GEMINI_API_KEY) else 9999

        st.caption(
            f"Genera el zip-de-zips para los clientes filtrados. Cada paquete usa "
            f"~{_por_paquete} imágenes Gemini (cache si ya existen). "
            + (
                f"Hoy quedan **{_restante}** imágenes en tu cupo gratuito → "
                f"hasta **{_max_pkgs_cuota}** paquetes nuevos como máximo."
                if config.GEMINI_API_KEY else
                "Sin GEMINI_API_KEY → paquetes solo con prompt (sin imágenes)."
            )
        )

        _estados_pkg = st.multiselect(
            "Filtrar por estado",
            options=_all_estados,
            default=_all_estados,
            key="pkg_estados_filter",
            help="Solo se incluirán los clientes con uno de estos estados.",
        )
        _clientes_pkg = [
            c for c in all_clients
            if (c.get("estado") or "Pendiente") in _estados_pkg
        ]

        # Cap dinámico: lo menor entre seleccionados y cuota disponible
        _cap_efectivo = min(len(_clientes_pkg), _max_pkgs_cuota) if _clientes_pkg else 0
        _se_recortan = config.GEMINI_API_KEY and len(_clientes_pkg) > _max_pkgs_cuota and _max_pkgs_cuota > 0

        col_pp1, col_pp2 = st.columns(2)
        col_pp1.metric("Filtrados", len(_clientes_pkg))
        col_pp2.metric("Se procesarán", _cap_efectivo)

        if _se_recortan:
            st.warning(
                f"⚠️ Tu cupo solo alcanza para {_max_pkgs_cuota} paquetes nuevos. "
                f"Procesaré los primeros {_cap_efectivo} de los {len(_clientes_pkg)} filtrados. "
                f"Si los clientes ya tienen imágenes en cache no consumen cuota."
            )

        _disabled = (_cap_efectivo == 0)
        _btn_label = (
            f"📦 Generar {_cap_efectivo} paquetes en paralelo (~1-3 min)"
            if not _disabled
            else "Sin clientes filtrados"
        )

        _pkg_lote_state_key = "pkg_lote_result"
        if st.button(
            _btn_label,
            use_container_width=True,
            disabled=_disabled,
            type="primary",
            key="btn_pkg_lote",
        ):
            from core.landing import export_landing_packages_parallel

            _to_process = _clientes_pkg[:_cap_efectivo]
            progress_bar = st.progress(0.0, text="Iniciando…")
            status_box = st.empty()

            def _cb(done: int, total: int, last_name: str):
                progress_bar.progress(
                    done / total,
                    text=f"{done}/{total} paquetes listos · último: {last_name}",
                )

            try:
                final_path, lote_results = export_landing_packages_parallel(
                    _to_process,
                    max_workers=10,
                    progress_cb=_cb,
                )
                progress_bar.empty()
                n_ok = sum(1 for r in lote_results if r["ok"])
                n_fail = sum(1 for r in lote_results if not r["ok"])
                n_imgs = sum(r["images"] for r in lote_results)
                status_box.success(
                    f"✅ {n_ok} paquetes generados · {n_imgs} imágenes Gemini · "
                    f"{n_fail} fallaron · cupo restante: {_img_mod.remaining_today()}/{config.GEMINI_DAILY_BUDGET}"
                )
                # Leer los bytes AHORA y guardarlos en session_state para que la
                # descarga sobreviva aunque se limpie outputs/lotes/.
                zip_bytes_lote = final_path.read_bytes()
                st.session_state[_pkg_lote_state_key] = {
                    "bytes": zip_bytes_lote,
                    "size": len(zip_bytes_lote),
                    "results": lote_results,
                }
            except Exception as e:
                progress_bar.empty()
                logger.exception("Falló export_landing_packages_parallel")
                status_box.error(f"Error: {e}")

        # Botón de descarga: SIEMPRE renderizado fuera del if del botón generar.
        # Lee los bytes del session_state (no del path) para que sobreviva limpieza.
        _pkg_lote = st.session_state.get(_pkg_lote_state_key)
        if _pkg_lote and _pkg_lote.get("bytes"):
            st.download_button(
                f"⬇️ Descargar zip-de-zips ({_pkg_lote['size'] // 1024} KB)",
                data=_pkg_lote["bytes"],
                file_name=f"landing_packages_{date.today().strftime('%Y%m%d')}.zip",
                mime="application/zip",
                use_container_width=True,
                key="dl_pkg_lote",
            )
            with st.expander("📋 Ver detalle del lote"):
                for r in _pkg_lote["results"]:
                    icon = "✅" if r["ok"] else "❌"
                    extra = f" · {r['images']} imgs" if r["ok"] else f" · {r['error']}"
                    st.write(f"{icon} {r['name']}{extra}")
        else:
            st.caption("ℹ️ Click en **Generar paquetes** primero — el botón de descarga aparecerá aquí.")

        st.markdown("---")
        st.markdown("### 📤 Carga masiva de landings")
        st.caption(
            "Sube varios `.html` de una vez. La app los asigna automáticamente al cliente "
            "más parecido por nombre de archivo. Revisa y corrige antes de guardar."
        )

        bulk_files = st.file_uploader(
            "Arrastra los archivos HTML aquí",
            type=["html", "htm"],
            accept_multiple_files=True,
            key="bulk_html_upload",
        )

        if bulk_files:
            from core.html_validator import validate_html

            _clist = all_clients
            _cnames = ["— Sin asignar —"] + [c["name"] for c in _clist]
            _cid_map = {c["name"]: c["id"] for c in _clist}

            # Auto-confirmar matches ≥85% (umbral alto = pocos falsos positivos).
            # Los <85% sí se muestran para revisión manual.
            AUTO_CONFIRM_THRESHOLD = 0.85
            auto_assigned: list[tuple] = []   # (uf, cliente_name)  — fuera de UI
            ambiguous: list[tuple] = []       # (uf, best_name, score) — pide revisión

            for uf in bulk_files:
                best, score = _fuzzy_match_client(uf.name, _clist)
                if best and score is not None and score >= AUTO_CONFIRM_THRESHOLD:
                    auto_assigned.append((uf, best["name"], score))
                else:
                    ambiguous.append((uf, best["name"] if best else None, score))

            # Resumen + opción de auto-publicar
            col_b1, col_b2 = st.columns(2)
            col_b1.metric("✅ Auto-asignados (≥85%)", len(auto_assigned))
            col_b2.metric("⚠️ Para revisar", len(ambiguous))

            _bulk_autopub = st.checkbox(
                "🚀 Auto-publicar a Netlify cada landing al guardar",
                value=False,
                key="bulk_html_autopub",
                disabled=not config.NETLIFY_API_TOKEN,
                help="Si está activo, cada landing guardada se sube a Netlify automáticamente. Más lento pero ahorra clicks.",
            )

            confirmed: list[tuple] = list((uf, cname) for uf, cname, _ in auto_assigned)

            if auto_assigned:
                with st.expander(f"Ver los {len(auto_assigned)} auto-asignados"):
                    for uf, cname, score in auto_assigned:
                        st.write(f"✅ `{uf.name}` → **{cname}** ({int(score * 100)}%)")

            if ambiguous:
                st.markdown("**Revisa estas asignaciones:**")
                hc1, hc2, hc3, hc4 = st.columns([3, 4, 1, 2])
                hc1.markdown("**Archivo**")
                hc2.markdown("**Cliente asignado**")
                hc3.markdown("**Match**")
                hc4.markdown("**Estado actual**")

                for uf, best_name, score in ambiguous:
                    default_idx = (_cnames.index(best_name)
                                   if best_name and best_name in _cnames else 0)
                    c1, c2, c3, c4 = st.columns([3, 4, 1, 2])
                    with c1:
                        ok_html, _ = validate_html(uf.read().decode("utf-8", errors="replace"))
                        uf.seek(0)
                        icon = "✅" if ok_html else "⚠️"
                        st.markdown(f"{icon} `{uf.name}`")
                    with c2:
                        selected = st.selectbox(
                            "cliente",
                            options=_cnames,
                            index=default_idx,
                            key=f"bulk_assign_{uf.name}",
                            label_visibility="collapsed",
                        )
                    with c3:
                        if score:
                            color = "orange" if score >= 0.5 else "red"
                            st.markdown(f":{color}[{int(score * 100)}%]")
                        else:
                            st.markdown(":red[—]")
                    with c4:
                        cli_estado = (
                            next((c.get("estado", "") for c in _clist
                                  if c["name"] == selected), "")
                            if selected != "— Sin asignar —" else ""
                        )
                        st.caption(cli_estado or "—")

                    if selected != "— Sin asignar —":
                        confirmed.append((uf, selected))

            n_ok = len(confirmed)
            if st.button(
                f"💾 Guardar {n_ok} landing(s)" + (" + publicar" if _bulk_autopub else ""),
                type="primary",
                use_container_width=True,
                disabled=n_ok == 0,
                key="bulk_html_save",
            ):
                saved_ok, saved_fail, pub_ok, pub_fail = 0, 0, 0, 0
                for uf, cname in confirmed:
                    cid = _cid_map.get(cname)
                    if not cid:
                        saved_fail += 1
                        continue
                    html_text = uf.read().decode("utf-8", errors="replace")
                    clients_store.save_landing_html(cid, html_text)
                    saved_ok += 1

                    if _bulk_autopub and config.NETLIFY_API_TOKEN:
                        try:
                            from core import netlify as _netlify
                            cli_obj = clients_store.get(cid, include_html=False) or {}
                            res = _netlify.publish_html(
                                html_text, cli_obj.get("name", cname),
                                site_id=cli_obj.get("netlify_site_id"),
                            )
                            clients_store.update(
                                cid,
                                netlify_url=res["url"],
                                netlify_site_id=res["site_id"],
                                netlify_deploy_at=datetime.now().isoformat(timespec="seconds"),
                            )
                            pub_ok += 1
                        except Exception:
                            logger.exception("Bulk auto-publish falló para %s", cname)
                            pub_fail += 1

                if saved_ok:
                    msg = f"✅ {saved_ok} landing(s) guardadas"
                    if _bulk_autopub:
                        msg += f" · 🚀 {pub_ok} publicadas en Netlify"
                        if pub_fail:
                            msg += f" ({pub_fail} fallaron)"
                    st.success(msg)
                if saved_fail:
                    st.warning(f"{saved_fail} no se pudieron guardar.")
                _refresh()

        st.markdown("---")
        st.markdown("### Resumen rápido")
        rows_summary = [{
            "Nombre": c["name"],
            "Categoría": c.get("category"),
            "Score": c.get("score"),
            "Estado": c.get("estado"),
            "Email": c.get("email") or "—",
            "Teléfono": c.get("phone") or "—",
            "Próximo contacto": c.get("fecha_proximo_contacto") or "—",
            "Precio (MXN)": c.get("precio_cotizado") or "—",
            "Landing": "✅" if c.get("landing_path") else "—",
        } for c in all_clients]
        st.dataframe(rows_summary, hide_index=True, use_container_width=True)


# ============================================================
# TAB 4 — AUTOMATIZACIÓN MASIVA
# ============================================================
with tab_automation:
    st.markdown("### 🚀 Automatización masiva de prospectos")
    st.caption(
        "Sube un Excel exportado de la app, selecciona prospectos y deja que el "
        "sistema los publique en Netlify y arme los links de WhatsApp listos para enviar."
    )

    # Validación de configuración
    if not config.NETLIFY_API_TOKEN:
        st.error(
            "❌ `NETLIFY_API_TOKEN` no está configurado en `.env`. "
            "Sin él, no se pueden publicar las landings automáticamente."
        )
        st.stop()

    # Estado del tab
    st.session_state.setdefault("auto_imported_ids", [])
    st.session_state.setdefault("auto_results", [])

    # ===== Paso 1: Subir Excel =====
    st.markdown("#### 1️⃣ Subir Excel de prospectos")

    excel_uploaded = st.file_uploader(
        "Arrastra el archivo `.xlsx` exportado de la pestaña Exportar",
        type=["xlsx"],
        key="auto_excel_upload",
    )

    if excel_uploaded is not None:
        # Guardar temporal
        tmp_path = config.EXCEL_DIR / f"_upload_{excel_uploaded.name}"
        tmp_path.write_bytes(excel_uploaded.read())

        if st.button("📥 Importar a Mis clientes", type="primary"):
            try:
                from core.automation import import_excel_to_store
                with st.spinner("Importando..."):
                    result = import_excel_to_store(str(tmp_path))
                st.success(
                    f"✅ Importación completada: {result['imported']} nuevos, "
                    f"{result['already_existed']} ya existían "
                    f"({result['rows_total']} filas totales en el Excel)"
                )
                _refresh()
            except Exception as e:
                logger.exception("Falló import Excel")
                st.error(f"Error al importar: {e}")

    st.markdown("---")

    # ===== Paso 2: Filtros + selección =====
    st.markdown("#### 2️⃣ Selecciona prospectos a procesar")

    all_clients = _clients()
    if not all_clients:
        st.info("Aún no hay clientes. Importa un Excel arriba o ve a 🔍 Buscar prospectos.")
    else:
        f1, f2, f3 = st.columns(3)
        with f1:
            min_score_auto = st.slider("Score mínimo", 1, 10, 7, key="auto_min_score")
        with f2:
            estados_filtro = st.multiselect(
                "Solo estados",
                options=["Pendiente", "Mensaje listo", "Falta landing", "Sin teléfono", "Mensaje enviado"],
                default=["Pendiente", "Falta landing"],
                key="auto_estados",
            )
        with f3:
            cats_filtro = st.multiselect(
                "Solo categorías (vacío = todas)",
                options=config.CATEGORIES,
                default=[],
                key="auto_cats",
            )

        candidatos = [
            c for c in all_clients
            if (c.get("score") or 0) >= min_score_auto
            and (not estados_filtro or c.get("estado") in estados_filtro)
            and (not cats_filtro or c.get("category") in cats_filtro)
        ]

        # Métricas
        c_total = len(candidatos)
        c_with_landing = sum(1 for c in candidatos if c.get("landing_path"))
        c_with_phone = sum(1 for c in candidatos if c.get("phone"))
        c_ready = sum(1 for c in candidatos if c.get("landing_path") and c.get("phone"))
        c_pending_landing = c_total - c_with_landing

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Candidatos", c_total)
        m2.metric("Listos para procesar", c_ready, help="Con landing + teléfono")
        m3.metric("Falta landing", c_pending_landing)
        m4.metric("Sin teléfono", c_total - c_with_phone)

        if c_total == 0:
            st.warning("Ningún cliente cumple los filtros.")
            st.stop()

        # Plantilla
        tpl_keys_auto = list(config.WHATSAPP_TEMPLATES.keys())
        tpl_label = st.selectbox(
            "Plantilla de mensaje WhatsApp para todos",
            options=[config.WHATSAPP_TEMPLATE_LABELS[k] for k in tpl_keys_auto],
            index=0,
            key="auto_tpl",
        )
        tpl_key_auto = tpl_keys_auto[
            [config.WHATSAPP_TEMPLATE_LABELS[k] for k in tpl_keys_auto].index(tpl_label)
        ]

        # ===== Fase A: procesar =====
        st.markdown("---")
        st.markdown("#### 3️⃣ Fase A — Publicar landings y armar mensajes")
        st.caption(
            f"Se procesarán **{c_ready}** clientes con landing + teléfono. "
            f"Los **{c_pending_landing}** sin landing quedarán marcados para Fase B."
        )

        col_run1, col_run2 = st.columns([3, 1])
        with col_run2:
            run_auto = st.button(
                "🚀 Iniciar pipeline",
                type="primary",
                use_container_width=True,
                disabled=(c_total == 0),
            )

        if run_auto:
            from core.automation import run_phase_a
            ids = [c["id"] for c in candidatos]
            progress_bar = st.progress(0, text="Iniciando...")
            status_box = st.empty()

            def _on_progress(idx: int, total: int, msg: str) -> None:
                progress_bar.progress(idx / total, text=f"{idx}/{total} — {msg}")

            try:
                results = run_phase_a(ids, template_key=tpl_key_auto, progress_cb=_on_progress)
                st.session_state["auto_results"] = results
                progress_bar.empty()
                ok = sum(1 for r in results if r.get("ok"))
                pendientes = sum(1 for r in results if r.get("estado") == "Falta landing")
                err = sum(1 for r in results if not r.get("ok") and r.get("estado") != "Falta landing")
                st.success(f"✅ Pipeline completado: **{ok}** listos, **{pendientes}** sin landing, **{err}** errores")
            except Exception as e:
                progress_bar.empty()
                logger.exception("Pipeline falló")
                st.error(f"Error: {e}")

        # ===== Resultados =====
        if st.session_state["auto_results"]:
            st.markdown("---")
            st.markdown("#### 📋 Resultados")

            res_rows = []
            for r in st.session_state["auto_results"]:
                res_rows.append({
                    "OK": "✅" if r.get("ok") else ("⏳" if r.get("estado") == "Falta landing" else "❌"),
                    "Nombre": r.get("name"),
                    "Estado": r.get("estado"),
                    "URL Netlify": r.get("url") or "—",
                    "Error": r.get("error") or "",
                })
            st.dataframe(res_rows, hide_index=True, use_container_width=True)

            # Botones de descarga / siguiente fase
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                if st.button("📊 Generar Excel actualizado", use_container_width=True):
                    from core.automation import regenerate_excel_from_store
                    ids = [r["id"] for r in st.session_state["auto_results"]]
                    path = regenerate_excel_from_store(only_ids=ids)
                    with open(path, "rb") as f:
                        st.download_button(
                            "⬇️ Descargar",
                            data=f.read(),
                            file_name=Path(path).name,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )

            with col_d2:
                pendientes = [r for r in st.session_state["auto_results"]
                              if r.get("estado") == "Falta landing"]
                if pendientes and st.button(
                    f"📥 Ver {len(pendientes)} pendientes de landing",
                    use_container_width=True,
                ):
                    # Cambiar al modo Fase B abajo
                    st.session_state["auto_show_phase_b"] = True
                    _refresh()

            # Listos para WhatsApp: mostrar links
            listos = [r for r in st.session_state["auto_results"] if r.get("ok") and r.get("wa_url")]
            if listos:
                st.markdown("---")
                st.markdown(f"#### 💬 {len(listos)} mensajes listos para enviar")
                for r in listos:
                    col_a, col_b, col_c = st.columns([3, 1, 1])
                    with col_a:
                        st.markdown(f"**{r['name']}** · [{r['url']}]({r['url']})")
                    with col_b:
                        st.link_button("📲 Enviar", r["wa_url"], use_container_width=True)
                    with col_c:
                        if st.button("✅ Enviado", key=f"sent_auto_{r['id']}", use_container_width=True):
                            _dialog_enviado(r["id"], r.get("name", ""))

        # ===== Fase B: subir landings pendientes =====
        if st.session_state.get("auto_show_phase_b"):
            st.markdown("---")
            st.markdown("#### 📥 Fase B — Cargar landings pendientes")
            st.caption(
                "Para cada uno: copia el prompt → pégalo en claude.ai → descarga "
                "el HTML → súbelo aquí. Cuando termines, vuelve a la Fase A."
            )

            from core.landing_prompt import build_landing_prompt

            pendientes_ids = [
                r["id"] for r in st.session_state["auto_results"]
                if r.get("estado") == "Falta landing"
            ]
            for cid in pendientes_ids:
                cli_p = clients_store.get(cid)
                if not cli_p:
                    continue
                if cli_p.get("landing_html"):
                    continue  # Ya se cargó

                with st.expander(f"⏳ {cli_p['name']} — falta HTML"):
                    st.text_area(
                        "Prompt",
                        value=build_landing_prompt(cli_p),
                        height=200,
                    )
                    upl = st.file_uploader(
                        "Sube el HTML descargado",
                        type=["html", "htm"],
                        key=f"upl_phaseb_{cid}",
                    )
                    if upl is not None:
                        try:
                            html_text = upl.read().decode("utf-8", errors="replace")
                            from core.html_validator import validate_html
                            ok, msg = validate_html(html_text)
                            if ok:
                                clients_store.save_landing_html(cid, html_text)
                                st.success(f"✅ {cli_p['name']} — landing guardada")
                                _refresh()
                            else:
                                st.error(f"❌ {msg}")
                        except Exception as e:
                            st.error(f"Error: {e}")


# ============================================================
# TAB 5 — AYUDA / FAQ
# ============================================================
with tab_help:
    from core.help_content import HELP_SECTIONS

    st.markdown("### ❓ Guía rápida — Prospector Web")
    st.caption(
        f"Hecha por **{config.AGENCY_NAME}** para cualquier persona que use esta app. "
        "Lee esto si es tu primera vez o si algo no funciona como esperas."
    )
    st.markdown("---")

    for section in HELP_SECTIONS:
        with st.expander(section["title"], expanded=False):
            st.markdown(section["content"])

    st.markdown("---")
    st.markdown(
        f"**{config.AGENCY_NAME}** · {config.YOUR_NAME} · "
        f"{config.AGENCY_PHONE} · {config.AGENCY_EMAIL}"
    )


st.markdown("---")
st.caption(f"Prospector Web · {config.AGENCY_NAME}")
