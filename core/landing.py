"""Generación de landing HTML con Claude API (con mock para desarrollo)."""
from __future__ import annotations

import logging
import re
from pathlib import Path

import config

logger = logging.getLogger(__name__)


# ============================================================
# Paleta de colores sugerida por categoría
# ============================================================
CATEGORY_PALETTES: dict[str, dict] = {
    "Restaurantes":          {"primary": "#C0392B", "accent": "#F39C12", "bg": "#FFF8F0"},
    "Cafeterías":            {"primary": "#6F4E37", "accent": "#D2A679", "bg": "#FAF6F1"},
    "Estéticas y barberías": {"primary": "#1C1C1C", "accent": "#C9A227", "bg": "#F8F6F2"},
    "Talleres mecánicos":    {"primary": "#2C3E50", "accent": "#E67E22", "bg": "#F4F6F8"},
    "Tiendas de abarrotes":  {"primary": "#27AE60", "accent": "#F1C40F", "bg": "#F6FBF6"},
    "Consultorios dentales": {"primary": "#1F6FEB", "accent": "#56C2E6", "bg": "#F4F9FE"},
    "Gimnasios":             {"primary": "#111111", "accent": "#FF3B30", "bg": "#F4F4F4"},
    "Veterinarias":          {"primary": "#16A085", "accent": "#F39C12", "bg": "#F2FBF8"},
    "Lavanderías":           {"primary": "#3498DB", "accent": "#2ECC71", "bg": "#F4F9FD"},
    "Florerías":             {"primary": "#C0397A", "accent": "#9B59B6", "bg": "#FBF4F9"},
    "Panaderías":            {"primary": "#A0522D", "accent": "#F4A460", "bg": "#FFF8EE"},
    "Otros":                 {"primary": "#1F6FEB", "accent": "#22C55E", "bg": "#F5F7FB"},
}


def _slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "negocio"


def _palette_for(category: str) -> dict:
    return CATEGORY_PALETTES.get(category, CATEGORY_PALETTES["Otros"])


# ============================================================
# Mock — landing HTML standalone "bonita" sin llamar a Claude
# ============================================================
def _mock_landing_html(business: dict) -> str:
    palette = _palette_for(business.get("category", "Otros"))
    name = business.get("name", "Tu Negocio")
    category = business.get("category", "")
    address = business.get("address", "")
    phone = business.get("phone", "")
    rating = business.get("rating") or "—"
    reviews = business.get("reviews_count") or 0

    # Mensaje de tagline simple según categoría
    taglines = {
        "Restaurantes":          "Sabor auténtico que enamora",
        "Cafeterías":            "Tu rincón favorito de la ciudad",
        "Estéticas y barberías": "Estilo que te define",
        "Talleres mecánicos":    "Tu auto en las mejores manos",
        "Tiendas de abarrotes":  "Lo que necesitas, cerca de ti",
        "Consultorios dentales": "Sonríe con confianza",
        "Gimnasios":             "Construye tu mejor versión",
        "Veterinarias":          "Cuidamos a quien más quieres",
        "Lavanderías":           "Tu ropa, impecable y a tiempo",
        "Florerías":             "Flores que dicen lo que sientes",
        "Panaderías":            "Recién horneado todos los días",
    }
    tagline = taglines.get(category, "Calidad y servicio que confías")

    services = {
        "Restaurantes":          ["Menú del día", "Servicio a domicilio", "Eventos privados"],
        "Cafeterías":            ["Café de especialidad", "Postres caseros", "Wi-Fi gratis"],
        "Estéticas y barberías": ["Cortes modernos", "Tratamientos capilares", "Diseño de barba"],
        "Talleres mecánicos":    ["Diagnóstico computarizado", "Cambio de aceite", "Mecánica general"],
        "Tiendas de abarrotes":  ["Productos frescos", "Servicio a domicilio", "Pago con tarjeta"],
        "Consultorios dentales": ["Limpieza profesional", "Ortodoncia", "Blanqueamiento"],
        "Gimnasios":             ["Clases grupales", "Entrenamiento personal", "Equipos de última gen"],
        "Veterinarias":          ["Consultas", "Vacunación", "Cirugía especializada"],
        "Lavanderías":           ["Lavado al kilo", "Planchado", "Servicio express"],
        "Florerías":             ["Arreglos a domicilio", "Bodas y eventos", "Diseño personalizado"],
        "Panaderías":            ["Pan recién horneado", "Pasteles por encargo", "Cafetería"],
    }
    svc = services.get(category, ["Calidad", "Servicio personalizado", "Experiencia comprobada"])

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name}</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: {palette['bg']};
  color: #222;
  line-height: 1.6;
}}
.hero {{
  background: linear-gradient(135deg, {palette['primary']} 0%, {palette['accent']} 100%);
  color: white;
  padding: 100px 20px 80px;
  text-align: center;
}}
.hero h1 {{ font-size: 3rem; margin-bottom: 12px; font-weight: 800; letter-spacing: -0.5px; }}
.hero p.tagline {{ font-size: 1.4rem; opacity: 0.95; margin-bottom: 32px; }}
.cta {{
  display: inline-block;
  background: white;
  color: {palette['primary']};
  padding: 14px 32px;
  border-radius: 50px;
  text-decoration: none;
  font-weight: 700;
  font-size: 1.05rem;
  transition: transform 0.2s;
}}
.cta:hover {{ transform: translateY(-2px); }}
.container {{ max-width: 1100px; margin: 0 auto; padding: 60px 20px; }}
.about {{ text-align: center; margin-bottom: 60px; }}
.about h2 {{ color: {palette['primary']}; font-size: 2rem; margin-bottom: 16px; }}
.about p {{ font-size: 1.1rem; max-width: 700px; margin: 0 auto; color: #555; }}
.services {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 24px;
  margin-top: 40px;
}}
.service {{
  background: white;
  padding: 32px 24px;
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.06);
  text-align: center;
  transition: transform 0.2s, box-shadow 0.2s;
}}
.service:hover {{ transform: translateY(-4px); box-shadow: 0 8px 24px rgba(0,0,0,0.1); }}
.service-icon {{
  width: 60px; height: 60px;
  background: {palette['accent']};
  border-radius: 50%;
  margin: 0 auto 16px;
  display: flex; align-items: center; justify-content: center;
  color: white; font-size: 1.6rem; font-weight: bold;
}}
.service h3 {{ color: {palette['primary']}; margin-bottom: 8px; }}
.rating-block {{
  background: white;
  padding: 32px;
  border-radius: 12px;
  text-align: center;
  margin: 40px 0;
}}
.stars {{ font-size: 2rem; color: {palette['accent']}; margin-bottom: 8px; }}
.rating-num {{ font-size: 3rem; color: {palette['primary']}; font-weight: 800; }}
.contact {{
  background: {palette['primary']};
  color: white;
  padding: 60px 20px;
  text-align: center;
}}
.contact h2 {{ font-size: 2rem; margin-bottom: 24px; }}
.contact-info {{ display: flex; flex-wrap: wrap; justify-content: center; gap: 32px; margin-top: 24px; }}
.contact-info div {{ min-width: 200px; }}
.contact-info strong {{ display: block; opacity: 0.8; font-size: 0.85rem; text-transform: uppercase; margin-bottom: 4px; }}
.contact-info span {{ font-size: 1.1rem; }}
footer {{
  background: #111;
  color: #888;
  padding: 24px;
  text-align: center;
  font-size: 0.85rem;
}}
@media (max-width: 600px) {{
  .hero h1 {{ font-size: 2rem; }}
  .hero p.tagline {{ font-size: 1.1rem; }}
}}
</style>
</head>
<body>

<section class="hero">
  <h1>{name}</h1>
  <p class="tagline">{tagline}</p>
  <a href="#contacto" class="cta">Contáctanos</a>
</section>

<section class="container">
  <div class="about">
    <h2>Sobre nosotros</h2>
    <p>En <strong>{name}</strong> nos dedicamos a ofrecer la mejor experiencia en {category.lower()}. Ubicados en {address}, nos hemos convertido en una opción de confianza para nuestra comunidad.</p>
  </div>

  <div class="services">
    <div class="service">
      <div class="service-icon">★</div>
      <h3>{svc[0]}</h3>
      <p>Calidad garantizada en cada servicio.</p>
    </div>
    <div class="service">
      <div class="service-icon">✓</div>
      <h3>{svc[1]}</h3>
      <p>Atención profesional y personalizada.</p>
    </div>
    <div class="service">
      <div class="service-icon">♥</div>
      <h3>{svc[2]}</h3>
      <p>Comprometidos con tu satisfacción.</p>
    </div>
  </div>

  <div class="rating-block">
    <div class="stars">★ ★ ★ ★ ★</div>
    <div class="rating-num">{rating}</div>
    <p>{reviews} reseñas en Google Maps</p>
  </div>
</section>

<section class="contact" id="contacto">
  <h2>Visítanos</h2>
  <div class="contact-info">
    <div>
      <strong>Dirección</strong>
      <span>{address}</span>
    </div>
    <div>
      <strong>Teléfono</strong>
      <span>{phone or '—'}</span>
    </div>
  </div>
</section>

<footer>
  Sitio de demostración generado por <strong>{config.AGENCY_NAME}</strong> · Todos los derechos reservados
</footer>

</body>
</html>
"""
    return html


# ============================================================
# Llamada real a Claude
# ============================================================
def _claude_landing_html(business: dict) -> str:
    """Genera la landing usando claude-sonnet-4-5."""
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    palette = _palette_for(business.get("category", "Otros"))

    prompt = f"""Eres un diseñador web senior. Genera una landing page completa en HTML standalone (todo inline: CSS dentro de <style>, sin dependencias externas) para el siguiente negocio mexicano:

- Nombre: {business.get('name')}
- Categoría: {business.get('category')}
- Dirección: {business.get('address')}
- Teléfono: {business.get('phone') or 'no disponible'}
- Rating Google Maps: {business.get('rating')} ({business.get('reviews_count')} reseñas)

Requisitos de diseño:
- Paleta principal: {palette['primary']}, acento: {palette['accent']}, fondo: {palette['bg']}
- Hero llamativo con nombre + tagline + CTA
- Sección "Sobre nosotros" breve
- 3 servicios o características de la categoría
- Bloque de rating
- Sección de contacto con dirección y teléfono
- Footer con: "Sitio de demostración generado por {config.AGENCY_NAME}"
- Responsive (media queries)
- Tipografía sans-serif del sistema
- Tono profesional pero cálido, en español de México

Devuelve SOLO el HTML completo desde <!DOCTYPE html> hasta </html>. Sin explicaciones."""

    msg = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in msg.content if hasattr(b, "text"))

    # Extraer solo el HTML si Claude metió backticks
    m = re.search(r"<!DOCTYPE html>.*?</html>", text, re.DOTALL | re.IGNORECASE)
    return m.group(0) if m else text


# ============================================================
# Punto de entrada
# ============================================================
def generate_landing(business: dict) -> tuple[str, str]:
    """Genera el HTML y lo guarda en outputs/landings/.

    Decide la fuente según `ANTHROPIC_API_KEY` (no según USE_MOCK_DATA, para
    permitir el flujo real de Google Places + landing mock al mismo tiempo).

    Returns:
        (html_string, ruta_archivo_guardado)
    """
    if not config.ANTHROPIC_API_KEY:
        logger.info("Sin ANTHROPIC_API_KEY → mock para %s", business.get("name"))
        html = _mock_landing_html(business)
    else:
        logger.info("Generando landing con Claude para %s", business.get("name"))
        try:
            html = _claude_landing_html(business)
        except Exception as e:
            logger.exception("Falló Claude, fallback a mock: %s", e)
            html = _mock_landing_html(business)

    slug = _slugify(business.get("name", "negocio"))
    path = config.LANDINGS_DIR / f"{slug}.html"
    path.write_text(html, encoding="utf-8")
    return html, str(path)
