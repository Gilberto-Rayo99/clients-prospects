"""Generación de landings: prompt v2 + paquetes para subir a claude.ai.

- `generate_landing` → HTML mock placeholder (sin APIs externas).
- `export_landing_package` → zip con prompt.txt + imágenes Gemini para
  un solo prospecto.
- `export_landing_packages_parallel` → zip-de-zips para un lote.
"""
from __future__ import annotations

import logging
import re
from datetime import date
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
{{SEÑALES_EXTRA}}- **Hash de variación:** {{HASH_VARIACION}} ← úsalo solo para asegurar que dos prospectos similares NO produzcan el mismo HTML (ajusta orden de secciones, copy, microcopy, formas de cards). NO menciones el hash en el HTML.
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

    # ===== Señales extra opcionales (si Google Places las trajo) =====
    extras_lines: list[str] = []
    price_level = business.get("price_level")
    if price_level is not None:
        price_map = {
            0: "$ — económico (refleja accesibilidad, no austeridad)",
            1: "$ — económico",
            2: "$$ — medio (la mayoría de comercios locales)",
            3: "$$$ — medio-alto / premium (justifica diseño editorial)",
            4: "$$$$ — alto / lujo",
        }
        extras_lines.append(f"- **Nivel de precio (Maps):** {price_map.get(int(price_level), price_level)}")

    horario = business.get("opening_hours") or business.get("horario")
    if horario:
        if isinstance(horario, list):
            horario_str = " · ".join(str(h) for h in horario[:3])
        else:
            horario_str = str(horario)
        extras_lines.append(f"- **Horario:** {horario_str}")

    # Frases de reseñas (si las tenemos): ayudan al modelo a captar tono real.
    reviews_quotes = business.get("review_quotes")
    if reviews_quotes:
        if isinstance(reviews_quotes, list):
            sample = " | ".join(str(q)[:120] for q in reviews_quotes[:3])
        else:
            sample = str(reviews_quotes)[:300]
        extras_lines.append(f"- **Frases de reseñas reales:** {sample}")

    senales_extra = ("\n".join(extras_lines) + "\n") if extras_lines else ""

    # ===== Hash corto para forzar variación entre prospectos similares =====
    import hashlib as _hashlib
    seed = f"{name}|{business.get('place_id', '')}|{rating}|{reviews}"
    hash_var = _hashlib.md5(seed.encode("utf-8")).hexdigest()[:8]

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
        "{{SEÑALES_EXTRA}}":           senales_extra,
        "{{HASH_VARIACION}}":          hash_var,
        "{{AGENCIA}}":                 config.AGENCY_NAME,
    }

    out = _PROMPT_TEMPLATE_V2
    for k, v in replacements.items():
        out = out.replace(k, v)
    return out


# ============================================================
# Punto de entrada — landing mock (placeholder gratis, sin API)
# ============================================================
def generate_landing(business: dict) -> tuple[str, str]:
    """Genera un HTML placeholder local y lo guarda en outputs/landings/.

    No llama a APIs externas. Sirve como landing inicial mientras el usuario
    genera la versión final con Gemini + claude.ai (ver `export_landing_package`).

    Returns:
        (html_string, ruta_archivo_guardado)
    """
    logger.info("Generando landing mock para %s", business.get("name"))
    html = _mock_landing_html(business)
    slug = _slugify(business.get("name", "negocio"))
    path = config.LANDINGS_DIR / f"{slug}.html"
    path.write_text(html, encoding="utf-8")
    return html, str(path)


# ============================================================
# Export package para flujo claude.ai (NUEVO — flujo correcto)
# ============================================================
def export_landing_package(business: dict) -> tuple[bytes, dict]:
    """Genera el prompt para claude.ai como `.txt` con el slug del negocio.

    Devuelve los bytes UTF-8 del prompt, listos para descargar como
    `{slug}.txt`. El nombre coincide con el slug del cliente, así cuando
    claude.ai te devuelva el HTML y lo guardes con el mismo nombre
    (`{slug}.html`), la carga masiva del bulk upload empareja al 100%
    por fuzzy match.

    NOTA: la versión anterior empaquetaba imágenes Gemini en un zip.
    Como Gemini Image salió del free tier y la app cae a Unsplash,
    el .zip era puro ruido — un solo .txt es más simple y rápido de
    arrastrar a claude.ai.

    Returns:
        (prompt_bytes_utf8, metadata) — metadata = {
            "slug": str,
            "filename": str,    # ej. "el-lugar-de-victor.txt"
            "size": int,        # bytes
            "had_gemini_key": bool,  # informativo
        }
    """
    # Importar perezosamente para evitar import cycle con landing_prompt
    try:
        from core.landing_prompt import _detect_business_context  # type: ignore
    except Exception:
        _detect_business_context = None  # noqa: N806

    # Detectar giro real específico (heurística por palabras del nombre)
    giro_real_override = None
    if _detect_business_context is not None:
        try:
            ctx = _detect_business_context(business.get("name", ""), business.get("category", "Otros"))
            if ctx and ctx.get("description"):
                giro_real_override = ctx["description"]
        except Exception:
            giro_real_override = None

    prompt_text = _build_prompt_v2(
        business,
        gemini_imgs=None,  # sin imágenes — claude.ai usa los keywords Unsplash del prompt
        giro_real_override=giro_real_override,
    )

    name = business.get("name", "negocio")
    slug = _slugify(name)
    filename = f"{slug}.txt"
    payload = prompt_text.encode("utf-8")

    metadata = {
        "slug": slug,
        "filename": filename,
        "size": len(payload),
        "had_gemini_key": bool(config.GEMINI_API_KEY),
    }
    return payload, metadata


# ============================================================
# Generación paralela de paquetes (lote)
# ============================================================
def export_landing_packages_parallel(
    businesses: list[dict],
    max_workers: int = 10,
    progress_cb=None,
) -> tuple[Path, list[dict]]:
    """Genera N prompts en paralelo y los empaqueta en un zip plano de `.txt`s.

    Estructura del zip resultante:
        MANIFEST.txt
        {slug-empresa-1}.txt
        {slug-empresa-2}.txt
        ...

    Cuando claude.ai te devuelva el HTML, guárdalo con el mismo nombre
    (`{slug-empresa-1}.html`) y al subirlo en la carga masiva el fuzzy
    match acierta al 100% — sin revisión manual.

    Args:
        businesses: lista de dicts de prospectos.
        max_workers: hilos concurrentes. Default 10 (suficiente para
            generar prompts; cada uno solo construye texto, sin I/O externo).
        progress_cb: callable(done: int, total: int, last_name: str).

    Returns:
        (path_zip_final, results) donde results = [{name, ok, slug, error}].
    """
    import concurrent.futures
    import threading
    import zipfile

    if not businesses:
        raise ValueError("Lista de prospectos vacía")

    out_dir = config.OUTPUTS_DIR / "lotes"
    out_dir.mkdir(parents=True, exist_ok=True)
    final_zip_path = out_dir / f"landing_prompts_{date.today().isoformat()}.zip"

    results: list[dict] = []
    results_lock = threading.Lock()
    total = len(businesses)
    done = 0

    def _worker(biz: dict) -> dict:
        name = biz.get("name", "(sin nombre)")
        try:
            payload, meta = export_landing_package(biz)
            return {
                "name": name,
                "ok": True,
                "slug": meta["slug"],
                "filename": meta["filename"],
                "payload": payload,
                "size": meta["size"],
                "error": None,
            }
        except Exception as e:
            logger.exception("Falló prompt para %s", name)
            return {
                "name": name,
                "ok": False,
                "slug": _slugify(name),
                "filename": f"{_slugify(name)}.txt",
                "payload": None,
                "size": 0,
                "error": str(e),
            }

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_worker, b): b for b in businesses}
        for fut in concurrent.futures.as_completed(futures):
            res = fut.result()
            with results_lock:
                results.append(res)
                done += 1
                if progress_cb:
                    try:
                        progress_cb(done, total, res["name"])
                    except Exception:
                        pass

    # Zip plano: un .txt por prospecto en la raíz + MANIFEST
    with zipfile.ZipFile(final_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        n_ok = sum(1 for r in results if r["ok"])
        n_err = sum(1 for r in results if not r["ok"])
        manifest_lines = [
            f"# Lote de prompts generado el {date.today().isoformat()}",
            f"# Total: {total} prospectos · OK: {n_ok} · Errores: {n_err}",
            "",
            "Instrucciones:",
            "1. Para cada .txt, abre un chat nuevo en claude.ai",
            "2. Pega el contenido del .txt como mensaje",
            "3. Guarda el HTML que te devuelva claude.ai con EL MISMO NOMBRE",
            "   pero extensión .html (ej. el-lugar-de-victor.txt → el-lugar-de-victor.html)",
            "4. Sube todos los .html a la app en 'Carga masiva' — el fuzzy match",
            "   los empareja automáticamente con el cliente correcto.",
            "",
            "Archivos incluidos:",
        ]
        for r in results:
            status = "OK" if r["ok"] else f"ERROR: {r['error']}"
            manifest_lines.append(f"- {r['filename']:50s} → {r['name']} · {status}")
        zf.writestr("MANIFEST.txt", "\n".join(manifest_lines))

        for r in results:
            if r["ok"] and r["payload"]:
                zf.writestr(r["filename"], r["payload"])

    # Limpieza eventual de lotes viejos (>7 días)
    try:
        import time
        for pattern in ("landing_packages_*.zip", "landing_prompts_*.zip"):
            for old in out_dir.glob(pattern):
                if time.time() - old.stat().st_mtime > 7 * 86400:
                    old.unlink(missing_ok=True)
    except Exception:
        pass

    # Limpiar payload de los results (ya no lo necesitamos en memoria una vez
    # escrito el zip; los results son solo para la UI)
    for r in results:
        r.pop("payload", None)

    return final_zip_path, results
