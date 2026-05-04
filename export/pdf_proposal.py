"""Genera PDF de propuesta imprimible (1 página A4) para visita presencial."""
from __future__ import annotations

import logging
import re
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

import config

logger = logging.getLogger(__name__)


# Paletas en colores reportlab
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
    "Otros":                 {"primary": colors.HexColor("#1F6FEB"), "accent": colors.HexColor("#22C55E")},
}


VALUE_PROPS_BY_CATEGORY: dict[str, list[str]] = {
    "Restaurantes":          [
        "Más reservas y pedidos: tus clientes encuentran tu menú actualizado en Google al instante.",
        "Confianza profesional: una web propia te diferencia de la competencia que solo tiene Facebook.",
        "Vendes 24/7: aunque cierres tu local, tu web sigue trayendo clientes nuevos.",
    ],
    "Cafeterías":            [
        "Atrae más clientes locales con tu menú, fotos y horarios siempre disponibles.",
        "Posicionamiento en Google Maps: aparece arriba cuando alguien busca cafetería cerca.",
        "Reservas y eventos privados gestionados desde tu propia página.",
    ],
    "Estéticas y barberías": [
        "Agenda en línea 24/7: tus clientes reservan sin llamarte, tú no pierdes ventas.",
        "Galería de cortes y servicios que muestra tu estilo y atrae al cliente correcto.",
        "Más reseñas y referidos: una web profesional inspira confianza inmediata.",
    ],
    "Talleres mecánicos":    [
        "Genera confianza antes de que el cliente llegue: tu trayectoria, especialidades y testimonios.",
        "Cotizaciones y citas en línea para reducir llamadas y agilizar el flujo.",
        "Apareces en Google cuando buscan 'taller mecánico cerca de mí'.",
    ],
    "Tiendas de abarrotes":  [
        "Pedidos a domicilio gestionados desde la web — sin depender de WhatsApp solamente.",
        "Catálogo de productos y promociones siempre actualizado.",
        "Posicionamiento local para que vecinos te encuentren rápido en Google.",
    ],
    "Consultorios dentales": [
        "Agenda de citas en línea: pacientes nuevos sin sobrecargar la recepción.",
        "Imagen profesional que transmite limpieza, modernidad y confianza.",
        "Posicionamiento SEO local — apareces arriba cuando buscan 'dentista cerca'.",
    ],
    "Gimnasios":             [
        "Inscripciones y pago de membresías en línea, sin filas en recepción.",
        "Galería de instalaciones y horarios de clases visibles 24/7.",
        "Conversión de visitas en clases de prueba con un solo CTA bien colocado.",
    ],
    "Veterinarias":          [
        "Citas en línea para vacunas, consultas y servicios — menos llamadas, más eficiencia.",
        "Confianza para nuevos clientes: tu equipo, especialidades y testimonios visibles.",
        "Sección de emergencias y horarios siempre actualizada.",
    ],
    "Lavanderías":           [
        "Pedidos de recolección y entrega gestionados desde la web.",
        "Lista de precios actualizable sin reimprimir lonas.",
        "Posicionamiento local para captar clientes nuevos del barrio.",
    ],
    "Florerías":             [
        "Catálogo y pedidos en línea para fechas especiales (Día de las Madres, San Valentín…).",
        "Galería profesional que vende solita.",
        "Posicionamiento Google Maps + SEO local.",
    ],
    "Panaderías":            [
        "Encargos para eventos y pasteles personalizados desde la web.",
        "Catálogo de productos del día, siempre fresco.",
        "Apareces en Google con menú y horarios cuando alguien busca 'panadería cerca'.",
    ],
}


def _slugify(name: str) -> str:
    s = name.lower().strip()
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


def generate_pdf_proposal(business: dict, landing_html_path: str | None = None) -> str:
    """Genera un PDF A4 de 1 página para llevar impreso al cliente."""
    palette = _color_for(business.get("category", "Otros"))
    primary = palette["primary"]
    accent = palette["accent"]

    slug = _slugify(business.get("name", "negocio"))
    out_path = config.PDF_DIR / f"{slug}_propuesta.pdf"

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        rightMargin=1.6 * cm, leftMargin=1.6 * cm,
        topMargin=1.4 * cm, bottomMargin=1.2 * cm,
        title=f"Propuesta — {business.get('name', '')}",
        author=config.AGENCY_NAME,
    )

    styles = getSampleStyleSheet()
    s_h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold",
                         fontSize=20, leading=24, textColor=colors.white, alignment=0, spaceAfter=0)
    s_subtitle = ParagraphStyle("Sub", parent=styles["Normal"], fontName="Helvetica",
                               fontSize=11, leading=14, textColor=colors.white, spaceAfter=0)
    s_h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold",
                         fontSize=13, leading=16, textColor=primary, spaceBefore=10, spaceAfter=6)
    s_body = ParagraphStyle("Body", parent=styles["Normal"], fontName="Helvetica",
                           fontSize=10, leading=14, textColor=colors.HexColor("#222222"))
    s_bullet = ParagraphStyle("Bullet", parent=s_body, leftIndent=14, bulletIndent=2,
                             spaceAfter=4)
    s_caption = ParagraphStyle("Cap", parent=styles["Normal"], fontName="Helvetica-Oblique",
                              fontSize=8, textColor=colors.HexColor("#666666"), alignment=1)
    s_footer = ParagraphStyle("Foot", parent=styles["Normal"], fontName="Helvetica-Bold",
                             fontSize=10, textColor=colors.white, alignment=1)
    s_footer_sub = ParagraphStyle("FootSub", parent=styles["Normal"], fontName="Helvetica",
                                 fontSize=8, textColor=colors.white, alignment=1)

    story = []

    # ============ HEADER ============
    name = business.get("name", "")
    category = business.get("category", "")
    header = Table(
        [[Paragraph(f"<b>{name}</b>", s_h1)],
         [Paragraph(f"{category} · {business.get('address', '')}", s_subtitle)]],
        colWidths=[18 * cm],
    )
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), primary),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(header)
    story.append(Spacer(1, 0.5 * cm))

    # ============ INTRO ============
    rating = business.get("rating") or "—"
    reviews = business.get("reviews_count") or 0
    intro = (
        f"Hola, somos <b>{config.AGENCY_NAME}</b>. Vimos que <b>{name}</b> tiene "
        f"<b>{rating}★</b> con <b>{reviews}</b> reseñas en Google Maps — sin duda haces un excelente trabajo. "
        f"Por eso pensamos que mereces tener una página web a la altura de tu negocio."
    )
    story.append(Paragraph(intro, s_body))

    # ============ ¿Por qué necesitas una web? ============
    story.append(Paragraph("¿Por qué necesitas una página web?", s_h2))
    for prop in _value_props(category)[:3]:
        story.append(Paragraph(f"• {prop}", s_bullet))

    # ============ Demo de tu landing ============
    story.append(Paragraph("Tu sitio, listo para mostrar", s_h2))
    demo_msg = (
        "Ya preparamos una <b>demo de cómo se vería tu página web</b>. "
        "Diseño profesional, responsivo, listo para celular y computadora. "
    )
    if landing_html_path:
        demo_msg += f"Archivo de demostración: <font color='#666666'>{landing_html_path}</font>"
    story.append(Paragraph(demo_msg, s_body))

    # Caja "preview" simulada
    preview_box = Table(
        [[Paragraph(
            f"<font color='white'><b>{name.upper()}</b></font><br/>"
            f"<font color='white' size='8'>Vista previa de tu nueva web</font>",
            ParagraphStyle("p", fontName="Helvetica-Bold", fontSize=14,
                          textColor=colors.white, alignment=1, leading=20)
        )]],
        colWidths=[18 * cm], rowHeights=[3.5 * cm],
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
    story.append(Paragraph("Vista previa — diseño totalmente personalizado para tu negocio", s_caption))

    # ============ Datos del negocio (sirve como confirmación) ============
    story.append(Paragraph("Tus datos en Google", s_h2))
    biz_data = [
        ["Teléfono:", business.get("phone") or "—",
         "Rating:", f"{rating}★ ({reviews} reseñas)"],
        ["Dirección:", business.get("address") or "—",
         "Web actual:", business.get("website") or "Sin web"],
    ]
    biz_table = Table(biz_data, colWidths=[2.6 * cm, 6.4 * cm, 2.6 * cm, 6.4 * cm])
    biz_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), primary),
        ("TEXTCOLOR", (2, 0), (2, -1), primary),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(biz_table)

    # Espaciador flexible para empujar el footer abajo
    story.append(Spacer(1, 0.6 * cm))

    # ============ FOOTER (datos de la agencia) ============
    contact_lines = [config.AGENCY_NAME]
    extras = []
    if config.AGENCY_PHONE:
        extras.append(f"Tel: {config.AGENCY_PHONE}")
    if config.AGENCY_EMAIL:
        extras.append(config.AGENCY_EMAIL)
    if config.AGENCY_WEBSITE:
        extras.append(config.AGENCY_WEBSITE)
    contact_line2 = " · ".join(extras) if extras else "Hablemos de tu nuevo sitio"

    footer = Table(
        [[Paragraph(contact_lines[0], s_footer)],
         [Paragraph(contact_line2, s_footer_sub)],
         [Paragraph(
             f"Propuesta generada el {datetime.now().strftime('%d/%m/%Y')}",
             s_footer_sub,
         )]],
        colWidths=[18 * cm],
    )
    footer.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), primary),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(footer)

    doc.build(story)
    logger.info("PDF generado: %s", out_path)
    return str(out_path)
