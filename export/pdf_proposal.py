"""Genera PDF de propuesta imprimible (1 página A4) para visita presencial.

Diseño:
  - Hero con nombre + estrellas grandes (rating + reseñas) — gancho social.
  - Diagnóstico actual (PageSpeed si lo tenemos, o "sin web" según corresponda).
  - Vista previa de la landing + QR code apuntando a Netlify si existe.
  - Beneficios cuantificados por giro.
  - Inversión + plazos + qué incluye.
  - Footer con datos del consultor.
"""
from __future__ import annotations

import io
import logging
import re
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image as PlatypusImage,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

import config

logger = logging.getLogger(__name__)


# ============================================================
# Paletas y mensajes por giro
# ============================================================
CATEGORY_COLORS: dict[str, dict] = {
    "Restaurantes":          {"primary": colors.HexColor("#C0392B"), "accent": colors.HexColor("#F39C12")},
    "Cafeterías":            {"primary": colors.HexColor("#6F4E37"), "accent": colors.HexColor("#D2A679")},
    "Estéticas y barberías": {"primary": colors.HexColor("#1C1C1C"), "accent": colors.HexColor("#C9A227")},
    "Talleres mecánicos":    {"primary": colors.HexColor("#2C3E50"), "accent": colors.HexColor("#E67E22")},
    "Tiendas de abarrotes":  {"primary": colors.HexColor("#27AE60"), "accent": colors.HexColor("#F1C40F")},
    "Consultorios dentales": {"primary": colors.HexColor("#1F6FEB"), "accent": colors.HexColor("#56C2E6")},
    "Gimnasios":             {"primary": colors.HexColor("#111111"), "accent": colors.HexColor("#FF3B30")},
    "Veterinarias":          {"primary": colors.HexColor("#16A085"), "accent": colors.HexColor("#F39C12")},
    "Lavanderías":           {"primary": colors.HexColor("#3498DB"), "accent": colors.HexColor("#2ECC71")},
    "Florerías":             {"primary": colors.HexColor("#C0397A"), "accent": colors.HexColor("#9B59B6")},
    "Panaderías":            {"primary": colors.HexColor("#A0522D"), "accent": colors.HexColor("#F4A460")},
    "Inmobiliarias":         {"primary": colors.HexColor("#0F3D5C"), "accent": colors.HexColor("#D4AF37")},
    "Otros":                 {"primary": colors.HexColor("#1F6FEB"), "accent": colors.HexColor("#22C55E")},
}


VALUE_PROPS_BY_CATEGORY: dict[str, list[str]] = {
    "Restaurantes":          [
        "Más reservas y pedidos: tu menú actualizado en Google al instante.",
        "Confianza profesional: te diferencias de la competencia que solo tiene Facebook.",
        "Vendes 24/7: tu web sigue trayendo clientes nuevos aunque cierres.",
    ],
    "Cafeterías":            [
        "Atrae más clientes locales con menú, fotos y horarios siempre disponibles.",
        "Posicionamiento en Google Maps: aparece arriba cuando buscan cafetería cerca.",
        "Reservas y eventos privados gestionados desde tu propia página.",
    ],
    "Estéticas y barberías": [
        "Agenda en línea 24/7: clientes reservan sin llamarte, no pierdes ventas.",
        "Galería de cortes y servicios que muestra tu estilo y atrae al cliente correcto.",
        "Más reseñas y referidos: una web profesional inspira confianza inmediata.",
    ],
    "Talleres mecánicos":    [
        "Genera confianza antes de que el cliente llegue: trayectoria, especialidades, testimonios.",
        "Cotizaciones y citas en línea para reducir llamadas y agilizar el flujo.",
        "Apareces en Google cuando buscan 'taller mecánico cerca de mí'.",
    ],
    "Tiendas de abarrotes":  [
        "Pedidos a domicilio gestionados desde la web — sin depender solo de WhatsApp.",
        "Catálogo de productos y promociones siempre actualizado.",
        "Posicionamiento local para que vecinos te encuentren rápido en Google.",
    ],
    "Consultorios dentales": [
        "Agenda de citas en línea: pacientes nuevos sin saturar la recepción.",
        "Imagen profesional que transmite limpieza, modernidad y confianza.",
        "SEO local — apareces arriba cuando buscan 'dentista cerca'.",
    ],
    "Gimnasios":             [
        "Inscripciones y pago de membresías en línea, sin filas en recepción.",
        "Galería de instalaciones y horarios de clases visibles 24/7.",
        "Conversión de visitas en clases de prueba con un solo CTA bien colocado.",
    ],
    "Veterinarias":          [
        "Citas en línea para vacunas, consultas y servicios — menos llamadas, más eficiencia.",
        "Confianza para nuevos clientes: equipo, especialidades, testimonios visibles.",
        "Sección de emergencias y horarios siempre actualizada.",
    ],
    "Lavanderías":           [
        "Pedidos de recolección y entrega gestionados desde la web.",
        "Lista de precios actualizable sin reimprimir lonas.",
        "Posicionamiento local para captar clientes nuevos del barrio.",
    ],
    "Florerías":             [
        "Catálogo y pedidos en línea para fechas especiales (Madres, San Valentín…).",
        "Galería profesional que vende solita.",
        "Posicionamiento Google Maps + SEO local.",
    ],
    "Panaderías":            [
        "Encargos para eventos y pasteles personalizados desde la web.",
        "Catálogo de productos del día, siempre fresco.",
        "Apareces en Google con menú y horarios cuando buscan 'panadería cerca'.",
    ],
    "Inmobiliarias":         [
        "Catálogo de propiedades navegable con fotos profesionales y filtros.",
        "Captura leads cualificados con formularios y agenda de visitas online.",
        "SEO local potente para 'casas en venta en [zona]'.",
    ],
}


# ============================================================
# Helpers
# ============================================================
def _slugify(name: str) -> str:
    s = (name or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "negocio"


def _value_props(category: str) -> list[str]:
    return VALUE_PROPS_BY_CATEGORY.get(category, [
        "Imagen profesional que genera confianza desde el primer contacto.",
        "Apareces en Google cuando buscan negocios como el tuyo.",
        "Vendes 24/7 — tu sitio trabaja aunque tú estés cerrado.",
    ])


def _color_for(category: str) -> dict:
    return CATEGORY_COLORS.get(category, CATEGORY_COLORS["Otros"])


def _stars_glyph(rating: Optional[float]) -> str:
    """Convierte rating 0-5 en glifos ★★★★☆ (4 sólidas, 1 vacía)."""
    if rating is None:
        return "—"
    try:
        r = max(0.0, min(5.0, float(rating)))
    except (TypeError, ValueError):
        return "—"
    full = int(round(r))
    return "★" * full + "☆" * (5 - full)


def _format_price(precio: Optional[float], default: int = 3000) -> str:
    """Formatea precio en MXN. Si no hay precio cotizado, usa el default."""
    try:
        v = float(precio) if precio else 0
    except (TypeError, ValueError):
        v = 0
    if v <= 0:
        v = default
    return f"${int(v):,} MXN".replace(",", ",")


def _build_qr_drawing(url: str, size_cm: float = 3.5) -> Drawing:
    """Genera un QR code en formato Drawing reportlab."""
    qr = QrCodeWidget(url)
    bounds = qr.getBounds()
    w_qr = bounds[2] - bounds[0]
    h_qr = bounds[3] - bounds[1]
    target = size_cm * cm
    d = Drawing(target, target, transform=[target / w_qr, 0, 0, target / h_qr, 0, 0])
    d.add(qr)
    return d


def _pagespeed_data_for(url: Optional[str]) -> Optional[dict]:
    """Lee PageSpeed cacheado (read_only — nunca llama al API)."""
    if not url:
        return None
    try:
        from core import pagespeed
        return pagespeed.get_score(url, read_only=True)
    except Exception:
        return None


def _diagnostico_actual(business: dict) -> tuple[str, str]:
    """Devuelve (titulo, mensaje) del bloque de diagnóstico según contexto.

    Si hay PageSpeed cacheado y mobile_score < 80 → frase con score concreto.
    Si tiene web sin PageSpeed → frase genérica de modernización.
    Si no tiene web → frase de "sin presencia digital".
    """
    website = business.get("website")
    if not website:
        return (
            "Hoy no apareces en internet",
            "Cuando alguien busca un negocio como el tuyo en Google, no te encuentra. "
            "Mientras tanto, tus competidores con web atraen a esos clientes que "
            "podrían ser tuyos. Una web profesional cierra ese hueco."
        )

    ps = _pagespeed_data_for(website)
    if ps and ps.get("mobile_score") is not None:
        m = ps["mobile_score"]
        if m < 50:
            return (
                f"Tu sitio actual saca {m}/100 en velocidad móvil",
                f"Según PageSpeed Insights de Google, tu web carga muy lento en celular "
                f"({m}/100). Esto afecta directamente tu posición en búsquedas locales y "
                "hace que muchos visitantes se vayan antes de ver tu contenido."
            )
        if m < 80:
            return (
                f"Tu sitio puede mejorar — saca {m}/100 en móvil",
                f"Tu web carga aceptable pero no destaca ({m}/100 en velocidad móvil "
                "según Google). Una versión optimizada subiría tu conversión y SEO local."
            )

    return (
        "Tu sitio actual se puede modernizar",
        "Revisamos tu sitio y vemos espacio importante para modernizarlo: diseño actual, "
        "velocidad en celular y mejor llamada a la acción para que más visitas se "
        "conviertan en clientes."
    )


# ============================================================
# Generador de PDF individual
# ============================================================
def generate_pdf_proposal(
    business: dict,
    landing_html_path: str | None = None,
    out_path: Optional[Path] = None,
) -> str:
    """Genera el PDF de propuesta para un cliente.

    Args:
        business: dict del cliente (al menos con name + category).
        landing_html_path: opcional, info para mencionar.
        out_path: si se da, escribe ahí; si no, en config.PDF_DIR.

    Returns:
        Ruta absoluta del PDF generado.
    """
    palette = _color_for(business.get("category", "Otros"))
    primary = palette["primary"]
    accent = palette["accent"]

    slug = _slugify(business.get("name", "negocio"))
    if out_path is None:
        out_path = config.PDF_DIR / f"{slug}_propuesta.pdf"
    else:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        rightMargin=1.4 * cm, leftMargin=1.4 * cm,
        topMargin=1.0 * cm, bottomMargin=1.0 * cm,
        title=f"Propuesta — {business.get('name', '')}",
        author=config.AGENCY_NAME,
    )

    # ===== Estilos =====
    styles = getSampleStyleSheet()
    s_h1 = ParagraphStyle(
        "H1", parent=styles["Heading1"], fontName="Helvetica-Bold",
        fontSize=22, leading=26, textColor=colors.white, alignment=0, spaceAfter=0,
    )
    s_subtitle = ParagraphStyle(
        "Sub", parent=styles["Normal"], fontName="Helvetica",
        fontSize=10, leading=13, textColor=colors.HexColor("#FFFFFF"), spaceAfter=0,
    )
    s_stars = ParagraphStyle(
        "Stars", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=18, leading=22, textColor=accent, spaceAfter=2,
    )
    s_stars_label = ParagraphStyle(
        "StarsL", parent=styles["Normal"], fontName="Helvetica",
        fontSize=9, textColor=colors.HexColor("#DDDDDD"),
    )
    s_h2 = ParagraphStyle(
        "H2", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=12, leading=15, textColor=primary, spaceBefore=8, spaceAfter=5,
    )
    s_body = ParagraphStyle(
        "Body", parent=styles["Normal"], fontName="Helvetica",
        fontSize=9.5, leading=13, textColor=colors.HexColor("#222222"),
    )
    s_diagnostico_title = ParagraphStyle(
        "DT", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=11, leading=14, textColor=primary, spaceAfter=3,
    )
    s_bullet = ParagraphStyle(
        "Bullet", parent=s_body, leftIndent=12, bulletIndent=2, spaceAfter=3,
    )
    s_caption = ParagraphStyle(
        "Cap", parent=styles["Normal"], fontName="Helvetica-Oblique",
        fontSize=8, textColor=colors.HexColor("#666666"), alignment=1,
    )
    s_footer_main = ParagraphStyle(
        "Foot", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=10, textColor=colors.white, alignment=1,
    )
    s_footer_sub = ParagraphStyle(
        "FootSub", parent=styles["Normal"], fontName="Helvetica",
        fontSize=8, textColor=colors.HexColor("#EEEEEE"), alignment=1,
    )
    s_price = ParagraphStyle(
        "Price", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=22, leading=26, textColor=primary, alignment=1,
    )
    s_price_label = ParagraphStyle(
        "PriceL", parent=styles["Normal"], fontName="Helvetica",
        fontSize=9, leading=11, textColor=colors.HexColor("#666666"), alignment=1,
    )

    story = []

    # ============ HERO con rating ============
    name = business.get("name", "")
    category = business.get("category", "")
    rating = business.get("rating") or 0
    reviews = business.get("reviews_count") or 0
    address = business.get("address", "")

    stars_text = _stars_glyph(rating)
    rating_label = (
        f"{rating}<font size='9'>/5</font>" if rating else "Sin rating"
    )

    hero_left = Table(
        [
            [Paragraph(f"<b>{name}</b>", s_h1)],
            [Paragraph(f"{category} · {address}", s_subtitle)],
        ],
        colWidths=[12 * cm],
    )
    hero_left.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    hero_right = Table(
        [
            [Paragraph(stars_text, s_stars)],
            [Paragraph(
                f"<b><font color='white' size='13'>{rating_label}</font></b>",
                s_stars_label,
            )],
            [Paragraph(f"{reviews} reseñas en Google", s_stars_label)],
        ],
        colWidths=[6.2 * cm],
    )
    hero_right.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    hero = Table(
        [[hero_left, hero_right]],
        colWidths=[12 * cm, 6.2 * cm],
    )
    hero.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), primary),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LINEBELOW", (0, 0), (-1, -1), 4, accent),
    ]))
    story.append(hero)
    story.append(Spacer(1, 0.4 * cm))

    # ============ INTRO ============
    intro = (
        f"Hola, somos <b>{config.AGENCY_NAME}</b>. Vimos tu negocio en Google y "
        f"queremos ayudarte a llevar la presencia digital de <b>{name}</b> al "
        "siguiente nivel. Aquí está nuestra propuesta."
    )
    story.append(Paragraph(intro, s_body))

    # ============ DIAGNÓSTICO ACTUAL ============
    story.append(Spacer(1, 0.3 * cm))
    diag_title, diag_msg = _diagnostico_actual(business)

    diag_card = Table(
        [
            [Paragraph(f"⚠️  {diag_title}", s_diagnostico_title)],
            [Paragraph(diag_msg, s_body)],
        ],
        colWidths=[18.2 * cm],
    )
    diag_card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF7E6")),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
        ("LINEBEFORE", (0, 0), (0, -1), 4, accent),
    ]))
    story.append(diag_card)
    story.append(Spacer(1, 0.4 * cm))

    # ============ PROPUESTA + QR ============
    story.append(Paragraph("Tu nueva web está lista para verla", s_h2))

    netlify_url = (business.get("netlify_url") or "").strip()
    has_qr = bool(netlify_url)

    if has_qr:
        propuesta_msg = (
            "Ya preparamos una <b>demo de cómo se vería tu sitio</b>. "
            "Diseño profesional, responsivo, optimizado para celular. "
            "<b>Escanea el QR con tu cámara →</b> y la ves al instante."
        )
        qr = _build_qr_drawing(netlify_url, size_cm=3.2)

        propuesta_left = Paragraph(propuesta_msg, s_body)
        propuesta_right = qr

        propuesta_block = Table(
            [[propuesta_left, propuesta_right]],
            colWidths=[14.4 * cm, 3.6 * cm],
        )
        propuesta_block.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E5E5E5")),
            ("BACKGROUND", (1, 0), (1, 0), colors.white),
            ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ]))
        story.append(propuesta_block)
        story.append(Paragraph(
            f"O ábrela directo: <font color='#666666'>{netlify_url}</font>",
            s_caption,
        ))
    else:
        propuesta_msg = (
            "Estamos preparando una <b>demo personalizada</b> de cómo se vería tu sitio: "
            "diseño profesional, responsivo, optimizado para que cargue rápido en celular. "
            "Te la mostramos en cuanto agendemos una llamada o visita."
        )
        story.append(Paragraph(propuesta_msg, s_body))

        # Caja "preview" simulada cuando no hay QR
        preview_box = Table(
            [[Paragraph(
                f"<font color='white'><b>{name.upper()}</b></font><br/>"
                f"<font color='white' size='8'>Vista previa de tu nueva web</font>",
                ParagraphStyle("p", fontName="Helvetica-Bold", fontSize=14,
                              textColor=colors.white, alignment=1, leading=20)
            )]],
            colWidths=[18.2 * cm], rowHeights=[2.6 * cm],
        )
        preview_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), primary),
            ("LINEABOVE", (0, 0), (-1, 0), 4, accent),
            ("LINEBELOW", (0, 0), (-1, -1), 4, accent),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        story.append(Spacer(1, 0.15 * cm))
        story.append(preview_box)

    story.append(Spacer(1, 0.35 * cm))

    # ============ BENEFICIOS ============
    story.append(Paragraph("Lo que vas a tener", s_h2))
    for prop in _value_props(category)[:3]:
        story.append(Paragraph(f"✓ {prop}", s_bullet))

    story.append(Spacer(1, 0.35 * cm))

    # ============ INVERSIÓN + INCLUYE ============
    story.append(Paragraph("Inversión", s_h2))

    precio_text = _format_price(business.get("precio_cotizado"))

    incluye_text = (
        "Diseño 100% personalizado · Versión móvil + escritorio · "
        "Hasta 5 secciones · Botón de WhatsApp directo · "
        "Optimización SEO local · Hospedaje el primer año<br/>"
        "<font size='8' color='#666666'>Entrega en 5–7 días hábiles · Pago 50% al inicio, 50% a la entrega</font>"
    )

    invest_left = Table(
        [
            [Paragraph(precio_text, s_price)],
            [Paragraph("Inversión total · IVA incluido", s_price_label)],
        ],
        colWidths=[5.0 * cm],
    )
    invest_left.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F5F5F7")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))

    invest_right = Paragraph(incluye_text, s_body)

    invest_block = Table(
        [[invest_left, invest_right]],
        colWidths=[5.0 * cm, 13.2 * cm],
    )
    invest_block.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (1, 0), (1, 0), 12),
        ("LEFTPADDING", (1, 0), (1, 0), 14),
    ]))
    story.append(invest_block)

    # Espaciador flexible para empujar el footer abajo
    story.append(Spacer(1, 0.5 * cm))

    # ============ FOOTER ============
    contact_lines = [config.AGENCY_NAME]
    extras = []
    if config.AGENCY_PHONE:
        extras.append(f"📞 {config.AGENCY_PHONE}")
    if config.AGENCY_EMAIL:
        extras.append(f"✉ {config.AGENCY_EMAIL}")
    if config.AGENCY_WEBSITE:
        extras.append(f"🌐 {config.AGENCY_WEBSITE}")
    contact_line2 = "  ·  ".join(extras) if extras else "Hablemos de tu nuevo sitio"

    footer = Table(
        [
            [Paragraph(f"Hablemos. {config.YOUR_NAME} — {contact_lines[0]}", s_footer_main)],
            [Paragraph(contact_line2, s_footer_sub)],
            [Paragraph(
                f"Propuesta generada el {datetime.now().strftime('%d/%m/%Y')}",
                s_footer_sub,
            )],
        ],
        colWidths=[18.2 * cm],
    )
    footer.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), primary),
        ("LINEABOVE", (0, 0), (-1, 0), 3, accent),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(footer)

    doc.build(story)
    logger.info("PDF generado: %s", out_path)
    return str(out_path)


# ============================================================
# Generador de PDFs en lote (zip)
# ============================================================
def generate_pdf_proposals_batch(
    businesses: list[dict],
    progress_cb=None,
) -> tuple[Path, list[dict]]:
    """Genera N PDFs y los empaqueta en un zip plano.

    Args:
        businesses: lista de clientes a procesar.
        progress_cb: callable(done, total, name) — opcional.

    Returns:
        (path_zip, results) con results = [{name, ok, pdf_filename, error}].
    """
    if not businesses:
        raise ValueError("Lista de clientes vacía")

    out_dir = config.OUTPUTS_DIR / "lotes"
    out_dir.mkdir(parents=True, exist_ok=True)
    final_zip = out_dir / f"propuestas_pdf_{date.today().isoformat()}.zip"

    results: list[dict] = []
    total = len(businesses)

    # Generamos los PDFs a archivos individuales en PDF_DIR (queda cacheado
    # ahí para el botón individual también) y los metemos al zip.
    for i, biz in enumerate(businesses, start=1):
        name = biz.get("name", "(sin nombre)")
        slug = _slugify(name)
        try:
            pdf_path = generate_pdf_proposal(biz)
            results.append({
                "name": name,
                "ok": True,
                "pdf_filename": f"{slug}_propuesta.pdf",
                "pdf_path": pdf_path,
                "error": None,
            })
        except Exception as e:
            logger.exception("Falló PDF para %s", name)
            results.append({
                "name": name,
                "ok": False,
                "pdf_filename": f"{slug}_propuesta.pdf",
                "pdf_path": None,
                "error": str(e),
            })

        if progress_cb:
            try:
                progress_cb(i, total, name)
            except Exception:
                pass

    # Empaquetar en zip plano
    with zipfile.ZipFile(final_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        n_ok = sum(1 for r in results if r["ok"])
        n_err = total - n_ok
        manifest = [
            f"# Propuestas PDF generadas el {date.today().isoformat()}",
            f"# Total: {total} · OK: {n_ok} · Errores: {n_err}",
            "",
        ]
        for r in results:
            status = "OK" if r["ok"] else f"ERROR: {r['error']}"
            manifest.append(f"- {r['pdf_filename']:50s} → {r['name']} · {status}")
        zf.writestr("MANIFEST.txt", "\n".join(manifest))

        for r in results:
            if r["ok"] and r["pdf_path"]:
                p = Path(r["pdf_path"])
                if p.exists():
                    zf.write(p, arcname=r["pdf_filename"])

    # Limpieza eventual de zips de propuestas viejas (>7 días)
    try:
        import time
        for old in out_dir.glob("propuestas_pdf_*.zip"):
            if time.time() - old.stat().st_mtime > 7 * 86400:
                old.unlink(missing_ok=True)
    except Exception:
        pass

    return final_zip, results
