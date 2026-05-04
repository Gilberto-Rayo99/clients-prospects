"""Streamlit app — Prospector Web (RAIO Development)."""
from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

import config
from core import clients_store
from core.contact import suggest_contact_channel
from core.enrich import enrich_contact
from core.html_validator import validate_html
from core.landing import generate_landing
from core.landing_prompt import build_landing_prompt, build_short_summary
from core.score import calculate_score
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
# State
# ============================================================
st.session_state.setdefault("prospects", [])
st.session_state.setdefault("last_search", None)
st.session_state.setdefault("preview_landing", None)         # (name, html)
st.session_state.setdefault("editing_client_id", None)       # cliente abierto en detalle


# ============================================================
# Helpers
# ============================================================
def _process_prospects(prospects: list[dict]) -> list[dict]:
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
    st.rerun()


# ============================================================
# Sidebar
# ============================================================
with st.sidebar:
    st.title("🎯 Prospector Web")
    st.caption(f"**{config.AGENCY_NAME}**")
    n_clients = len(clients_store.list_all())
    st.metric("👥 Clientes guardados", n_clients)

    if config.USE_MOCK_DATA:
        st.info("🧪 Modo DEMO. Configura las API keys en `.env` y `USE_MOCK_DATA=false` para datos reales.")

    st.markdown("---")
    st.subheader("Búsqueda")

    zone = st.text_input("Zona / colonia", value="Coyoacán, CDMX")
    radius_km = st.slider("Radio (km)", 1, 30, 5)
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
            raw = search_businesses(zone, radius_km, category, web_filter_key)
            st.session_state["prospects"] = _process_prospects(raw)
            st.session_state["last_search"] = {
                "zone": zone, "radius_km": radius_km,
                "category": category, "filter": web_filter_label,
            }
            st.session_state["preview_landing"] = None
        except Exception as e:
            logger.exception("Falló la búsqueda")
            st.error(f"Error al buscar: {e}")


# ============================================================
# TABS
# ============================================================
tab_search, tab_clients, tab_export = st.tabs([
    "🔍 Buscar prospectos",
    f"👥 Mis clientes ({n_clients})",
    "📤 Exportar",
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
        ya_guardados = sum(1 for p in prospects if clients_store.exists_by_place_id(p.get("place_id")))

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

        # Tabla
        rows = []
        for p in prospects:
            saved = clients_store.exists_by_place_id(p.get("place_id"))
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
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

        st.markdown("### Detalles")
        for i, p in enumerate(prospects):
            saved = clients_store.exists_by_place_id(p.get("place_id"))
            badge = " · ✅ guardado" if saved else ""
            with st.expander(f"{_score_color(p['score'])} **{p['name']}** — Score {p['score']}/10{badge}"):
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
                    st.markdown(f"**Canal sugerido:** {CHANNEL_ICON.get(p['contact_channel'], '')} `{p['contact_channel']}` → {p['contact_value']}")
                    if p.get("maps_url"):
                        st.markdown(f"[📍 Ver en Google Maps]({p['maps_url']})")

                with col_r:
                    place_id = p.get("place_id", f"idx_{i}")
                    if saved:
                        st.success("Ya está en tus clientes guardados.")
                        if st.button("📂 Abrir en 'Mis clientes'", key=f"open_{place_id}", use_container_width=True):
                            existing = next(
                                (c for c in clients_store.list_all() if c.get("place_id") == p.get("place_id")),
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
    all_clients = clients_store.list_all()

    if not all_clients:
        st.info("Aún no has guardado clientes. Ve a la pestaña **🔍 Buscar prospectos** y guarda los que te interesen.")
    else:
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

                with col_right:
                    st.markdown("### 📌 Seguimiento")
                    new_estado = st.selectbox(
                        "Estado",
                        options=clients_store.CLIENT_STATUSES,
                        index=clients_store.CLIENT_STATUSES.index(cli.get("estado", "Pendiente")),
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
                    st.caption("Copia este prompt, pégalo en claude.ai (Pro/Max), copia el HTML que te devuelva, y pégalo en la pestaña **📥 Cargar HTML**.")
                    prompt_text = build_landing_prompt(cli)
                    st.text_area("Prompt", value=prompt_text, height=380, key=f"prompt_{sel_id}")
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
                                if st.button("💾 Guardar landing", key=f"saveupload_{sel_id}",
                                             type="primary", use_container_width=True):
                                    clients_store.save_landing_html(sel_id, html_content)
                                    st.success("Landing guardada.")
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
                        if st.button("✅ Validar y guardar (pegado)", key=f"savehtml_{sel_id}",
                                     use_container_width=True):
                            ok, msg = validate_html(pasted)
                            if not ok:
                                st.error(f"❌ {msg}")
                            else:
                                clients_store.save_landing_html(sel_id, pasted)
                                st.success(f"✅ {msg} Landing guardada.")
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
    all_clients = clients_store.list_all()
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
        st.markdown("### Resumen rápido")
        df = pd.DataFrame([{
            "Nombre": c["name"],
            "Categoría": c.get("category"),
            "Score": c.get("score"),
            "Estado": c.get("estado"),
            "Email": c.get("email") or "—",
            "Teléfono": c.get("phone") or "—",
            "Próximo contacto": c.get("fecha_proximo_contacto") or "—",
            "Precio (MXN)": c.get("precio_cotizado") or "—",
            "Landing": "✅" if c.get("landing_html") else "—",
        } for c in all_clients])
        st.dataframe(df, hide_index=True, use_container_width=True)


st.markdown("---")
st.caption(f"Prospector Web · {config.AGENCY_NAME}")
