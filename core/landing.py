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
# Cada paleta incluye: primary, accent, bg, text_dark, text_soft, border
CATEGORY_PALETTES: dict[str, dict] = {
    "Restaurantes":          {"primary": "#C0392B", "accent": "#F39C12", "bg": "#FFF8F0", "text_dark": "#1A1A1A", "text_soft": "#5A5048", "border": "#EADFD3"},
    "Cafeterías":            {"primary": "#6F4E37", "accent": "#D2A679", "bg": "#FAF6F1", "text_dark": "#1F1A14", "text_soft": "#6B5E50", "border": "#E5DCCD"},
    "Estéticas y barberías": {"primary": "#1C1C1C", "accent": "#C9A227", "bg": "#F8F6F2", "text_dark": "#0E0E0E", "text_soft": "#5A5A5A", "border": "#E0DCD3"},
    "Talleres mecánicos":    {"primary": "#2C3E50", "accent": "#E67E22", "bg": "#F4F6F8", "text_dark": "#13202E", "text_soft": "#56636F", "border": "#D8DEE5"},
    "Tiendas de abarrotes":  {"primary": "#27AE60", "accent": "#F1C40F", "bg": "#F6FBF6", "text_dark": "#173B26", "text_soft": "#5A6E5F", "border": "#D8E8DB"},
    "Consultorios dentales": {"primary": "#1F6FEB", "accent": "#56C2E6", "bg": "#F4F9FE", "text_dark": "#0E1F3A", "text_soft": "#5A6A82", "border": "#D6E2F2"},
    "Gimnasios":             {"primary": "#111111", "accent": "#FF3B30", "bg": "#F4F4F4", "text_dark": "#0A0A0A", "text_soft": "#4F4F4F", "border": "#D7D7D7"},
    "Veterinarias":          {"primary": "#16A085", "accent": "#F39C12", "bg": "#F2FBF8", "text_dark": "#0E2A24", "text_soft": "#5A6E68", "border": "#D2E8E0"},
    "Lavanderías":           {"primary": "#3498DB", "accent": "#2ECC71", "bg": "#F4F9FD", "text_dark": "#0E2638", "text_soft": "#5A6B7A", "border": "#D6E3EE"},
    "Florerías":             {"primary": "#C0397A", "accent": "#9B59B6", "bg": "#FBF4F9", "text_dark": "#2A0E20", "text_soft": "#6E5A66", "border": "#EAD6E0"},
    "Panaderías":            {"primary": "#A0522D", "accent": "#F4A460", "bg": "#FFF8EE", "text_dark": "#2A1810", "text_soft": "#6E5A4F", "border": "#E8D9C2"},
    "Inmobiliarias":         {"primary": "#0E2A47", "accent": "#C19B5C", "bg": "#F7F5F0", "text_dark": "#0E1A2A", "text_soft": "#5A6573", "border": "#DDD6C8"},
    "Otros":                 {"primary": "#1F6FEB", "accent": "#22C55E", "bg": "#F5F7FB", "text_dark": "#111827", "text_soft": "#4B5563", "border": "#D8DEE9"},
}


# ============================================================
# Keywords Unsplash por categoría — sirven al modelo para variar imágenes
# ============================================================
CATEGORY_UNSPLASH_KEYWORDS: dict[str, list[str]] = {
    "Restaurantes":          ["restaurant", "mexican-food", "tacos", "plates", "chef", "kitchen", "dining-table", "fresh-ingredients"],
    "Cafeterías":            ["coffee", "cafe-interior", "latte-art", "espresso", "barista", "coffee-beans", "pastry", "cozy-cafe"],
    "Estéticas y barberías": ["barbershop", "haircut", "barber", "scissors", "beauty-salon", "hairstylist", "men-grooming", "shaving"],
    "Talleres mecánicos":    ["car-repair", "mechanic", "auto-shop", "engine", "wrench", "tire-change", "oil-change", "garage"],
    "Tiendas de abarrotes":  ["grocery-store", "shelves", "convenience-store", "fresh-produce", "neighborhood-shop", "vegetables", "cashier"],
    "Consultorios dentales": ["dentist", "dental-clinic", "teeth", "smile", "dentist-tools", "dental-chair", "modern-clinic", "orthodontist"],
    "Gimnasios":             ["gym", "fitness", "workout", "dumbbells", "training", "crossfit", "athlete", "weight-room"],
    "Veterinarias":          ["veterinarian", "pet-clinic", "dog-checkup", "cat-vet", "puppy", "kitten", "vet-doctor", "pet-care"],
    "Lavanderías":           ["laundry", "washing-machine", "clean-clothes", "folded-linen", "laundromat", "soap", "ironed-shirts"],
    "Florerías":             ["flowers", "bouquet", "florist", "roses", "flower-arrangement", "wedding-flowers", "flower-shop"],
    "Panaderías":            ["bakery", "fresh-bread", "pastries", "croissant", "baker", "bakery-shelf", "oven", "cinnamon-roll"],
    "Inmobiliarias":         ["real-estate", "modern-house", "apartment-interior", "living-room", "luxury-home", "city-skyline", "house-keys"],
    "Otros":                 ["local-business", "storefront", "small-shop", "neighborhood", "service", "team-working"],
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
_PROMPT_TEMPLATE_V2 = """Eres un DIRECTOR DE ARTE Y DESARROLLADOR FRONTEND senior. No eres un generador de plantillas. Tu trabajo es diseñar una landing page que se sienta hecha A LA MEDIDA de UN negocio específico — no una plantilla con el color cambiado.

Antes de escribir HTML, vas a tomar decisiones de diseño explícitas. Después codeas. Si te saltas la fase de decisión, el resultado va a ser genérico y eso es un fallo.

═══════════════════════════════════════════════
DATOS DEL NEGOCIO
═══════════════════════════════════════════════
- **Nombre:** {{NOMBRE}}
- **Categoría:** {{CATEGORIA}}
- **Giro real detectado:** {{GIRO_REAL}}
- **Dirección:** {{DIRECCION}}
- **Teléfono:** {{TELEFONO}}
- **Web actual:** {{WEB_ACTUAL}}
- **Rating Google Maps:** {{RATING}} ({{RESEÑAS}} reseñas)
- **Paleta sugerida (puedes ajustarla si el arquetipo lo pide):**
  - Primario: {{COLOR_PRIMARIO}}
  - Acento: {{COLOR_ACENTO}}
  - Fondo claro: {{COLOR_FONDO}}
  - Texto oscuro: {{COLOR_TEXTO_OSCURO}}
  - Texto secundario: {{COLOR_TEXTO_SECUNDARIO}}
  - Bordes: {{COLOR_BORDES}}
- **Imágenes disponibles:** {{IMAGENES_DISPONIBLES}}

═══════════════════════════════════════════════
FASE 1 — DIRECCIÓN DE ARTE (OBLIGATORIA, ANTES DEL HTML)
═══════════════════════════════════════════════

Antes de escribir cualquier HTML, escribe en un comentario HTML al inicio del archivo (<!-- ... -->) las siguientes decisiones. NO te las saltes. Si las omites, el diseño será genérico.

1. **ARQUETIPO VISUAL** (elige UNO y comprométete con él):
   - `editorial-magazine` → tipografías serif grandes, layouts asimétricos tipo revista, mucho aire, fotos a sangre. Bueno para: spa, restaurantes finos, boutique, joyería, arquitectura.
   - `bold-energetic` → tipografías condensadas/pesadas, alto contraste, diagonales, colores saturados, animaciones agresivas. Bueno para: gym, crossfit, autos, bares deportivos, escuelas de baile.
   - `warm-artisan` → texturas, serif humanista, paleta tierra, fotos cálidas, hand-drawn touches, layouts orgánicos. Bueno para: panadería, café de especialidad, taquería tradicional, carpintería, productos artesanales.
   - `clinical-trust` → mucho whitespace, sans-serif neutra, azules/verdes suaves, iconografía limpia, cards con sombras suaves. Bueno para: clínicas, dentistas, despachos legales, contadores, laboratorios.
   - `playful-vibrant` → colores múltiples, formas geométricas, ilustraciones, tipografías redondas, microanimaciones divertidas. Bueno para: heladerías, juguetes, fiestas infantiles, pastelerías, escuelas para niños.
   - `street-urban` → tipografías display agresivas, fondos oscuros, neones, fotos con grano, layouts brutalistas. Bueno para: barbería moderna, tatuajes, streetwear, gaming, tuning.
   - `nature-calm` → verdes/beige, serif elegante, mucho espacio en blanco, fotos naturales, transiciones lentas. Bueno para: veterinaria holística, yoga, herbolaria, jardinería, retiros.
   - `tech-minimal` → grids matemáticos, mono-fuentes opcionales, paleta restringida, microinteracciones precisas. Bueno para: estudio de diseño, agencia, coworking, software.

   IMPORTANTE: el arquetipo debe surgir del NEGOCIO REAL, no de la categoría. Una veterinaria de barrio NO es igual que una clínica veterinaria 24h premium NI que una estética canina con vibe playful. Lee el nombre, dirección (zona) y reseñas para inferir el carácter del negocio.

2. **LAYOUT DOMINANTE** (elige UNO):
   - Hero clásico centrado (úsalo SOLO si justificas por qué no hay mejor opción — es el default aburrido).
   - Hero split (texto izquierda, foto/imagen derecha de borde a borde).
   - Hero asimétrico estilo magazine (título enorme tapando parcialmente la imagen).
   - Hero full-bleed con overlay (foto pantalla completa, texto encima con gradient).
   - Hero apilado vertical (foto arriba a sangre, contenido abajo, estilo editorial).
   - Hero con grid de varias imágenes (mosaico tipo galería desde el inicio).

3. **TIPOGRAFÍA** (combo headline + body):
   - Usa Google Fonts via @import en el <style> (UNA sola petición, máximo 2 familias). Justifica la elección.
   - Ejemplos de combos según arquetipo:
     - editorial-magazine → `Playfair Display` + `Inter`
     - bold-energetic → `Archivo Black` o `Bebas Neue` + `Inter`
     - warm-artisan → `Fraunces` o `DM Serif Display` + `Nunito`
     - clinical-trust → `Manrope` o `Inter` (solo sans, distintos pesos)
     - playful-vibrant → `Fredoka` o `Quicksand` + `Nunito`
     - street-urban → `Anton` o `Oswald` + `Space Grotesk`
     - nature-calm → `Cormorant Garamond` + `Inter`
     - tech-minimal → `Space Grotesk` + `JetBrains Mono` (acentos)
   - NO uses solo `-apple-system` system fonts. Eso garantiza que todo se vea igual.

4. **PALETA FINAL**:
   - Toma la paleta sugerida como punto de partida, pero AJÚSTALA si el arquetipo lo pide. Ej: si te dieron `#16A085` (verde) pero el arquetipo es `street-urban`, oscurece el fondo a casi negro y usa el verde como acento neón. Justifícalo.
   - Define en :root al menos: --primario, --acento, --fondo, --fondo-alt, --texto, --texto-suave, --borde.
   - Considera agregar una tercera variable de "color destacado" inesperado para romper la monotonía (ej. un coral en una paleta verde).

5. **DIFERENCIADOR VISUAL** (obligatorio, mínimo UNO):
   Algo que esta landing tenga y otras no. Ejemplos:
   - Tickets de menú estilo recibo de papel para una taquería.
   - Polaroid scattered con rotaciones leves para una galería de mascotas.
   - Cronómetros / barras de progreso para un gym.
   - Tarjeta de cita médica con tipografía monospace para una clínica.
   - Sello de "atendemos desde [año]" con textura.
   - Sección "el día en la clínica/taller/gym" con timeline horizontal.
   - Mapa de servicios estilo infografía dibujada.
   - Galería con efecto masonry irregular.
   - Cita destacada gigante tipo editorial entre secciones.

6. **SECCIONES — ESTRUCTURA REQUERIDA + LIBERTAD CREATIVA**:

   Secciones núcleo (deben existir, pero TÚ decides el orden, el formato visual y cómo se llaman):
   - Apertura / Hero
   - Lo que hacemos / ofrecemos (servicios, menú, productos — el formato depende del giro)
   - Prueba social (testimonios, reseñas, rating, casos)
   - Equipo o "quiénes somos" (si aplica al giro)
   - Galería visual del lugar/producto
   - Llamada a la acción principal (formulario, reserva, contacto, WhatsApp)
   - Ubicación + horarios + contacto

   Secciones EXTRAS obligatorias (mínimo UNA, idealmente DOS, propias del giro):
   Tú las inventas según el negocio. Ejemplos por giro:
   - Taquería: "nuestras salsas", "cómo se hace nuestra tortilla", "los favoritos de la casa"
   - Veterinaria: "qué hacer en una emergencia", "calendario de vacunación", "tips de cuidado mensual"
   - Gym: "horario de clases", "transformaciones reales", "tu primera semana", "el equipo de coaches"
   - Barbería: "cortes de la casa", "el ritual completo", "productos que usamos"
   - Cafetería: "nuestro origen del café", "el método de preparación", "panadería del día"
   - Spa: "rituales", "qué esperar en tu primera visita"
   - Dentista: "antes y después", "tecnología que usamos", "tu primera consulta paso a paso"

   El ORDEN de las secciones debe servir a la narrativa del negocio, no ser fijo. Una taquería quizá lleva el menú casi al inicio. Una clínica lleva confianza/equipo antes que servicios. Un gym lleva transformaciones antes que precios.

7. **PROHIBICIONES (rompe el molde genérico)**:
   - ❌ No uses el patrón "hero centrado con h1 + subtítulo + 2 botones lado a lado". Si lo usas, justifica MUY bien por qué.
   - ❌ No uses grids de exactamente 3 columnas con ícono + título + párrafo idénticas. Rompe el ritmo: tamaños distintos, una destacada, layout asimétrico, o un formato totalmente diferente (lista numerada grande, acordeón, tabs, scroll horizontal).
   - ❌ No uses el típico "card con sombra suave, border-radius 12px, padding 2rem" para TODO. Varía: algunas cards sin borde, otras con borde grueso, otras con fondo de color, otras tipo ticket, etc.
   - ❌ No pongas todos los CTAs como botones rectangulares con el color primario. Considera botones outline, links subrayados gruesos, botones con flecha, botones con forma irregular.
   - ❌ No uses emojis como íconos principales si el arquetipo es editorial, clinical, nature-calm o tech-minimal. Usa SVG inline simples (líneas, formas geométricas) o ningún ícono.

═══════════════════════════════════════════════
FASE 2 — REQUISITOS TÉCNICOS (no negociables)
═══════════════════════════════════════════════

- HTML5 standalone, todo inline (CSS en <style>, JS solo si es vanilla y necesario).
- Mobile-first con media queries en 768px y 480px.
- Google Fonts permitido vía @import (única dependencia externa además de imágenes).
- Sin Font Awesome, sin Bootstrap, sin Tailwind CDN, sin librerías JS.
- Accesibilidad: alt descriptivos, labels en inputs, contraste correcto, focus states visibles.
- Microinteracciones: transiciones suaves, hovers con sentido (no solo translateY -2px en todo).
- Formularios visualmente funcionales aunque no tengan backend.
- Responsive real: en móvil el diseño debe REORGANIZARSE, no solo encogerse.

═══════════════════════════════════════════════
FASE 3 — IMÁGENES (regla estricta)
═══════════════════════════════════════════════

{{INSTRUCCIONES_IMG}}

- alt descriptivo y específico en español ("Cliente recibiendo afeitado clásico con navaja", no "barbería").
- Prohibido: picsum, via.placeholder, Flickr, repetir URLs, SVG geométricos como reemplazo de fotos reales.
- Prohibido inventar rutas locales que no estén en la lista de "Imágenes disponibles".

═══════════════════════════════════════════════
FASE 4 — TONO Y CONTENIDO
═══════════════════════════════════════════════

- Español de México, cálido pero profesional.
- NADA de "calidad y servicio", "los mejores", "tu mejor opción". Frases muertas.
- Inventa contenido ESPECÍFICO del giro real:
  - Taquería → nombres de tacos con descripción ("Pastor con piña fresca al trompo, en tortilla recién hecha")
  - Veterinaria → servicios con detalle clínico real ("Vacunación múltiple felina con desparasitante")
  - Barbería → cortes con personalidad ("Fade bajo con diseño lateral")
  - Gym → clases con horario y nivel ("Funcional avanzado, 6:00 AM, lunes y miércoles")
- Testimonios: nombres mexicanos creíbles + comentarios que mencionen un servicio/producto específico del negocio + zona o colonia cuando aplique.
- Footer SIEMPRE incluye: "Sitio de demostración generado por **{{AGENCIA}}**".

═══════════════════════════════════════════════
FORMATO DE SALIDA
═══════════════════════════════════════════════

Tu respuesta debe ser EXCLUSIVAMENTE:

1. Un comentario HTML al inicio del archivo con tus decisiones de Fase 1 (arquetipo, layout, tipografía, paleta final, diferenciador, secciones extras elegidas, justificación breve de cada una). Algo así:

```
<!--
DIRECCIÓN DE ARTE
- Arquetipo: warm-artisan (negocio de barrio, vibe familiar, no clínica corporativa)
- Layout dominante: hero apilado con foto a sangre arriba
- Tipografía: Fraunces (headlines) + Nunito (body)
- Paleta ajustada: bajé saturación del verde a tono salvia, añadí coral #E07856 como acento inesperado
- Diferenciador: tarjeta de "primera consulta gratis" estilo ticket de papel + galería polaroid scattered
- Secciones extras: "qué hacer en una emergencia" (banda roja sticky en mobile) + "calendario de vacunación" (tabla visual)
- Orden: Hero → Equipo (confianza primero) → Servicios → Emergencia → Galería → Vacunación → Testimonios → Cita → Mapa
-->
```

2. Inmediatamente después, el HTML completo desde `<!DOCTYPE html>` hasta `</html>`.

Sin texto previo. Sin texto posterior. Sin bloques de código markdown. Solo el comentario de dirección de arte + el HTML, listo para guardar como .html.
"""


def _build_image_block(
    gemini_imgs: dict[str, str] | None,
    category: str,
) -> tuple[str, str]:
    """Construye los bloques `IMAGENES_DISPONIBLES` e `INSTRUCCIONES_IMG`.

    - Si hay imágenes Gemini → priorizarlas, dar lista exacta de rutas locales.
      Para huecos no cubiertos, autorizar Unsplash con keywords del giro.
    - Si no hay nada → instrucciones puras de Unsplash (modo legacy).
    """
    keywords = CATEGORY_UNSPLASH_KEYWORDS.get(category, CATEGORY_UNSPLASH_KEYWORDS["Otros"])

    if gemini_imgs:
        # Lista de rutas locales generadas para este negocio
        lines = [f"- `{slot}` → `{path}`" for slot, path in gemini_imgs.items()]
        disponibles = (
            "Tienes IMÁGENES REALES generadas a medida para este negocio "
            "(usa estas rutas locales tal cual, son relativas al HTML):\n"
            + "\n".join(lines)
            + f"\n\nKeywords Unsplash de respaldo (úsalos SOLO si necesitas "
            f"más imágenes que las generadas): {', '.join(keywords)}"
        )
        instrucciones = (
            "Tienes imágenes REALES, hechas a medida, listadas arriba. "
            "USA ESAS RUTAS LOCALES TAL CUAL en los `<img src=\"...\">` "
            "(son relativas al HTML que vas a generar). NO les agregues "
            "dominios, NO las reemplaces por Unsplash, NO inventes rutas "
            "que no estén en la lista.\n\n"
            "- El slot `hero` es la imagen principal del Hero (1600x900, panorámica).\n"
            "- Los slots `service-1..N` son para sección de servicios/menú/cards (800x600).\n"
            "- Los slots `gallery-1..N` son para galería visual del lugar (600x400).\n\n"
            "Si necesitas imágenes adicionales que no estén en la lista, "
            "y SOLO en ese caso, usa Unsplash Source con UN keyword distinto:\n"
            "```\nhttps://source.unsplash.com/featured/<ancho>x<alto>/?<keyword>\n```\n"
            "- Sin parámetros extra (`?sig=`, `?lock=`, `&` están prohibidos)."
        )
    else:
        disponibles = (
            f"No hay imágenes pregeneradas. Usa Unsplash Source con estos "
            f"keywords del giro: {', '.join(keywords)}"
        )
        instrucciones = (
            "Usa Unsplash Source con UN keyword distinto por imagen:\n"
            "```\nhttps://source.unsplash.com/featured/<ancho>x<alto>/?<keyword>\n```\n\n"
            "- Tamaños: hero 1600x900, cards 800x600, galería 600x400, miniaturas 400x300.\n"
            "- Sin parámetros extra (`?sig=`, `?lock=`, `&` están prohibidos).\n"
            "- Cada `<img>` debe tener un keyword DIFERENTE de los disponibles + "
            "variantes relacionadas si se acaban."
        )
    return disponibles, instrucciones


def _build_prompt_v2(
    business: dict,
    gemini_imgs: dict[str, str] | None = None,
    giro_real_override: str | None = None,
) -> str:
    """Sustituye los placeholders {{...}} del template con datos del negocio.

    Args:
        business: datos del negocio.
        gemini_imgs: dict {slot: ruta_relativa} si Gemini generó imágenes
            para este negocio. None → instrucciones Unsplash.
        giro_real_override: descripción específica del giro detectada con
            heurística de palabras del nombre (sustituye al fallback genérico).
    """
    category = business.get("category", "Otros")
    palette = _palette_for(category)

    name = business.get("name", "")
    if giro_real_override:
        giro_real = giro_real_override
    else:
        giro_real = f"{category} — interpreta el carácter (barrio, premium, tradicional, moderno) a partir del nombre '{name}' y la zona"

    web_actual = business.get("website") or "no tiene sitio web propio"
    phone = business.get("phone") or "no disponible"
    rating = business.get("rating") if business.get("rating") is not None else "—"
    reviews = business.get("reviews_count") or 0

    disponibles, instrucciones = _build_image_block(gemini_imgs, category)

    replacements = {
        "{{NOMBRE}}":                  name,
        "{{CATEGORIA}}":               category,
        "{{GIRO_REAL}}":               giro_real,
        "{{DIRECCION}}":               business.get("address", ""),
        "{{TELEFONO}}":                phone,
        "{{WEB_ACTUAL}}":              web_actual,
        "{{RATING}}":                  str(rating),
        "{{RESEÑAS}}":                 str(reviews),
        "{{COLOR_PRIMARIO}}":          palette["primary"],
        "{{COLOR_ACENTO}}":            palette["accent"],
        "{{COLOR_FONDO}}":             palette["bg"],
        "{{COLOR_TEXTO_OSCURO}}":      palette["text_dark"],
        "{{COLOR_TEXTO_SECUNDARIO}}":  palette["text_soft"],
        "{{COLOR_BORDES}}":            palette["border"],
        "{{IMAGENES_DISPONIBLES}}":    disponibles,
        "{{INSTRUCCIONES_IMG}}":       instrucciones,
        "{{AGENCIA}}":                 config.AGENCY_NAME,
    }

    out = _PROMPT_TEMPLATE_V2
    for k, v in replacements.items():
        out = out.replace(k, v)
    return out


def _claude_landing_html(business: dict, gemini_imgs: dict[str, str] | None = None) -> str:
    """Genera la landing usando claude-sonnet-4-5 con el prompt v2 (director de arte)."""
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    prompt = _build_prompt_v2(business, gemini_imgs=gemini_imgs)

    msg = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in msg.content if hasattr(b, "text"))

    # Quitar fences markdown si Claude los metió por error
    text = re.sub(r"^```(?:html)?\s*\n", "", text.strip())
    text = re.sub(r"\n```\s*$", "", text)

    # Capturar desde el primer comentario HTML (dirección de arte) si existe,
    # si no, desde <!DOCTYPE html>. Hasta </html>.
    m = re.search(r"(<!--.*?-->\s*)?<!DOCTYPE html>.*?</html>", text, re.DOTALL | re.IGNORECASE)
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
        # 1) Generar imágenes a medida con Gemini (si hay key + cuota)
        gemini_imgs: dict[str, str] | None = None
        try:
            from core import images as _img
            gemini_imgs = _img.generate_business_images(business)
            if gemini_imgs:
                logger.info("Gemini generó %d imágenes para %s",
                            len(gemini_imgs), business.get("name"))
        except Exception as e:
            logger.exception("Falló generación de imágenes Gemini: %s", e)
            gemini_imgs = None

        # 2) Pedir HTML a Claude pasándole las rutas locales
        logger.info("Generando landing con Claude para %s", business.get("name"))
        try:
            html = _claude_landing_html(business, gemini_imgs=gemini_imgs)
        except Exception as e:
            logger.exception("Falló Claude, fallback a mock: %s", e)
            html = _mock_landing_html(business)

    slug = _slugify(business.get("name", "negocio"))
    path = config.LANDINGS_DIR / f"{slug}.html"
    path.write_text(html, encoding="utf-8")
    return html, str(path)


# ============================================================
# Export package para flujo claude.ai (NUEVO — flujo correcto)
# ============================================================
def export_landing_package(business: dict) -> tuple[bytes, dict]:
    """Empaqueta `prompt.txt` + imágenes Gemini en un .zip listo para subir a claude.ai.

    Flujo:
      1. Genera (o reusa cache) las imágenes a medida con Gemini.
      2. Construye el prompt v2 con rutas RELATIVAS al HTML que va a generar
         claude.ai (ej. `img/hero.png`, no la ruta absoluta del filesystem).
      3. Empaqueta todo en un zip en memoria con la estructura:
            prompt.txt
            README.md
            img/hero.png
            img/service-1.png
            ...

    Returns:
        (zip_bytes, metadata) — metadata = {
            "images_generated": int,
            "remaining_today": int | None,
            "had_gemini_key": bool,
        }
    """
    import io
    import zipfile

    # Importar perezosamente para evitar import cycle con landing_prompt
    try:
        from core.landing_prompt import _detect_business_context  # type: ignore
    except Exception:
        _detect_business_context = None  # noqa: N806

    # 1) Detectar giro real específico (heurística por palabras del nombre)
    giro_real_override = None
    if _detect_business_context is not None:
        try:
            ctx = _detect_business_context(business.get("name", ""), business.get("category", "Otros"))
            if ctx and ctx.get("description"):
                giro_real_override = ctx["description"]
        except Exception:
            giro_real_override = None

    # 2) Generar imágenes Gemini (cache por place_id si ya existen en disco)
    from core import images as _img

    gemini_imgs: dict[str, str] | None = None
    had_key = bool(config.GEMINI_API_KEY)
    try:
        gemini_imgs = _img.generate_business_images(business)
    except Exception as e:
        logger.exception("export_landing_package: falló Gemini: %s", e)
        gemini_imgs = None

    # 3) Re-mapear paths para el prompt: dentro del zip las imágenes van a vivir
    #    en `img/<slot>.png`, así que el HTML que genere claude.ai debe usar
    #    exactamente esas rutas (no las del cache `img/<place_id>/...`).
    prompt_imgs: dict[str, str] | None = None
    if gemini_imgs:
        prompt_imgs = {slot: f"img/{slot}.png" for slot in gemini_imgs.keys()}

    prompt_text = _build_prompt_v2(
        business,
        gemini_imgs=prompt_imgs,
        giro_real_override=giro_real_override,
    )

    # 4) Construir el zip en memoria
    name = business.get("name", "negocio")
    slug = _slugify(name)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{slug}/prompt.txt", prompt_text)

        # README explicando cómo usar el paquete
        readme = (
            f"# Paquete de landing — {name}\n\n"
            "## Cómo usarlo en claude.ai\n\n"
            "1. Abre **claude.ai** (con tu plan Pro/Max).\n"
            "2. Inicia un chat nuevo y **adjunta** todos los archivos de este zip "
            "(`prompt.txt` + las imágenes de la carpeta `img/`).\n"
            "3. En el mensaje, pega: \"Sigue las instrucciones del prompt.txt y "
            "genera el HTML completo de la landing usando las imágenes adjuntas. "
            "Devuelve solo el HTML.\"\n"
            "4. Cuando Claude te dé el HTML, **guárdalo como `index.html` "
            "junto a la carpeta `img/`** que viene en este zip — así las rutas "
            "relativas funcionan al abrirlo en el navegador.\n"
            "5. Sube el `index.html` a la pestaña 📥 Cargar HTML del prospecto en "
            "la app, o publícalo directo (Netlify, etc.).\n\n"
            "## Estructura\n\n"
            "```\n"
            f"{slug}/\n"
            "├── prompt.txt          ← instrucciones para claude.ai\n"
            "├── README.md           ← este archivo\n"
            "└── img/                ← imágenes generadas con Gemini Nano Banana\n"
        )
        if gemini_imgs:
            for slot in gemini_imgs.keys():
                readme += f"    ├── {slot}.png\n"
        else:
            readme += (
                "    (vacío — Gemini no estaba disponible. El prompt usará Unsplash.)\n"
            )
        readme += "```\n"
        zf.writestr(f"{slug}/README.md", readme)

        # Imágenes
        if gemini_imgs:
            for slot, rel_cache_path in gemini_imgs.items():
                full = config.LANDINGS_DIR / rel_cache_path
                if full.exists() and full.stat().st_size > 0:
                    zf.write(full, arcname=f"{slug}/img/{slot}.png")

    metadata = {
        "images_generated": len(gemini_imgs) if gemini_imgs else 0,
        "remaining_today": _img.remaining_today() if had_key else None,
        "had_gemini_key": had_key,
        "slug": slug,
    }
    return buf.getvalue(), metadata
